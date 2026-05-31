# tests/unit/test_task_dashboard.py

import sys
import os
import pytest
import time
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

sys.modules['curl_cffi'] = MockModule()
sys.modules['curl_cffi.requests'] = MockModule()
sys.modules['mega'] = MockModule()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from colab_leecher.utility.task_context import create_task_context, TASK_QUEUE
from colab_leecher.utility.task_dashboard import update_summary_dashboard, force_update_summary


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture(autouse=True)
def mock_os_path_exists():
    with patch("colab_leecher.utility.task_dashboard.os.path.exists", return_value=False):
        yield


@pytest.fixture(autouse=True)
async def reset_task_queue():
    # Make sure TASK_QUEUE is empty and state is fresh before each test
    TASK_QUEUE.active_tasks.clear()
    TASK_QUEUE.running_tasks.clear()
    TASK_QUEUE.summary_msg = None
    TASK_QUEUE.last_summary_text = ""
    TASK_QUEUE.last_summary_keyboard_signature = ""
    TASK_QUEUE._ui_suspended_until = 0.0
    TASK_QUEUE.last_summary_update = 0.0
    TASK_QUEUE._last_force_time = 0.0
    TASK_QUEUE._dashboard_page = 0
    yield


@pytest.mark.anyio
async def test_update_dashboard_empty_queue():
    # Mock status message to delete
    mock_msg = AsyncMock()
    TASK_QUEUE.summary_msg = mock_msg
    
    # Run dashboard update with empty queue
    result = await update_summary_dashboard(client=MagicMock(), force=True)
    
    assert result is None
    assert TASK_QUEUE.summary_msg is None
    # Verify the previous summary message was deleted
    mock_msg.delete.assert_called_once()


@pytest.mark.anyio
async def test_update_dashboard_global_view():
    # Create mock client and task context
    mock_client = AsyncMock()
    mock_client.send_message = AsyncMock(return_value=AsyncMock())
    
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.messages.download_name = "Avatar.mp4"
    task_ctx.transfer.down_bytes = 500
    task_ctx.transfer.total_size = 1000
    
    await TASK_QUEUE.add_task(task_ctx)
    await TASK_QUEUE.set_dashboard_page(0) # Page 0 = Global Summary View
    
    # Run dashboard update
    result = await update_summary_dashboard(client=mock_client, force=True)
    
    assert result is not None
    # Verify new message is sent since there was no existing summary message
    mock_client.send_message.assert_called_once()
    call_kwargs = mock_client.send_message.call_args[1]
    
    # Assert global view layout characters and progress bar exist in message text
    message_text = call_kwargs.get("text")
    assert message_text is not None
    assert "Global Manager" in message_text
    assert "Avatar.mp4" in message_text
    assert "50.0%" in message_text


@pytest.mark.anyio
async def test_update_dashboard_task_detail_view():
    # Create mock client and task context
    mock_client = AsyncMock()
    mock_client.send_message = AsyncMock(return_value=AsyncMock())
    
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.messages.download_name = "Interstellar.mkv"
    task_ctx.transfer.down_bytes = 200
    task_ctx.transfer.total_size = 1000
    
    await TASK_QUEUE.add_task(task_ctx)
    await TASK_QUEUE.set_dashboard_page(1) # Page 1 = Details for Task 1
    
    # Run dashboard update
    result = await update_summary_dashboard(client=mock_client, force=True)
    
    assert result is not None
    mock_client.send_message.assert_called_once()
    call_kwargs = mock_client.send_message.call_args[1]
    
    # Assert detail view headers exist
    message_text = call_kwargs.get("text")
    assert message_text is not None
    assert "Task Details" in message_text
    assert "Interstellar.mkv" in message_text
    assert "20.0%" in message_text


@pytest.mark.anyio
async def test_update_dashboard_throttling_avoidance():
    # Create mock client
    mock_client = AsyncMock()
    
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    await TASK_QUEUE.add_task(task_ctx)
    
    # Set suspension time to future to simulate FloodWait throttling
    TASK_QUEUE._ui_suspended_until = time.monotonic() + 100.0
    
    result = await update_summary_dashboard(client=mock_client, force=False)
    
    # Verify that the update call was skipped/throttled early, returning None/previous state
    assert result is None
    mock_client.send_message.assert_not_called()
