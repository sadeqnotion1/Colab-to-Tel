# tests/unit/test_aria2.py

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

from colab_leecher.utility.task_context import create_task_context
from colab_leecher.downlader.aria2 import download_and_upload_torrent_streaming

@pytest.fixture
def anyio_backend():
    return 'asyncio'

class MockProcess:
    def __init__(self, stdout_lines, stderr_lines, returncode=0):
        self.stdout = AsyncMock()
        # Add b'' at the end to simulate EOF
        self.stdout.readline = AsyncMock(side_effect=stdout_lines + [b''])
        self.stderr = AsyncMock()
        self.stderr.readline = AsyncMock(side_effect=stderr_lines + [b''])
        self._stdout_bytes = b'\n'.join(stdout_lines)
        self._stderr_bytes = b'\n'.join(stderr_lines)
        self.returncode = returncode
        self.pid = 1234

    async def communicate(self):
        return self._stdout_bytes, self._stderr_bytes

    async def wait(self):
        return self.returncode

    def kill(self):
        pass

@pytest.mark.anyio
async def test_download_and_upload_torrent_streaming_parsing():
    # Setup mock task context
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.paths.down_path = "/tmp/down_path"
    task_ctx.paths.WORK_PATH = "/tmp/work_path"
    task_ctx.paths.mirror_dir = "/tmp/mirror_dir"
    task_ctx.bot.Mode.mode = "leech"
    task_ctx.status_msg = MagicMock()

    # Stub aria2c -S output
    aria2_s_output = (
        b"File Alloc: [none]\n"
        b"Mode: [multi]\n"
        b"Name: Lexi Lore pack\n"
        b"=== Files ===\n"
        b"Idx|Path/to/file|Size\n"  # Testing case variations and pipe structure
        b"1|./Lexi Lore pack/video1.mp4|1.2GiB\n"
        b"2|./Lexi Lore pack/video2.mp4|850MiB\n"
    )

    # Subprocess execution mock
    mock_processes = [
        # First call: aria2c -S
        MockProcess(stdout_lines=aria2_s_output.split(b'\n'), stderr_lines=[]),
        # Second call: aria2c download file 1
        MockProcess(stdout_lines=[b"Downloading file 1..."], stderr_lines=[]),
        # Third call: aria2c download file 2
        MockProcess(stdout_lines=[b"Downloading file 2..."], stderr_lines=[])
    ]
    process_iter = iter(mock_processes)

    def mock_create_subprocess_exec(*args, **kwargs):
        return next(process_iter)

    # Mock filesystem operations
    def mock_exists(path):
        if path == "/tmp/test.torrent":
            return True
        if "video1.mp4" in path or "video2.mp4" in path:
            return True
        return False

    with patch('asyncio.create_subprocess_exec', side_effect=mock_create_subprocess_exec), \
         patch('os.path.exists', side_effect=mock_exists), \
         patch('os.path.isfile', return_value=True), \
         patch('os.path.getsize', return_value=1024 * 1024), \
         patch('os.remove'), \
         patch('shutil.rmtree'), \
         patch('tempfile.mkdtemp', return_value="/tmp/torrent_metadata_temp"), \
         patch('colab_leecher.utility.helper.status_bar', new_callable=AsyncMock) as mock_status_bar, \
         patch('colab_leecher.uploader.telegram.upload_file', new_callable=AsyncMock, return_value=True) as mock_upload:

        result = await download_and_upload_torrent_streaming("/tmp/test.torrent", task_ctx)
        
        # Verify success
        assert result is True
        
        # Verify both files got uploaded
        assert mock_upload.call_count == 2
        mock_upload.assert_any_call(
            file_path=os.path.normpath("/tmp/down_path/Lexi Lore pack/video1.mp4"),
            display_name="video1.mp4",
            task_ctx=task_ctx
        )
        mock_upload.assert_any_call(
            file_path=os.path.normpath("/tmp/down_path/Lexi Lore pack/video2.mp4"),
            display_name="video2.mp4",
            task_ctx=task_ctx
        )

@pytest.mark.anyio
async def test_download_and_upload_torrent_streaming_parsing_multiline():
    # Setup mock task context
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.paths.down_path = "/tmp/down_path"
    task_ctx.paths.WORK_PATH = "/tmp/work_path"
    task_ctx.paths.mirror_dir = "/tmp/mirror_dir"
    task_ctx.bot.Mode.mode = "leech"
    task_ctx.status_msg = MagicMock()

    # Stub aria2c -S multi-line output
    aria2_s_output = (
        b"*** BitTorrent File Information ***\n"
        b"Mode: multi\n"
        b"Name: Lexi Lore\n"
        b"Files:\n"
        b"idx|path/length\n"
        b"===+===========================================================================\n"
        b"  1|./Lexi Lore/video1.mp4\n"
        b"   |5.9GiB (6,391,353,748)\n"
        b"---+---------------------------------------------------------------------------\n"
        b"  2|./Lexi Lore/video2.mp4\n"
        b"   |3.1GiB (3,400,434,821)\n"
    )

    # Subprocess execution mock
    mock_processes = [
        # First call: aria2c -S
        MockProcess(stdout_lines=aria2_s_output.split(b'\n'), stderr_lines=[]),
        # Second call: aria2c download file 1
        MockProcess(stdout_lines=[b"Downloading file 1..."], stderr_lines=[]),
        # Third call: aria2c download file 2
        MockProcess(stdout_lines=[b"Downloading file 2..."], stderr_lines=[])
    ]
    process_iter = iter(mock_processes)

    def mock_create_subprocess_exec(*args, **kwargs):
        return next(process_iter)

    # Mock filesystem operations
    def mock_exists(path):
        if path == "/tmp/test.torrent":
            return True
        if "video1.mp4" in path or "video2.mp4" in path:
            return True
        return False

    with patch('asyncio.create_subprocess_exec', side_effect=mock_create_subprocess_exec), \
         patch('os.path.exists', side_effect=mock_exists), \
         patch('os.path.isfile', return_value=True), \
         patch('os.path.getsize', return_value=1024 * 1024), \
         patch('os.remove'), \
         patch('shutil.rmtree'), \
         patch('tempfile.mkdtemp', return_value="/tmp/torrent_metadata_temp"), \
         patch('colab_leecher.utility.helper.status_bar', new_callable=AsyncMock) as mock_status_bar, \
         patch('colab_leecher.uploader.telegram.upload_file', new_callable=AsyncMock, return_value=True) as mock_upload:

        result = await download_and_upload_torrent_streaming("/tmp/test.torrent", task_ctx)
        
        # Verify success
        assert result is True
        
        # Verify both files got uploaded
        assert mock_upload.call_count == 2
        mock_upload.assert_any_call(
            file_path=os.path.normpath("/tmp/down_path/Lexi Lore/video1.mp4"),
            display_name="video1.mp4",
            task_ctx=task_ctx
        )
        mock_upload.assert_any_call(
            file_path=os.path.normpath("/tmp/down_path/Lexi Lore/video2.mp4"),
            display_name="video2.mp4",
            task_ctx=task_ctx
        )
