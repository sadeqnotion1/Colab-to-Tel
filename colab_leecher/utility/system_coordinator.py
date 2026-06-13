import asyncio
import logging
from contextlib import contextmanager

from .worker_slot_manager import WorkerSlotManager
import colab_leecher.utility.worker_slot_manager as wsm

from .queue_operation_manager import QueueOperationManager
import colab_leecher.utility.queue_operation_manager as qom

from .progress_manager import ProgressManager
import colab_leecher.utility.progress_manager as pm

from .upload_error_manager import UploadErrorManager
import colab_leecher.utility.upload_error_manager as uem

log = logging.getLogger(__name__)

class GuaranteedCleanup:
    def __init__(self):
        self._cleanup_locks = {}
    
    @contextmanager
    def managed_slot(self, task_id):
        """Context manager for guaranteed slot cleanup"""
        lock = asyncio.Lock()
        self._cleanup_locks[task_id] = lock
        
        try:
            yield
        finally:
            # Always release slot
            asyncio.create_task(self._safe_release(task_id))
    
    async def _safe_release(self, task_id):
        """Safely release worker slot"""
        async with self._cleanup_locks.get(task_id, asyncio.Lock()):
            try:
                from .worker_slot_manager import get_worker_slot_manager
                manager = get_worker_slot_manager()
                await manager.release_slot(task_id)
            except Exception as e:
                log.error(f"Failed to release slot for {task_id}: {e}")
                try:
                    from .worker_slot_manager import get_worker_slot_manager
                    manager = get_worker_slot_manager()
                    await manager.force_release_slot(task_id)
                except Exception as force_err:
                    log.error(f"Failed to force release slot for {task_id}: {force_err}")

class SystemCoordinator:
    def __init__(self):
        self._progress_manager = None
        self._worker_manager = None
        self._queue_manager = None
        self._error_manager = None
        self.guaranteed_cleanup = GuaranteedCleanup()
        self._initialized = False
    
    async def initialize(self):
        """Initialize all managers in proper order"""
        if self._initialized:
            return
        
        # 1. Worker management first (most critical)
        self._worker_manager = WorkerSlotManager()
        wsm._worker_slot_manager = self._worker_manager
        
        # 2. Queue management
        self._queue_manager = QueueOperationManager()
        qom._queue_operation_manager = self._queue_manager
        
        # 3. Progress management
        self._progress_manager = ProgressManager()
        pm._progress_manager_instance = self._progress_manager
        
        # 4. Error handling
        self._error_manager = UploadErrorManager()
        uem._upload_error_manager = self._error_manager
        
        # 5. Start monitoring tasks
        await self._start_monitoring()
        
        self._initialized = True
    
    async def _start_monitoring(self):
        """Start background monitoring tasks"""
        asyncio.create_task(self._monitor_worker_slots())
        asyncio.create_task(self._monitor_queue_health())
        asyncio.create_task(self._cleanup_stuck_errors())

    async def _monitor_worker_slots(self):
        """Monitor and recover stuck worker slots"""
        from .worker_slot_manager import recover_stuck_slots
        await recover_stuck_slots()

    async def _monitor_queue_health(self):
        """Monitor health of the task queue"""
        while True:
            try:
                await asyncio.sleep(60)
                from .task_context import TASK_QUEUE
                for task_id, task_ctx in list(TASK_QUEUE.active_tasks.items()):
                    if task_ctx.async_task and task_ctx.async_task.done():
                        log.warning(f"SystemCoordinator: Task {task_id[:8]} loop is finished but task not cleared. Cleaning up.")
                        from .queue_operation_manager import coordinated_cleanup
                        await coordinated_cleanup(task_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.error(f"Error in queue health monitor: {e}", exc_info=True)

    async def _cleanup_stuck_errors(self):
        """Monitor and clean up stuck errors"""
        from .upload_error_manager import cleanup_stuck_errors
        await cleanup_stuck_errors()

_system_coordinator = None

def get_system_coordinator() -> SystemCoordinator:
    global _system_coordinator
    if _system_coordinator is None:
        _system_coordinator = SystemCoordinator()
    return _system_coordinator
