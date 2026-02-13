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
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime
from typing import Dict, Optional, List, Set, Deque
from pyrogram.types import Message

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

    # Rolling windows for averages (thread-safe deque)
    # Using maxlen ensures we don't leak memory over time
    recent_completion_times: Deque[float] = field(default_factory=lambda: deque(maxlen=50))

    def record_completion(self, duration_seconds: float):
        """Record a successful task completion"""
        self.completed_tasks_total += 1
        self.recent_completion_times.append(duration_seconds)

    def record_failure(self):
        """Record a task failure"""
        self.failed_tasks_total += 1

    def record_cancellation(self):
        """Record a task cancellation"""
        self.cancelled_tasks_total += 1

    def get_success_rate(self) -> float:
        """Calculate success rate percentage"""
        total = self.completed_tasks_total + self.failed_tasks_total
        if total == 0:
            return 100.0
        return (self.completed_tasks_total / total) * 100

    def get_avg_completion_time(self) -> float:
        """Get average completion time in seconds"""
        if not self.recent_completion_times:
            return 0.0
        return sum(self.recent_completion_times) / len(self.recent_completion_times)


# Replicate Transfer class structure for per-task statistics
@dataclass
class TaskTransfer:
    """Per-task transfer statistics"""
    down_bytes: int = 0
    up_bytes: int = 0
    total_size: int = 0  # Total file size (for progress percentage and ETA)
    sent_file: List = field(default_factory=list)  # List of successfully sent message objects (from Pyrogram)
    sent_file_names: List[str] = field(default_factory=list)
    successful_downloads: List[dict] = field(default_factory=list)  # List of {'url': url, 'filename': filename}
    start_time: float = field(default_factory=lambda: time.time())
    last_speed: str = "0 B/s"  # Last recorded download/upload speed (for dashboard display)

    def reset(self):
        """Reset transfer statistics"""
        self.down_bytes = 0
        self.up_bytes = 0
        self.total_size = 0
        self.sent_file = []
        self.sent_file_names = []
        self.successful_downloads = []
        self.start_time = time.time()
        self.last_speed = "0 B/s"

    def get_percentage(self, total_size: int = 0) -> float:
        """Calculate download percentage"""
        size_to_use = total_size if total_size > 0 else self.total_size
        if size_to_use == 0:
            return 0.0
        return min(100.0, (self.down_bytes / size_to_use) * 100)

    def get_eta(self) -> float:
        """Calculate ETA in seconds based on current speed"""
        if self.total_size == 0 or self.down_bytes == 0:
            return 0.0

        elapsed = time.time() - self.start_time
        if elapsed < 0.01:
            return 0.0

        speed = self.down_bytes / elapsed  # bytes per second
        remaining_bytes = self.total_size - self.down_bytes

        if speed > 0:
            return remaining_bytes / speed
        return 0.0

    def get_speed(self) -> str:
        """Calculate current download/upload speed"""
        elapsed = time.time() - self.start_time
        # Use threshold instead of == 0 for float comparison
        if elapsed < 0.01:  # Less than 10ms
            return "0 B/s"

        total_bytes = max(self.down_bytes, self.up_bytes)
        speed = total_bytes / elapsed

        # Format speed
        if speed < 1024:
            return f"{speed:.0f} B/s"
        elif speed < 1024 * 1024:
            return f"{speed/1024:.1f} KB/s"
        elif speed < 1024 * 1024 * 1024:
            return f"{speed/(1024*1024):.1f} MB/s"
        else:
            return f"{speed/(1024*1024*1024):.1f} GB/s"


@dataclass
class TaskError:
    """Per-task error tracking"""
    state: bool = False  # True if error occurred
    message: str = ""    # Error message
    text: str = ""       # Alias for message (used by task_manager)
    failed_links: List[dict] = field(default_factory=list)  # List of {'url': url, 'error': error}

    def set_error(self, message: str):
        """Set error state"""
        self.state = True
        self.message = message
        self.text = message

    def clear(self):
        """Clear error state"""
        self.state = False
        self.message = ""
        self.text = ""
        self.failed_links = []


@dataclass
class TaskMessages:
    """Per-task message templates"""
    download_name: str = ""
    task_msg: str = ""
    status_head: str = ""
    dump_task: str = ""
    src_link: str = ""

    # Archiving/processing progress
    current_file: str = ""  # Current file being processed (archiving/extracting)
    files_processed: int = 0  # Number of files processed
    total_files: int = 0  # Total files to process
    archive_size: int = 0  # Current archive size in bytes


@dataclass
class TaskBotTimes:
    """Per-task timing information"""
    current_time: float = field(default_factory=time.time)
    start_time: datetime = field(default_factory=datetime.now)
    task_start: datetime = field(default_factory=datetime.now)

    def reset(self):
        """Reset timing information"""
        self.current_time = time.time()
        self.start_time = datetime.now()
        self.task_start = datetime.now()


@dataclass
class TaskContext:
    """
    Isolated context for a single download/upload task.

    Each task gets its own:
    - Unique ID and file paths
    - Status messages
    - Transfer statistics
    - Error tracking
    - Source URLs and configuration

    This ensures tasks don't interfere with each other when running in parallel.
    """

    # Unique identifier
    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # User information
    user_id: int = 0
    chat_id: int = 0

    # Task configuration
    mode: str = "leech"  # leech, mirror, dir-leech, etc.
    mode_type: str = "normal"  # normal, zip, unzip, undzip
    service_type: Optional[str] = None  # ytdl, gdrive, telegram, mega, etc.

    # Source data
    source_urls: List[str] = field(default_factory=list)
    filenames: List[str] = field(default_factory=list)

    # Per-task file paths (unique to avoid collisions)
    work_path: str = ""  # e.g., /content/Telegram-Leecher/BOT_WORK/{task_id}
    down_path: str = ""  # e.g., {work_path}/Downloads
    hero_image: str = ""  # Per-task thumbnail path

    # Per-task Pyrogram messages
    status_msg: Optional[Message] = None  # Main progress message
    sent_msg: Optional[Message] = None    # Dump chat source links message

    # Per-task statistics and state
    transfer: TaskTransfer = field(default_factory=TaskTransfer)
    error: TaskError = field(default_factory=TaskError)
    messages: TaskMessages = field(default_factory=TaskMessages)
    bot_times: TaskBotTimes = field(default_factory=TaskBotTimes)

    # Asyncio task reference
    async_task: Optional[asyncio.Task] = None

    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_status_update: float = 0.0  # Timestamp of last status bar update (for throttling)

    # State flags
    is_cancelled: bool = False
    is_completed: bool = False

    def get_short_id(self) -> str:
        """Get shortened task ID for display (first 8 chars)"""
        return self.task_id[:8]

    def get_elapsed_time(self) -> float:
        """Get elapsed time in seconds since task started"""
        if not self.started_at:
            return 0.0
        end_time = self.completed_at if self.completed_at else datetime.now()
        return (end_time - self.started_at).total_seconds()

    def mark_started(self):
        """Mark task as started"""
        self.started_at = datetime.now()

    def mark_completed(self):
        """Mark task as completed"""
        self.completed_at = datetime.now()
        self.is_completed = True

    def mark_cancelled(self):
        """Mark task as cancelled"""
        self.completed_at = datetime.now()
        self.is_cancelled = True

    @property
    def task_error(self):
        """Backward compatibility alias for error attribute"""
        return self.error

    @property
    def bot(self):
        """Backward compatibility: Return global BOT for archive/Leech functions"""
        if getattr(self, '_bot_override', None) is not None:
            return self._bot_override
        from .variables import BOT
        return BOT

    @bot.setter
    def bot(self, value):
        self._bot_override = value

    @property
    def msg(self):
        """Backward compatibility: Return global MSG for archive/Leech functions"""
        if getattr(self, '_msg_override', None) is not None:
            return self._msg_override
        from .variables import MSG
        return MSG

    @msg.setter
    def msg(self, value):
        self._msg_override = value

    @property
    def paths(self):
        """
        Backward compatibility: Return Paths-like object for archive/Leech functions

        Creates a dynamic object with path attributes needed by legacy code
        """
        if getattr(self, '_paths_override', None) is not None:
            return self._paths_override
        from .variables import Paths

        class _TaskPaths:
            """Dynamic paths object that uses task-specific paths when available"""
            def __init__(self, task_ctx):
                self._task_ctx = task_ctx
                self._global_paths = Paths

                # Task-specific paths
                self.down_path = task_ctx.down_path if task_ctx.down_path else Paths.down_path
                self.work_path = task_ctx.work_path if task_ctx.work_path else Paths.work_path

                # Generate task-specific temp paths
                if task_ctx.work_path:
                    self.temp_zpath = f"{task_ctx.work_path}/temp_zip"
                    self.temp_unzip_path = f"{task_ctx.work_path}/temp_unzip"
                else:
                    self.temp_zpath = Paths.temp_zpath
                    self.temp_unzip_path = Paths.temp_unzip_path

                # Use global paths for these (shared across tasks)
                self.thumbnail_ytdl = Paths.thumbnail_ytdl
                self.config_file = Paths.config_file

        return _TaskPaths(self)

    @paths.setter
    def paths(self, value):
        self._paths_override = value


class TaskQueue:
    """
    Global task queue manager for parallel multi-task execution.

    Manages all active tasks, provides task registration/removal,
    and maintains the summary dashboard message.
    """

    # Task limit constants
    MAX_TASKS_PER_USER = 5
    MAX_TOTAL_TASKS = 20

    def __init__(self):
        self.active_tasks: Dict[str, TaskContext] = {}  # task_id → TaskContext
        self.summary_msg: Optional[Message] = None  # Summary dashboard message
        self.last_summary_text: str = ""  # Last rendered summary text (for no-op updates)
        self.last_summary_keyboard_signature: str = ""  # Last keyboard signature (for no-op updates)
        self.last_summary_update: float = 0  # Last time summary was updated
        self.summary_update_interval: float = 5.0  # Update summary every 5 seconds
        self.min_forced_update_interval: float = 1.0  # Minimum 1 second between forced updates (debounce)
        self._lock = asyncio.Lock()  # Thread-safe operations for task dict
        self._summary_lock = asyncio.Lock()  # Thread-safe operations for summary updates
        
        # master-level additions
        self.metrics = SystemMetrics()
        self.background_tasks: Set[asyncio.Task] = set()
        self.is_shutting_down: bool = False

    def create_background_task(self, coro, name: str) -> asyncio.Task:
        """Create and track a background task to prevent leaks"""
        task = asyncio.create_task(coro, name=name)
        self.background_tasks.add(task)
        # Remove from set when done
        task.add_done_callback(self.background_tasks.discard)
        return task

    async def add_task(self, task_ctx: TaskContext):
        """Register a new task (thread-safe)"""
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
                
                # Record metrics based on task outcome
                duration = task_ctx.get_elapsed_time()
                if task_ctx.is_cancelled:
                    self.metrics.record_cancellation()
                elif task_ctx.error.state:
                    self.metrics.record_failure()
                else:
                    self.metrics.record_completion(duration)
                    
                # Track data volume
                self.metrics.total_bytes_downloaded += sum(task_ctx.transfer.down_bytes) if isinstance(task_ctx.transfer.down_bytes, list) else task_ctx.transfer.down_bytes
                self.metrics.total_bytes_uploaded += sum(task_ctx.transfer.up_bytes) if isinstance(task_ctx.transfer.up_bytes, list) else task_ctx.transfer.up_bytes
                
                log.info(f"Task {task_ctx.get_short_id()} removed from queue. Remaining: {len(self.active_tasks)}")
            return task_ctx

    def get_health_summary(self) -> str:
        """Generate human-readable health check report"""
        uptime = time.time() - self.metrics.start_time
        import math
        
        def format_time(seconds):
            if seconds < 60: return f"{seconds:.0f}s"
            if seconds < 3600: return f"{seconds/60:.1f}m"
            return f"{seconds/3600:.1f}h"

        return (
            f"🏥 **System Health Report**\n"
            f"├ **Status:** {'🔴 Shutting Down' if self.is_shutting_down else '🟢 Healthy'}\n"
            f"├ **Uptime:** `{format_time(uptime)}`\n"
            f"├ **Active Tasks:** `{len(self.active_tasks)}` / `{self.MAX_TOTAL_TASKS}`\n"
            f"├ **Background Tasks:** `{len(self.background_tasks)}` (monitored)\n"
            f"├ **Success Rate:** `{self.metrics.get_success_rate():.1f}%`\n"
            f"├ **Avg Task Time:** `{format_time(self.metrics.get_avg_completion_time())}`\n"
            f"├ **Total Down:** `{self.metrics.total_bytes_downloaded / 1e9:.2f} GB`\n"
            f"╰ **Total Up:** `{self.metrics.total_bytes_uploaded / 1e9:.2f} GB`"
        )

    async def shutdown(self):
        """Perform graceful shutdown of all tasks and background operations"""
        log.info("Starting system-wide graceful shutdown...")
        self.is_shutting_down = True
        
        # 1. Cancel all active tasks
        async with self._lock:
            tasks_to_cancel = list(self.active_tasks.values())
            
        for ctx in tasks_to_cancel:
            if ctx.async_task and not ctx.async_task.done():
                log.info(f"Cancelling task {ctx.get_short_id()} during shutdown")
                ctx.async_task.cancel()
                
        # 2. Cancel monitored background tasks
        log.info(f"Cancelling {len(self.background_tasks)} background tasks")
        for task in list(self.background_tasks):
            if not task.done():
                task.cancel()
                
        # 3. Wait for everything to settle (with timeout)
        try:
            await asyncio.wait_for(
                asyncio.gather(*self.background_tasks, return_exceptions=True),
                timeout=10.0
            )
        except asyncio.TimeoutError:
            log.warning("Shutdown timeout - some tasks may have been force-killed")
            
        log.info("Graceful shutdown complete")

    async def get_task(self, task_id: str) -> Optional[TaskContext]:
        """Get task by ID (thread-safe)"""
        async with self._lock:
            return self.active_tasks.get(task_id)

    async def has_task(self, task_id: str) -> bool:
        """Check if a task exists in the queue (thread-safe)"""
        async with self._lock:
            return task_id in self.active_tasks

    async def get_user_tasks(self, user_id: int) -> List[TaskContext]:
        """Get all tasks for a specific user (thread-safe)"""
        async with self._lock:
            return [
                task_ctx for task_ctx in self.active_tasks.values()
                if task_ctx.user_id == user_id
            ]

    async def get_all_tasks(self) -> Dict[str, TaskContext]:
        """Get all active tasks (thread-safe copy)"""
        async with self._lock:
            return self.active_tasks.copy()

    def get_task_count(self) -> int:
        """Get number of active tasks (non-blocking, may be slightly stale)"""
        return len(self.active_tasks)

    def has_active_tasks(self) -> bool:
        """Check if any tasks are active (non-blocking, may be slightly stale)"""
        return len(self.active_tasks) > 0

    async def can_start_task(self, user_id: int = None) -> tuple[bool, str]:
        """
        Check if a new task can be started.

        Returns:
            (can_start, reason) - True/False and reason message
        """
        async with self._lock:
            # Global limit check
            total_tasks = len(self.active_tasks)
            if total_tasks >= self.MAX_TOTAL_TASKS:
                return False, f"System limit reached ({total_tasks}/{self.MAX_TOTAL_TASKS} tasks active). Please wait for some to complete."

            # Per-user limit check
            if user_id:
                user_tasks = [
                    task for task in self.active_tasks.values()
                    if task.user_id == user_id
                ]
                user_task_count = len(user_tasks)

                if user_task_count >= self.MAX_TASKS_PER_USER:
                    return False, f"You have {user_task_count}/{self.MAX_TASKS_PER_USER} tasks active. Please wait for some to complete."

            return True, "OK"

    def should_update_summary(self) -> bool:
        """
        Check if summary dashboard should be updated (throttled).

        WARNING: This is NOT thread-safe. Only use for quick non-critical checks.
        For critical updates, use update_summary_dashboard with force=True.
        """
        return time.time() - self.last_summary_update >= self.summary_update_interval

    def mark_summary_updated(self):
        """
        Mark summary as updated.

        WARNING: This is NOT thread-safe. Should only be called from within
        _summary_lock to avoid race conditions.
        """
        self.last_summary_update = time.time()

    async def clear_completed_tasks(self, max_age_hours: int = 1):
        """
        Clean up old completed tasks from memory.
        This prevents memory leaks from tasks that completed but weren't removed.

        Note: This acquires self._lock, so do not call this while holding the lock.
        """
        async with self._lock:
            now = datetime.now()
            to_remove = []

            for task_id, task_ctx in self.active_tasks.items():
                if task_ctx.is_completed or task_ctx.is_cancelled:
                    if task_ctx.completed_at:
                        age_hours = (now - task_ctx.completed_at).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            to_remove.append(task_id)

            # Remove directly from dict to avoid nested lock acquisition (deadlock)
            for task_id in to_remove:
                removed_task = self.active_tasks.pop(task_id, None)
                if removed_task:
                    log.info(f"Auto-removed old completed task: {task_id[:8]}")


# Global singleton instance
TASK_QUEUE = TaskQueue()


# Helper functions for backward compatibility

def get_current_task_ctx() -> Optional[TaskContext]:
    """
    Get current task context from asyncio context.
    This is a placeholder for future implementation where we store
    task_ctx in asyncio context variables for easy access.

    For now, returns None - callers should pass task_ctx explicitly.
    """
    # TODO: Implement using contextvars if needed
    return None


def create_task_context(user_id: int, chat_id: int, mode: str = "leech") -> TaskContext:
    """
    Factory function to create a new TaskContext with proper initialization.

    Args:
        user_id: Telegram user ID
        chat_id: Telegram chat ID
        mode: Task mode (leech, mirror, etc.)

    Returns:
        Initialized TaskContext ready for use
    """
    task_ctx = TaskContext(
        user_id=user_id,
        chat_id=chat_id,
        mode=mode
    )

    # Set up unique paths
    from .variables import Paths  # Import here to avoid circular dependency
    task_ctx.work_path = f"{Paths.WORK_PATH}/{task_ctx.task_id}"
    task_ctx.down_path = f"{task_ctx.work_path}/Downloads"
    task_ctx.hero_image = f"{task_ctx.work_path}/hero_{task_ctx.get_short_id()}.jpg"

    log.info(f"Created TaskContext {task_ctx.get_short_id()} for user {user_id}")
    return task_ctx


# Export main classes and singleton
__all__ = [
    'TaskContext',
    'TaskQueue',
    'TaskTransfer',
    'TaskError',
    'TaskMessages',
    'TASK_QUEUE',
    'create_task_context',
    'get_current_task_ctx',
]
