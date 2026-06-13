# tests/unit/test_telegram_uploader.py

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
sys.modules['curl_cffi'] = MockModule()
sys.modules['curl_cffi.requests'] = MockModule()
sys.modules['mega'] = MockModule()

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from colab_leecher.uploader.telegram import upload_file
from colab_leecher.utility.task_context import create_task_context

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.mark.anyio
async def test_upload_file_safety_net():
    # Setup mock task context
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.paths.down_path = os.path.normpath("/tmp/down_path")
    task_ctx.paths.temp_zpath = os.path.normpath("/tmp/temp_zpath")
    task_ctx.bot.Mode.mode = "leech"
    task_ctx.status_msg = MagicMock()
    
    large_file_path = os.path.normpath("/tmp/large_file.mp4")
    large_file_size = 3 * 1024 * 1024 * 1024  # 3 GB (exceeds 2000 MiB limit)
    
    # Mock sizeChecker to split the file and generate parts in temp_zpath
    async def mock_size_checker(file_path, remove, task_ctx):
        return True

    # Mock os/shutil/helper operations
    def mock_exists(path):
        if path == large_file_path:
            return True
        if os.path.normpath("/tmp/temp_zpath") in path:
            return True
        return False

    def mock_listdir(path):
        if path == os.path.normpath("/tmp/temp_zpath"):
            return ["large_file.mp4.001", "large_file.mp4.002"]
        return []

    # Mock sizeChecker call and other parts
    with patch('colab_leecher.utility.converters.sizeChecker', new=AsyncMock(side_effect=mock_size_checker)) as mock_size_checker_func, \
         patch('os.path.exists', side_effect=mock_exists), \
         patch('os.path.isfile', return_value=True), \
         patch('os.listdir', side_effect=mock_listdir), \
         patch('colab_leecher.utility.helper.getSize', side_effect=lambda p: large_file_size if p == large_file_path else 1024 * 1024), \
         patch('shutil.rmtree') as mock_rmtree, \
         patch('os.makedirs') as mock_makedirs, \
         patch('colab_leecher.uploader.telegram.upload_file', new_callable=AsyncMock) as mock_recursive_upload_file:
         
         mock_recursive_upload_file.return_value = True

         result = await upload_file(large_file_path, "large_file.mp4", task_ctx)
         
         assert result is True
         # Verify sizeChecker was called
         mock_size_checker_func.assert_called_once_with(large_file_path, remove=True, task_ctx=task_ctx)
         # Verify recursive uploads were called for both parts
         assert mock_recursive_upload_file.call_count == 2
         mock_recursive_upload_file.assert_any_call(
             os.path.join(task_ctx.paths.temp_zpath, "large_file.mp4.001"),
             "large_file.mp4.001",
             task_ctx
         )
         mock_recursive_upload_file.assert_any_call(
             os.path.join(task_ctx.paths.temp_zpath, "large_file.mp4.002"),
             "large_file.mp4.002",
             task_ctx
         )
