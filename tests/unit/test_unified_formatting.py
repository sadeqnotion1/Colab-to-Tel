import math
import pytest
from colab_leecher.utility.formatting import format_bytes, format_speed, format_eta
from colab_leecher.utility.task_context import TaskTransfer

def test_format_bytes_edge_cases():
    # 0 bytes
    assert format_bytes(0) == "0 B"
    # Negative bytes
    assert format_bytes(-100) == "0 B"
    # NaN/Invalid inputs
    assert format_bytes("invalid") == "N/A"
    assert format_bytes(None) == "N/A"
    
    # Standard sizes
    assert format_bytes(1024) == "1.00 KiB"
    assert format_bytes(1024 * 1024) == "1.00 MiB"
    assert format_bytes(1024 * 1024 * 1024) == "1.00 GiB"
    assert format_bytes(1.5 * 1024 * 1024 * 1024) == "1.50 GiB"
    
    # Custom precision
    assert format_bytes(1024 * 1024 * 1.2346, precision=3) == "1.235 MiB"

def test_format_speed_edge_cases():
    assert format_speed(0) == "N/A"
    assert format_speed(-50) == "N/A"
    assert format_speed("invalid") == "N/A"
    assert format_speed(None) == "N/A"
    
    assert format_speed(1024 * 1024 * 5.5) == "5.50 MiB/s"

def test_format_eta_edge_cases():
    assert format_eta(0) == "N/A"
    assert format_eta(-10) == "N/A"
    assert format_eta("invalid") == "N/A"
    assert format_eta(None) == "N/A"
    # Greater than 7 days
    assert format_eta(86400 * 7 + 1) == "N/A"
    
    # Standard formats
    assert format_eta(45) == "45s"
    assert format_eta(125) == "2m 5s"
    assert format_eta(3725) == "1h 2m 5s"
    assert format_eta(90005) == "1d 1h 0m"

def test_session_uploaded_bytes_field():
    transfer = TaskTransfer()
    assert hasattr(transfer, "session_uploaded_bytes")
    assert transfer.session_uploaded_bytes == 0
    
    transfer.session_uploaded_bytes += 1000
    assert transfer.session_uploaded_bytes == 1000
    
    transfer.reset()
    assert transfer.session_uploaded_bytes == 0

def test_aria2_size_parsing():
    from colab_leecher.downlader.aria2 import _parse_size_to_bytes
    # IEC units
    assert _parse_size_to_bytes("16MiB") == 16 * 1024**2
    assert _parse_size_to_bytes("5GiB") == 5 * 1024**3
    assert _parse_size_to_bytes("700KiB") == 700 * 1024
    assert _parse_size_to_bytes("1.5GiB") == int(1.5 * 1024**3)
    
    # SI units
    assert _parse_size_to_bytes("16MB") == 16 * 1000**2
    assert _parse_size_to_bytes("5GB") == 5 * 1000**3
    
    # Optional spacing
    assert _parse_size_to_bytes("16 MiB") == 16 * 1024**2
    assert _parse_size_to_bytes(" 5.5 GiB ") == int(5.5 * 1024**3)
    
    # Edge cases
    assert _parse_size_to_bytes("unknown") == 0
    assert _parse_size_to_bytes(None) == 0
