import time
import asyncio
import logging
from typing import Optional, Any
from .task_context import TaskContext

log = logging.getLogger(__name__)

class ProgressDispatcher:
    """
    Centralized controller for task progress updates.
    Decouples download/upload loops from Pyrogram message editing.
    Implements a per-task asyncio-based safe throttle/debounce mechanism.
    """

    def __init__(
        self,
        task_ctx: TaskContext,
        operation: str = "download",
        engine: Optional[str] = None,
        style: str = "sleek",
        interval: float = 2.5,
        destination: str = "Telegram"
    ):
        """
        Args:
            task_ctx: The context of the active task.
            operation: "download" or "upload".
            engine: The downloader/uploader engine name (e.g. "Pyrogram 💥", "Aria2 🌐").
            style: The UI style to use for StatusDisplay ("sleek", "modern", "compact", "classic").
            interval: Throttling interval in seconds.
            destination: The target upload destination (used if operation is "upload").
        """
        self.task_ctx = task_ctx
        self.operation = operation.lower()
        self.engine = engine
        self.style = style
        self.interval = interval
        self.destination = destination

        # Ensure task_ctx start_time is set
        if not self.task_ctx.started_at:
            self.task_ctx.mark_started()

    async def update(self, current_bytes: float, total_bytes: Optional[float] = None, force: bool = False):
        """
        Accepts raw progress ticks, updates task statistics, and delegates
        the update to ProgressManager.
        """
        # 1. Check for cancellation
        if self.task_ctx.is_cancelled:
            raise asyncio.CancelledError("Task cancellation requested.")

        # 2. Delegate to centralized ProgressManager
        from .progress_manager import get_progress_manager
        pm = get_progress_manager()
        
        is_upload = (self.operation == "upload")
        engine_or_dest = self.destination if is_upload else self.engine

        await pm.update_progress(
            task_id=self.task_ctx.task_id,
            bytes_done=current_bytes,
            bytes_total=total_bytes,
            speed="N/A",
            eta="N/A",
            is_upload=is_upload,
            engine=engine_or_dest,
            force=force,
            task_ctx=self.task_ctx,
            throttle_interval=self.interval
        )

    async def finalize(self):
        """Force the final 100% or completion status update, bypassing throttling checks."""
        await self.update(
            current_bytes=self.task_ctx.transfer.get_current_bytes(),
            total_bytes=self.task_ctx.transfer.total_size,
            force=True
        )

    async def __call__(self, current: int, total: int):
        """
        Allows ProgressDispatcher instance to be called directly as a Pyrogram progress callback.
        Signature matches: callback(current, total)
        """
        await self.update(current_bytes=current, total_bytes=total)
