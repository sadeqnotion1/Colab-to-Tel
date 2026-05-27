# /content/Telegram-Leecher/colab_leecher/utility/task_context.py

"""
Multi-Task Parallel Download System - Task Context and Queue Manager

This module provides isolated task contexts for running multiple download/upload
tasks in parallel. Each TaskContext maintains its own state, paths, messages,
and statistics to prevent interference between concurrent tasks.
"""

import uuid
import logging
import time
import asyncio
import copy
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
from typing import Dict, Optional, List, Set, Deque, Any
from pyrogram.types import Message
from .ui_copy import build_health_summary_text
from .transfer_state import SmartBytes

log = logging.getLogger(__name__)


@dataclass
class SystemMetrics:
    """Real-time system health metrics for observability"""
    active_tasks: int = 0
    completed_tasks_total: int = 0
    failed_tasks_total: int = 0
    cancelled_tasks_total: int = 0
    total_bytes_downloaded: int = 0
    total_bytes_uploaded: int = 0
    aria2_restarts: int = 0
    telegram_api_errors: int = 0
    start_time: float = field(default_factory=time.time)

    recent_completion_times: Deque[float] = field(
        default_factory=lambda: deque(maxlen=50))

    def record_completion(self, duration_seconds: float):
        self.completed_tasks_total += 1
        self.recent_completion_times.append(duration_seconds)

    def record_failure(self):
        self.failed_tasks_total += 1

    def record_cancellation(self):
        self.cancelled_tasks_total += 1

    def get_success_rate(self) -> float:
        total = self.completed_tasks_total + self.failed_tasks_total + self.cancelled_tasks_total
        if total == 0:
            return 100.0
        return (self.completed_tasks_total / total) * 100

    def get_avg_completion_time(self) -> float:
        if not self.recent_completion_times:
            return 0.0
        return sum(self.recent_completion_times) / len(self.recent_completion_times)


@dataclass
class TaskTransfer:
    """Per-task transfer statistics"""
    down_bytes: Any = field(default_factory=lambda: SmartBytes(0))
    up_bytes: Any = field(default_factory=lambda: SmartBytes(0))
    total_size: int = 0
    total_down_size: int = 0
    sent_file: List = field(default_factory=list)
    sent_file_names: List[str] = field(default_factory=list)
    successful_downloads: List[dict] = field(default_factory=list)
    start_time: float = field(default_factory=lambda: time.time())
    last_speed: float = 0.0
    last_speed_bytes: float = 0.0

    def reset(self):
        self.down_bytes = SmartBytes(0)
        self.up_bytes = SmartBytes(0)
        self.total_size = 0
        self.total_down_size = 0
        self.sent_file = []
        self.sent_file_names = []
        self.successful_downloads = []
        self.start_time = time.time()
        self.last_speed = 0.0

    def get_current_bytes(self) -> int:
        down = sum(self.down_bytes) if isinstance(self.down_bytes, (list, tuple, set)) else self.down_bytes
        up = sum(self.up_bytes) if isinstance(self.up_bytes, (list, tuple, set)) else self.up_bytes
        return max(down or 0, up or 0)


    def get_percentage(self, total_size: int = 0) -> float:
        size_to_use = total_size if total_size > 0 else self.total_size
        if size_to_use == 0:
            return 0.0
        current_bytes = self.get_current_bytes()
        return min(100.0, (current_bytes / size_to_use) * 100)

    def get_eta(self) -> float:
        current_bytes = self.get_current_bytes()
        if self.total_size == 0 or current_bytes == 0:
            return 0.0
        elapsed = time.time() - self.start_time
        if elapsed < 0.01:
            return 0.0
        speed = current_bytes / elapsed
        remaining_bytes = self.total_size - current_bytes
        if speed > 0:
            return remaining_bytes / speed
        return 0.0

    def get_speed(self) -> float:
        elapsed = time.time() - self.start_time
        if elapsed < 0.01:
            return 0.0
        current_bytes = self.get_current_bytes()
        return current_bytes / elapsed


@dataclass
class TaskError:
    """Per-task error tracking"""
    state: bool = False
    message: str = ""
    text: str = ""
    failed_links: List[dict] = field(default_factory=list)

    def set_error(self, message: str):
        self.state = True
        self.message = message
        self.text = message

    def clear(self):
        self.state = False
        self.message = ""
        self.text = ""
        self.failed_links = []


@dataclass
class TaskMessages:
    """Per-task message templates"""
    download_name: str = ""
    current_action: str = "downloading"  # Model state identifier
    task_msg: str = ""
    status_head: str = ""
    dump_task: str = ""
    src_link: str = ""
    current_file: str = ""
    files_processed: int = 0
    total_files: int = 0
    archive_size: int = 0


@dataclass
class TaskBotTimes:
    """Per-task timing information"""
    current_time: float = field(default_factory=time.time)
    start_time: datetime = field(default_factory=datetime.now)
    task_start: datetime = field(default_factory=datetime.now)

    def reset(self):
        self.current_time = time.time()
        self.start_time = datetime.now()
        self.task_start = datetime.now()


# --- ISOLATED CONTAINERS FOR TASK COMPATIBILITY --- #


class IsolationError(RuntimeError):
    """
    Raised when the isolation layer encounters a type it cannot safely clone.

    This is an explicit, loud failure — far preferable to silently sharing a
    mutable reference across concurrent tasks.
    """


# Types that are considered *intrinsically immutable* and safe to share by
# reference across task boundaries.  Extend this tuple if you add new value
# types (e.g. enum members, frozenset already handled below).
_PRIMITIVE_TYPES = (
    type(None), bool, int, float, complex, str, bytes, bytearray,
)

# Pyrogram (and any other Telegram-client) objects embed asyncio primitives
# (Locks, Events, Queues) that are neither picklable nor deepcopy-safe.
# We detect them by module prefix so we never silently share or fail on them.
_UNCOPYABLE_MODULE_PREFIXES = ("pyrogram", "telethon", "hydrogram")


def _is_pyrogram_type(val: object) -> bool:
    """Return True if *val* originates from a known un-cloneable Telegram library."""
    mod = getattr(type(val), "__module__", "") or ""
    return any(mod.startswith(p) for p in _UNCOPYABLE_MODULE_PREFIXES)


def _collect_class_namespace(obj: object) -> dict:
    """
    Return a flat dict of all non-dunder, non-callable attributes visible on
    *obj*, merging instance ``__dict__`` (if any) over the class ``__dict__``.

    Using ``vars()`` + class ``__dict__`` instead of ``dir()`` avoids:
    - Inherited dunder noise (``__class__``, ``__doc__``, …)
    - MRO-walked attributes from unexpected base classes
    - Descriptor side-effects triggered by ``getattr`` on irrelevant names
    """
    merged: dict = {}

    # 1. Class-level attributes (covers class-variable namespaces like BOT.Setting)
    for klass in type(obj).__mro__:
        for k, v in vars(klass).items():
            if not k.startswith("__") and not callable(v) and k not in merged:
                merged[k] = v

    # 2. Instance-level attributes win over class-level
    try:
        for k, v in vars(obj).items():
            if not k.startswith("__") and not callable(v):
                merged[k] = v
    except TypeError:
        # Some objects (e.g. pure class namespaces) have no instance __dict__
        pass

    return merged


def _deep_isolate_value(val: object, attr_name: str = "<unknown>") -> object:
    """
    Produce a fully isolated (no shared mutable state) copy of *val*.

    Dispatch table (in priority order):
      1. Primitives / frozenset  → returned as-is (immutable, safe to share)
      2. Pyrogram / Telegram objects → IsolationError (un-cloneable)
      3. asyncio primitives      → IsolationError (not cross-task safe)
      4. list / tuple            → recursively isolated element-by-element
      5. dict                    → recursively isolated key-value pairs
      6. set / frozenset         → deepcopy (contains only hashable values)
      7. deque                   → recursively isolated element-by-element
      8. dataclass instances     → deepcopy (pure-Python value containers)
      9. Everything else         → deepcopy, with IsolationError on failure
    """
    # --- 1. Primitives ---
    if isinstance(val, _PRIMITIVE_TYPES):
        return val
    if isinstance(val, frozenset):
        return val  # frozenset is immutable

    # --- 2. Pyrogram / Telegram objects ---
    if _is_pyrogram_type(val):
        raise IsolationError(
            f"Attribute '{attr_name}': value of type '{type(val).__qualname__}' "
            f"is a Pyrogram/Telegram object and cannot be deep-copied. "
            f"Store only message IDs (int) in isolated task state, not live "
            f"Message objects."
        )

    # --- 3. asyncio primitives ---
    if isinstance(val, (asyncio.Lock, asyncio.Event, asyncio.Condition,
                        asyncio.Semaphore, asyncio.BoundedSemaphore,
                        asyncio.Queue, asyncio.Task)):
        raise IsolationError(
            f"Attribute '{attr_name}': value of type '{type(val).__qualname__}' "
            f"is an asyncio primitive and cannot be shared across task contexts. "
            f"Create a fresh instance per task instead."
        )

    # --- 4. list / tuple ---
    if isinstance(val, (list, tuple)):
        isolated = [_deep_isolate_value(item, f"{attr_name}[{i}]")
                    for i, item in enumerate(val)]
        return isolated if isinstance(val, list) else tuple(isolated)

    # --- 5. dict ---
    if isinstance(val, dict):
        return {
            _deep_isolate_value(k, f"{attr_name}.key"): _deep_isolate_value(v, f"{attr_name}[{k!r}]")
            for k, v in val.items()
        }

    # --- 6. set ---
    if isinstance(val, set):
        try:
            return copy.deepcopy(val)
        except Exception as exc:
            raise IsolationError(
                f"Attribute '{attr_name}': set contains un-cloneable element — {exc}"
            ) from exc

    # --- 7. deque ---
    if isinstance(val, deque):
        isolated_items = [_deep_isolate_value(item, f"{attr_name}[{i}]")
                          for i, item in enumerate(val)]
        return deque(isolated_items, maxlen=val.maxlen)

    # --- 8. dataclass instances ---
    import dataclasses as _dc
    if _dc.is_dataclass(val) and not isinstance(val, type):
        try:
            return copy.deepcopy(val)
        except Exception as exc:
            raise IsolationError(
                f"Attribute '{attr_name}': dataclass '{type(val).__qualname__}' "
                f"cannot be deep-copied — {exc}"
            ) from exc

    # --- 9. General fallback — deepcopy with explicit failure reporting ---
    try:
        return copy.deepcopy(val)
    except Exception as exc:
        raise IsolationError(
            f"Attribute '{attr_name}': value of type '{type(val).__qualname__}' "
            f"cannot be deep-copied (it likely holds un-serialisable state). "
            f"Original error: {exc}"
        ) from exc


def _safe_copy_attrs(source_obj: object, target_obj: object) -> None:
    """
    Walk every non-dunder, non-callable attribute on *source_obj* and write a
    fully isolated copy onto *target_obj*.

    Raises ``IsolationError`` immediately if any attribute value cannot be
    safely cloned — this makes leaks impossible to ignore.
    """
    namespace = _collect_class_namespace(source_obj)
    errors: list[str] = []

    for attr, val in namespace.items():
        try:
            setattr(target_obj, attr, _deep_isolate_value(val, attr_name=attr))
        except IsolationError as exc:
            errors.append(str(exc))

    if errors:
        error_block = "\n  • ".join(errors)
        raise IsolationError(
            f"Context isolation failed for '{type(source_obj).__qualname__}'. "
            f"Fix the following attributes before proceeding:\n  • {error_block}"
        )


class IsolatedPaths:
    """Fully isolated paths configuration per task."""

    def __init__(self, task_ctx: "TaskContext", global_paths: object) -> None:
        _safe_copy_attrs(global_paths, self)

        # Override with task-specific sandbox paths (always strings — safe)
        self.work_path = task_ctx.work_path
        self.WORK_PATH = task_ctx.work_path          # legacy alias
        self.down_path = task_ctx.down_path
        self.temp_zpath = f"{self.work_path}/temp_zip"
        self.temp_unzip_path = f"{self.work_path}/temp_unzip"
        self.temp_unzip = self.temp_unzip_path        # legacy alias
        self.temp_dirleech_path = f"{self.work_path}/dir_leech_temp"
        self.temp_files_dir = f"{self.work_path}/leech_temp"


class IsolatedBotOptions:
    """Isolated copy of ``BOT.Options`` for a single task."""

    def __init__(self, global_options: object, task_ctx: "TaskContext") -> None:
        _safe_copy_attrs(global_options, self)
        # Task-level override wins over the global default
        if task_ctx.service_type is not None:
            self.service_type = task_ctx.service_type


class IsolatedBot:
    """
    Fully isolated bot configuration per task.

    Each of the five well-known category namespaces (SOURCE, TASK, Setting,
    Mode, State) is deep-cloned into a fresh anonymous object.  Pyrogram /
    asyncio values inside State (e.g. ``password_retry_context`` when it holds
    a live Message) will raise ``IsolationError`` at construction time —
    callers must reset such attributes to ``None`` before spawning a task.
    """

    def __init__(self, global_bot: object, task_ctx: "TaskContext") -> None:
        for category in ("SOURCE", "TASK", "Setting", "Mode", "State"):
            if not hasattr(global_bot, category):
                continue
            cat_obj = getattr(global_bot, category)
            isolated_cat = type(category, (), {})()
            try:
                _safe_copy_attrs(cat_obj, isolated_cat)
            except IsolationError as exc:
                raise IsolationError(
                    f"IsolatedBot: failed to isolate BOT.{category} — {exc}"
                ) from exc
            setattr(self, category, isolated_cat)

        if hasattr(global_bot, "Options"):
            self.Options = IsolatedBotOptions(global_bot.Options, task_ctx)


class IsolatedMsg:
    """
    Fully isolated message configuration per task.

    Pyrogram ``Message`` objects (``MSG.sent_msg``, ``MSG.status_msg``) are
    **not** copied — they embed asyncio locks and cannot be deepcopy'd.
    Instead, only the integer message IDs are stored so the task can reference
    them if needed.  The live ``Message`` objects remain owned by the event
    handler that created them.
    """

    def __init__(self, global_msg: object) -> None:
        namespace = _collect_class_namespace(global_msg)
        for attr, val in namespace.items():
            if _is_pyrogram_type(val):
                # Store only the integer id — never the live object
                msg_id = getattr(val, "id", None)
                setattr(self, attr, msg_id)
                log.debug(
                    "IsolatedMsg: attribute '%s' is a Pyrogram object — "
                    "storing message id=%s instead of the live reference.",
                    attr, msg_id,
                )
            else:
                try:
                    setattr(self, attr, _deep_isolate_value(val, attr_name=attr))
                except IsolationError as exc:
                    raise IsolationError(
                        f"IsolatedMsg: failed to isolate MSG.{attr} — {exc}"
                    ) from exc


@dataclass
class TaskContext:
    """
    Isolated context for a single download/upload task.
    Enforces strict architectural boundaries to prevent tasks from polluting global state.
    """
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int = 0
    chat_id: int = 0
    mode: str = "leech"
    mode_type: str = "normal"
    service_type: Optional[str] = None
    source_urls: List[str] = field(default_factory=list)
    filenames: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    work_path: str = ""
    down_path: str = ""
    hero_image: str = ""

    status_msg: Optional[Message] = None
    sent_msg: Optional[Message] = None

    transfer: TaskTransfer = field(default_factory=TaskTransfer)
    error: TaskError = field(default_factory=TaskError)
    messages: TaskMessages = field(default_factory=TaskMessages)
    bot_times: TaskBotTimes = field(default_factory=TaskBotTimes)
    async_task: Optional[asyncio.Task] = None

    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_status_update: float = 0.0

    is_cancelled: bool = False
    is_completed: bool = False
    report_dispatched: bool = False
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)

    # Strictly isolated containers - initialized during task factory creation
    _bot_isolated: Any = field(default=None, init=False, repr=False, compare=False)
    _paths_isolated: Any = field(default=None, init=False, repr=False, compare=False)
    _msg_isolated: Any = field(default=None, init=False, repr=False, compare=False)

    def get_short_id(self) -> str:
        return self.task_id[:8]

    def get_elapsed_time(self) -> float:
        if not self.started_at:
            return 0.0
        end_time = self.completed_at if self.completed_at else datetime.now()
        return (end_time - self.started_at).total_seconds()

    def mark_started(self):
        self.started_at = datetime.now()

    def mark_completed(self):
        self.completed_at = datetime.now()
        self.is_completed = True

    def mark_cancelled(self):
        self.completed_at = datetime.now()
        self.is_cancelled = True
        self.cancel_event.set()

    @property
    def task_error(self):
        return self.error

    # --- STRICT ISOLATION ENFORCEMENT PROPERTIES --- #
    # These properties trap invalid accesses and prevent silent global fallbacks.
    
    @property
    def bot(self):
        if self._bot_isolated is None:
            raise RuntimeError("Strict Isolation Violation: Task bot configuration accessed before initialization. Global import blocked.")
        return self._bot_isolated

    @bot.setter
    def bot(self, value):
        self._bot_isolated = value

    @property
    def msg(self):
        if self._msg_isolated is None:
            raise RuntimeError("Strict Isolation Violation: Task message configuration accessed before initialization. Global import blocked.")
        return self._msg_isolated

    @msg.setter
    def msg(self, value):
        self._msg_isolated = value

    @property
    def paths(self):
        if self._paths_isolated is None:
            raise RuntimeError("Strict Isolation Violation: Task paths accessed before initialization. Global import blocked.")
        return self._paths_isolated

    @paths.setter
    def paths(self, value):
        self._paths_isolated = value


class TaskQueue:
    """
    Global task queue manager for parallel multi-task execution.
    """
    MAX_TASKS_PER_USER = 5
    MAX_TOTAL_TASKS = 20

    def __init__(self):
        self.active_tasks: Dict[str, TaskContext] = {}
        self.running_tasks: Set[str] = set()
        self.summary_msg: Optional[Message] = None
        self.last_summary_text: str = ""
        self.last_summary_keyboard_signature = ""
        # --- Dashboard pagination state (backend-owned, never scraped from message markup) ---
        self._dashboard_page: int = 0
        self.last_summary_update: float = 0
        self.summary_update_interval: float = 5.0
        self.min_forced_update_interval: float = 1.0
        self._lock = asyncio.Lock()
        self._summary_lock = asyncio.Lock()
        self._worker_cond = asyncio.Condition()

        self.metrics = SystemMetrics()
        self.background_tasks: Set[asyncio.Task] = set()
        self.is_shutting_down: bool = False
        self.user_locks: Dict[int, asyncio.Lock] = {}

        # --- Debounce state for force_update_summary (owned here, not in task_dashboard) ---
        # Holds the single in-flight delayed-update asyncio.Task (if any).
        self._scheduled_update_task: Optional[asyncio.Task] = None
        # Monotonic timestamp of the last *completed* forced update.
        self._last_force_time: float = 0.0
        # Monotonic timestamp until which UI edits are suspended after a FloodWait.
        # A value of 0.0 means no active suspension.
        self._ui_suspended_until: float = 0.0

    def get_user_lock(self, user_id: int) -> asyncio.Lock:
        """
        Get or create a thread-safe / task-safe asyncio.Lock for a specific user.
        This prevents rapid-fire duplicate commands from the same user.
        """
        if user_id not in self.user_locks:
            self.user_locks[user_id] = asyncio.Lock()
        return self.user_locks[user_id]


    # ------------------------------------------------------------------
    # Dashboard pagination — thread-safe accessors
    # ------------------------------------------------------------------

    def get_dashboard_page(self) -> int:
        """
        Return the current dashboard page index.

        This is a *synchronous* read and is safe to call from inside a
        coroutine that already holds ``_summary_lock`` (e.g. inside
        ``update_summary_dashboard``).  The integer is written atomically
        by CPython's GIL, so a bare read is always consistent.
        """
        return self._dashboard_page

    async def set_dashboard_page(self, page: int) -> None:
        """
        Persist the chosen dashboard page.

        Acquires ``_summary_lock`` so the write is serialised against any
        in-progress render that reads the same field — preventing a page
        transition from landing mid-render and producing a torn frame.
        """
        async with self._summary_lock:
            self._dashboard_page = page
            log.debug("Dashboard page set to %d", page)

    def get_worker_limit(self) -> int:
        if not self.active_tasks:
            return 2
        all_tiktok = all(
            getattr(t, 'service_type', None) == "tiktokbulk" 
            for t in self.active_tasks.values()
        )
        return 3 if all_tiktok else 2

    async def acquire_worker_slot(self, task_id: str):
        async with self._worker_cond:
            while True:
                limit = self.get_worker_limit()
                if len(self.running_tasks) < limit:
                    self.running_tasks.add(task_id)
                    log.info(f"Task {task_id[:8]} acquired worker slot. ({len(self.running_tasks)}/{limit})")
                    return
                await self._worker_cond.wait()

    async def release_worker_slot(self, task_id: str):
        async with self._worker_cond:
            if task_id in self.running_tasks:
                self.running_tasks.remove(task_id)
                log.info(f"Task {task_id[:8]} released worker slot. ({len(self.running_tasks)} running)")
                self._worker_cond.notify_all()

    def create_background_task(self, coro, name: str) -> asyncio.Task:
        task = asyncio.create_task(coro, name=name)
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)
        return task

    async def cancel_scheduled_update(self) -> None:
        """
        Cancel the in-flight debounced dashboard-update task (if any) and wait
        for it to finish so we never hold a dangling reference.

        Design notes
        ------------
        * ``asyncio.Task.cancel()`` only *requests* cancellation — the task is
          not guaranteed to be done until the next ``await``.  We shield the
          wait from a *second* cancellation so this helper is safe to call from
          within a coroutine that may itself be cancelled.
        * After this returns, ``self._scheduled_update_task`` is set to ``None``
          so callers can rely on a clean slate.
        """
        task = self._scheduled_update_task
        if task is None or task.done():
            self._scheduled_update_task = None
            return
        task.cancel()
        try:
            await asyncio.shield(asyncio.gather(task, return_exceptions=True))
        except asyncio.CancelledError:
            log.warning("cancel_scheduled_update: CancelledError raised, re-raising to ensure token bubbles up.")
            raise
        finally:
            self._scheduled_update_task = None

    async def add_task(self, task_ctx: TaskContext):
        async with self._lock:
            if self.is_shutting_down:
                log.warning(f"Rejecting task {task_ctx.get_short_id()} - system shutting down")
                return
            self.active_tasks[task_ctx.task_id] = task_ctx
            self.metrics.active_tasks = len(self.active_tasks)
            log.info(f"Task {task_ctx.get_short_id()} added to queue. Total active: {len(self.active_tasks)}")

    async def remove_task(self, task_id: str) -> Optional[TaskContext]:
        """Remove a completed/cancelled task (thread-safe)"""
        async with self._lock:
            task_ctx = self.active_tasks.pop(task_id, None)
            if task_ctx:
                self.metrics.active_tasks = len(self.active_tasks)

                duration = task_ctx.get_elapsed_time()
                if task_ctx.is_cancelled:
                    self.metrics.record_cancellation()
                elif task_ctx.error.state:
                    self.metrics.record_failure()
                else:
                    self.metrics.record_completion(duration)

                # Track data volume (safely handle lists if TikTok bulk downloader set them)
                down_b = sum(task_ctx.transfer.down_bytes) if isinstance(task_ctx.transfer.down_bytes, list) else task_ctx.transfer.down_bytes
                up_b = sum(task_ctx.transfer.up_bytes) if isinstance(task_ctx.transfer.up_bytes, list) else task_ctx.transfer.up_bytes
                self.metrics.total_bytes_downloaded += down_b
                self.metrics.total_bytes_uploaded += up_b

                log.info(
                    f"Task {task_ctx.get_short_id()} removed from queue. Remaining: {len(self.active_tasks)}"
                )
            return task_ctx

    def get_health_summary(self) -> str:
        uptime = time.time() - self.metrics.start_time

        def format_time(seconds):
            if seconds < 60:
                return f"{seconds:.0f}s"
            if seconds < 3600:
                return f"{seconds / 60:.1f}m"
            return f"{seconds / 3600:.1f}h"

        return build_health_summary_text(
            is_shutting_down=self.is_shutting_down,
            uptime_text=format_time(uptime),
            active_tasks=len(self.active_tasks),
            max_total_tasks=self.MAX_TOTAL_TASKS,
            background_tasks=len(self.background_tasks),
            success_rate_text=f"{self.metrics.get_success_rate():.1f}%",
            avg_task_time_text=format_time(self.metrics.get_avg_completion_time()),
            total_down_text=f"{self.metrics.total_bytes_downloaded / 1e9:.2f} GB",
            total_up_text=f"{self.metrics.total_bytes_uploaded / 1e9:.2f} GB",
        )

    async def shutdown(self):
        log.info("Starting system-wide graceful shutdown...")
        self.is_shutting_down = True
        async with self._lock:
            tasks_to_cancel = list(self.active_tasks.values())

        for ctx in tasks_to_cancel:
            if ctx.async_task and not ctx.async_task.done():
                log.info(f"Cancelling task {ctx.get_short_id()} during shutdown")
                ctx.async_task.cancel()

        log.info(f"Cancelling {len(self.background_tasks)} background tasks")
        for task in list(self.background_tasks):
            if not task.done():
                task.cancel()

        try:
            await asyncio.wait_for(asyncio.gather(*self.background_tasks, return_exceptions=True), timeout=10.0)
        except asyncio.TimeoutError:
            log.warning("Shutdown timeout - some tasks may have been force-killed")
        log.info("Graceful shutdown complete")

    async def get_task(self, task_id: str) -> Optional[TaskContext]:
        async with self._lock:
            return self.active_tasks.get(task_id)

    async def has_task(self, task_id: str) -> bool:
        async with self._lock:
            return task_id in self.active_tasks

    async def get_user_tasks(self, user_id: int) -> List[TaskContext]:
        async with self._lock:
            return [task_ctx for task_ctx in self.active_tasks.values() if task_ctx.user_id == user_id]

    async def get_all_tasks(self) -> Dict[str, TaskContext]:
        async with self._lock:
            return self.active_tasks.copy()

    def get_task_count(self) -> int:
        return len(self.active_tasks)

    def has_active_tasks(self) -> bool:
        return len(self.active_tasks) > 0

    async def can_start_task(self, user_id: int = None) -> tuple[bool, str]:
        async with self._lock:
            total_tasks = len(self.active_tasks)
            if total_tasks >= self.MAX_TOTAL_TASKS:
                return (False, f"System limit reached ({total_tasks}/{self.MAX_TOTAL_TASKS} tasks active). Please wait for some to complete.")

            if user_id:
                user_task_count = len([task for task in self.active_tasks.values() if task.user_id == user_id])
                if user_task_count >= self.MAX_TASKS_PER_USER:
                    return (False, f"You have {user_task_count}/{self.MAX_TASKS_PER_USER} tasks active. Please wait for some to complete.")
            return True, "OK"

    def should_update_summary(self) -> bool:
        return time.time() - self.last_summary_update >= self.summary_update_interval

    def mark_summary_updated(self):
        self.last_summary_update = time.time()

    async def clear_completed_tasks(self, max_age_hours: int = 1):
        async with self._lock:
            now = datetime.now()
            to_remove = []
            for task_id, task_ctx in self.active_tasks.items():
                if task_ctx.is_completed or task_ctx.is_cancelled:
                    if task_ctx.completed_at:
                        age_hours = (now - task_ctx.completed_at).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            to_remove.append(task_id)
            for task_id in to_remove:
                removed_task = self.active_tasks.pop(task_id, None)
                if removed_task:
                    log.info(f"Auto-removed old completed task: {task_id[:8]}")


TASK_QUEUE = TaskQueue()

def get_current_task_ctx() -> Optional[TaskContext]:
    return None

def create_task_context(
        user_id: int,
        chat_id: int,
        mode: str = "leech") -> TaskContext:
    """
    Factory that creates a fully isolated ``TaskContext`` for a single task.

    Isolation guarantee
    -------------------
    All mutable global state (``Paths``, ``BOT``, ``MSG``) is deep-cloned into
    per-task containers before the ``TaskContext`` is returned.  The cloning is
    performed by the strict ``_deep_isolate_value`` dispatcher, which raises
    ``IsolationError`` on any type it cannot safely copy — so a half-baked
    context is **never** silently returned to the caller.

    Pre-flight contract on global state
    ------------------------------------
    The caller is responsible for ensuring that ``BOT.State`` does **not**
    contain live Pyrogram ``Message`` objects (e.g. ``password_retry_context``
    should be ``None``) before calling this factory.  If it does, an
    ``IsolationError`` is raised immediately with a clear attribution.
    """
    task_ctx = TaskContext(
        user_id=user_id,
        chat_id=chat_id,
        mode=mode,
    )
    task_ctx.cancel_event = asyncio.Event()

    # Import globals exactly once, at task-creation time.
    from .variables import Paths, BOT, MSG

    # Establish per-task sandbox paths (pure strings, no isolation risk).
    task_ctx.work_path = f"{Paths.WORK_PATH}/{task_ctx.task_id}"
    task_ctx.down_path = f"{task_ctx.work_path}/Downloads"
    task_ctx.hero_image = f"{task_ctx.work_path}/hero_{task_ctx.get_short_id()}.jpg"

    # ------------------------------------------------------------------ #
    # STRICT ISOLATION PHASE
    # Each container constructor will raise IsolationError loudly if it
    # encounters a type it cannot clone.  We let that propagate without
    # swallowing it so the caller's error handler sees the exact attribute
    # that caused the failure.
    # ------------------------------------------------------------------ #
    try:
        task_ctx.paths = IsolatedPaths(task_ctx, Paths)
        task_ctx.bot   = IsolatedBot(BOT, task_ctx)
        task_ctx.msg   = IsolatedMsg(MSG)
    except IsolationError:
        log.critical(
            "TaskContext %s ABORTED — isolation phase failed. "
            "Ensure BOT.State holds no live Pyrogram objects before calling "
            "create_task_context(). See traceback for the offending attribute.",
            task_ctx.get_short_id(),
        )
        raise  # Re-raise unmodified so the full chain is visible upstream

    log.info(
        "Created Strictly Isolated TaskContext %s for user %s",
        task_ctx.get_short_id(), user_id,
    )
    return task_ctx


def cleanup_task_artifacts(task_ctx: "TaskContext"):
    """
    Safely and robustly deletes the isolated workspace directory for a task.
    Handles Windows file-in-use and read-only file locks gracefully without crashing
    or raising exceptions.
    """
    import os
    import shutil
    import stat
    import logging

    log = logging.getLogger(__name__)

    # 1. Retrieve the isolated work path
    try:
        work_path = task_ctx.paths.work_path
    except Exception as e:
        log.error(f"Failed to retrieve work_path from task context: {e}")
        return

    if not work_path:
        log.debug("Workspace path is empty. Skipping cleanup.")
        return

    if not os.path.exists(work_path):
        log.debug(f"Workspace path does not exist: {work_path}. No cleanup needed.")
        return

    log.info(f"Initiating robust cleanup of task workspace: {work_path}")

    # Helper function to clear read-only flag and retry deletion
    def remove_readonly(func, path, excinfo):
        try:
            # Change permissions to writable
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception as e:
            # Ignore and log warning; do not propagate so rmtree can try to proceed
            log.warning(f"Could not change permissions or delete {path} in onerror handler: {e}")

    try:
        # Standard deletion with our custom onerror handler to handle read-only files
        shutil.rmtree(work_path, onerror=remove_readonly)
        log.info(f"Successfully cleaned up task workspace: {work_path}")
    except Exception as rmtree_err:
        log.warning(f"shutil.rmtree failed for {work_path}: {rmtree_err}. Attempting aggressive fallback cleanup.")
        
        # Aggressive fallback: walk bottom-up, force chmod, delete what we can
        try:
            for root, dirs, files in os.walk(work_path, topdown=False):
                for name in files:
                    file_path = os.path.join(root, name)
                    try:
                        os.chmod(file_path, stat.S_IWRITE)
                        os.remove(file_path)
                    except Exception as f_err:
                        log.debug(f"Failed to remove file {file_path} during fallback cleanup: {f_err}")

                for name in dirs:
                    dir_path = os.path.join(root, name)
                    try:
                        os.chmod(dir_path, stat.S_IWRITE)
                        os.rmdir(dir_path)
                    except Exception as d_err:
                        log.debug(f"Failed to remove directory {dir_path} during fallback cleanup: {d_err}")

            # Try to delete the root directory again
            try:
                os.chmod(work_path, stat.S_IWRITE)
                os.rmdir(work_path)
                log.info(f"Successfully cleaned up workspace on fallback: {work_path}")
            except Exception as final_err:
                log.warning(f"Could not remove root workspace directory {work_path} on final attempt: {final_err}")
        except Exception as walk_err:
            log.error(f"Critical error during fallback walk of {work_path}: {walk_err}")


__all__ = [
    'TaskContext',
    'TaskQueue',
    'TaskTransfer',
    'TaskError',
    'TaskMessages',
    'IsolationError',
    'TASK_QUEUE',
    'create_task_context',
    'get_current_task_ctx',
    'cleanup_task_artifacts',
]
