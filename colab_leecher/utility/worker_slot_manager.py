# colab_leecher/utility/worker_slot_manager.py
import time
import asyncio
import logging
import traceback
from typing import List

log = logging.getLogger(__name__)

class WorkerSlotManager:
    """
    Centralized manager for worker slot concurrency.
    Supports dynamic worker limits, lock-synchronized slot acquisition/release,
    timeout checks, and recovery/monitoring of stuck worker slots.
    """
    def __init__(self):
        self._slot_owners = {}  # task_id -> info dict
        self._lock = asyncio.Lock()
        self._release_cond = asyncio.Condition()

    def reset(self):
        """
        Resets the worker slot manager state by clearing all slot owners
        and recreating the lock/condition objects to bind to the active event loop.
        """
        self._slot_owners.clear()
        self._lock = asyncio.Lock()
        self._release_cond = asyncio.Condition()

    def get_slot_owners(self) -> List[str]:
        return list(self._slot_owners.keys())

    def get_running_count(self) -> int:
        return len(self._slot_owners)

    async def acquire_slot(self, task_id: str, timeout: float = 60.0) -> bool:
        """
        Acquires a worker slot for a task. Waits if the running count has reached the worker limit.
        """
        start_time = time.monotonic()
        while True:
            async with self._lock:
                from .task_context import TASK_QUEUE
                limit = TASK_QUEUE.get_worker_limit()
                
                # If the task already owns a slot, return True immediately
                if task_id in self._slot_owners:
                    return True
                
                if len(self._slot_owners) < limit:
                    self._slot_owners[task_id] = {
                        'acquired_at': time.monotonic(),
                        'stack_trace': ''.join(traceback.format_stack())
                    }
                    log.info(f"WorkerSlotManager: Task {task_id[:8]} acquired worker slot. ({len(self._slot_owners)}/{limit})")
                    return True

            # Calculate remaining timeout
            elapsed = time.monotonic() - start_time
            remaining = timeout - elapsed
            if remaining <= 0:
                log.warning(f"WorkerSlotManager: Timeout acquiring slot for task {task_id[:8]}")
                return False

            # Wait for any slot release
            async with self._release_cond:
                try:
                    await asyncio.wait_for(self._release_cond.wait(), timeout=remaining)
                except asyncio.TimeoutError:
                    log.warning(f"WorkerSlotManager: Timeout waiting for slot release for task {task_id[:8]}")
                    return False

    async def release_slot(self, task_id: str) -> bool:
        """
        Releases a worker slot for a task and notifies waiting tasks.
        """
        async with self._lock:
            if task_id not in self._slot_owners:
                log.debug(f"WorkerSlotManager: Release requested for unknown task {task_id[:8]} (already released)")
                return False
            
            del self._slot_owners[task_id]
            log.info(f"WorkerSlotManager: Task {task_id[:8]} released worker slot. ({len(self._slot_owners)} running)")

        async with self._release_cond:
            self._release_cond.notify_all()
        return True

    async def force_release_slot(self, task_id: str) -> bool:
        """
        Forcibly releases a slot, used for error recovery of stuck tasks.
        """
        return await self.release_slot(task_id)

    async def get_stuck_slots(self, max_hold_time: float = 1800.0) -> List[str]:
        """
        Identifies slots held longer than max_hold_time.
        """
        async with self._lock:
            now = time.monotonic()
            stuck = []
            for tid, info in self._slot_owners.items():
                if now - info['acquired_at'] > max_hold_time:
                    stuck.append(tid)
            return stuck

# Global instance
_worker_slot_manager = WorkerSlotManager()

def get_worker_slot_manager() -> WorkerSlotManager:
    return _worker_slot_manager


async def recover_stuck_slots():
    """
    Recover slots held too long (greater than 30 minutes).
    Runs periodically as a background task.
    """
    wsm = get_worker_slot_manager()
    while True:
        try:
            await asyncio.sleep(300)  # Check every 5 minutes
            stuck_tasks = await wsm.get_stuck_slots(max_hold_time=1800.0)
            for task_id in stuck_tasks:
                log.warning(f"WorkerSlotManager: Force releasing stuck slot for task {task_id}")
                await wsm.force_release_slot(task_id)
                # Keep running_tasks on TASK_QUEUE in sync
                from .task_context import TASK_QUEUE
                if task_id in TASK_QUEUE.running_tasks:
                    TASK_QUEUE.running_tasks.remove(task_id)
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"Error in recover_stuck_slots loop: {e}", exc_info=True)
