# tests/unit/test_worker_queue_management.py

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

from colab_leecher.utility.worker_slot_manager import get_worker_slot_manager, recover_stuck_slots
from colab_leecher.utility.queue_operation_manager import get_queue_operation_manager, coordinated_cleanup
from colab_leecher.utility.task_context import TASK_QUEUE, TaskContext

@pytest.fixture
def anyio_backend():
    return 'asyncio'

@pytest.fixture(autouse=True)
def reset_managers():
    # Clear active_tasks, running_tasks and slot manager before/after each test
    TASK_QUEUE.active_tasks.clear()
    TASK_QUEUE.running_tasks.clear()
    get_worker_slot_manager().reset()
    yield
    TASK_QUEUE.active_tasks.clear()
    TASK_QUEUE.running_tasks.clear()
    get_worker_slot_manager().reset()

@pytest.mark.anyio
async def test_worker_slot_acquisition_and_release():
    wsm = get_worker_slot_manager()
    
    # Mock TASK_QUEUE limit to 2
    with patch.object(TASK_QUEUE, 'get_worker_limit', return_value=2):
        # 1. Acquire first slot
        acquired1 = await wsm.acquire_slot("task_1")
        assert acquired1 is True
        assert wsm.get_running_count() == 1
        assert wsm.get_slot_owners() == ["task_1"]
        
        # 2. Acquire same slot again (should be idempotent)
        acquired1_again = await wsm.acquire_slot("task_1")
        assert acquired1_again is True
        assert wsm.get_running_count() == 1
        
        # 3. Acquire second slot
        acquired2 = await wsm.acquire_slot("task_2")
        assert acquired2 is True
        assert wsm.get_running_count() == 2
        
        # 4. Attempt to acquire third slot (should block and timeout)
        acquired3 = await wsm.acquire_slot("task_3", timeout=0.1)
        assert acquired3 is False
        assert wsm.get_running_count() == 2
        
        # 5. Release one slot and acquire third slot
        released = await wsm.release_slot("task_1")
        assert released is True
        assert wsm.get_running_count() == 1
        
        acquired3_new = await wsm.acquire_slot("task_3")
        assert acquired3_new is True
        assert wsm.get_running_count() == 2
        assert set(wsm.get_slot_owners()) == {"task_2", "task_3"}

@pytest.mark.anyio
async def test_worker_slot_reset():
    wsm = get_worker_slot_manager()
    with patch.object(TASK_QUEUE, 'get_worker_limit', return_value=2):
        await wsm.acquire_slot("task_1")
        assert wsm.get_running_count() == 1
        
        wsm.reset()
        assert wsm.get_running_count() == 0
        assert wsm.get_slot_owners() == []

@pytest.mark.anyio
async def test_stuck_slots_monitoring_and_recovery():
    wsm = get_worker_slot_manager()
    with patch.object(TASK_QUEUE, 'get_worker_limit', return_value=2):
        await wsm.acquire_slot("task_1")
        await wsm.acquire_slot("task_2")
        
        # Manually alter acquired_at to simulate a stuck task (e.g., 2000 seconds ago)
        import time
        wsm._slot_owners["task_1"]["acquired_at"] = time.monotonic() - 2000.0
        
        stuck = await wsm.get_stuck_slots(max_hold_time=1800.0)
        assert stuck == ["task_1"]
        
        # Test background recovery loop simulation
        TASK_QUEUE.running_tasks.add("task_1")
        TASK_QUEUE.running_tasks.add("task_2")
        
        # Mock asyncio.sleep only in worker_slot_manager.py to yield control
        import asyncio
        original_sleep = asyncio.sleep
        async def mock_sleep(seconds):
            await original_sleep(0.001 if seconds > 1.0 else seconds)
            
        with patch('colab_leecher.utility.worker_slot_manager.asyncio.sleep', side_effect=mock_sleep), \
             patch.object(TASK_QUEUE, 'running_tasks', TASK_QUEUE.running_tasks):
            # Run the recovery loop
            loop_task = asyncio.create_task(recover_stuck_slots())
            # Yield control to allow recovery loop to execute once
            await asyncio.sleep(0.02)
            loop_task.cancel()
            try:
                await loop_task
            except asyncio.CancelledError:
                pass
                
        # task_1 should have been force released and removed from running_tasks
        assert "task_1" not in wsm.get_slot_owners()
        assert "task_1" not in TASK_QUEUE.running_tasks
        assert "task_2" in wsm.get_slot_owners()
        assert "task_2" in TASK_QUEUE.running_tasks

@pytest.mark.anyio
async def test_queue_operation_manager_safe_operations():
    qom = get_queue_operation_manager()
    wsm = get_worker_slot_manager()
    
    with patch.object(TASK_QUEUE, 'get_worker_limit', return_value=2):
        # Setup task in slot and in queue
        await wsm.acquire_slot("task_1")
        TASK_QUEUE.running_tasks.add("task_1")
        
        task_ctx = MagicMock(spec=TaskContext)
        task_ctx.task_id = "task_1"
        TASK_QUEUE.active_tasks["task_1"] = task_ctx
        
        # Test safe_release_slot
        released = await qom.safe_release_slot("task_1")
        assert released is True
        assert "task_1" not in wsm.get_slot_owners()
        assert "task_1" not in TASK_QUEUE.running_tasks
        
        # Test safe_remove_task
        mock_remove = AsyncMock()
        with patch.object(TASK_QUEUE, 'remove_task', mock_remove):
            removed = await qom.safe_remove_task("task_1")
            assert removed is True
            mock_remove.assert_called_once_with("task_1")

@pytest.mark.anyio
async def test_coordinated_cleanup():
    qom = get_queue_operation_manager()
    wsm = get_worker_slot_manager()
    
    with patch.object(TASK_QUEUE, 'get_worker_limit', return_value=2):
        await wsm.acquire_slot("task_1")
        TASK_QUEUE.running_tasks.add("task_1")
        
        task_ctx = MagicMock(spec=TaskContext)
        task_ctx.task_id = "task_1"
        TASK_QUEUE.active_tasks["task_1"] = task_ctx
        
        with patch('colab_leecher.utility.task_dashboard.force_update_summary', new_callable=AsyncMock) as mock_force_update:
            await coordinated_cleanup("task_1")
            
            # Slot should be released, running_tasks updated, and dashboard update triggered
            assert "task_1" not in wsm.get_slot_owners()
            assert "task_1" not in TASK_QUEUE.running_tasks
            mock_force_update.assert_called_once()
