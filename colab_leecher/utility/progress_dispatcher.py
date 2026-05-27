import time
import asyncio
import logging
from typing import Optional, Any
from .enhanced_status import StatusDisplay
from .task_context import TaskContext

log = logging.getLogger(__name__)

# Safe imports for Pyrogram errors
try:
    from pyrogram.errors import MessageNotModified, FloodWait
except ImportError:
    MessageNotModified = None
    FloodWait = None

# Safe dynamic import of ParseMode
try:
    from pyrogram import enums
    PARSE_MODE_HTML = enums.ParseMode.HTML
except ImportError:
    PARSE_MODE_HTML = "html"


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
        Accepts raw progress ticks, updates task statistics, and edits the Telegram message
        if the throttling check passes or if force=True.
        """
        # 1. Check for cancellation
        if self.task_ctx.is_cancelled:
            raise asyncio.CancelledError("Task cancellation requested.")

        # 2. Update task_ctx.transfer stats
        transfer = self.task_ctx.transfer
        if self.operation == "upload":
            if isinstance(transfer.up_bytes, list):
                if not transfer.up_bytes:
                    transfer.up_bytes.append(int(current_bytes))
                else:
                    transfer.up_bytes[-1] = int(current_bytes)
            else:
                transfer.up_bytes = int(current_bytes)
        else:
            if isinstance(transfer.down_bytes, list):
                if not transfer.down_bytes:
                    transfer.down_bytes.append(int(current_bytes))
                else:
                    transfer.down_bytes[-1] = int(current_bytes)
            else:
                transfer.down_bytes = int(current_bytes)

        if total_bytes is not None and total_bytes > 0:
            transfer.total_size = int(total_bytes)

        # 3. Update dashboard summary if available
        try:
            from .task_dashboard import try_update_summary
            await try_update_summary()
        except Exception:
            pass

        # 4. Check throttle: skip Pyrogram edits if throttled and not forced
        now = time.time()
        if not force:
            # If in parallel queue dashboard mode and not forced, bypass individual status edits
            try:
                from .task_context import TASK_QUEUE
                if await TASK_QUEUE.has_task(self.task_ctx.task_id):
                    # We are in parallel dashboard mode; skip individual edits
                    return
            except Exception:
                pass

            if now - self.task_ctx.last_status_update < self.interval:
                return

        # Record this update time
        self.task_ctx.last_status_update = now

        # 5. Push raw floats through stateless StatusDisplay
        msg = self.task_ctx.status_msg
        if not msg:
            log.debug(f"ProgressDispatcher [{self.task_ctx.get_Granular_id() if hasattr(self.task_ctx, 'get_Granular_id') else self.task_ctx.get_short_id()}]: status_msg is not set. Skipping edit.")
            return

        filename = (
            self.task_ctx.messages.download_name
            or (self.task_ctx.filenames[0] if self.task_ctx.filenames else None)
            or "Unknown_File"
        )
        progress = transfer.get_percentage()
        speed = transfer.get_speed()
        eta = transfer.get_eta()
        elapsed = self.task_ctx.get_elapsed_time()
        downloaded = transfer.get_current_bytes()
        total = transfer.total_size or int(total_bytes or 0)

        if self.operation == "upload":
            text, keyboard = StatusDisplay.upload_status(
                filename=filename,
                progress=progress,
                speed=speed,
                uploaded=downloaded,
                total_size=total,
                elapsed_time=elapsed,
                task_id=self.task_ctx.task_id,
                eta=eta,
                destination=self.destination,
                style=self.style
            )
        else:
            text, keyboard = StatusDisplay.download_status(
                filename=filename,
                progress=progress,
                speed=speed,
                downloaded=downloaded,
                total_size=total,
                elapsed_time=elapsed,
                task_id=self.task_ctx.task_id,
                eta=eta,
                engine=self.engine,
                style=self.style
            )

        # 6. Safe Pyrogram edit_message call
        try:
            if hasattr(msg, "photo") and msg.photo:
                await msg.edit_caption(
                    caption=text,
                    reply_markup=keyboard,
                    parse_mode=PARSE_MODE_HTML
                )
            else:
                await msg.edit_text(
                    text=text,
                    reply_markup=keyboard,
                    parse_mode=PARSE_MODE_HTML,
                    disable_web_page_preview=True
                )
        except Exception as e:
            err_name = type(e).__name__
            is_not_modified = err_name == "MessageNotModified" or (
                MessageNotModified and isinstance(MessageNotModified, type) and isinstance(e, MessageNotModified)
            )
            is_flood_wait = err_name == "FloodWait" or (
                FloodWait and isinstance(FloodWait, type) and isinstance(e, FloodWait)
            )

            if is_not_modified:
                pass
            elif is_flood_wait:
                wait_time = getattr(e, "value", getattr(e, "x", 5))
                log.warning(f"Pyrogram FloodWait: must wait for {wait_time}s. Skipping status edit.")
            else:
                # Avoid logging if message was deleted (e.g. "Message to edit not found")
                if "message to edit not found" not in str(e).lower():
                    log.warning(f"ProgressDispatcher status update failed: {e}")

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
