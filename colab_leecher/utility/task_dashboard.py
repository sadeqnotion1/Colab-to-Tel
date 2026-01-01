# /content/Telegram-Leecher/colab_leecher/utility/task_dashboard.py

"""
Multi-Task Summary Dashboard

Displays real-time overview of all active download/upload tasks.
Updates periodically to show progress across parallel tasks.
"""

import logging
from typing import Optional
from pyrogram.types import Message
from .. import OWNER, colab_bot
from .task_context import TASK_QUEUE, TaskContext
from .helper import getTime

log = logging.getLogger(__name__)


async def update_summary_dashboard(client=None) -> Optional[Message]:
    """
    Update or create the summary dashboard showing all active tasks.

    Returns:
        Updated/created summary message, or None if no tasks active
    """
    if not client:
        client = colab_bot

    tasks = TASK_QUEUE.get_all_tasks()

    # If no active tasks, delete summary message if it exists
    if not tasks:
        if TASK_QUEUE.summary_msg:
            try:
                await TASK_QUEUE.summary_msg.delete()
                TASK_QUEUE.summary_msg = None
                log.info("Summary dashboard deleted (no active tasks)")
            except Exception as e:
                log.warning(f"Failed to delete summary: {e}")
        return None

    # Build summary text with better formatting
    summary_lines = [
        f"🚀 **Parallel Downloads** ({len(tasks)} active)\n"
    ]

    for idx, (task_id, task_ctx) in enumerate(tasks.items(), 1):
        short_id = task_ctx.get_short_id()

        # Get filename from source URL or messages
        filename = "Unknown"
        if task_ctx.source_urls:
            # Extract filename from URL
            url = task_ctx.source_urls[0]
            try:
                from urllib.parse import urlparse, unquote
                path = urlparse(url).path
                filename = unquote(path.split('/')[-1]) if path else url[:50]
            except:
                filename = url[:50]
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

    # Update or create message
    try:
        if TASK_QUEUE.summary_msg:
            # Update existing message
            try:
                await TASK_QUEUE.summary_msg.edit_text(
                    summary_text,
                    disable_web_page_preview=True
                )
                log.debug(f"Summary dashboard updated ({len(tasks)} tasks)")
            except Exception as edit_err:
                # Message might have been deleted, try creating new one
                log.warning(f"Failed to edit summary, creating new: {edit_err}")
                TASK_QUEUE.summary_msg = await client.send_message(
                    OWNER,
                    summary_text,
                    disable_web_page_preview=True
                )
        else:
            # Create new message (shouldn't happen with parallel downloads, but fallback)
            TASK_QUEUE.summary_msg = await client.send_message(
                OWNER,
                summary_text,
                disable_web_page_preview=True
            )
            log.info("Summary dashboard created")

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
    if TASK_QUEUE.should_update_summary():
        await update_summary_dashboard(client)


async def force_update_summary(client=None):
    """
    Force update summary dashboard immediately (bypasses throttling).
    Use this when tasks start/complete/cancel.
    """
    await update_summary_dashboard(client)
    TASK_QUEUE.mark_summary_updated()
