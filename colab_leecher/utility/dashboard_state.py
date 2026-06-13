# colab_leecher/utility/dashboard_state.py
import time
import asyncio
import logging
from typing import Optional
from pyrogram.types import Message
from .task_context import TASK_QUEUE

log = logging.getLogger(__name__)

class DashboardStateManager:
    """
    State manager for the multi-task summary dashboard.
    Coordinates page transitions, handles photo/text mode switching with hysteresis
    and cooldown, and executes message updates atomically to prevent duplicates and API race conditions.
    """
    def __init__(self):
        self._page_lock = asyncio.Lock()
        self._update_lock = asyncio.Lock()
        self._current_mode = 'text'  # Default display mode: 'text' or 'photo'
        self._last_mode_switch = 0.0
        
        # Hysteresis and Cooldown Parameters
        self._mode_switch_cooldown = 5.0  # seconds
        self._photo_caption_limit = 1024
        self._hysteresis_buffer = 50      # characters

    def reset(self):
        self._current_mode = 'text'
        self._last_mode_switch = 0.0

    def get_current_page(self) -> int:
        return TASK_QUEUE.get_dashboard_page()

    async def navigate_to_page(self, new_page: int, client=None):
        """
        Synchronized page navigation.
        Acquires self._page_lock to prevent torn rendering during rapid navigation inputs.
        """
        async with self._page_lock:
            # Check if this page index is still valid (number of tasks may have changed)
            tasks = await TASK_QUEUE.get_all_tasks()
            total_pages = len(tasks) + 1
            if new_page >= total_pages:
                new_page = 0

            # Set the backend page index first
            await TASK_QUEUE.set_dashboard_page(new_page)
            
            # Render/update the dashboard immediately without moving it to the bottom
            from .task_dashboard import force_update_summary
            await force_update_summary(client, move_to_bottom=False)

    def should_use_photo(self, text_length: int) -> bool:
        """
        Determines if the summary text length fits the photo caption limit,
        applying hysteresis to avoid oscillation around the 1024-character threshold.
        """
        if self._current_mode == 'photo':
            # Stay in photo mode unless the text exceeds the hard 1024-character limit
            return text_length <= self._photo_caption_limit
        else:
            # In text mode, only switch back to photo mode if we are comfortably below the limit
            return text_length < (self._photo_caption_limit - self._hysteresis_buffer)

    async def update_display_mode(self, text_length: int) -> str:
        """
        Calculates and updates display mode using cooldown and hysteresis.
        Returns 'photo' or 'text'.
        """
        now = time.monotonic()
        
        # Hard limits override cooldown (if text exceeds 1024, it MUST be 'text')
        if text_length > self._photo_caption_limit:
            new_mode = 'text'
        else:
            new_mode = 'photo' if self.should_use_photo(text_length) else 'text'

        if new_mode != self._current_mode:
            # Check mode switch cooldown, but bypass it if forced to 'text' by hard caption limits
            is_forced_text_switch = (new_mode == 'text' and text_length > self._photo_caption_limit)
            if is_forced_text_switch or now - self._last_mode_switch >= self._mode_switch_cooldown:
                self._current_mode = new_mode
                self._last_mode_switch = now
                log.info(f"DashboardStateManager: Switched mode to {new_mode}")
            else:
                log.debug(f"DashboardStateManager: Mode switch to {new_mode} throttled by cooldown")
        
        return self._current_mode

    async def atomic_message_update(
        self, client, text: str, reply_markup, thumbnail_path: Optional[str], move_to_bottom: bool = False
    ) -> Optional[Message]:
        """
        Performs an atomic update of the Telegram dashboard message.
        Acquires _update_lock to prevent interleaved deletes/sends and duplicates.
        """
        async with self._update_lock:
            # 1. Determine the mode
            mode = await self.update_display_mode(len(text))
            use_photo = (mode == 'photo' and thumbnail_path is not None)

            # 2. Check if we must recreate the message due to mode change or move_to_bottom
            recreate = move_to_bottom
            if TASK_QUEUE.summary_msg:
                is_photo_msg = bool(hasattr(TASK_QUEUE.summary_msg, 'photo') and TASK_QUEUE.summary_msg.photo)
                if is_photo_msg != use_photo:
                    recreate = True

            # 3. Safely delete the old message if recreating
            if recreate and TASK_QUEUE.summary_msg:
                old_msg = TASK_QUEUE.summary_msg
                TASK_QUEUE.summary_msg = None
                try:
                    await old_msg.delete()
                except Exception as e:
                    log.debug(f"DashboardStateManager failed to delete old message: {e}")

            from pyrogram import enums
            from pyrogram.errors import MessageNotModified, FloodWait
            from .. import OWNER

            if not client:
                from .. import colab_bot
                client = colab_bot

            # 4. Attempt to edit the existing message
            if TASK_QUEUE.summary_msg:
                from .ui_components_unified import get_safe_message_editor
                editor = get_safe_message_editor()
                try:
                    TASK_QUEUE.summary_msg = await editor.safe_edit(
                        TASK_QUEUE.summary_msg,
                        text,
                        reply_markup=reply_markup,
                        parse_mode=enums.ParseMode.HTML
                    )
                except MessageNotModified:
                    pass
                except FloodWait as fw:
                    wait_secs = fw.value
                    log.warning(f"FloodWait hit during dashboard edit: suspending updates for {wait_secs}s")
                    TASK_QUEUE._ui_suspended_until = time.monotonic() + wait_secs
                except Exception as edit_err:
                    error_msg = str(edit_err).lower()
                    msg_gone = any(
                        kw in error_msg
                        for kw in ("message to edit not found", "message_id_invalid",
                                   "channel_invalid", "chat not found")
                    )
                    if msg_gone:
                        log.warning(f"Summary message gone on Telegram; clearing reference. Error: {edit_err}")
                        TASK_QUEUE.summary_msg = None
                    else:
                        log.warning(f"Dashboard edit failed: {edit_err}")

            # 5. Send a new message if it was recreated or the edit failed/cleared the reference
            if not TASK_QUEUE.summary_msg:
                try:
                    if use_photo:
                        TASK_QUEUE.summary_msg = await client.send_photo(
                            chat_id=OWNER,
                            photo=thumbnail_path,
                            caption=text,
                            parse_mode=enums.ParseMode.HTML,
                            reply_markup=reply_markup
                        )
                    else:
                        TASK_QUEUE.summary_msg = await client.send_message(
                            chat_id=OWNER,
                            text=text,
                            parse_mode=enums.ParseMode.HTML,
                            disable_web_page_preview=True,
                            reply_markup=reply_markup
                        )
                except FloodWait as fw:
                    wait_secs = fw.value
                    log.warning(f"FloodWait hit during dashboard send: suspending updates for {wait_secs}s")
                    TASK_QUEUE._ui_suspended_until = time.monotonic() + wait_secs
                except Exception as send_err:
                    log.error(f"Failed to send dashboard summary message: {send_err}")

            return TASK_QUEUE.summary_msg

# Global instance
_dashboard_state_instance = DashboardStateManager()

def get_dashboard_state() -> DashboardStateManager:
    return _dashboard_state_instance
