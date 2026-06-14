# tests/unit/test_ui_consistency_safety.py

import sys
import os
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Satisfy Pyrogram and other imports
class MockModule(MagicMock):
    @property
    def __path__(self):
        return []

sys.modules['pyrogram'] = MockModule()
sys.modules['pyrogram.client'] = MockModule()
sys.modules['pyrogram.types'] = MockModule()
sys.modules['pyrogram.enums'] = MockModule()
sys.modules['pyrogram.errors'] = MockModule()
sys.modules['pyrogram.filters'] = MockModule()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from colab_leecher.utility.ui_components_unified import UIComponents, SafeMessageEditor, get_safe_message_editor
from colab_leecher.utility.helper import keyboard, status_bar


@pytest.fixture
def anyio_backend():
    return 'asyncio'


def test_ui_components_buttons():
    from pyrogram.types import InlineKeyboardButton
    InlineKeyboardButton.reset_mock()
    
    # 1. Cancel button
    btn_cancel = UIComponents.cancel_button("cancel_data")
    assert btn_cancel is not None
    InlineKeyboardButton.assert_any_call('❌ Cancel', callback_data='cancel_data')
    
    # 2. Confirm button
    btn_confirm = UIComponents.confirm_button("confirm_data")
    assert btn_confirm is not None
    InlineKeyboardButton.assert_any_call('✅ Confirm', callback_data='confirm_data')
    
    # 3. Delete button
    btn_delete = UIComponents.delete_button("file.mp4", "delete_data")
    assert btn_delete is not None
    InlineKeyboardButton.assert_any_call('🗑️ Delete file.mp4', callback_data='delete_data')
    
    # 4. Keep button
    btn_keep = UIComponents.keep_button("file.mp4", "keep_data")
    assert btn_keep is not None
    InlineKeyboardButton.assert_any_call('💾 Keep file.mp4', callback_data='keep_data')


def test_ui_components_error_keyboard():
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    InlineKeyboardMarkup.reset_mock()
    InlineKeyboardButton.reset_mock()
    
    task_ctx = MagicMock()
    task_ctx.task_id = "error_task_123"
    task_ctx.messages.download_name = "LongFileNameThatExceedsLimit.mp4"
    
    kb = UIComponents.error_keyboard(task_ctx)
    assert kb is not None
    
    # Verify standard buttons inside the keyboard
    InlineKeyboardMarkup.assert_called_once()
    buttons = InlineKeyboardMarkup.call_args[0][0]
    assert len(buttons) == 2  # Row 1: Delete + Keep, Row 2: Cancel
    
    calls = InlineKeyboardButton.call_args_list
    assert len(calls) == 3
    # Delete button (first call) - label gets truncated to 15 chars + ...
    assert "Delete LongFileNameTha..." in calls[0][0][0]
    assert "err_action:delete:error_task_123" == calls[0][1]["callback_data"]
    # Keep button (second call)
    assert "Keep LongFileNameTha..." in calls[1][0][0]
    assert "err_action:keep:error_task_123" == calls[1][1]["callback_data"]
    # Cancel button (third call)
    assert "Cancel" in calls[2][0][0]
    assert "err_action:cancel:error_task_123" == calls[2][1]["callback_data"]


@pytest.mark.anyio
async def test_safe_message_editor_text_success():
    msg = MagicMock()
    msg.photo = None
    msg.edit_text = AsyncMock(return_value=msg)
    
    editor = get_safe_message_editor()
    res = await editor.safe_edit(msg, "New Text", reply_markup=None)
    
    assert res == msg
    msg.edit_text.assert_called_once_with(
        text="New Text", reply_markup=None, parse_mode="html", disable_web_page_preview=True
    )


@pytest.mark.anyio
async def test_safe_message_editor_photo_success():
    msg = MagicMock()
    msg.photo = MagicMock()
    msg.edit_caption = AsyncMock(return_value=msg)
    
    editor = get_safe_message_editor()
    res = await editor.safe_edit(msg, "New Caption", reply_markup=None)
    
    assert res == msg
    msg.edit_caption.assert_called_once_with(
        caption="New Caption", reply_markup=None, parse_mode="html"
    )


@pytest.mark.anyio
async def test_safe_message_editor_recovery_text():
    msg = MagicMock()
    msg.photo = None
    msg.edit_text = AsyncMock(side_effect=Exception("Generic Edit Error"))
    msg.delete = AsyncMock()
    msg.chat.id = 78910
    
    mock_bot = MagicMock()
    new_msg = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=new_msg)
    
    with patch("colab_leecher.colab_bot", mock_bot):
        editor = get_safe_message_editor()
        res = await editor.safe_edit(msg, "Recovered text", reply_markup=None)
        
        msg.delete.assert_called_once()
        mock_bot.send_message.assert_called_once_with(
            chat_id=78910,
            text="Recovered text",
            parse_mode="html",
            reply_markup=None
        )
        assert res == new_msg


@pytest.mark.anyio
async def test_safe_message_editor_recovery_photo():
    msg = MagicMock()
    msg.photo = MagicMock()
    msg.photo.file_id = "photo_file_id_123"
    msg.edit_caption = AsyncMock(side_effect=Exception("Caption Edit Error"))
    msg.delete = AsyncMock()
    msg.chat.id = 78910
    
    mock_bot = MagicMock()
    new_msg = MagicMock()
    mock_bot.send_photo = AsyncMock(return_value=new_msg)
    
    with patch("colab_leecher.colab_bot", mock_bot):
        editor = get_safe_message_editor()
        res = await editor.safe_edit(msg, "Recovered photo caption", reply_markup=None)
        
        msg.delete.assert_called_once()
        mock_bot.send_photo.assert_called_once_with(
            chat_id=78910,
            photo="photo_file_id_123",
            caption="Recovered photo caption",
            parse_mode="html",
            reply_markup=None
        )
        assert res == new_msg


@pytest.mark.anyio
async def test_parse_any_size_via_status_bar():
    with patch("colab_leecher.utility.progress_manager.get_progress_manager") as mock_get_pm:
        mock_pm = MagicMock()
        mock_pm.update_progress = AsyncMock()
        mock_get_pm.return_value = mock_pm
        
        # Test Case 1: Decimals & Spacing
        await status_bar(
            down_msg="Downloading", speed=1024, percentage=50.0, eta=10,
            done="3.20 GiB", total_size="10.00 GiB", engine="aria2", task_ctx=None
        )
        mock_pm.update_progress.assert_called_once()
        args, kwargs = mock_pm.update_progress.call_args
        assert kwargs["bytes_done"] == int(3.20 * 1024**3)
        assert kwargs["bytes_total"] == int(10.00 * 1024**3)
        mock_pm.update_progress.reset_mock()
        
        # Test Case 2: No space & mixed case
        await status_bar(
            down_msg="Downloading", speed=1024, percentage=50.0, eta=10,
            done="250mib", total_size="1.5GiB", engine="aria2", task_ctx=None
        )
        args, kwargs = mock_pm.update_progress.call_args
        assert kwargs["bytes_done"] == int(250 * 1024**2)
        assert kwargs["bytes_total"] == int(1.5 * 1024**3)
        mock_pm.update_progress.reset_mock()
        
        # Test Case 3: Mixed units
        await status_bar(
            down_msg="Downloading", speed=1024, percentage=50.0, eta=10,
            done="3GiB200MiB", total_size="4GiB500MiB", engine="aria2", task_ctx=None
        )
        args, kwargs = mock_pm.update_progress.call_args
        assert kwargs["bytes_done"] == int(3 * 1024**3 + 200 * 1024**2)
        assert kwargs["bytes_total"] == int(4 * 1024**3 + 500 * 1024**2)
        mock_pm.update_progress.reset_mock()

        # Test Case 4: Pure digits
        await status_bar(
            down_msg="Downloading", speed=1024, percentage=50.0, eta=10,
            done="52428800", total_size="104857600", engine="aria2", task_ctx=None
        )
        args, kwargs = mock_pm.update_progress.call_args
        assert kwargs["bytes_done"] == 52428800
        assert kwargs["bytes_total"] == 104857600
        mock_pm.update_progress.reset_mock()
