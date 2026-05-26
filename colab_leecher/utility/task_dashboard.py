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
from .. import OWNER, colab_bot
from .task_context import TASK_QUEUE
from .helper import getTime
from .variables import Paths, BOT
from .ui_components import SizeFormatter, ProgressBar, TimeFormatter
from .ui_copy import build_cancel_task_button_label, summarize_task_name

BOT_DEBUG = os.getenv("BOT_DEBUG", "0") == "1"

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
            summary_text += "<b>┌── Active Tasks Summary ──</b>\n"
            for idx, task_ctx in enumerate(tasks_list, 1):
                short_id = task_ctx.get_short_id()
                raw_name = task_ctx.messages.download_name if task_ctx.messages else None
                filename = summarize_task_name(raw_name, None, max_length=30)
                
                percentage = 0.0
                u_bytes = sum(task_ctx.transfer.up_bytes) if isinstance(task_ctx.transfer.up_bytes, list) else task_ctx.transfer.up_bytes
                d_bytes = sum(task_ctx.transfer.down_bytes) if isinstance(task_ctx.transfer.down_bytes, list) else task_ctx.transfer.down_bytes

                if u_bytes > 0 and task_ctx.transfer.total_size > 0:
                    percentage = (u_bytes / task_ctx.transfer.total_size) * 100
                elif d_bytes > 0 and task_ctx.transfer.total_size > 0:
                    percentage = task_ctx.transfer.get_percentage()
                
                bar = ProgressBar.generate(percentage, 8, "ascii")
                line_icon = "⬆️" if u_bytes > 0 else "⬇️"
                
                summary_text += f"<b>├ {idx}. {line_icon} {escape(filename)}</b>\n"
                summary_text += f"<b>│</b>  <code>[{bar}] {percentage:.1f}%</code>\n"
            
            summary_text += "<b>└── End of List ──</b>\n\n"
            summary_text += f"<i>Use the buttons below to view details for each task.</i>"
            
        else:
            # --- PAGE 1+: SPECIFIC TASK DETAIL VIEW ---
            task_idx = current_page - 1
            task_ctx = tasks_list[task_idx]
            short_id = task_ctx.get_short_id()
            
            source_url = task_ctx.source_urls[0] if task_ctx.source_urls else None
            raw_name = task_ctx.messages.download_name if task_ctx.messages else None
            filename = summarize_task_name(raw_name, source_url, max_length=42)
            
            summary_text += f"<b>Task: {escape(filename)}</b>\n"
            summary_text += f"<code>ID: {escape(short_id)}</code>\n\n"

            u_bytes = sum(task_ctx.transfer.up_bytes) if isinstance(task_ctx.transfer.up_bytes, list) else task_ctx.transfer.up_bytes
            d_bytes = sum(task_ctx.transfer.down_bytes) if isinstance(task_ctx.transfer.down_bytes, list) else task_ctx.transfer.down_bytes

            if u_bytes > 0:
                speed = SizeFormatter.format_speed(task_ctx.transfer.get_speed())
                uploaded = _format_bytes(task_ctx.transfer.up_bytes)
                percentage = 0.0
                if task_ctx.transfer.total_size > 0:
                    percentage = min(100.0, (u_bytes / task_ctx.transfer.total_size) * 100)
                    total = _format_bytes(task_ctx.transfer.total_size)
                else:
                    total = "Unknown"
                
                bar = "█" * int(percentage/5) + "▒" * (20 - int(percentage/5))
                summary_text += (
                    f"<b>┌「{bar}」 » {percentage:.1f}%</b>\n"
                    f"<b>├⚡️ Speed »</b> <code>{escape(speed)}</code>\n"
                    f"<b>├⚙️ Status »</b> <code>Uploading ⬆️</code>\n"
                    f"<b>├✅ Done »</b> <code>{uploaded}</code>\n"
                    f"<b>└📦 Total »</b> <code>{total}</code>"
                )

            elif d_bytes > 0:
                is_proc = False
                status_label = "Downloading ⬇️"
                if task_ctx.messages and task_ctx.messages.status_head:
                    sh = task_ctx.messages.status_head.lower()
                    if any(k in sh for k in ['archiving', 'zipping', 'compressing']):
                        status_label = "Archiving 🗜️"
                        is_proc = True
                    elif any(k in sh for k in ['extracting', 'unzipping', 'unpacking']):
                        status_label = "Extracting 📦"
                        is_proc = True
                
                if is_proc:
                    percentage = 0.0
                    if task_ctx.messages.total_files > 0:
                        percentage = (task_ctx.messages.files_processed / task_ctx.messages.total_files) * 100
                    
                    bar = "█" * int(percentage/5) + "▒" * (20 - int(percentage/5))
                    elapsed = getTime(task_ctx.get_elapsed_time())
                    summary_text += (
                        f"<b>┌「{bar}」 » {percentage:.1f}%</b>\n"
                        f"<b>├⚙️ Status »</b> <code>{status_label}</code>\n"
                        f"<b>├⏱️ Elapsed »</b> <code>{elapsed}</code>\n"
                        f"<b>└📦 Files »</b> <code>{task_ctx.messages.files_processed}/{task_ctx.messages.total_files}</code>"
                    )
                else:
                    speed = SizeFormatter.format_speed(task_ctx.transfer.get_speed())
                    percentage = task_ctx.transfer.get_percentage()
                    downloaded = _format_bytes(task_ctx.transfer.down_bytes)
                    total = _format_bytes(task_ctx.transfer.total_size) if task_ctx.transfer.total_size > 0 else "Unknown"
                    eta = task_ctx.transfer.get_eta()
                    eta_str = TimeFormatter.format_eta(eta) if eta > 0 else "?"
                    
                    bar = "█" * int(percentage/5) + "▒" * (20 - int(percentage/5))
                    summary_text += (
                        f"<b>┌「{bar}」 » {percentage:.1f}%</b>\n"
                        f"<b>├⚡️ Speed »</b> <code>{escape(speed)}</code>\n"
                        f"<b>├⚙️ Status »</b> <code>{status_label}</code>\n"
                        f"<b>├⏳ ETA »</b> <code>{eta_str}</code>\n"
                        f"<b>├✅ Done »</b> <code>{downloaded}</code>\n"
                        f"<b>└📦 Total »</b> <code>{total}</code>"
                    )
            else:
                summary_text += "<b>Status:</b> <code>Initializing... ⏳</code>"

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
                buttons.append([InlineKeyboardButton("❌ Cancel This Task", callback_data=f"cancel:{short_id}")])
        elif tasks_list:
            buttons.append([InlineKeyboardButton("❌ Cancel All Tasks", callback_data="cancel_all_tasks")])

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

        try:
            if move_to_bottom and TASK_QUEUE.summary_msg:
                try:
                    await TASK_QUEUE.summary_msg.delete()
                except Exception:
                    pass
                finally:
                    TASK_QUEUE.summary_msg = None

            if TASK_QUEUE.summary_msg:
                try:
                    if hasattr(TASK_QUEUE.summary_msg, 'photo') and TASK_QUEUE.summary_msg.photo:
                        await TASK_QUEUE.summary_msg.edit_caption(
                            summary_text, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard
                        )
                    else:
                        await TASK_QUEUE.summary_msg.edit_text(
                            summary_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard
                        )

                except MessageNotModified:
                    # Telegram confirmed the content is byte-for-byte identical.
                    # Cache the values so the pre-API equality check fires next time
                    # and avoid counting this as a real error.
                    log.debug("Dashboard edit skipped: content not modified (Telegram confirmed)")
                    TASK_QUEUE.last_summary_text = summary_text
                    TASK_QUEUE.last_summary_keyboard_signature = keyboard_signature
                    TASK_QUEUE.mark_summary_updated()
                    return TASK_QUEUE.summary_msg

                except FloodWait as fw:
                    # Telegram is rate-limiting us.  Record the suspension window
                    # on the queue so *all* callers (not just this coroutine) will
                    # back off for the required duration.  Then sleep non-blockingly
                    # so we don't block the event loop or crash the caller.
                    wait_secs = fw.value
                    log.warning(
                        "FloodWait hit while updating summary dashboard — "
                        "suspending UI edits for %ds.",
                        wait_secs,
                    )
                    TASK_QUEUE._ui_suspended_until = time.monotonic() + wait_secs
                    # Release the lock *before* sleeping so other coroutines are
                    # not blocked for the full flood-wait duration.  We do this by
                    # returning immediately; the suspension guard at the top of
                    # this function will protect us on the next invocation.
                    await asyncio.sleep(wait_secs)
                    TASK_QUEUE._ui_suspended_until = 0.0  # clear after sleep completes
                    return TASK_QUEUE.summary_msg

                except Exception as edit_err:
                    error_msg = str(edit_err).lower()
                    # Some errors mean the message no longer exists on Telegram's
                    # side (deleted externally, migrated chat, etc.).  Only clear
                    # summary_msg in that case so we recreate it on the next call.
                    msg_gone = any(
                        kw in error_msg
                        for kw in ("message to edit not found", "message_id_invalid",
                                   "channel_invalid", "chat not found")
                    )
                    if msg_gone:
                        log.warning("Summary message appears deleted; will recreate. Error: %s", edit_err)
                        TASK_QUEUE.summary_msg = None
                    else:
                        log.warning("Edit failed (non-critical); keeping existing summary_msg. Error: %s", edit_err)
                    return TASK_QUEUE.summary_msg

            if not TASK_QUEUE.summary_msg:
                if thumbnail_path and os.path.exists(thumbnail_path):
                    TASK_QUEUE.summary_msg = await client.send_photo(OWNER, photo=thumbnail_path, caption=summary_text, parse_mode=enums.ParseMode.HTML, reply_markup=keyboard)
                else:
                    TASK_QUEUE.summary_msg = await client.send_message(OWNER, text=summary_text, parse_mode=enums.ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard)

            TASK_QUEUE.last_summary_text = summary_text
            TASK_QUEUE.last_summary_keyboard_signature = keyboard_signature
            TASK_QUEUE.mark_summary_updated()

            return TASK_QUEUE.summary_msg

        except FloodWait as fw:
            wait_secs = fw.value
            log.warning(
                "FloodWait hit while sending new summary dashboard — "
                "suspending UI edits for %ds.",
                wait_secs,
            )
            TASK_QUEUE._ui_suspended_until = time.monotonic() + wait_secs
            await asyncio.sleep(wait_secs)
            TASK_QUEUE._ui_suspended_until = 0.0
            return TASK_QUEUE.summary_msg

        except Exception as e:
            log.error("Failed to update summary dashboard: %s", e)
            # Do NOT clear summary_msg here — only message-gone errors (handled
            # in the inner except above) warrant that.  Clearing it on a transient
            # network hiccup would cause an unwanted re-send on the next tick.
            return None


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
