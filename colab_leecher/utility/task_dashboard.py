# /content/Telegram-Leecher/colab_leecher/utility/task_dashboard.py

"""
Multi-Task Summary Dashboard

Displays real-time overview of all active download/upload tasks.
Updates periodically to show progress across parallel tasks.
"""

import logging
import os
from typing import Optional
from pyrogram import enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from .. import OWNER, colab_bot
from .task_context import TASK_QUEUE, TaskContext
from .helper import getTime
from .variables import Paths

log = logging.getLogger(__name__)


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
             
             if thumbnail_path: has_photo = True

        # Limits: Caption=1024, Text=4096. Reserve 100 chars for header/footer.
        CHAR_LIMIT = 900 if has_photo else 3800 
        
        header = f"🚀 **Parallel Downloads** ({len(tasks)} active)\n"
        summary_text = header
        tasks_shown = 0
        truncated = False

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
                speed = task_ctx.transfer.get_speed()
                uploaded_count = len(task_ctx.transfer.sent_file_names)
                status_emoji = "⬆️"
                status = f"Uploading ({uploaded_count} files) • {speed}"
            elif task_ctx.transfer.down_bytes > 0:
                # Check if we're in archiving/zipping phase (download done but upload not started)
                # Detect by checking if status_head contains archiving keywords
                is_archiving = False
                if task_ctx.messages and task_ctx.messages.status_head:
                    status_head_lower = task_ctx.messages.status_head.lower()
                    is_archiving = any(keyword in status_head_lower for keyword in ['archiving', 'zipping', 'creating archive'])

                if is_archiving:
                    # Archiving/Zipping phase
                    status_emoji = "🔐"
                    elapsed = task_ctx.get_elapsed_time()
                    elapsed_str = getTime(elapsed) if elapsed > 0 else "0s"
                    status = f"Archiving • {elapsed_str}"
                else:
                    # Downloading phase
                    speed = task_ctx.transfer.get_speed()
                    elapsed = task_ctx.get_elapsed_time()
                    elapsed_str = getTime(elapsed) if elapsed > 0 else "0s"
                    status_emoji = "⬇️"
                    status = f"Downloading • {speed} • {elapsed_str}"
            else:
                # Initializing
                status_emoji = "⏳"
                status = "Initializing..."

            # Format task line
            task_line = (
                f"{status_emoji} **Task {idx}** [`{short_id}`]\n"
                f"├ 📄 `{filename}`\n"
                f"╰ {status}\n"
            )

            # Check limit BEFORE adding
            if len(summary_text) + len(task_line) > CHAR_LIMIT:
                remaining_count = len(tasks) - tasks_shown
                summary_text += f"\n⚠️ **+ {remaining_count} more tasks...**"
                truncated = True
                break
            
            summary_text += task_line
            tasks_shown += 1

        # Create cancel buttons for each SHOWN task
        buttons = []
        # Re-iterate only up to tasks_shown to match display
        for idx, (task_id, task_ctx) in enumerate(list(tasks.items())[:tasks_shown], 1):
            short_id = task_ctx.get_short_id()
            buttons.append([InlineKeyboardButton(
                f"❌ Cancel Task {idx}",
                callback_data=f"cancel_task:{task_id}"
            )])

        # Add "Cancel All" button
        if len(tasks) > 1:
            buttons.append([InlineKeyboardButton(
                "🚫 Cancel All Tasks",
                callback_data="cancel_all_tasks"
            )])

        keyboard = InlineKeyboardMarkup(buttons) if buttons else None

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
        try:
            if TASK_QUEUE.summary_msg:
                # Update existing message
                try:
                    # Check if message has a photo (use edit_caption) or is text-only (use edit_text)
                    if hasattr(TASK_QUEUE.summary_msg, 'photo') and TASK_QUEUE.summary_msg.photo:
                        await TASK_QUEUE.summary_msg.edit_caption(
                            summary_text,
                            parse_mode=enums.ParseMode.MARKDOWN,
                            reply_markup=keyboard
                        )
                        log.debug(f"Summary dashboard caption updated ({tasks_shown}/{len(tasks)} tasks shown)")
                    else:
                        await TASK_QUEUE.summary_msg.edit_text(
                            summary_text,
                            parse_mode=enums.ParseMode.MARKDOWN,
                            disable_web_page_preview=True,
                            reply_markup=keyboard
                        )
                        log.debug(f"Summary dashboard text updated ({tasks_shown}/{len(tasks)} tasks shown)")
                except Exception as edit_err:
                    # Check if error is "message is not modified" - if so, skip recreation
                    error_msg = str(edit_err).lower()
                    if "not modified" in error_msg or "message is not modified" in error_msg:
                        log.debug(f"Summary message unchanged, skipping update (content identical)")
                        return TASK_QUEUE.summary_msg

                    # Message might have been deleted or other serious error - recreate ONCE
                    log.warning(f"❌ Failed to edit summary: {type(edit_err).__name__}: {edit_err}")
                    log.warning(f"🔄 Attempting message recreation (clearing reference first)")
                    TASK_QUEUE.summary_msg = None  # Clear reference before recreating
                    try:
                        if thumbnail_path and os.path.exists(thumbnail_path):
                            TASK_QUEUE.summary_msg = await client.send_photo(
                                OWNER,
                                photo=thumbnail_path,
                                caption=summary_text,
                                parse_mode=enums.ParseMode.MARKDOWN,
                                reply_markup=keyboard
                            )
                        else:
                            TASK_QUEUE.summary_msg = await client.send_message(
                                OWNER,
                                text=summary_text,
                                parse_mode=enums.ParseMode.MARKDOWN,
                                disable_web_page_preview=True,
                                reply_markup=keyboard
                            )
                    except FileNotFoundError:
                        # Thumbnail file deleted - fallback to text
                        log.warning(f"Thumbnail {thumbnail_path} not found, creating text-only dashboard")
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER,
                            text=summary_text,
                            parse_mode=enums.ParseMode.MARKDOWN,
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
                            parse_mode=enums.ParseMode.MARKDOWN,
                            reply_markup=keyboard
                        )
                        log.info("Summary dashboard created with photo")
                    else:
                        # Fallback to text-only if no thumbnail
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER,
                            text=summary_text,
                            parse_mode=enums.ParseMode.MARKDOWN,
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
                        parse_mode=enums.ParseMode.MARKDOWN,
                        disable_web_page_preview=True,
                        reply_markup=keyboard
                    )

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
