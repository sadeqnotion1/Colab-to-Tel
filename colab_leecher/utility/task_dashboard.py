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
from .task_context import TASK_QUEUE, TaskContext
from .helper import getTime
from .variables import Paths


def format_bytes(bytes_value: int) -> str:
    """Format bytes into human-readable format"""
    if bytes_value < 1024:
        return f"{bytes_value} B"
    elif bytes_value < 1024 * 1024:
        return f"{bytes_value/1024:.1f} KB"
    elif bytes_value < 1024 * 1024 * 1024:
        return f"{bytes_value/(1024*1024):.1f} MB"
    else:
        return f"{bytes_value/(1024*1024*1024):.2f} GB"


def create_progress_bar(percentage: float, length: int = 10) -> str:
    """Create a visual progress bar"""
    filled = int(percentage / 100 * length)
    empty = length - filled
    return f"[{'█' * filled}{'░' * empty}]"

log = logging.getLogger(__name__)


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



async def update_summary_dashboard(client=None, force: bool = False) -> Optional[Message]:
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
                log.debug(f"Forced update debounced (last update {time_since_last:.1f}s ago)")
                return TASK_QUEUE.summary_msg

        tasks = await TASK_QUEUE.get_all_tasks()
        log.info(f"📊 Dashboard update: Found {len(tasks)} active tasks")

        # If no active tasks, delete summary message if it exists
        if not tasks:
            if TASK_QUEUE.summary_msg:
                try:
                    await TASK_QUEUE.summary_msg.delete()
                except Exception as e:
                    log.warning(f"Failed to delete summary: {e}")
                finally:
                    # Always clear reference even if delete fails
                    TASK_QUEUE.summary_msg = None
                    TASK_QUEUE.last_summary_text = ""
                    TASK_QUEUE.last_summary_keyboard_signature = ""
                    log.info("Summary dashboard cleared (no active tasks)")
            return None

        # --- Build summary text with Safe Truncation ---
        # Determine strict limit based on message type
        has_photo = False
        if TASK_QUEUE.summary_msg and hasattr(TASK_QUEUE.summary_msg, 'photo') and TASK_QUEUE.summary_msg.photo:
            has_photo = True
        elif not TASK_QUEUE.summary_msg:
            # If creating new, check if we have a thumbnail
            first_task = next(iter(tasks.values()), None) if tasks else None
            thumbnail_path = None
            if first_task and hasattr(first_task, 'hero_image') and first_task.hero_image and os.path.exists(first_task.hero_image):
                thumbnail_path = first_task.hero_image
            elif os.path.exists(Paths.DEFAULT_HERO):
                thumbnail_path = Paths.DEFAULT_HERO

            if thumbnail_path:
                has_photo = True

        # Limits: Caption=1024, Text=4096. Reserve 100 chars for header/footer.
        CHAR_LIMIT = 900 if has_photo else 3800

        header = f"<b>Parallel Tasks</b> ({len(tasks)} active)\n"
        summary_text = header
        tasks_shown = 0

        for idx, (task_id, task_ctx) in enumerate(tasks.items(), 1):
            short_id = task_ctx.get_short_id()

            # Get filename - prioritize download_name over URL parsing
            filename = "Unknown"
            # First, try getting it from messages.download_name (set by task_manager)
            if task_ctx.messages and task_ctx.messages.download_name:
                filename = task_ctx.messages.download_name
            # Fallback: try to extract from URL
            elif task_ctx.source_urls and len(task_ctx.source_urls) > 0:
                url = task_ctx.source_urls[0]
                try:
                    from urllib.parse import urlparse, unquote
                    path = urlparse(url).path
                    # Skip parsing for NZBCloud "play" endpoints (use message.download_name instead)
                    if '/play?' in url or '/play#' in url:
                        filename = "NZBCloud File"  # Placeholder until download_name is set
                    else:
                        filename = unquote(path.split('/')[-1]) if path else url[:50]
                except Exception:
                    # Fallback if URL parsing fails
                    filename = url[:50] if url else "Unknown"

            # Limit filename length for display
            if len(filename) > 35:
                filename = filename[:32] + "..."

            # Calculate progress
            if task_ctx.transfer.up_bytes > 0:
                # Uploading phase
                speed = task_ctx.transfer.last_speed
                if not speed or speed == "0 B/s":
                    speed = task_ctx.transfer.get_speed()
                uploaded_count = len(task_ctx.transfer.sent_file_names)
                uploaded = format_bytes(task_ctx.transfer.up_bytes)

                status_label = "Uploading"
                if task_ctx.transfer.total_size > 0:
                    # Show percentage if we know total size
                    percentage = min(100.0, (task_ctx.transfer.up_bytes / task_ctx.transfer.total_size) * 100)
                    total = format_bytes(task_ctx.transfer.total_size)

                    # Create visual progress bar
                    progress_bar = create_progress_bar(percentage, length=10)

                    status_detail = f"{progress_bar} {percentage:.1f}%\n{uploaded}/{total} • {speed} • {uploaded_count} file(s)"
                else:
                    status_detail = f"{uploaded} • {speed} • {uploaded_count} file(s)"
            elif task_ctx.transfer.down_bytes > 0:
                # Check if we're in archiving/zipping/extracting phase (download done but upload not started)
                # Detect by checking if status_head contains archiving/extracting keywords
                is_archiving = False
                is_extracting = False
                if task_ctx.messages and task_ctx.messages.status_head:
                    status_head_lower = task_ctx.messages.status_head.lower()
                    is_archiving = any(keyword in status_head_lower for keyword in ['archiving', 'zipping', 'creating archive', 'compressing'])
                    is_extracting = any(keyword in status_head_lower for keyword in ['extracting', 'unzipping', 'decompressing', 'unpacking'])

                if is_archiving or is_extracting:
                    # Archiving/Zipping/Extracting phase
                    elapsed = task_ctx.get_elapsed_time()
                    elapsed_str = getTime(elapsed) if elapsed > 0 else "0s"
                    status_label = "Extracting" if is_extracting else "Archiving"

                    # Build detailed processing status
                    details = []

                    # Show file progress if available
                    if task_ctx.messages.total_files > 0:
                        files_done = task_ctx.messages.files_processed
                        total = task_ctx.messages.total_files
                        file_pct = (files_done / total * 100) if total > 0 else 0

                        # Create progress bar for file processing
                        progress_bar = create_progress_bar(file_pct, length=8)
                        details.append(f"{progress_bar} {files_done}/{total} files")

                    # Show archive size if available
                    if task_ctx.messages.archive_size > 0:
                        archive_size = format_bytes(task_ctx.messages.archive_size)
                        details.append(archive_size)

                    # Show current file being processed
                    if task_ctx.messages.current_file:
                        current = task_ctx.messages.current_file
                        if len(current) > 20:
                            current = current[:17] + "..."
                        details.append(f"'{current}'")

                    # Always show elapsed time
                    details.append(elapsed_str)

                    status_detail = " • ".join(details) if details else elapsed_str
                else:
                    # Downloading phase
                    speed = task_ctx.transfer.last_speed
                    if not speed or speed == "0 B/s":
                        speed = task_ctx.transfer.get_speed()

                    # Show progress with percentage and file sizes if total_size is known
                    if task_ctx.transfer.total_size > 0:
                        percentage = task_ctx.transfer.get_percentage()
                        downloaded = format_bytes(task_ctx.transfer.down_bytes)
                        total = format_bytes(task_ctx.transfer.total_size)
                        eta = task_ctx.transfer.get_eta()
                        eta_str = getTime(eta) if eta > 0 else "?"

                        # Create visual progress bar
                        progress_bar = create_progress_bar(percentage, length=10)

                        # Get server/service info if available
                        server_info = ""
                        if task_ctx.service_type:
                            server_info = f"{task_ctx.service_type.upper()} • "

                        status_label = "Downloading"
                        status_detail = f"{progress_bar} {percentage:.1f}%\n{server_info}{downloaded}/{total} • {speed} • ETA: {eta_str}"
                    else:
                        # Fallback if total size unknown
                        elapsed = task_ctx.get_elapsed_time()
                        elapsed_str = getTime(elapsed) if elapsed > 0 else "0s"
                        downloaded = format_bytes(task_ctx.transfer.down_bytes) if task_ctx.transfer.down_bytes > 0 else "?"
                        status_label = "Downloading"
                        status_detail = f"{downloaded} • {speed} • {elapsed_str}"
            else:
                # Initializing
                status_label = "Initializing"
                status_detail = ""

            status_line = f"<b>{status_label}</b>"
            if status_detail:
                status_line += f": <code>{escape(status_detail)}</code>"

            # Format task line
            task_line = (
                f"<b>Task {idx}</b> <code>{escape(short_id)}</code>\n"
                f"<code>{escape(filename)}</code>\n"
                f"{status_line}\n"
            )

            # Check limit BEFORE adding
            if len(summary_text) + len(task_line) > CHAR_LIMIT:
                remaining_count = len(tasks) - tasks_shown
                summary_text += f"\n<b>+ {remaining_count} more tasks...</b>"
                break

            summary_text += task_line
            tasks_shown += 1

        # Create cancel buttons for each SHOWN task
        buttons = []
        # Re-iterate only up to tasks_shown to match display
        for idx, (task_id, task_ctx) in enumerate(list(tasks.items())[:tasks_shown], 1):
            short_id = task_ctx.get_short_id()
            buttons.append([InlineKeyboardButton(
                f"Cancel Task {idx}",
                callback_data=f"cancel:{short_id}"
            )])

        # Add "Cancel All" button when multiple tasks are active
        if len(tasks) > 1:
            buttons.append([InlineKeyboardButton(
                "Cancel All Tasks",
                callback_data="cancel_all_tasks"
            )])

        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        keyboard_signature = _keyboard_signature(keyboard)

        # Avoid Telegram edits if text and keyboard are unchanged
        if TASK_QUEUE.summary_msg and summary_text == TASK_QUEUE.last_summary_text and keyboard_signature == TASK_QUEUE.last_summary_keyboard_signature:
            TASK_QUEUE.mark_summary_updated()
            return TASK_QUEUE.summary_msg

        # Determine thumbnail to use (from first task or fallback)
        thumbnail_path = None
        first_task = next(iter(tasks.values()), None) if tasks else None

        if first_task and hasattr(first_task, 'hero_image') and first_task.hero_image:
            # Check file exists before using (TOCTOU safe - handled in try-except below)
            if os.path.exists(first_task.hero_image):
                thumbnail_path = first_task.hero_image

        if not thumbnail_path and os.path.exists(Paths.DEFAULT_HERO):
            thumbnail_path = Paths.DEFAULT_HERO

        if not thumbnail_path:
            log.warning("No valid thumbnail found for summary dashboard")

        # Update or create message
        log.info(f"📊 Updating dashboard: {tasks_shown} tasks shown, message exists: {TASK_QUEUE.summary_msg is not None}")
        try:
            if TASK_QUEUE.summary_msg:
                # Update existing message
                log.debug(f"Editing existing summary message (ID: {TASK_QUEUE.summary_msg.id})")
                try:
                    # Check if message has a photo (use edit_caption) or is text-only (use edit_text)
                    if hasattr(TASK_QUEUE.summary_msg, 'photo') and TASK_QUEUE.summary_msg.photo:
                        await TASK_QUEUE.summary_msg.edit_caption(
                            summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            reply_markup=keyboard
                        )
                        log.debug(f"Summary dashboard caption updated ({tasks_shown}/{len(tasks)} tasks shown)")
                    else:
                        log.debug(f"Editing text-only message with {len(summary_text)} chars")
                        await TASK_QUEUE.summary_msg.edit_text(
                            summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
                        log.info(f"✅ Summary dashboard text updated ({tasks_shown}/{len(tasks)} tasks shown)")
                except Exception as edit_err:
                    # Check if error is "message is not modified" - if so, skip recreation
                    error_msg = str(edit_err).lower()
                    log.warning(f"⚠️ Edit failed: {type(edit_err).__name__}: {edit_err}")
                    if "not modified" in error_msg or "message is not modified" in error_msg:
                        log.debug("Summary message unchanged, skipping update (content identical)")
                        TASK_QUEUE.last_summary_text = summary_text
                        TASK_QUEUE.last_summary_keyboard_signature = keyboard_signature
                        TASK_QUEUE.mark_summary_updated()
                        return TASK_QUEUE.summary_msg

                    # Message might have been deleted or other serious error - recreate ONCE
                    log.warning(f"Failed to edit summary: {type(edit_err).__name__}: {edit_err}")
                    log.warning("Attempting message recreation (clearing reference first)")
                    TASK_QUEUE.summary_msg = None  # Clear reference before recreating
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
                        # Thumbnail file deleted - fallback to text
                        log.warning(f"Thumbnail {thumbnail_path} not found, creating text-only dashboard")
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER,
                            text=summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
            else:
                # Create new message with photo
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
                        # Fallback to text-only if no thumbnail
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER,
                            text=summary_text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
                        log.info("Summary dashboard created (text-only, no thumbnail)")
                except FileNotFoundError:
                    # Thumbnail deleted between check and send - fallback to text
                    log.warning(f"Thumbnail {thumbnail_path} deleted during send, creating text-only")
                    TASK_QUEUE.summary_msg = await client.send_message(
                        OWNER,
                        text=summary_text,
                        parse_mode=enums.ParseMode.HTML,
                        disable_web_page_preview=True,
                        reply_markup=keyboard
                    )

            TASK_QUEUE.last_summary_text = summary_text
            TASK_QUEUE.last_summary_keyboard_signature = keyboard_signature

            # Mark as updated
            TASK_QUEUE.mark_summary_updated()
            return TASK_QUEUE.summary_msg

        except Exception as e:
            log.error(f"Failed to update summary dashboard: {e}")
            return None


async def try_update_summary(client=None):
    """
    Update summary dashboard only if throttle interval has passed.
    Use this in progress update loops to avoid spamming updates.
    """
    # Throttling checked inside update_summary_dashboard
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
    
    # Try immediate update
    result = await update_summary_dashboard(client, force=True)
    
    # Check if we need to schedule a delayed update to catch any debounced changes
    # We do this blindly on every force update to be safe, or we could return a 'debounced' flag
    # For simplicity/safety against race conditions, if an update happens, 
    # ensure one final check runs after the debounce window.
    
    if _scheduled_update_task and not _scheduled_update_task.done():
        return # Already scheduled
        
    async def delayed_update():
        import asyncio
        # Wait slightly longer than the min_forced_update_interval (assumed ~1-2s)
        await asyncio.sleep(2.0) 
        await update_summary_dashboard(client, force=True)
        
    import asyncio
    _scheduled_update_task = asyncio.create_task(delayed_update())
