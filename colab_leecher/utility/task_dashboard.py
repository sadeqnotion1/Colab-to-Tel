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

    # Build summary text
    summary_lines = [
        f"📊 **Multi-Task Dashboard**",
        f"",
        f"**Active Tasks: {len(tasks)}**",
        f""
    ]

    for task_id, task_ctx in tasks.items():
        short_id = task_ctx.get_short_id()
        mode_display = f"{task_ctx.mode_type.capitalize()} {task_ctx.mode.capitalize()}"

        # Calculate progress
        if task_ctx.transfer.down_bytes > 0:
            # TODO: Need total size to calculate accurate percentage
            # For now, just show bytes downloaded
            speed = task_ctx.transfer.get_speed()
            elapsed = task_ctx.get_elapsed_time()
            elapsed_str = getTime(elapsed) if elapsed > 0 else "0s"

            status_line = (
                f"🎯 `{short_id}` - {mode_display}\n"
                f"├ Speed: {speed}\n"
                f"├ Elapsed: {elapsed_str}\n"
                f"├ Downloaded: {len(task_ctx.source_urls)} files\n"
                f"╰ Uploaded: {len(task_ctx.transfer.sent_file_names)} files\n"
            )
        else:
            # Task starting or waiting
            status_line = (
                f"🎯 `{short_id}` - {mode_display}\n"
                f"╰ Status: Initializing...\n"
            )

        summary_lines.append(status_line)

    summary_text = "\n".join(summary_lines)

    # Update or create message
    try:
        if TASK_QUEUE.summary_msg:
            # Update existing message
            await TASK_QUEUE.summary_msg.edit_text(summary_text)
            log.debug(f"Summary dashboard updated ({len(tasks)} tasks)")
        else:
            # Create new message and pin it
            TASK_QUEUE.summary_msg = await client.send_message(
                OWNER,
                summary_text
            )
            try:
                await TASK_QUEUE.summary_msg.pin(disable_notification=True)
                log.info("Summary dashboard created and pinned")
            except Exception as pin_err:
                log.warning(f"Failed to pin summary: {pin_err}")

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
