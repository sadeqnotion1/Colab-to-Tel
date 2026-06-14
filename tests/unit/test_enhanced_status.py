# tests/unit/test_enhanced_status.py

import sys
import os
from unittest.mock import MagicMock

# Create a mock module structure to satisfy imports
class MockModule(MagicMock):
    @property
    def __path__(self):
        return []

pyrogram_mock = MockModule()
sys.modules['pyrogram'] = pyrogram_mock
sys.modules['pyrogram.client'] = MockModule()
sys.modules['pyrogram.types'] = MockModule()
sys.modules['pyrogram.enums'] = MockModule()
sys.modules['pyrogram.errors'] = MockModule()

# Add the project root to sys.path so we can import colab_leecher
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from colab_leecher.utility.enhanced_status import StatusDisplay, create_download_status, create_upload_status
from colab_leecher.utility.ui_components import Emoji

def test_status_display_stateless():
    # Verify that StatusDisplay does not have __init__ or instance state
    assert not hasattr(StatusDisplay, '__init__') or StatusDisplay.__init__ is object.__init__

def test_speed_emoji():
    # Verify speed emoji thresholds
    assert StatusDisplay.speed_emoji(15 * 1024 * 1024) == "\U0001f7e2"  # Fast >= 10 MB/s
    assert StatusDisplay.speed_emoji(5 * 1024 * 1024) == "\U0001f7e1"   # Medium 3-10 MB/s
    assert StatusDisplay.speed_emoji(1 * 1024 * 1024) == "\U0001f7e0"   # Slow 0.5-3 MB/s
    assert StatusDisplay.speed_emoji(0.1 * 1024 * 1024) == "\U0001f534" # Very slow < 0.5 MB/s

def test_smart_eta():
    # Under 512KB, should show warming up
    assert StatusDisplay.smart_eta(10, downloaded=100 * 1024) == "\u23f3 Warming up..."
    # Above 512KB, should show formatted ETA
    assert StatusDisplay.smart_eta(12, downloaded=600 * 1024) == "12s"
    assert StatusDisplay.smart_eta(None, downloaded=600 * 1024) == "Calculating..."
    assert StatusDisplay.smart_eta(-5, downloaded=600 * 1024) == "Calculating..."

def test_download_status():
    # Call class method directly
    msg, kb = StatusDisplay.download_status(
        filename="test_file.mkv",
        progress=45.5,
        speed=1024 * 1024 * 5,  # 5 MB/s
        downloaded=1024 * 1024 * 50,
        total_size=1024 * 1024 * 100,
        elapsed_time=30.0,
        task_id="test_task_123",
        style="sleek"
    )
    
    assert "test_file.mkv" in msg
    assert "45.5%" in msg
    assert "5.00 MiB/s" in msg
    assert "30s" in msg
    assert "50.00 MiB" in msg
    assert "100.00 MiB" in msg

def test_upload_status():
    # Call class method directly
    msg, kb = StatusDisplay.upload_status(
        filename="upload_test.mp4",
        progress=90.0,
        speed=1024 * 1024 * 2,  # 2 MB/s
        uploaded=1024 * 1024 * 18,
        total_size=1024 * 1024 * 20,
        elapsed_time=9.0,
        task_id="test_task_456",
        style="modern"
    )
    
    assert "upload_test.mp4" in msg
    assert "90.0%" in msg
    assert "2.00 MiB/s" in msg
    assert "9s" in msg

def test_processing_status():
    msg, kb = StatusDisplay.processing_status(
        filename="extracting_archive.zip",
        operation="extracting",
        elapsed_time=45.0,
        task_id="proc_task_789"
    )
    
    assert "EXTRACTING" in msg
    assert "extracting_archive.zip" in msg
    assert "45s" in msg

def test_convenience_wrappers():
    # Verify download wrapper
    msg, kb = create_download_status(
        filename="wrap.zip",
        progress=20.0,
        speed=1024 * 1024,
        downloaded=1024 * 1024 * 2,
        total_size=1024 * 1024 * 10,
        elapsed_time=5.0,
        style="compact"
    )
    assert "wrap.zip" in msg
    assert "20.0%" in msg
    assert "5s" in msg

    # Verify upload wrapper
    msg2, kb2 = create_upload_status(
        filename="wrap_up.zip",
        progress=80.0,
        speed=1024 * 1024,
        uploaded=1024 * 1024 * 8,
        total_size=1024 * 1024 * 10,
        elapsed_time=8.0,
        style="sleek"
    )
    assert "wrap_up.zip" in msg2
    assert "80.0%" in msg2
    assert "8s" in msg2

if __name__ == "__main__":
    print("Running stateless StatusDisplay tests...")
    test_status_display_stateless()
    test_speed_emoji()
    test_smart_eta()
    test_download_status()
    test_upload_status()
    test_processing_status()
    test_convenience_wrappers()
    print("All StatusDisplay tests passed successfully!")
