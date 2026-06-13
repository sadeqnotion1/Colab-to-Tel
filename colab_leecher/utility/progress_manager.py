# colab_leecher/utility/progress_manager.py
import time
import asyncio
import logging
import re
from typing import Optional, Any
from os import path as ospath

# Safely import Pyrogram errors/enums
try:
    from pyrogram import enums
    PARSE_MODE_HTML = enums.ParseMode.HTML
except ImportError:
    PARSE_MODE_HTML = "html"

try:
    from pyrogram.errors import MessageNotModified, FloodWait
except ImportError:
    MessageNotModified = None
    FloodWait = None

from .transfer_state import SmartBytes
from .task_context import TaskContext, TASK_QUEUE
from .enhanced_status import StatusDisplay

log = logging.getLogger(__name__)

class ProgressManager:
    """
    Centralized Progress Manager for task progress updates.
    Deduplicates, throttles, and coordinates status updates across legacy status_bar,
    ProgressDispatcher, and summary dashboard.
    """
    def __init__(self):
        self._throttle_interval = 2.5  # seconds
        self._last_update_time = {}
        self._lock = asyncio.Lock()
        self._listeners = []

    def reset(self):
        self._last_update_time.clear()
        self._listeners.clear()

    def subscribe(self, callback):
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unsubscribe(self, callback):
        if callback in self._listeners:
            self._listeners.remove(callback)

    async def _notify_listeners(self):
        for listener in self._listeners:
            try:
                if asyncio.iscoroutinefunction(listener):
                    await listener()
                else:
                    listener()
            except Exception as e:
                log.warning(f"Error in progress listener: {e}")

    async def update_progress(
        self,
        task_id: str,
        bytes_done: float,
        bytes_total: float,
        speed: Any = "N/A",
        eta: Any = "N/A",
        percentage: float = 0.0,
        is_upload: bool = False,
        engine: str = "Unknown",
        use_custom_text: bool = False,
        custom_text: str = "",
        force: bool = False,
        task_ctx: Optional[TaskContext] = None,
        throttle_interval: Optional[float] = None
    ):
        async with self._lock:
            # 1. Resolve task_ctx
            if not task_ctx:
                task_ctx = TASK_QUEUE.active_tasks.get(task_id) if task_id else None
            
            if not task_ctx:
                # If no task context (e.g. legacy single task mode fallback), use global state
                log.debug(f"ProgressManager: task_ctx missing for task_id {task_id}")
                from ..utility.variables import MSG
                _status_msg = MSG.status_msg
            else:
                _status_msg = task_ctx.status_msg
                task_id = task_ctx.task_id

            # 2. Update task_ctx stats in consistent SmartBytes format
            if task_ctx:
                transfer = task_ctx.transfer
                if not isinstance(transfer.down_bytes, SmartBytes):
                    transfer.down_bytes = SmartBytes(transfer.down_bytes)
                if not isinstance(transfer.up_bytes, SmartBytes):
                    transfer.up_bytes = SmartBytes(transfer.up_bytes)

                if is_upload:
                    if not transfer.up_bytes:
                        transfer.up_bytes.append(int(bytes_done))
                    else:
                        transfer.up_bytes[-1] = int(bytes_done)
                else:
                    if not transfer.down_bytes:
                        transfer.down_bytes.append(int(bytes_done))
                    else:
                        transfer.down_bytes[-1] = int(bytes_done)

                if bytes_total is not None and bytes_total > 0:
                    transfer.total_size = int(bytes_total)

                transfer.update_progress(transfer.get_current_bytes(), transfer.total_size)

                # Parse and set speed for dashboard (float speed in bytes/sec)
                parsed_speed = 0.0
                if isinstance(speed, (int, float)):
                    parsed_speed = float(speed)
                elif speed and speed != "N/A":
                    try:
                        speed_str = str(speed).strip()
                        speed_match = re.search(r"(\d+\.?\d*)\s*([a-zA-Z/]+)", speed_str)
                        if speed_match:
                            speed_val = float(speed_match.group(1))
                            unit = speed_match.group(2).replace('/s', '').upper().strip()
                            multiplier = 1
                            if 'G' in unit:
                                multiplier = 1024**3
                            elif 'M' in unit:
                                multiplier = 1024**2
                            elif 'K' in unit:
                                multiplier = 1024
                            parsed_speed = speed_val * multiplier
                    except Exception as e:
                        log.debug(f"ProgressManager failed to parse speed '{speed}': {e}")
                else:
                    parsed_speed = transfer.get_speed()
                
                transfer.last_speed = parsed_speed
                transfer.last_speed_bytes = parsed_speed

            # 3. Notify subscribers
            await self._notify_listeners()

            # 4. Throttling and dashboard bypass checks for individual status edits
            now = time.time()
            last_time = self._last_update_time.get(task_id, 0.0) if task_id else 0.0

            current_interval = throttle_interval if throttle_interval is not None else self._throttle_interval
            if not force:
                # Bypass individual status edits in parallel mode
                if task_ctx and await TASK_QUEUE.has_task(task_ctx.task_id):
                    return

                # Time throttle check
                if now - last_time < current_interval:
                    return

            if task_id:
                self._last_update_time[task_id] = now

            # 5. Render/Format message text & markup
            # If no status message to edit, stop here
            if not _status_msg:
                return

            from html import escape
            from .ui_components import ProgressBar
            from .helper import sysINFO, getTime, keyboard

            _kb_markup = keyboard(task_ctx.get_short_id()) if task_ctx else keyboard()

            if use_custom_text:
                final_text = custom_text + sysINFO()
            else:
                if task_ctx:
                    filename = (
                        task_ctx.messages.download_name
                        or (task_ctx.filenames[0] if task_ctx.filenames else None)
                        or "Unknown_File"
                    )
                    progress = task_ctx.transfer.get_percentage()
                    elapsed = task_ctx.get_elapsed_time()
                    downloaded = task_ctx.transfer.get_current_bytes()
                    total = task_ctx.transfer.total_size

                    try:
                        speed_val = float(speed)
                    except (ValueError, TypeError):
                        if speed == "N/A" or speed is None:
                            speed_val = task_ctx.transfer.get_speed()
                        else:
                            speed_val = parsed_speed if task_ctx else 0.0

                    try:
                        eta_val = float(eta)
                    except (ValueError, TypeError):
                        eta_val = task_ctx.transfer.get_eta() if task_ctx else 0.0

                    if is_upload:
                        final_text, _kb_markup = StatusDisplay.upload_status(
                            filename=filename,
                            progress=progress,
                            speed=speed_val,
                            uploaded=downloaded,
                            total_size=total,
                            elapsed_time=elapsed,
                            task_id=task_ctx.task_id,
                            eta=eta_val,
                            destination=engine if engine and engine != "Unknown" else "Telegram",
                            style="sleek"
                        )
                    else:
                        final_text, _kb_markup = StatusDisplay.download_status(
                            filename=filename,
                            progress=progress,
                            speed=speed_val,
                            downloaded=downloaded,
                            total_size=total,
                            elapsed_time=elapsed,
                            task_id=task_ctx.task_id,
                            eta=eta_val,
                            engine=engine,
                            style="sleek"
                        )
                else:
                    # Fallback classic legacy text generation
                    from datetime import datetime
                    from ..utility.variables import BotTimes
                    bar_length = 20
                    percentage_float = float(percentage) if percentage else 0.0
                    bar = ProgressBar.generate(percentage_float, length=bar_length, style='smooth')
                    elapsed_seconds = (datetime.now() - BotTimes.task_start).seconds
                    elapsed_str = getTime(elapsed_seconds)
                    text_body = (
                        f"\n<b>┌「{bar}」 » {percentage_float:.1f}%</b>"
                        f"\n<b>├⚡️ Speed »</b> <code>{escape(str(speed))}</code>"
                        f"\n<b>├⚙️ Engine »</b> <code>{escape(str(engine))}</code>"
                        f"\n<b>├⏳ ETA »</b> <code>{escape(str(eta))}</code>"
                        f"\n<b>├⏱️ Elapsed »</b> <code>{escape(elapsed_str)}</code>"
                        f"\n<b>├✅ Done »</b> <code>{escape(str(bytes_done))}</code>"
                        f"\n<b>└📦 Total »</b> <code>{escape(str(bytes_total))}</code>"
                    )
                    final_text = custom_text + text_body + sysINFO()

            # 6. Execute Telegram edit message call safely
            from .helper import _edit_status_message
            try:
                await _edit_status_message(_status_msg, final_text, _kb_markup, PARSE_MODE_HTML)
            except Exception as e:
                err_name = type(e).__name__
                is_not_modified = err_name == "MessageNotModified" or (
                    MessageNotModified and isinstance(MessageNotModified, type) and isinstance(e, MessageNotModified)
                )
                if is_not_modified:
                    pass
                elif "Message to edit not found" not in str(e):
                    log.warning(f"ProgressManager status update failed: {e}")

# Global instance
_progress_manager_instance = ProgressManager()

def get_progress_manager() -> ProgressManager:
    return _progress_manager_instance
