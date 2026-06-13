import asyncio
import logging

log = logging.getLogger(__name__)

class UIComponents:
    """
    Centralized, unified UI components to ensure consistent button styles
    across the entire application.
    """
    BUTTON_STYLES = {
        'cancel': {'text': '❌ Cancel', 'emoji': '❌'},
        'confirm': {'text': '✅ Confirm', 'emoji': '✅'},
        'delete': {'text': '🗑️ Delete', 'emoji': '🗑️'},
        'keep': {'text': '💾 Keep', 'emoji': '💾'}
    }
    
    @classmethod
    def cancel_button(cls, callback_data="cancel"):
        from pyrogram.types import InlineKeyboardButton
        style = cls.BUTTON_STYLES['cancel']
        return InlineKeyboardButton(
            style['text'],
            callback_data=callback_data
        )
    
    @classmethod
    def confirm_button(cls, callback_data="confirm"):
        from pyrogram.types import InlineKeyboardButton
        style = cls.BUTTON_STYLES['confirm']
        return InlineKeyboardButton(
            style['text'],
            callback_data=callback_data
        )

    @classmethod
    def delete_button(cls, label_suffix="", callback_data="delete"):
        from pyrogram.types import InlineKeyboardButton
        style = cls.BUTTON_STYLES['delete']
        text = f"{style['emoji']} Delete {label_suffix}".strip()
        return InlineKeyboardButton(
            text,
            callback_data=callback_data
        )

    @classmethod
    def keep_button(cls, label_suffix="", callback_data="keep"):
        from pyrogram.types import InlineKeyboardButton
        style = cls.BUTTON_STYLES['keep']
        text = f"{style['emoji']} Keep {label_suffix}".strip()
        return InlineKeyboardButton(
            text,
            callback_data=callback_data
        )

    @classmethod
    def error_keyboard(cls, task_ctx, error_id=None):
        """Create standardized error keyboard"""
        from pyrogram.types import InlineKeyboardMarkup
        # Accept either task_ctx (from our managers) or ID
        if hasattr(task_ctx, "task_id"):
            task_id = task_ctx.task_id
            download_name = task_ctx.messages.download_name or "Files"
        else:
            task_id = str(task_ctx)
            download_name = "Files"
            
        short_name = download_name[:15] + "..." if len(download_name) > 15 else download_name
        
        return InlineKeyboardMarkup([
            [
                cls.delete_button(short_name, f"err_action:delete:{task_id}"),
                cls.keep_button(short_name, f"err_action:keep:{task_id}")
            ],
            [
                cls.cancel_button(f"err_action:cancel:{task_id}")
            ]
        ])

async def _edit_status_message_safe(msg, text: str, reply_markup, parse_mode) -> bool:
    """Unified message editor with null safety and error handling."""
    if msg is None:
        log.warning("_edit_status_message_safe: msg is None, skipping edit.")
        return False
        
    is_photo = hasattr(msg, 'photo') and msg.photo is not None
    try:
        if is_photo:
            await msg.edit_caption(caption=text, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            await msg.edit_text(text=text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=True)
        return True
    except Exception as e:
        class_name = e.__class__.__name__
        if class_name == 'MessageNotModified':
            return True
        elif class_name == 'FloodWait':
            raise e
        log.error(f"_edit_status_message_safe: Failed to edit message: {e}")
        return False

class SafeMessageEditor:
    """
    Safely edits messages with null checks, attribute safety,
    and automatic recovery by recreation on failure.
    """
    async def safe_edit(self, msg, text: str, reply_markup=None, parse_mode="html"):
        """Safely edit a message with error handling and fallback recreation on failure."""
        if msg is None:
            return None
            
        try:
            success = await _edit_status_message_safe(msg, text, reply_markup, parse_mode)
            if success:
                return msg
        except Exception as e:
            class_name = e.__class__.__name__
            if class_name == 'MessageNotModified':
                return msg
            elif class_name == 'FloodWait':
                raise e
            log.warning(f"SafeMessageEditor: Edit failed with exception: {e}")
            
        # If edit failed, try to recover by deleting and sending a new message
        log.warning(f"SafeMessageEditor: Edit failed for message {msg.id if hasattr(msg, 'id') else 'unknown'}. Attempting recovery by recreation...")
        try:
            await msg.delete()
        except Exception as del_err:
            log.debug(f"SafeMessageEditor: Could not delete old message: {del_err}")
            
        try:
            from .. import colab_bot
            chat_id = msg.chat.id
            
            is_photo = hasattr(msg, 'photo') and msg.photo is not None
            if is_photo:
                try:
                    photo_id = msg.photo.file_id
                    new_msg = await colab_bot.send_photo(
                        chat_id=chat_id,
                        photo=photo_id,
                        caption=text,
                        parse_mode=parse_mode,
                        reply_markup=reply_markup
                    )
                    log.info(f"SafeMessageEditor: Recreated photo message successfully. New message ID: {new_msg.id}")
                    return new_msg
                except Exception as photo_err:
                    log.warning(f"SafeMessageEditor: Recreating photo failed, falling back to text: {photo_err}")
            
            new_msg = await colab_bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
            log.info(f"SafeMessageEditor: Recreated message successfully. New message ID: {new_msg.id}")
            return new_msg
        except Exception as send_err:
            log.error(f"SafeMessageEditor: Message recovery/recreation failed: {send_err}")
            return None

_safe_message_editor = SafeMessageEditor()

def get_safe_message_editor() -> SafeMessageEditor:
    return _safe_message_editor
