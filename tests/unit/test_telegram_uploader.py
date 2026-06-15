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

class MockException(Exception):
    pass

class MockFloodWait(MockException):
    def __init__(self, value=0):
        self.value = value

class MockSlowmodeWait(MockException):
    def __init__(self, value=0):
        self.value = value

errors_mock = MockModule()
errors_mock.FloodWait = MockFloodWait
errors_mock.SlowmodeWait = MockSlowmodeWait

sys.modules['pyrogram'] = MockModule()
sys.modules['pyrogram.client'] = MockModule()
sys.modules['pyrogram.types'] = MockModule()
sys.modules['pyrogram.enums'] = MockModule()
sys.modules['pyrogram.errors'] = errors_mock
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


def test_convertIMG_non_destructive(tmp_path):
    from colab_leecher.utility.helper import convertIMG
    from PIL import Image

    # Create a dummy PNG file
    png_path = tmp_path / "test_image.png"
    img = Image.new("RGB", (100, 100), color="red")
    img.save(png_path, "PNG")

    assert png_path.exists()

    # Call convertIMG with delete_original=False (default)
    jpg_path = convertIMG(str(png_path), delete_original=False)

    # Verify both PNG and JPEG exist
    assert png_path.exists()
    assert os.path.exists(jpg_path)
    assert jpg_path.endswith(".jpg")

    # Clean up jpg file
    os.remove(jpg_path)


def test_convertIMG_destructive(tmp_path):
    from colab_leecher.utility.helper import convertIMG
    from PIL import Image

    # Create a dummy PNG file
    png_path = tmp_path / "test_image.png"
    img = Image.new("RGB", (100, 100), color="blue")
    img.save(png_path, "PNG")

    assert png_path.exists()

    # Call convertIMG with delete_original=True
    jpg_path = convertIMG(str(png_path), delete_original=True)

    # Verify PNG is deleted and JPEG exists
    assert not png_path.exists()
    assert os.path.exists(jpg_path)
    assert jpg_path.endswith(".jpg")

    # Clean up jpg file
    os.remove(jpg_path)


@pytest.mark.anyio
async def test_upload_file_photo_path_update(tmp_path):
    from PIL import Image
    import colab_leecher.uploader.telegram as telegram_mod

    # Setup mock task context
    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.paths.down_path = str(tmp_path)

    # Create a dummy png file
    png_path = tmp_path / "photo.png"
    img = Image.new("RGB", (100, 100), color="green")
    img.save(png_path, "PNG")

    # Mock bot options/settings
    from colab_leecher.utility.variables import BOT
    BOT.Setting.thumbnail = False  # Ensure no custom thumb is used
    BOT.Options.stream_upload = False  # Upload as photo if send_photo matches

    # Mock colab_bot send methods
    mock_bot = AsyncMock()
    mock_message = MagicMock()
    mock_message.id = 456
    mock_bot.send_photo.return_value = mock_message

    original_bot = telegram_mod.colab_bot
    original_owner = getattr(telegram_mod, 'OWNER', None)
    telegram_mod.colab_bot = mock_bot
    telegram_mod.OWNER = 12345
    try:
        # Call upload_file
        result = await upload_file(str(png_path), "photo.png", task_ctx)

        assert result is True

        # Verify send_photo was called with photo.jpg instead of photo.png
        expected_jpg_path = os.path.normpath(str(tmp_path / "photo.jpg"))
        mock_bot.send_photo.assert_called_once()
        called_args, called_kwargs = mock_bot.send_photo.call_args
        assert os.path.normpath(called_kwargs['photo']) == expected_jpg_path
    finally:
        telegram_mod.colab_bot = original_bot
        telegram_mod.OWNER = original_owner


@pytest.mark.anyio
async def test_upload_file_non_retryable_exception(tmp_path):
    import colab_leecher.uploader.telegram as telegram_mod

    task_ctx = create_task_context(user_id=123, chat_id=123, mode="leech")
    task_ctx.paths.down_path = str(tmp_path)

    # Create a dummy file
    dummy_path = tmp_path / "dummy.txt"
    dummy_path.write_text("hello world")

    # Mock colab_bot
    mock_bot = AsyncMock()
    mock_bot.send_document.side_effect = ValueError("Failed to decode base64")

    original_bot = telegram_mod.colab_bot
    original_owner = getattr(telegram_mod, 'OWNER', None)
    telegram_mod.colab_bot = mock_bot
    telegram_mod.OWNER = 12345
    try:
        # When we call upload_file, it should fail immediately and return False
        # (retry_count should not increment to max_retries).
        with patch('asyncio.sleep') as mock_sleep:
            result = await upload_file(str(dummy_path), "dummy.txt", task_ctx)

            assert result is False
            # Since it is deterministic, it should not call asyncio.sleep (which is called during retry waits)
            mock_sleep.assert_not_called()
            # send_document should be called exactly once
            mock_bot.send_document.assert_called_once()
    finally:
        telegram_mod.colab_bot = original_bot
        telegram_mod.OWNER = original_owner

