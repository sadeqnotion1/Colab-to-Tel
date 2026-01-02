# /content/Telegram-Leecher/colab_leecher/utility/task_dashboard.py

"""
Multi-Task Summary Dashboard

Displays real-time overview of all active download/upload tasks.
Updates periodically to show progress across parallel tasks.
"""

import logging
import os
from typing import Optional
from pyrogram.types import Message
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

        # Build summary text with better formatting
        summary_lines = [
            f"🚀 **Parallel Downloads** ({len(tasks)} active)\n"
        ]

        for idx, (task_id, task_ctx) in enumerate(tasks.items(), 1):
            short_id = task_ctx.get_short_id()

            # Get filename from source URL or messages
            filename = "Unknown"
            if task_ctx.source_urls and len(task_ctx.source_urls) > 0:
                # Extract filename from URL (safe list access)
                url = task_ctx.source_urls[0]
                try:
                    from urllib.parse import urlparse, unquote
                    path = urlparse(url).path
                    filename = unquote(path.split('/')[-1]) if path else url[:50]
                except Exception:
                    # Fallback if URL parsing fails
                    filename = url[:50] if url else "Unknown"
            elif task_ctx.messages.download_name:
                filename = task_ctx.messages.download_name

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

            summary_lines.append(task_line)

        summary_text = "\n".join(summary_lines)

        # Note: Truncation is applied later based on message type
        # Photo captions: 1024 chars, Text messages: 4096 chars

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
                        # Message has photo - edit caption (1024 char limit)
                        caption_text = summary_text
                        if len(caption_text) > 1024:
                            caption_text = caption_text[:974] + "\n\n⚠️ ... (truncated)"
                            log.warning(f"Caption truncated from {len(summary_text)} to 1024 chars (photo limit)")
                        await TASK_QUEUE.summary_msg.edit_caption(caption_text)
                        log.debug(f"Summary dashboard caption updated ({len(tasks)} tasks)")
                    else:
                        # Text-only message - edit text (4096 char limit)
                        text_content = summary_text
                        if len(text_content) > 4096:
                            text_content = text_content[:4046] + "\n\n⚠️ ... (truncated)"
                            log.warning(f"Text truncated from {len(summary_text)} to 4096 chars (text limit)")
                        await TASK_QUEUE.summary_msg.edit_text(
                            text_content,
                            disable_web_page_preview=True
                        )
                        log.debug(f"Summary dashboard text updated ({len(tasks)} tasks)")
                except Exception as edit_err:
                    # Message might have been deleted or other error - recreate
                    log.warning(f"Failed to edit summary, recreating: {edit_err}")
                    try:
                        if thumbnail_path and os.path.exists(thumbnail_path):
                            # Truncate for photo caption (1024 char limit)
                            caption_text = summary_text
                            if len(caption_text) > 1024:
                                caption_text = caption_text[:974] + "\n\n⚠️ ... (truncated)"
                            TASK_QUEUE.summary_msg = await client.send_photo(
                                OWNER,
                                photo=thumbnail_path,
                                caption=caption_text
                            )
                        else:
                            # Truncate for text message (4096 char limit)
                            text_content = summary_text
                            if len(text_content) > 4096:
                                text_content = text_content[:4046] + "\n\n⚠️ ... (truncated)"
                            TASK_QUEUE.summary_msg = await client.send_message(
                                OWNER,
                                text=text_content,
                                disable_web_page_preview=True
                            )
                    except FileNotFoundError:
                        # Thumbnail file deleted - fallback to text
                        log.warning(f"Thumbnail {thumbnail_path} not found, creating text-only dashboard")
                        text_content = summary_text
                        if len(text_content) > 4096:
                            text_content = text_content[:4046] + "\n\n⚠️ ... (truncated)"
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER,
                            text=text_content,
                            disable_web_page_preview=True
                        )
            else:
                # Create new message with photo
                try:
                    if thumbnail_path and os.path.exists(thumbnail_path):
                        # Truncate for photo caption (1024 char limit)
                        caption_text = summary_text
                        if len(caption_text) > 1024:
                            caption_text = caption_text[:974] + "\n\n⚠️ ... (truncated)"
                        TASK_QUEUE.summary_msg = await client.send_photo(
                            OWNER,
                            photo=thumbnail_path,
                            caption=caption_text
                        )
                        log.info("Summary dashboard created with photo")
                    else:
                        # Fallback to text-only if no thumbnail (4096 char limit)
                        text_content = summary_text
                        if len(text_content) > 4096:
                            text_content = text_content[:4046] + "\n\n⚠️ ... (truncated)"
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER,
                            text=text_content,
                            disable_web_page_preview=True
                        )
                        log.info("Summary dashboard created (text-only, no thumbnail)")
                except FileNotFoundError:
                    # Thumbnail deleted between check and send - fallback to text
                    log.warning(f"Thumbnail {thumbnail_path} deleted during send, creating text-only")
                    text_content = summary_text
                    if len(text_content) > 4096:
                        text_content = text_content[:4046] + "\n\n⚠️ ... (truncated)"
                    TASK_QUEUE.summary_msg = await client.send_message(
                        OWNER,
                        text=text_content,
                        disable_web_page_preview=True
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
