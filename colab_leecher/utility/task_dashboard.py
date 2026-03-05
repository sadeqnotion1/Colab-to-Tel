# /content/Telegram-Leecher/colab_leecher/utility/task_dashboard.py

"""
Multi-Task Summary Dashboard

Displays real-time overview of all active download/upload tasks.
Updates periodically to show progress across parallel tasks.
"""

import logging
import os
from html import escape
from typing import Optional
from pyrogram import enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from .. import OWNER, colab_bot
from .task_context import TASK_QUEUE
from .helper import getTime
from .variables import Paths
# FIX: import shared utilities instead of duplicating them locally
from .ui_components import SizeFormatter, ProgressBar
from .ui_copy import build_cancel_task_button_label, summarize_task_name

# Gate all debug file I/O behind BOT_DEBUG env var.
# Set BOT_DEBUG=1 in your environment to enable.
BOT_DEBUG = os.getenv("BOT_DEBUG", "0") == "1"

log = logging.getLogger(__name__)


def _format_bytes(x: int) -> str:
    """Thin wrapper so existing callers inside this file keep working."""
    return SizeFormatter.format_bytes(x)


def _progress_bar(percentage: float, length: int = 10) -> str:
    """Return an ASCII-safe progress bar for consistent Telegram rendering."""
    return "[" + ProgressBar.generate(percentage, length, "ascii") + "]"


def _keyboard_signature(keyboard: Optional[InlineKeyboardMarkup]) -> str:
    if not keyboard:
        return ""
    rows = []
    for row in keyboard.inline_keyboard:
        row_sig = ",".join(
            f"{button.text}:{button.callback_data}" for button in row
        )
        rows.append(row_sig)
    return "|".join(rows)


async def update_summary_dashboard(
        client=None,
        force: bool = False) -> Optional[Message]:
    """
    Update or create the summary dashboard showing all active tasks (thread-safe).

    Args:
        client: Pyrogram client instance
        force: If True, bypass throttling and update immediately

    Returns:
        Updated/created summary message, or None if no tasks active
    """
    if not client:
        client = colab_bot

    # Optimization: Fast fail check outside lock (read-only)
    if not force and not TASK_QUEUE.should_update_summary():
        return TASK_QUEUE.summary_msg

    # Use lock to prevent concurrent updates
    async with TASK_QUEUE._summary_lock:
        # Check throttling (unless forced)
        if not force and not TASK_QUEUE.should_update_summary():
            return TASK_QUEUE.summary_msg

        # Even for forced updates, apply debouncing to prevent Telegram rate limits
        if force:
            import time
            time_since_last = time.time() - TASK_QUEUE.last_summary_update
            if time_since_last < TASK_QUEUE.min_forced_update_interval:
                log.debug(
                    f"Forced update debounced (last update {time_since_last:.1f}s ago)")
                return TASK_QUEUE.summary_msg

        tasks = await TASK_QUEUE.get_all_tasks()
        log.info(f"\U0001f4ca Dashboard update: Found {len(tasks)} active tasks")

        if BOT_DEBUG:
            try:
                from datetime import datetime
                with open("dashboard_debug.txt", "a", encoding="utf-8") as f:
                    f.write(f"\n{'=' * 80}\n")
                    f.write(f"DASHBOARD UPDATE at {datetime.now()}\n")
                    f.write(f"{'=' * 80}\n")
                    f.write(f"Tasks found: {len(tasks)}\n")
                    f.write(f"Force update: {force}\n")
                    f.write(
                        f"Summary message exists: {TASK_QUEUE.summary_msg is not None}\n")
                    if TASK_QUEUE.summary_msg:
                        f.write(
                            f"Summary message ID: {TASK_QUEUE.summary_msg.id}\n")
                    f.write("\nTask details:\n")
                    for task_id, task_ctx in tasks.items():
                        f.write(f"  - {task_ctx.get_short_id()}: ")
                        f.write(
                            f"down={task_ctx.transfer.down_bytes}, up={task_ctx.transfer.up_bytes}, ")
                        f.write(f"total={task_ctx.transfer.total_size}\n")
                    f.write("\n")
            except Exception as debug_err:
                log.warning(f"Debug file write failed: {debug_err}")

        # If no active tasks, delete summary message if it exists
        if not tasks:
            if TASK_QUEUE.summary_msg:
                try:
                    await TASK_QUEUE.summary_msg.delete()
                except Exception as e:
                    log.warning(f"Failed to delete summary: {e}")
                finally:
                    TASK_QUEUE.summary_msg = None
                    TASK_QUEUE.last_summary_text = ""
                    TASK_QUEUE.last_summary_keyboard_signature = ""
                    log.info("Summary dashboard cleared (no active tasks)")
            return None

        # --- Build summary text ---
        has_photo = False
        if TASK_QUEUE.summary_msg and hasattr(
                TASK_QUEUE.summary_msg, 'photo') and TASK_QUEUE.summary_msg.photo:
            has_photo = True
        elif not TASK_QUEUE.summary_msg:
            first_task = next(iter(tasks.values()), None) if tasks else None
            thumbnail_path = None
            if first_task and hasattr(
                    first_task, 'hero_image') and first_task.hero_image and os.path.exists(
                    first_task.hero_image):
                thumbnail_path = first_task.hero_image
            elif os.path.exists(Paths.DEFAULT_HERO):
                thumbnail_path = Paths.DEFAULT_HERO
            if thumbnail_path:
                has_photo = True

        # Limits: Caption=1024, Text=4096. Reserve chars for header/footer.
        CHAR_LIMIT = 900 if has_photo else 3800

        # FIX: Build aggregate speed string for header
        total_speed_str = ""
        try:
            speed_values = []
            for t in tasks.values():
                raw = getattr(t.transfer, "last_speed_bytes", None)
                if raw and isinstance(raw, (int, float)) and raw > 0:
                    speed_values.append(raw)
            if speed_values:
                total_speed_str = f"  \u26a1 <b>{SizeFormatter.format_speed(sum(speed_values))}</b>"
        except Exception:
            pass

        header = (
            f"<b>\U0001f680 Active Tasks</b> \u2022 <b>{len(tasks)}</b> running{total_speed_str}\n\n"
        )
        summary_text = header
        tasks_shown = 0

        for idx, (task_id, task_ctx) in enumerate(tasks.items(), 1):
            short_id = task_ctx.get_short_id()

            source_url = task_ctx.source_urls[0] if task_ctx.source_urls else None
            raw_name = task_ctx.messages.download_name if task_ctx.messages else None
            if not raw_name and source_url and (
                "/play?" in source_url or "/play#" in source_url
            ):
                raw_name = "NZBCloud File"
            filename = summarize_task_name(
                raw_name,
                source_url,
                fallback="Unknown",
                max_length=42,
            )

            # Calculate progress
            if task_ctx.transfer.up_bytes > 0:
                speed = task_ctx.transfer.last_speed
                if not speed or speed == "0 B/s":
                    speed = task_ctx.transfer.get_speed()
                uploaded_count = len(task_ctx.transfer.sent_file_names)
                uploaded = _format_bytes(task_ctx.transfer.up_bytes)

                status_label = "\U0001f4e4 Uploading"
                if task_ctx.transfer.total_size > 0:
                    percentage = min(
                        100.0, (task_ctx.transfer.up_bytes / task_ctx.transfer.total_size) * 100)
                    total = _format_bytes(task_ctx.transfer.total_size)
                    progress_bar = _progress_bar(percentage, length=10)
                    status_detail = f"{progress_bar} {percentage:.1f}%\n{uploaded}/{total} \u2022 {speed} \u2022 {uploaded_count} file(s)"
                else:
                    status_detail = f"{uploaded} \u2022 {speed} \u2022 {uploaded_count} file(s)"

            elif task_ctx.transfer.down_bytes > 0:
                is_archiving = False
                is_extracting = False
                if task_ctx.messages and task_ctx.messages.status_head:
                    status_head_lower = task_ctx.messages.status_head.lower()
                    is_archiving = any(
                        keyword in status_head_lower for keyword in [
                            'archiving', 'zipping', 'creating archive', 'compressing'])
                    is_extracting = any(
                        keyword in status_head_lower for keyword in [
                            'extracting', 'unzipping', 'decompressing', 'unpacking'])

                if is_archiving or is_extracting:
                    elapsed = task_ctx.get_elapsed_time()
                    elapsed_str = getTime(elapsed) if elapsed > 0 else "0s"
                    status_label = "\U0001f4c2 Extracting" if is_extracting else "\U0001f5dc\ufe0f Archiving"

                    details = []
                    if task_ctx.messages.total_files > 0:
                        files_done = task_ctx.messages.files_processed
                        total = task_ctx.messages.total_files
                        file_pct = (files_done / total * 100) if total > 0 else 0
                        progress_bar = _progress_bar(file_pct, length=8)
                        details.append(f"{progress_bar} {files_done}/{total} files")

                    if task_ctx.messages.archive_size > 0:
                        archive_size = _format_bytes(task_ctx.messages.archive_size)
                        details.append(archive_size)

                    if task_ctx.messages.current_file:
                        current = task_ctx.messages.current_file
                        if len(current) > 20:
                            current = current[:17] + "..."
                        details.append(f"'{current}'")

                    details.append(elapsed_str)
                    status_detail = " \u2022 ".join(details) if details else elapsed_str

                else:
                    speed = task_ctx.transfer.last_speed
                    if not speed or speed == "0 B/s":
                        speed = task_ctx.transfer.get_speed()

                    if task_ctx.transfer.total_size > 0:
                        percentage = task_ctx.transfer.get_percentage()
                        downloaded = _format_bytes(task_ctx.transfer.down_bytes)
                        total = _format_bytes(task_ctx.transfer.total_size)
                        eta = task_ctx.transfer.get_eta()
                        eta_str = getTime(eta) if eta > 0 else "?"

                        progress_bar = _progress_bar(percentage, length=10)

                        server_info = ""
                        if task_ctx.service_type:
                            server_info = f"{task_ctx.service_type.upper()} \u2022 "

                        status_label = "\U0001f4e5 Downloading"
                        status_detail = f"{progress_bar} {percentage:.1f}%\n{server_info}{downloaded}/{total} \u2022 {speed} \u2022 ETA: {eta_str}"
                    else:
                        elapsed = task_ctx.get_elapsed_time()
                        elapsed_str = getTime(elapsed) if elapsed > 0 else "0s"
                        downloaded = _format_bytes(
                            task_ctx.transfer.down_bytes) if task_ctx.transfer.down_bytes > 0 else "?"
                        status_label = "\U0001f4e5 Downloading"
                        status_detail = f"{downloaded} \u2022 {speed} \u2022 {elapsed_str}"
            else:
                status_label = "\U0001f4dd Initializing"
                status_detail = ""

            status_line = f"<b>{status_label}</b>"
            if status_detail:
                status_line += f"\n{escape(status_detail)}"

            task_line = (
                f"<b>{idx}. {escape(filename)}</b>\n"
                f"<code>ID: {escape(short_id)}</code>\n"
                f"{status_line}\n\n"
            )

            if len(summary_text) + len(task_line) > CHAR_LIMIT:
                remaining_count = len(tasks) - tasks_shown
                summary_text += (
                    f"<i>+ {remaining_count} more task(s) not shown</i>\n"
                )
                break

            summary_text += task_line
            tasks_shown += 1

        # Create cancel buttons for each shown task
        buttons = []
        for task_id, task_ctx in list(tasks.items())[:tasks_shown]:
            short_id = task_ctx.get_short_id()
            download_name = task_ctx.messages.download_name if task_ctx.messages else None
            source_url = task_ctx.source_urls[0] if task_ctx.source_urls else None
            buttons.append([InlineKeyboardButton(
                build_cancel_task_button_label(download_name, source_url, short_id),
                callback_data=f"cancel:{short_id}"
            )])

        if len(tasks) > 1:
            buttons.append([InlineKeyboardButton(
                "\u274c Cancel All Tasks",
                callback_data="cancel_all_tasks"
            )])

        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        keyboard_signature = _keyboard_signature(keyboard)

        # Skip edit if content unchanged
        if TASK_QUEUE.summary_msg and summary_text == TASK_QUEUE.last_summary_text and keyboard_signature == TASK_QUEUE.last_summary_keyboard_signature:
            TASK_QUEUE.mark_summary_updated()
            return TASK_QUEUE.summary_msg

        # Determine thumbnail
        thumbnail_path = None
        first_task = next(iter(tasks.values()), None) if tasks else None

        if first_task and hasattr(first_task, 'hero_image') and first_task.hero_image:
            if os.path.exists(first_task.hero_image):
                thumbnail_path = first_task.hero_image

        if not thumbnail_path and os.path.exists(Paths.DEFAULT_HERO):
            thumbnail_path = Paths.DEFAULT_HERO

        if not thumbnail_path:
            log.warning("No valid thumbnail found for summary dashboard")

        if BOT_DEBUG:
            try:
                from datetime import datetime
                with open("dashboard_debug.txt", "a", encoding="utf-8") as f:
                    f.write(
                        f"Generated dashboard text ({len(summary_text)} chars, {tasks_shown} tasks shown):\n")
                    f.write(f"{'-' * 80}\n")
                    f.write(summary_text)
                    f.write(f"\n{'-' * 80}\n\n")
            except Exception as debug_err:
                log.warning(f"Debug text dump failed: {debug_err}")

        log.info(
            f"\U0001f4ca Updating dashboard: {tasks_shown} tasks shown, message exists: {TASK_QUEUE.summary_msg is not None}")

        try:
            if TASK_QUEUE.summary_msg:
                log.debug(
                    f"Editing existing summary message (ID: {TASK_QUEUE.summary_msg.id})")
                try:
                    if hasattr(TASK_QUEUE.summary_msg, 'photo') and TASK_QUEUE.summary_msg.photo:
                        await TASK_QUEUE.summary_msg.edit_caption(
                            summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            reply_markup=keyboard
                        )
                        log.debug(
                            f"Summary dashboard caption updated ({tasks_shown}/{len(tasks)} tasks shown)")
                    else:
                        log.debug(
                            f"Editing text-only message with {len(summary_text)} chars")
                        await TASK_QUEUE.summary_msg.edit_text(
                            summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
                        log.info(
                            f"\u2705 Summary dashboard text updated ({tasks_shown}/{len(tasks)} tasks shown)")
                except Exception as edit_err:
                    if BOT_DEBUG:
                        try:
                            import traceback
                            with open("dashboard_debug.txt", "a", encoding="utf-8") as f:
                                f.write("\u274c EDIT FAILED:\n")
                                f.write(f"Exception type: {type(edit_err).__name__}\n")
                                f.write(f"Exception message: {str(edit_err)}\n")
                                f.write("Full traceback:\n")
                                f.write(traceback.format_exc())
                                f.write("\n")
                        except Exception as debug_err2:
                            log.warning(f"Debug exception dump failed: {debug_err2}")

                    error_msg = str(edit_err).lower()
                    log.warning(
                        f"\u26a0\ufe0f Edit failed: {type(edit_err).__name__}: {edit_err}")
                    if "not modified" in error_msg or "message is not modified" in error_msg:
                        log.debug(
                            "Summary message unchanged, skipping update (content identical)")
                        TASK_QUEUE.last_summary_text = summary_text
                        TASK_QUEUE.last_summary_keyboard_signature = keyboard_signature
                        TASK_QUEUE.mark_summary_updated()
                        return TASK_QUEUE.summary_msg

                    log.warning(
                        f"Failed to edit summary: {type(edit_err).__name__}: {edit_err}")
                    log.warning(
                        "Attempting message recreation (clearing reference first)")
                    TASK_QUEUE.summary_msg = None
                    try:
                        if thumbnail_path and os.path.exists(thumbnail_path):
                            TASK_QUEUE.summary_msg = await client.send_photo(
                                OWNER,
                                photo=thumbnail_path,
                                caption=summary_text,
                                parse_mode=enums.ParseMode.HTML,
                                reply_markup=keyboard
                            )
                        else:
                            TASK_QUEUE.summary_msg = await client.send_message(
                                OWNER,
                                text=summary_text,
                                parse_mode=enums.ParseMode.HTML,
                                disable_web_page_preview=True,
                                reply_markup=keyboard
                            )
                    except FileNotFoundError:
                        log.warning(
                            f"Thumbnail {thumbnail_path} not found, creating text-only dashboard")
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER,
                            text=summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
            else:
                try:
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        TASK_QUEUE.summary_msg = await client.send_photo(
                            OWNER,
                            photo=thumbnail_path,
                            caption=summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            reply_markup=keyboard
                        )
                        log.info("Summary dashboard created with photo")
                    else:
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER,
                            text=summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
                        log.info(
                            "Summary dashboard created (text-only, no thumbnail)")
                except FileNotFoundError:
                    log.warning(
                        f"Thumbnail {thumbnail_path} deleted during send, creating text-only")
                    TASK_QUEUE.summary_msg = await client.send_message(
                        OWNER,
                        text=summary_text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=keyboard
                    )

            TASK_QUEUE.last_summary_text = summary_text
            TASK_QUEUE.last_summary_keyboard_signature = keyboard_signature

            if BOT_DEBUG:
                try:
                    with open("dashboard_debug.txt", "a", encoding="utf-8") as f:
                        f.write("\u2705 Dashboard update SUCCESS\n")
                        f.write(
                            f"   Message ID: {TASK_QUEUE.summary_msg.id if TASK_QUEUE.summary_msg else 'None'}\n")
                        f.write(f"   Tasks shown: {tasks_shown}/{len(tasks)}\n\n")
                except Exception:
                    pass

            TASK_QUEUE.mark_summary_updated()
            return TASK_QUEUE.summary_msg

        except Exception as e:
            if BOT_DEBUG:
                try:
                    import traceback
                    with open("dashboard_debug.txt", "a", encoding="utf-8") as f:
                        f.write("\u274c\u274c\u274c CRITICAL DASHBOARD FAILURE \u274c\u274c\u274c\n")
                        f.write(f"Exception type: {type(e).__name__}\n")
                        f.write(f"Exception message: {str(e)}\n")
                        f.write("Full traceback:\n")
                        f.write(traceback.format_exc())
                        f.write(f"\n{'=' * 80}\n\n")
                except Exception:
                    pass

            log.error(
                f"Failed to update summary dashboard: {e}",
                exc_info=True)
            return None


async def try_update_summary(client=None):
    """
    Update summary dashboard only if throttle interval has passed.
    Use this in progress update loops to avoid spamming updates.
    """
    await update_summary_dashboard(client, force=False)


_scheduled_update_task = None


async def force_update_summary(client=None):
    """
    Force update summary dashboard immediately (bypasses throttling).
    Use this when tasks start/complete/cancel.

    Note: Debouncing is handled internally to prevent Telegram rate limits.
    If debounced, a delayed update is scheduled to ensure final state consistency.
    """
    global _scheduled_update_task

    if BOT_DEBUG:
        try:
            from datetime import datetime
            with open("dashboard_debug.txt", "a", encoding="utf-8") as f:
                f.write(f"\U0001f525 force_update_summary() CALLED at {datetime.now()}\n")
                f.write(f"   Client provided: {client is not None}\n")
                f.write(f"   Active tasks: {TASK_QUEUE.get_task_count()}\n\n")
        except Exception:
            pass

    await update_summary_dashboard(client, force=True)

    if _scheduled_update_task and not _scheduled_update_task.done():
        return

    async def delayed_update():
        import asyncio
        await asyncio.sleep(2.0)
        await update_summary_dashboard(client, force=True)

    import asyncio
    _scheduled_update_task = asyncio.create_task(delayed_update())
