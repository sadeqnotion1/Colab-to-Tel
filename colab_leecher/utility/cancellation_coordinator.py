import asyncio
import logging
from typing import Optional

log = logging.getLogger(__name__)

class CancellationCoordinator:
    def __init__(self):
        self._cancellation_lock = asyncio.Lock()
        self._cancellation_in_progress = False
    
    async def cancel_all_tasks(self):
        """Cancel all tasks with proper coordination"""
        async with self._cancellation_lock:
            if self._cancellation_in_progress:
                return  # Already cancelling
            
            self._cancellation_in_progress = True
            
            try:
                # 1. Stop accepting new tasks
                from .task_context import TASK_QUEUE
                TASK_QUEUE.paused = True
                
                # 2. Get all tasks
                all_tasks = list(TASK_QUEUE.active_tasks.values())
                
                # 3. Cancel concurrently
                cancel_tasks = []
                for task_ctx in all_tasks:
                    cancel_task = asyncio.create_task(
                        self._cancel_single_task(task_ctx)
                    )
                    cancel_tasks.append(cancel_task)
                
                # 4. Wait for all cancellations
                await asyncio.gather(*cancel_tasks, return_exceptions=True)
                
                # 5. Verify cleanup
                await self._verify_cleanup()
                
            finally:
                from .task_context import TASK_QUEUE
                TASK_QUEUE.paused = False
                self._cancellation_in_progress = False
    
    async def _cancel_single_task(self, task_ctx):
        """Cancel single task with error handling"""
        try:
            from .handler import cancelTask
            await cancelTask("User pressed Cancel All.", task_ctx=task_ctx)
        except Exception as e:
            log.error(f"Failed to cancel task {task_ctx.task_id}: {e}")
            
    async def _verify_cleanup(self):
        from .task_context import TASK_QUEUE
        from .queue_operation_manager import coordinated_cleanup
        
        # For any tasks still in active_tasks, run cleanup
        remaining_tasks = list(TASK_QUEUE.active_tasks.keys())
        for task_id in remaining_tasks:
            try:
                await coordinated_cleanup(task_id)
            except Exception as e:
                log.error(f"Error forcing cleanup for task {task_id}: {e}")

_cancellation_coordinator = None

def get_cancellation_coordinator() -> CancellationCoordinator:
    global _cancellation_coordinator
    if _cancellation_coordinator is None:
        _cancellation_coordinator = CancellationCoordinator()
    return _cancellation_coordinator
