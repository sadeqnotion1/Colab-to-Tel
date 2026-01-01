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
from typing import Dict, Optional, List
from datetime import datetime
from pyrogram.types import Message

log = logging.getLogger(__name__)


# Replicate Transfer class structure for per-task statistics
@dataclass
class TaskTransfer:
    """Per-task transfer statistics"""
    down_bytes: int = 0
    up_bytes: int = 0
    sent_file: List = field(default_factory=list)  # List of successfully sent message objects (from Pyrogram)
    sent_file_names: List[str] = field(default_factory=list)
    successful_downloads: List[dict] = field(default_factory=list)  # List of {'url': url, 'filename': filename}
    start_time: float = field(default_factory=time.time)

    def reset(self):
        """Reset transfer statistics"""
        self.down_bytes = 0
        self.up_bytes = 0
        self.sent_file = []
        self.sent_file_names = []
        self.successful_downloads = []
        self.start_time = time.time()

    def get_percentage(self, total_size: int = 0) -> float:
        """Calculate download percentage"""
        if total_size == 0:
            return 0.0
        return min(100.0, (self.down_bytes / total_size) * 100)

    def get_speed(self) -> str:
        """Calculate current download/upload speed"""
        elapsed = time.time() - self.start_time
        if elapsed == 0:
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


class TaskQueue:
    """
    Global task queue manager for parallel multi-task execution.

    Manages all active tasks, provides task registration/removal,
    and maintains the summary dashboard message.
    """

    def __init__(self):
        self.active_tasks: Dict[str, TaskContext] = {}  # task_id → TaskContext
        self.summary_msg: Optional[Message] = None  # Summary dashboard message
        self.last_summary_update: float = 0  # Last time summary was updated
        self.summary_update_interval: float = 5.0  # Update summary every 5 seconds
        self._lock = asyncio.Lock()  # Thread-safe operations

    def add_task(self, task_ctx: TaskContext):
        """Register a new task"""
        self.active_tasks[task_ctx.task_id] = task_ctx
        log.info(f"Task {task_ctx.get_short_id()} added to queue. Total active: {len(self.active_tasks)}")

    def remove_task(self, task_id: str) -> Optional[TaskContext]:
        """Remove a completed/cancelled task"""
        task_ctx = self.active_tasks.pop(task_id, None)
        if task_ctx:
            log.info(f"Task {task_ctx.get_short_id()} removed from queue. Remaining: {len(self.active_tasks)}")
        return task_ctx

    def get_task(self, task_id: str) -> Optional[TaskContext]:
        """Get task by ID"""
        return self.active_tasks.get(task_id)

    def get_user_tasks(self, user_id: int) -> List[TaskContext]:
        """Get all tasks for a specific user"""
        return [
            task_ctx for task_ctx in self.active_tasks.values()
            if task_ctx.user_id == user_id
        ]

    def get_all_tasks(self) -> Dict[str, TaskContext]:
        """Get all active tasks"""
        return self.active_tasks.copy()

    def get_task_count(self) -> int:
        """Get number of active tasks"""
        return len(self.active_tasks)

    def has_active_tasks(self) -> bool:
        """Check if any tasks are active"""
        return len(self.active_tasks) > 0

    def can_start_task(self, user_id: int = None) -> bool:
        """
        Check if a new task can be started.
        Since we support unlimited parallel tasks, this always returns True.
        Override this method to implement limits if needed.
        """
        # No limits for now - unlimited parallel tasks
        return True

    def should_update_summary(self) -> bool:
        """Check if summary dashboard should be updated (throttled)"""
        return time.time() - self.last_summary_update >= self.summary_update_interval

    def mark_summary_updated(self):
        """Mark summary as updated"""
        self.last_summary_update = time.time()

    async def clear_completed_tasks(self, max_age_hours: int = 1):
        """
        Clean up old completed tasks from memory.
        This prevents memory leaks from tasks that completed but weren't removed.
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

            for task_id in to_remove:
                self.remove_task(task_id)
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
