# tests/unit/test_progress_dispatcher.py

import sys
import os
import time
import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

# Create a mock module structure to satisfy imports if needed
class MockModule(MagicMock):
    @property
    def __path__(self):
        return []

sys.modules['pyrogram'] = MockModule()
sys.modules['pyrogram.client'] = MockModule()
sys.modules['pyrogram.types'] = MockModule()
sys.modules['pyrogram.enums'] = MockModule()
sys.modules['pyrogram.errors'] = MockModule()

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from colab_leecher.utility.task_context import TaskContext, TaskTransfer, TaskMessages
from colab_leecher.utility.progress_dispatcher import ProgressDispatcher
from colab_leecher.utility.enhanced_status import StatusDisplay


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.fixture(autouse=True)
def reset_progress_manager():
    from colab_leecher.utility.progress_manager import get_progress_manager
    get_progress_manager().reset()
    from colab_leecher.utility.unified_progress import get_unified_progress
    get_unified_progress().reset()
    yield



@pytest.fixture
def mock_task_ctx():
    ctx = MagicMock(spec=TaskContext)
    ctx.task_id = "test-task-uuid"
    ctx.filenames = ["test_file.zip"]
    ctx.started_at = None
    ctx.last_status_update = 0.0
    ctx.is_cancelled = False
    
    # Concrete dataclass objects to ensure realistic behaviors
    ctx.transfer = TaskTransfer()
    ctx.transfer.down_bytes = 0
    ctx.transfer.up_bytes = 0
    ctx.transfer.total_size = 0
    ctx.transfer.start_time = time.time() - 10.0 # 10s elapsed
    
    ctx.messages = TaskMessages()
    ctx.messages.download_name = "test_file.zip"
    
    # Mock status_msg with edit_text and edit_caption AsyncMocks
    status_msg = AsyncMock()
    status_msg.photo = None
    status_msg.edit_text = AsyncMock()
    status_msg.edit_caption = AsyncMock()
    ctx.status_msg = status_msg
    
    # Setup short id and helper methods
    ctx.get_short_id = MagicMock(return_value="test-tas")
    ctx.get_elapsed_time = MagicMock(return_value=10.0)
    
    return ctx


@pytest.mark.anyio
async def test_progress_dispatcher_basic_update(mock_task_ctx):
    # Setup dispatcher
    dispatcher = ProgressDispatcher(
        task_ctx=mock_task_ctx,
        operation="download",
        engine="TestEngine 🚀",
        style="sleek",
        interval=0.1
    )
    
    # Perform update
    await dispatcher.update(current_bytes=500, total_bytes=1000, force=True)
    
    # Check stats updated
    assert mock_task_ctx.transfer.down_bytes == 500
    assert mock_task_ctx.transfer.total_size == 1000
    
    # Check Pyrogram edit_text was called
    mock_task_ctx.status_msg.edit_text.assert_called_once()
    call_kwargs = mock_task_ctx.status_msg.edit_text.call_args[1]
    assert "test_file.zip" in call_kwargs["text"]
    assert "50.0%" in call_kwargs["text"]
    assert "TestEngine" in call_kwargs["text"]


@pytest.mark.anyio
async def test_progress_dispatcher_throttling(mock_task_ctx):
    # Setup dispatcher with high interval (e.g. 5 seconds)
    dispatcher = ProgressDispatcher(
        task_ctx=mock_task_ctx,
        operation="download",
        engine="TestEngine 🚀",
        interval=5.0
    )
    
    # First update should proceed because mock_task_ctx.last_status_update = 0.0
    await dispatcher.update(current_bytes=100, total_bytes=1000)
    assert mock_task_ctx.status_msg.edit_text.call_count == 1
    
    # Second update immediately after should be throttled
    await dispatcher.update(current_bytes=200, total_bytes=1000)
    assert mock_task_ctx.status_msg.edit_text.call_count == 1 # Still 1
    
    # Stats should still have updated in the transfer object despite throttling!
    assert mock_task_ctx.transfer.down_bytes == 200
    
    # Force or finalize should bypass throttle
    await dispatcher.finalize()
    assert mock_task_ctx.status_msg.edit_text.call_count == 2


@pytest.mark.anyio
async def test_progress_dispatcher_cancellation(mock_task_ctx):
    dispatcher = ProgressDispatcher(
        task_ctx=mock_task_ctx,
        operation="download"
    )
    
    # Mark task as cancelled
    mock_task_ctx.is_cancelled = True
    
    with pytest.raises(asyncio.CancelledError):
        await dispatcher.update(current_bytes=100)


@pytest.mark.anyio
async def test_progress_dispatcher_callable_interface(mock_task_ctx):
    dispatcher = ProgressDispatcher(
        task_ctx=mock_task_ctx,
        operation="download",
        interval=0.1
    )
    
    # Call directly as a callback
    await dispatcher(300, 1000)
    
    assert mock_task_ctx.transfer.down_bytes == 300
    assert mock_task_ctx.transfer.total_size == 1000


@pytest.mark.anyio
async def test_progress_dispatcher_resilient_to_pyrogram_exceptions(mock_task_ctx):
    dispatcher = ProgressDispatcher(
        task_ctx=mock_task_ctx,
        operation="download",
        interval=0.1
    )
    
    # Make edit_text raise an Exception to simulate error
    mock_task_ctx.status_msg.edit_text.side_effect = Exception("MessageNotModified")
    
    # This should not raise an exception, it should be swallowed safely
    await dispatcher.update(current_bytes=100, total_bytes=1000, force=True)
    
    # Also verify that FloodWait doesn't crash the loop
    from unittest.mock import Mock
    class DummyFloodWait(Exception):
        def __init__(self):
            self.value = 9
            self.x = 9
    
    mock_task_ctx.status_msg.edit_text.side_effect = DummyFloodWait()
    await dispatcher.update(current_bytes=200, total_bytes=1000, force=True)
    
    # Verify the values were still stored
    assert mock_task_ctx.transfer.down_bytes == 200
