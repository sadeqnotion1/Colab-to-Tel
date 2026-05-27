import time
import pytest
from colab_leecher.utility.task_context import TaskTransfer

def test_task_transfer_initialization():
    transfer = TaskTransfer()
    assert isinstance(transfer.last_speed, float)
    assert transfer.last_speed == 0.0
    assert isinstance(transfer.last_speed_bytes, float)
    assert transfer.last_speed_bytes == 0.0

def test_task_transfer_reset():
    transfer = TaskTransfer(
        down_bytes=1000,
        up_bytes=500,
        total_size=10000,
        last_speed=15.5,
        last_speed_bytes=15.5
    )
    transfer.reset()
    assert transfer.down_bytes == 0
    assert transfer.up_bytes == 0
    assert transfer.total_size == 0
    assert transfer.last_speed == 0.0

def test_task_transfer_percentage():
    transfer = TaskTransfer(down_bytes=50, total_size=100)
    pct = transfer.get_percentage()
    assert isinstance(pct, float)
    assert pct == 50.0

    transfer2 = TaskTransfer(down_bytes=0, total_size=0)
    assert transfer2.get_percentage() == 0.0

def test_task_transfer_speed_and_eta():
    transfer = TaskTransfer(down_bytes=1000, total_size=2000)
    transfer.start_time = time.time() - 10.0  # 10 seconds ago
    
    speed = transfer.get_speed()
    assert isinstance(speed, float)
    assert speed > 0.0
    assert pytest.approx(speed, rel=1e-2) == 100.0  # 100 bytes/sec
    
    eta = transfer.get_eta()
    assert isinstance(eta, float)
    assert abs(eta - 10.0) < 0.1  # 10 seconds remaining

if __name__ == "__main__":
    print("Running TaskTransfer tests...")
    test_task_transfer_initialization()
    test_task_transfer_reset()
    test_task_transfer_percentage()
    test_task_transfer_speed_and_eta()
    print("All tests passed successfully!")
