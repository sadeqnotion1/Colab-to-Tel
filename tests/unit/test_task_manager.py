# tests/unit/test_task_manager.py

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

from colab_leecher.utility.task_context import create_task_context, TaskContext
from colab_leecher.utility.task_manager import _stage_download, Do_Leech, Do_GDrive_Upload


@pytest.fixture
def anyio_backend():
    return 'asyncio'


@pytest.mark.anyio
async def test_stage_download_smart_name_propagation():
    # Setup isolated task context
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    
    # Mock task_ctx properties to avoid actual file system cleanups
    task_ctx.paths.down_path = "/tmp/down_path"
    task_ctx.paths.temp_zpath = "/tmp/temp_zpath"
    task_ctx.paths.temp_unzip_path = "/tmp/temp_unzip_path"
    
    # Mock bot options and state
    task_ctx.bot.Options.service_type = 'direct'
    task_ctx.bot.Options.filenames = []
    task_ctx.bot.Mode.ytdl = False
    
    # Mock files in download dir
    mock_files = ["my_awesome_movie.mp4"]
    
    with patch('os.path.exists', return_value=True), \
         patch('os.path.isdir', return_value=True), \
         patch('os.path.isfile', return_value=True), \
         patch('shutil.rmtree') as mock_rmtree, \
         patch('colab_leecher.utility.task_manager.makedirs') as mock_makedirs, \
         patch('os.listdir', return_value=mock_files), \
         patch('colab_leecher.utility.task_manager.downloadManager', new_callable=AsyncMock) as mock_dl_manager:
         
         # Execute download stage
         result = await _stage_download(["http://link.com/file"], task_ctx)
         
         assert result == "/tmp/down_path"
         # Verify downloadManager was called
         mock_dl_manager.assert_called_once()
         # Verify smart_name was updated on messages context
         assert task_ctx.messages.download_name == "my_awesome_movie"


@pytest.mark.anyio
async def test_batch_size_configuration():
    # Setup task context
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.bot.Options.batch_size = 3
    
    source_links = ["link1", "link2", "link3", "link4", "link5"]
    
    # Mock the pipeline stages inside Do_Leech
    with patch('colab_leecher.utility.task_manager._stage_download', new_callable=AsyncMock, return_value="/tmp/down_path") as mock_stage_down, \
         patch('colab_leecher.utility.task_manager._stage_process', new_callable=AsyncMock, return_value="/tmp/processed_path") as mock_stage_process, \
         patch('colab_leecher.utility.task_manager._stage_upload', new_callable=AsyncMock) as mock_stage_upload:
         
         await Do_Leech(source_links, is_dir=False, is_ytdl=False, is_zip=False, is_unzip=False, is_dualzip=False, is_stream_unzip=False, task_ctx=task_ctx)
         
         # Link count is 5, batch_size is 3. So total batches = ceil(5/3) = 2.
         assert mock_stage_down.call_count == 2
         # Verify correct batches were processed
         mock_stage_down.assert_any_call(["link1", "link2", "link3"], task_ctx)
         mock_stage_down.assert_any_call(["link4", "link5"], task_ctx)


@pytest.mark.anyio
async def test_thumbnail_download_lazy_opt():
    # Setup task context
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.bot.Setting.thumbnail = False
    
    # Setup mock global queue task status
    with patch('colab_leecher.utility.task_manager.TASK_QUEUE.has_task', new_callable=AsyncMock, return_value=True) as mock_has_task, \
         patch('colab_leecher.utility.task_manager.thumbnail_urls', ["http://thumb.url/1.jpg"]), \
         patch('aiohttp.ClientSession') as mock_session_class:
         
         # If parallel mode is active (has_task=True) and setting is False, need_thumbnail should be False.
         # So no aiohttp ClientSession should be instantiated to download the thumbnail.
         from colab_leecher.utility.task_manager import taskScheduler
         
         # Mock all other taskScheduler interactions to prevent full execution
         with patch('colab_leecher.utility.task_manager.colab_bot', new_callable=MagicMock) as mock_bot, \
              patch('colab_leecher.utility.task_manager.Do_Leech', new_callable=AsyncMock) as mock_do_leech, \
              patch('colab_leecher.utility.task_manager.cleanup_task_artifacts') as mock_cleanup, \
              patch('colab_leecher.utility.task_manager.keyboard') as mock_kb:
              
              # Run scheduler
              await taskScheduler(task_ctx)
              
              # Session class should never have been called/instantiated for thumbnail download
              mock_session_class.assert_not_called()
