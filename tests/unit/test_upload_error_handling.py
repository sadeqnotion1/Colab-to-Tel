# tests/unit/test_upload_error_handling.py

import sys
import os
import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

# Create a mock module structure to satisfy imports
class MockModule(MagicMock):
    @property
    def __path__(self):
        return []

sys.modules['pyrogram'] = MockModule()
sys.modules['pyrogram.client'] = MockModule()
sys.modules['pyrogram.types'] = MockModule()
sys.modules['pyrogram.enums'] = MockModule()
sys.modules['pyrogram.errors'] = MockModule()

sys.modules['curl_cffi'] = MockModule()
sys.modules['curl_cffi.requests'] = MockModule()
sys.modules['mega'] = MockModule()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from colab_leecher.utility.upload_error_manager import get_upload_error_manager, cleanup_stuck_errors
from colab_leecher.utility.timeout_manager import get_timeout_manager
from colab_leecher.utility.task_context import TASK_QUEUE, TaskContext
from colab_leecher.utility.ui_components import MessageTemplate

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture(autouse=True)
def reset_queues():
    TASK_QUEUE.active_tasks.clear()
    TASK_QUEUE.running_tasks.clear()
    get_upload_error_manager()._pending_errors.clear()
    yield
    TASK_QUEUE.active_tasks.clear()
    TASK_QUEUE.running_tasks.clear()
    get_upload_error_manager()._pending_errors.clear()

@pytest.mark.anyio
async def test_timeout_manager():
    tm = get_timeout_manager()
    
    async def sample_coro():
        await asyncio.sleep(0.01)
        return "success"
        
    res = await tm.wait_with_timeout(sample_coro(), 'cleanup')
    assert res == "success"
    
    async def slow_coro():
        await asyncio.sleep(1.0)
        
    # Set the decision timeout very low temporarily to trigger a timeout
    tm._timeouts['decision'] = 0.01
    with pytest.raises(asyncio.TimeoutError):
        await tm.wait_with_timeout(slow_coro(), 'decision')
    # Restore standard timeout
    tm._timeouts['decision'] = 300

@pytest.mark.anyio
async def test_ui_keyboard_with_context():
    task_ctx = MagicMock(spec=TaskContext)
    task_ctx.task_id = "test_task_123"
    task_ctx.messages = MagicMock()
    task_ctx.messages.download_name = "Avatar_Movie_2009.mp4"
    
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    InlineKeyboardMarkup.reset_mock()
    InlineKeyboardButton.reset_mock()
    
    kb = MessageTemplate.get_upload_error_keyboard(task_ctx)
    assert kb is not None
    
    # Verify the keyboard matches task context via mock calls
    InlineKeyboardMarkup.assert_called_once()
    buttons = InlineKeyboardMarkup.call_args[0][0]
    assert len(buttons) == 2
    
    calls = InlineKeyboardButton.call_args_list
    assert len(calls) == 3
    assert "Delete Avatar_Movie_20..." in calls[0][0][0]
    assert "err_action:delete:test_task_123" == calls[0][1]["callback_data"]
    assert "Keep Avatar_Movie_20..." in calls[1][0][0]
    assert "err_action:keep:test_task_123" == calls[1][1]["callback_data"]
    assert "Cancel" in calls[2][0][0]
    assert "err_action:cancel:test_task_123" == calls[2][1]["callback_data"]

@pytest.mark.anyio
async def test_upload_error_manager_keep_files():
    uem = get_upload_error_manager()
    
    task_ctx = MagicMock(spec=TaskContext)
    task_ctx.task_id = "task_keep"
    task_ctx.chat_id = 12345
    task_ctx.get_short_id.return_value = "task_kee"
    task_ctx.messages = MagicMock()
    task_ctx.messages.download_name = "keep_this.mp4"
    task_ctx.user_decision_event = asyncio.Event()
    task_ctx.keep_files_decision = True
    task_ctx.is_aborted = False
    
    TASK_QUEUE.running_tasks.add("task_keep")
    
    mock_bot = AsyncMock()
    with patch('colab_leecher.colab_bot', mock_bot), \
         patch('colab_leecher.utility.task_context.cleanup_task_artifacts') as mock_cleanup:
         
        # Simulate user setting decision event immediately
        task_ctx.user_decision_event.set()
        
        with pytest.raises(Exception) as exc_info:
            await uem.handle_upload_error(task_ctx, "Simulated upload error")
            
        assert str(exc_info.value) == "ABORTED"
        assert task_ctx.is_aborted is True
        mock_cleanup.assert_not_called()
        mock_bot.send_message.assert_called_once()
        # Verify worker slot was released (not in running_tasks initially when waiting, then re-acquired)
        assert "task_keep" in TASK_QUEUE.running_tasks

@pytest.mark.anyio
async def test_upload_error_manager_delete_files():
    uem = get_upload_error_manager()
    
    task_ctx = MagicMock(spec=TaskContext)
    task_ctx.task_id = "task_delete"
    task_ctx.chat_id = 12345
    task_ctx.get_short_id.return_value = "task_del"
    task_ctx.messages = MagicMock()
    task_ctx.messages.download_name = "delete_this.mp4"
    task_ctx.user_decision_event = asyncio.Event()
    task_ctx.keep_files_decision = False
    
    TASK_QUEUE.running_tasks.add("task_delete")
    
    mock_bot = AsyncMock()
    with patch('colab_leecher.colab_bot', mock_bot), \
         patch('colab_leecher.utility.task_context.cleanup_task_artifacts') as mock_cleanup:
         
        task_ctx.user_decision_event.set()
        
        with pytest.raises(Exception) as exc_info:
            await uem.handle_upload_error(task_ctx, "Simulated upload error")
            
        assert "Upload/split failed" in str(exc_info.value)
        mock_cleanup.assert_called_once_with(task_ctx)

@pytest.mark.anyio
async def test_upload_error_manager_timeout():
    uem = get_upload_error_manager()
    tm = get_timeout_manager()
    
    task_ctx = MagicMock(spec=TaskContext)
    task_ctx.task_id = "task_timeout"
    task_ctx.chat_id = 12345
    task_ctx.get_short_id.return_value = "task_tim"
    task_ctx.messages = MagicMock()
    task_ctx.messages.download_name = "timeout_this.mp4"
    task_ctx.user_decision_event = asyncio.Event()
    task_ctx.keep_files_decision = None
    
    TASK_QUEUE.running_tasks.add("task_timeout")
    
    # Temporarily set timeout to a very small value
    tm._timeouts['decision'] = 0.001
    
    mock_bot = AsyncMock()
    with patch('colab_leecher.colab_bot', mock_bot), \
         patch('colab_leecher.utility.task_context.cleanup_task_artifacts') as mock_cleanup:
         
        # We do NOT set user_decision_event to simulate a timeout
        with pytest.raises(Exception) as exc_info:
            await uem.handle_upload_error(task_ctx, "Simulated upload error")
            
        assert "timed out waiting for user decision" in str(exc_info.value)
        assert task_ctx.keep_files_decision is False
        mock_cleanup.assert_called_once_with(task_ctx)
        
    tm._timeouts['decision'] = 300

@pytest.mark.anyio
async def test_cleanup_stuck_errors_loop():
    uem = get_upload_error_manager()
    
    task_ctx = MagicMock(spec=TaskContext)
    task_ctx.task_id = "stuck_task"
    task_ctx.get_short_id.return_value = "stuck_ts"
    task_ctx.user_decision_event = asyncio.Event()
    task_ctx.keep_files_decision = None
    
    import time
    uem._pending_errors["stuck_task"] = {
        'timestamp': time.monotonic() - 700.0,  # stuck for > 10 minutes
        'task_ctx': task_ctx,
        'error': "Some error"
    }
    
    original_sleep = asyncio.sleep
    async def mock_sleep(seconds):
        await original_sleep(0.001 if seconds > 1.0 else seconds)
        
    with patch('colab_leecher.utility.upload_error_manager.asyncio.sleep', side_effect=mock_sleep):
        loop_task = asyncio.create_task(cleanup_stuck_errors())
        await asyncio.sleep(0.02)
        loop_task.cancel()
        try:
            await loop_task
        except asyncio.CancelledError:
            pass
            
    # Task should have been unpaused with default decision (False)
    assert task_ctx.keep_files_decision is False
    assert task_ctx.user_decision_event.is_set()
