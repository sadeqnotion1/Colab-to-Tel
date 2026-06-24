# /content/Telegram-Leecher/colab_leecher/utility/task_dashboard.py

"""
Multi-Task Summary Dashboard

Displays real-time overview of all active download/upload tasks.
Updates periodically to show progress across parallel tasks.
"""

import logging
import os
import time
import asyncio
from html import escape
from typing import Optional
from pyrogram import enums
from pyrogram.errors import MessageNotModified, FloodWait
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from .. import colab_bot
from .task_context import TASK_QUEUE
from .helper import getTime
from .variables import Paths, BOT
from .ui_components import SizeFormatter, ProgressBar, TimeFormatter
from .ui_copy import build_cancel_task_button_label, summarize_task_name
from .enhanced_status import StatusDisplay
from .formatting import format_bytes, format_speed

BOT_DEBUG = os.getenv("BOT_DEBUG", "0") == "1"
BAR_STYLE = os.environ.get("BAR_STYLE", "gradient")

log = logging.getLogger(__name__)




def _format_bytes(x) -> str:
    """Thin wrapper so existing callers inside this file keep working."""
    if isinstance(x, list):
        x = sum(x)
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
        force: bool = False,
        move_to_bottom: bool = False,
        page: Optional[int] = None) -> Optional[Message]:
    """
    Update or create the summary dashboard showing all active tasks (thread-safe).

    Args:
        client: Pyrogram client instance
        force: If True, bypass throttling and update immediately
        move_to_bottom: If True, delete old message and send new one to keep it at bottom
        page: Stateless indicator of which page to render (0=Global, 1+=Tasks). 
              If None, it infers the page from the existing message.

    Returns:
        Updated/created summary message, or None if no tasks active
    """
    from .. import OWNER

    if not client:
        client = colab_bot

    if not force and not move_to_bottom and not TASK_QUEUE.should_update_summary():
        return TASK_QUEUE.summary_msg

    async with TASK_QUEUE._summary_lock:
        # Re-check throttling inside lock
        if not force and not move_to_bottom and not TASK_QUEUE.should_update_summary():
            return TASK_QUEUE.summary_msg

        if force and not move_to_bottom:
            time_since_last = time.time() - TASK_QUEUE.last_summary_update
            if time_since_last < TASK_QUEUE.min_forced_update_interval:
                return TASK_QUEUE.summary_msg

        # --- FloodWait suspension guard ---
        # If a previous edit triggered a FloodWait we store the resume time on the
        # queue.  Skip all API writes until that window has expired.
        if time.monotonic() < TASK_QUEUE._ui_suspended_until:
            remaining = TASK_QUEUE._ui_suspended_until - time.monotonic()
            log.debug("UI updates suspended for %.1fs (FloodWait active)", remaining)
            return TASK_QUEUE.summary_msg

        tasks = await TASK_QUEUE.get_all_tasks()
        
        # Use the backend-owned page index; the `page` argument is an explicit
        # override supplied by the callback handler immediately after it calls
        # TASK_QUEUE.set_dashboard_page(), so we trust it when present.
        current_page = page if page is not None else TASK_QUEUE.get_dashboard_page()

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
            return None

        # --- Build summary text ---
        header_icon = "🛠️" if current_page == 0 else "📊"
        header_title = "Global Manager" if current_page == 0 else "Task Details"
        
        total_speed_str = ""
        try:
            speed_values = []
            for t in tasks.values():
                raw = getattr(t.transfer, "last_speed_bytes", None)
                if raw and isinstance(raw, (int, float)) and raw > 0:
                    speed_values.append(raw)
            if speed_values:
                total_speed_str = f"  ⚡️ <b>{SizeFormatter.format_speed(sum(speed_values))}</b>"
        except Exception:
            pass

        header = f"<b>{header_icon} {header_title}</b> \u2022 <b>{len(tasks)}</b> running{total_speed_str}\n\n"
        summary_text = header
        
        tasks_list = list(tasks.values())
        total_pages = len(tasks_list) + 1 
        
        # Fallback if a task finished and the requested page is now out of bounds
        if current_page >= total_pages:
            current_page = 0

        if current_page == 0:
            # --- PAGE 0: GLOBAL MANAGER VIEW ---
            summary_text += "<pre>"
            summary_text += "┌─── Active Tasks Summary ───┐\n"
            for idx, task_ctx in enumerate(tasks_list, 1):
                raw_name = task_ctx.messages.download_name if task_ctx.messages else None
                filename = summarize_task_name(raw_name, None, max_length=24)
                
                percentage = 0.0
                u_bytes = sum(task_ctx.transfer.up_bytes) if isinstance(task_ctx.transfer.up_bytes, list) else task_ctx.transfer.up_bytes
                d_bytes = sum(task_ctx.transfer.down_bytes) if isinstance(task_ctx.transfer.down_bytes, list) else task_ctx.transfer.down_bytes

                ts = task_ctx.transfer.total_size
                base = u_bytes if u_bytes > 0 else d_bytes
                if ts > 0 and base >= 0:
                    percentage = min(100.0, (base / ts) * 100)
                else:
                    percentage = 0.0
                
                bar = _progress_bar(percentage, 10)
                line_icon = "UP" if u_bytes > 0 else "DL"
                
                summary_text += f" {idx}. {line_icon} : {escape(filename)}\n"
                summary_text += f"      {bar} {percentage:.1f}%\n"
                if idx < len(tasks_list):
                    summary_text += "\n"
            
            summary_text += "└────────────────────────────┘"
            summary_text += "</pre>\n\n"
            summary_text += f"<i>Use the buttons below to view details for each task.</i>"
            
        else:
            # --- PAGE 1+: SPECIFIC TASK DETAIL VIEW ---
            task_idx = current_page - 1
            task_ctx = tasks_list[task_idx]
            short_id = task_ctx.get_short_id()
            
            source_url = task_ctx.source_urls[0] if task_ctx.source_urls else None
            raw_name = task_ctx.messages.download_name if task_ctx.messages else None
            filename = summarize_task_name(raw_name, source_url, max_length=42)
            
            u_bytes = sum(task_ctx.transfer.up_bytes) if isinstance(task_ctx.transfer.up_bytes, list) else task_ctx.transfer.up_bytes
            d_bytes = sum(task_ctx.transfer.down_bytes) if isinstance(task_ctx.transfer.down_bytes, list) else task_ctx.transfer.down_bytes

            is_proc = False
            current_action = getattr(task_ctx.messages, "current_action", "").lower()
            if current_action in ["archiving", "extracting", "splitting"]:
                is_proc = True

            if u_bytes > 0:
                emoji = "📤"
                verb = "UPLOADING TO TELEGRAM"
                speed_bps = task_ctx.transfer.get_speed()
                dot = StatusDisplay.speed_emoji(speed_bps)
                
                ts = task_ctx.transfer.total_size
                if ts <= 0 or ts < u_bytes:
                    cfs = getattr(task_ctx.transfer, "current_file_size", 0) or 0
                    if cfs > 0:
                        percentage = min(100.0, (u_bytes / cfs) * 100)
                        total_str = format_bytes(cfs)
                    else:
                        percentage = 0.0
                        total_str = "Unknown"
                else:
                    total_str = format_bytes(ts)
                    percentage = min(100.0, (u_bytes / ts) * 100)
                
                bar = ProgressBar.generate(percentage, length=16, style=BAR_STYLE)
                eta_seconds = task_ctx.transfer.get_eta()
                eta_str = StatusDisplay.smart_eta(eta_seconds, u_bytes)
                
                summary_text = header + (
                    "<pre>"
                    f"╭─── {emoji} {verb} ───╮\n"
                    f" 📄 {escape(filename)}\n"
                    f" 🆔 {escape(short_id)}\n"
                    f" {bar} {percentage:.1f}%\n"
                    f" {dot} Speed : {escape(format_speed(speed_bps))}\n"
                    f" 📦 Done  : {format_bytes(u_bytes)} / {total_str}\n"
                    f" ⏳ ETA   : {eta_str}\n"
                    "╰────────────────────────────────╯"
                    "</pre>"
                )

            elif d_bytes > 0:
                if is_proc:
                    if current_action == "archiving":
                        emoji = "🗜️"
                        verb = "ARCHIVING FILE"
                        status_label = "Archiving 🗜️"
                    elif current_action == "extracting":
                        emoji = "📦"
                        verb = "EXTRACTING FILE"
                        status_label = "Extracting 📦"
                    else: # splitting
                        emoji = "✂️"
                        verb = "SPLITTING FILE"
                        status_label = "Splitting ✂️"
                    
                    percentage = task_ctx.transfer.get_percentage()
                    if percentage == 0.0 and task_ctx.messages.total_files > 0:
                        percentage = (task_ctx.messages.files_processed / task_ctx.messages.total_files) * 100
                    
                    bar = ProgressBar.generate(percentage, length=16, style=BAR_STYLE)
                    elapsed = getTime(task_ctx.get_elapsed_time())
                    
                    summary_text = header + (
                        "<pre>"
                        f"╭─── {emoji} {verb} ───╮\n"
                        f" 📄 {escape(filename)}\n"
                        f" 🆔 {escape(short_id)}\n"
                        f" {bar} {percentage:.1f}%\n"
                        f" ⚙️ Status : {status_label}\n"
                        f" 📁 Files  : {task_ctx.messages.files_processed} / {task_ctx.messages.total_files}\n"
                        f" ⏱️ Elapsed: {elapsed}\n"
                        "╰────────────────────────────────╯"
                        "</pre>"
                    )
                else:
                    emoji = "📥"
                    verb = "DOWNLOADING FILE"
                    speed_bps = task_ctx.transfer.get_speed()
                    dot = StatusDisplay.speed_emoji(speed_bps)
                    
                    ts = task_ctx.transfer.total_size
                    if ts <= 0 or ts < d_bytes:
                        total_str = "Unknown"
                        percentage = task_ctx.transfer.get_percentage()
                    else:
                        total_str = format_bytes(ts)
                        percentage = task_ctx.transfer.get_percentage()
                    
                    bar = ProgressBar.generate(percentage, length=16, style=BAR_STYLE)
                    eta_seconds = task_ctx.transfer.get_eta()
                    eta_str = StatusDisplay.smart_eta(eta_seconds, d_bytes)
                    
                    summary_text = header + (
                        "<pre>"
                        f"╭─── {emoji} {verb} ───╮\n"
                        f" 📄 {escape(filename)}\n"
                        f" 🆔 {escape(short_id)}\n"
                        f" {bar} {percentage:.1f}%\n"
                        f" {dot} Speed : {escape(format_speed(speed_bps))}\n"
                        f" 📦 Done  : {format_bytes(d_bytes)} / {total_str}\n"
                        f" ⏳ ETA   : {eta_str}\n"
                        "╰────────────────────────────────╯"
                        "</pre>"
                    )
            else:
                emoji = "⏳"
                verb = "INITIALIZING"
                bar = ProgressBar.generate(0.0, length=16, style=BAR_STYLE)
                summary_text = header + (
                    "<pre>"
                    f"╭─── {emoji} {verb} ───╮\n"
                    f" 📄 {escape(filename)}\n"
                    f" 🆔 {escape(short_id)}\n"
                    f" {bar} 0.0%\n"
                    f" ⚙️ Status : Initializing...\n"
                    f" 📦 Done  : N/A\n"
                    f" ⏳ ETA   : Calculating...\n"
                    "╰────────────────────────────────╯"
                    "</pre>"
                )

        # --- NAVIGATION BUTTONS ---
        nav_buttons = []
        if total_pages > 1:
            prev_page = (current_page - 1) % total_pages
            next_page = (current_page + 1) % total_pages
            nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"dash_page:{prev_page}"))
            # Refresh re-renders the current backend page; no page number needed in the payload.
            nav_buttons.append(InlineKeyboardButton(f"Page {current_page + 1}/{total_pages}", callback_data="dash_refresh"))
            nav_buttons.append(InlineKeyboardButton("Next ➡️", callback_data=f"dash_page:{next_page}"))

        buttons = []
        if nav_buttons:
            buttons.append(nav_buttons)
            
        if current_page > 0:
            task_idx = current_page - 1
            if task_idx < len(tasks_list):
                task_ctx = tasks_list[task_idx]
                short_id = task_ctx.get_short_id()
                buttons.append([InlineKeyboardButton("🔴 Cancel This Task", callback_data=f"cancel:{short_id}")])
        elif tasks_list:
            buttons.append([InlineKeyboardButton("🚫 Cancel All Tasks", callback_data="cancel_all_tasks")])

        keyboard = InlineKeyboardMarkup(buttons) if buttons else None
        keyboard_signature = _keyboard_signature(keyboard)

        # Skip API hit if content is structurally identical
        if TASK_QUEUE.summary_msg and summary_text == TASK_QUEUE.last_summary_text and keyboard_signature == TASK_QUEUE.last_summary_keyboard_signature:
            TASK_QUEUE.mark_summary_updated()
            return TASK_QUEUE.summary_msg

        thumbnail_path = None
        if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
            thumbnail_path = Paths.THMB_PATH
        if not thumbnail_path:
            first_task = next(iter(tasks.values()), None) if tasks else None
            if first_task and hasattr(first_task, 'hero_image') and first_task.hero_image:
                if os.path.exists(first_task.hero_image):
                    thumbnail_path = first_task.hero_image
        if not thumbnail_path and os.path.exists(Paths.DEFAULT_HERO):
            thumbnail_path = Paths.DEFAULT_HERO

        from .dashboard_state import get_dashboard_state
        ds = get_dashboard_state()
        await ds.atomic_message_update(
            client=client,
            text=summary_text,
            reply_markup=keyboard,
            thumbnail_path=thumbnail_path if thumbnail_path and os.path.exists(thumbnail_path) else None,
            move_to_bottom=move_to_bottom
        )

        TASK_QUEUE.last_summary_text = summary_text
        TASK_QUEUE.last_summary_keyboard_signature = keyboard_signature
        TASK_QUEUE.mark_summary_updated()

        return TASK_QUEUE.summary_msg


async def try_update_summary(client=None):
    """
    Update summary dashboard only if throttle interval has passed.

    The page to render is read from ``TASK_QUEUE.get_dashboard_page()``;
    callers that need a page change must call
    ``await TASK_QUEUE.set_dashboard_page(n)`` before invoking this helper.
    """
    if TASK_QUEUE._summary_lock.locked():
        return
    await update_summary_dashboard(client, force=False)


async def force_update_summary(client=None, move_to_bottom: bool = True):
    """
    Force update summary dashboard with tracked debounce logic.

    Ensures bursts of task updates (e.g., bulk cancellations or fast downloads)
    don't slam the Telegram API with redundant move_to_bottom API calls.

    Debounce state is owned by ``TASK_QUEUE`` so it survives across imports and
    is never split between module-level variables and the queue instance.

    The page to render is read from ``TASK_QUEUE.get_dashboard_page()``;
    callers that need a page change must call
    ``await TASK_QUEUE.set_dashboard_page(n)`` before invoking this helper.
    """
    now = time.time()
    time_since_last = now - TASK_QUEUE._last_force_time

    # If it's been more than 2 seconds since the last forced update, push immediately.
    if time_since_last >= 2.0:
        TASK_QUEUE._last_force_time = now

        # A pending delayed update is now superseded — cancel it cleanly.
        await TASK_QUEUE.cancel_scheduled_update()

        await update_summary_dashboard(client, force=True, move_to_bottom=move_to_bottom)

    else:
        # Debouncing: if a delayed update is already in flight, let it run.
        if (
            TASK_QUEUE._scheduled_update_task is not None
            and not TASK_QUEUE._scheduled_update_task.done()
        ):
            return

        async def delayed_update():
            try:
                # Wait for the remainder of the throttle window to let the burst settle.
                await asyncio.sleep(2.0 - time_since_last)
                TASK_QUEUE._last_force_time = time.time()
                await update_summary_dashboard(
                    client, force=True, move_to_bottom=move_to_bottom
                )
            except asyncio.CancelledError:
                pass  # Superseded by a new immediate update — exit cleanly.
            except Exception as exc:
                log.error(f"Debounced background update failed: {exc}")

        task = TASK_QUEUE.create_background_task(
            delayed_update(),
            "debounced_dashboard_update",
        )
        TASK_QUEUE._scheduled_update_task = task
        # Auto-clear the reference once the task finishes naturally so the
        # field never holds a stale done-task.
        task.add_done_callback(
            lambda t: setattr(TASK_QUEUE, "_scheduled_update_task", None)
            if TASK_QUEUE._scheduled_update_task is t else None
        )

# Subscribe to ProgressManager events
try:
    from .progress_manager import get_progress_manager
    get_progress_manager().subscribe(try_update_summary)
except Exception as e:
    log.warning(f"Failed to subscribe dashboard to ProgressManager: {e}")

