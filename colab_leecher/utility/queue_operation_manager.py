# colab_leecher/utility/queue_operation_manager.py
import asyncio
import logging
from .task_context import TASK_QUEUE
from .worker_slot_manager import get_worker_slot_manager

log = logging.getLogger(__name__)

class QueueOperationManager:
    """
    Serializes potentially concurrent queue operations to prevent race conditions
    like negative worker counts and double task removal.
    """
    def __init__(self):
        self._operation_lock = asyncio.Lock()

    async def safe_release_slot(self, task_id: str) -> bool:
        async with self._operation_lock:
            wsm = get_worker_slot_manager()
            released = await wsm.release_slot(task_id)
            if task_id in TASK_QUEUE.running_tasks:
                TASK_QUEUE.running_tasks.remove(task_id)
            return released

    async def safe_remove_task(self, task_id: str) -> bool:
        async with self._operation_lock:
            if task_id not in TASK_QUEUE.active_tasks:
                log.debug(f"QueueOperationManager: Task {task_id[:8]} already removed from active queue")
                return False
            try:
                await TASK_QUEUE.remove_task(task_id)
                log.info(f"QueueOperationManager: Task {task_id[:8]} safely removed from active queue")
                return True
            except Exception as e:
                log.error(f"QueueOperationManager: Failed to remove task {task_id[:8]}: {e}", exc_info=True)
                return False

_queue_operation_manager = QueueOperationManager()

def get_queue_operation_manager() -> QueueOperationManager:
    return _queue_operation_manager

async def coordinated_cleanup(task_id: str):
    """
    Safely clean up task resources in the correct order:
    1. Release worker slot.
    2. Remove task from active queue.
    3. Update the summary dashboard.
    """
    qom = get_queue_operation_manager()
    
    # 1. Release worker slot first
    slot_released = await qom.safe_release_slot(task_id)
    
    # 2. Remove from active queue
    task_removed = await qom.safe_remove_task(task_id)
    
    # 3. Update dashboard only if we performed an actual release or removal
    if slot_released or task_removed:
        try:
            from .task_dashboard import force_update_summary
            from .. import colab_bot
            await force_update_summary(colab_bot)
        except Exception as e:
            log.warning(f"coordinated_cleanup: Failed to update dashboard: {e}")
