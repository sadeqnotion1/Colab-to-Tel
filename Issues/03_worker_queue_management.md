# Worker Slot & Queue Management Issues - Detailed Fix Prompt

## Status: ✅ SOLVED

## Problem Description
The task manager has critical worker slot and queue management issues that can cause:
1. **Worker slot leaks** leading to negative worker counts
2. **Race conditions** in concurrent task queue operations
3. **Double task removal** causing queue corruption
4. **Stuck tasks** preventing new task execution

## Root Cause Analysis

### 1. Worker Slot Leaks
**File**: `task_context.py`
```python
# Current problematic pattern:
async def task_scheduler(task_ctx):
    try:
        await TASK_QUEUE.acquire_worker_slot(task_ctx.task_id)
        # ... execute task ...
    except Exception as e:
        # Exception handler might fail
        log.error(f"Task failed: {e}")
    finally:
        # This cleanup might fail silently
        try:
            await TASK_QUEUE.release_worker_slot(task_ctx.task_id)
        except Exception as cleanup_err:
            log.error(f"Cleanup failed: {cleanup_err}")
```

**Problem**: If `release_worker_slot()` fails, the worker count becomes permanently inflated, eventually blocking all new tasks.

### 2. Race Conditions in Queue Operations
**File**: `task_manager.py:550-572`
```python
# Current problematic pattern:
async def _async_cleanup():
    try:
        await TASK_QUEUE.release_worker_slot(task_id)
    except Exception as slot_err:
        log.error(...)
    
    try:
        await TASK_QUEUE.remove_task(task_id)
    except Exception as remove_err:
        log.error(...)

# Called as background task:
create_background_task(_async_cleanup())
```

**Problem**: If multiple tasks finish simultaneously, their cleanup tasks interleave unsafely:
- Task A releases slot → Task B releases slot → Worker count goes negative
- Task A removes from queue → Task B removes same task → Double removal

### 3. Double Task Removal
**File**: `__main__.py:3595-3608`
```python
# Current problematic pattern:
for task_ctx in list(all_tasks.values()):
    await cancelTask("User pressed Cancel All.", task_ctx=task_ctx)
    # cancelTask calls taskScheduler finally block which removes from queue
    
    await TASK_QUEUE.remove_task(task_ctx.task_id)
    # Tries to remove again - double removal!
```

**Problem**: The explicit `remove_task()` call is redundant and can race with the finally block's removal.

## Step-by-Step Solution

### Phase 1: Implement Robust Worker Slot Management
1. **Create WorkerSlotManager class**:
   ```python
   class WorkerSlotManager:
       def __init__(self, max_workers):
           self._max_workers = max_workers
           self._current_workers = 0
           self._slot_owners = {}  # task_id -> owner info
           self._lock = asyncio.Lock()
           self._release_queue = asyncio.Queue()
       
       async def acquire_slot(self, task_id, timeout=30):
           async with self._lock:
               if self._current_workers >= self._max_workers:
                   # Wait for slot release
                   await asyncio.wait_for(
                       self._wait_for_slot(),
                       timeout=timeout
                   )
               
               self._current_workers += 1
               self._slot_owners[task_id] = {
                   'acquired_at': time.monotonic(),
                   'stack_trace': traceback.format_stack()
               }
               return True
       
       async def release_slot(self, task_id):
           async with self._lock:
               if task_id not in self._slot_owners:
                   log.warning(f"Slot release for unknown task: {task_id}")
                   return False
               
               del self._slot_owners[task_id]
               self._current_workers = max(0, self._current_workers - 1)
               
               # Notify waiting tasks
               await self._release_queue.put(True)
               return True
   ```

2. **Add slot monitoring**:
   ```python
   async def monitor_slots(self):
       while True:
           await asyncio.sleep(60)  # Check every minute
           async with self._lock:
               now = time.monotonic()
               for task_id, info in self._slot_owners.items():
                   held_for = now - info['acquired_at']
                   if held_for > 3600:  # Held for > 1 hour
                       log.error(f"Slot held too long: {task_id}, {held_for:.1f}s")
                       # Optional: force release with warning
   ```

### Phase 2: Implement Safe Queue Operations
1. **Create QueueOperationManager**:
   ```python
   class QueueOperationManager:
       def __init__(self):
           self._operation_lock = asyncio.Lock()
           self._pending_operations = []
       
       async def safe_remove_task(self, task_id):
           async with self._operation_lock:
               # Check if already removed
               if task_id not in TASK_QUEUE.tasks:
                   return True
               
               # Perform removal
               try:
                   await TASK_QUEUE.remove_task(task_id)
                   return True
               except Exception as e:
                   log.error(f"Failed to remove task {task_id}: {e}")
                   return False
       
       async def safe_release_slot(self, task_id):
           async with self._operation_lock:
               # Check if slot exists
               if task_id not in WORKER_SLOT_MANAGER._slot_owners:
                   return True
               
               # Perform release
               return await WORKER_SLOT_MANAGER.release_slot(task_id)
   ```

2. **Implement cleanup coordination**:
   ```python
   async def coordinated_cleanup(task_id):
       """Clean up task resources in proper order"""
       try:
           # 1. Release worker slot first
           slot_released = await QUEUE_OPS.safe_release_slot(task_id)
           if not slot_released:
               log.error(f"Failed to release slot for {task_id}")
           
           # 2. Then remove from queue
           task_removed = await QUEUE_OPS.safe_remove_task(task_id)
           if not task_removed:
               log.error(f"Failed to remove task {task_id} from queue")
           
           # 3. Clean up other resources
           await cleanup_task_resources(task_id)
           
       except Exception as e:
           log.error(f"Cleanup failed for {task_id}: {e}")
   ```

### Phase 3: Fix Double Removal in cancel_all_tasks
1. **Remove redundant removal**:
   ```python
   # Old code:
   for task_ctx in list(all_tasks.values()):
       await cancelTask("User pressed Cancel All.", task_ctx=task_ctx)
       await TASK_QUEUE.remove_task(task_ctx.task_id)  # REDUNDANT!
   
   # New code:
   for task_ctx in list(all_tasks.values()):
       await cancelTask("User pressed Cancel All.", task_ctx=task_ctx)
       # cancelTask already handles cleanup via finally block
   ```

2. **Add cancellation coordinator**:
   ```python
   async def cancel_all_tasks():
       """Cancel all tasks with proper coordination"""
       all_tasks = list(TASK_QUEUE.tasks.values())
       
       # Phase 1: Stop accepting new tasks
       TASK_QUEUE.paused = True
       
       # Phase 2: Cancel all tasks concurrently
       cancel_tasks = []
       for task_ctx in all_tasks:
           cancel_task = asyncio.create_task(
               cancelTask("Cancel All", task_ctx=task_ctx)
           )
           cancel_tasks.append(cancel_task)
       
       # Phase 3: Wait for all cancellations
       await asyncio.gather(*cancel_tasks, return_exceptions=True)
       
       # Phase 4: Verify cleanup
       await verify_all_tasks_cleaned_up()
   ```

## Specific Code Changes Needed

### 1. Modify task_scheduler Function
```python
# Old code:
async def task_scheduler(task_ctx):
    try:
        await TASK_QUEUE.acquire_worker_slot(task_ctx.task_id)
        # ... execute task ...
    finally:
        try:
            await TASK_QUEUE.release_worker_slot(task_ctx.task_id)
        except Exception:
            log.error("Failed to release worker slot")

# New code:
async def task_scheduler(task_ctx):
    try:
        # Acquire slot with monitoring
        slot_acquired = await WORKER_SLOT_MANAGER.acquire_slot(
            task_ctx.task_id, 
            timeout=60
        )
        if not slot_acquired:
            raise Exception("Failed to acquire worker slot")
        
        # ... execute task ...
        
    finally:
        # Use coordinated cleanup
        await coordinated_cleanup(task_ctx.task_id)
```

### 2. Modify Background Cleanup Tasks
```python
# Old code:
async def _async_cleanup():
    try:
        await TASK_QUEUE.release_worker_slot(task_id)
    except Exception as slot_err:
        log.error(...)
    
    try:
        await TASK_QUEUE.remove_task(task_id)
    except Exception as remove_err:
        log.error(...)

# New code:
async def _async_cleanup():
    await coordinated_cleanup(task_id)
```

### 3. Add Error Recovery
```python
async def recover_stuck_slots():
    """Recover slots held too long"""
    while True:
        await asyncio.sleep(300)  # Check every 5 minutes
        
        stuck_tasks = await WORKER_SLOT_MANAGER.get_stuck_slots(max_hold_time=1800)
        for task_id in stuck_tasks:
            log.warning(f"Force releasing stuck slot: {task_id}")
            await WORKER_SLOT_MANAGER.force_release_slot(task_id)
```

## Testing Considerations

### Unit Tests
1. Test worker slot acquisition/release balance
2. Test concurrent slot operations
3. Test queue operation serialization
4. Test error recovery mechanisms

### Integration Tests
1. Test multiple simultaneous task completions
2. Test cancel_all_tasks with concurrent operations
3. Test slot recovery after failures
4. Test queue corruption prevention

### Stress Tests
1. Test with max worker slots (20+)
2. Test rapid task creation/cancellation
3. Test长时间运行 (24+ hours) for memory leaks
4. Test API rate limiting effects

## Files to Modify
1. **Create**: `worker_slot_manager.py` (new slot management)
2. **Create**: `queue_operation_manager.py` (safe queue operations)
3. **Modify**: `task_context.py` (use new managers)
4. **Modify**: `task_manager.py` (replace cleanup logic)
5. **Modify**: `__main__.py` (fix cancel_all_tasks, initialize managers)
6. **Modify**: `helper.py` (add monitoring functions)

## Expected Outcomes
1. **No more worker slot leaks**: Robust acquisition/release
2. **No race conditions**: Serialized queue operations  
3. **No double removals**: Single cleanup path
4. **Better reliability**: Error recovery mechanisms
5. **Easier debugging**: Slot monitoring and logging

---

## Implementation Summary (Verified)

### ✅ All Three Phases Completed:

**Phase 1: Robust Worker Slot Management**
- `worker_slot_manager.py` created with `WorkerSlotManager` class (131 lines)
- Lock-synchronized slot acquisition/release with `asyncio.Lock()` and `asyncio.Condition()`
- Timeout support for slot acquisition (default 60s)
- `get_stuck_slots()` identifies slots held > 30 minutes
- `recover_stuck_slots()` runs every 5 minutes to force release stuck slots

**Phase 2: Safe Queue Operations**
- `queue_operation_manager.py` created with `QueueOperationManager` class (65 lines)
- `_operation_lock` serializes potentially concurrent operations
- `safe_release_slot()` and `safe_remove_task()` prevent race conditions
- `coordinated_cleanup()` function handles proper cleanup order

**Phase 3: Double Removal Fixed**
- `cancel_all_tasks_confirm` no longer has redundant `remove_task()` call
- Uses `coordinated_cleanup()` only for non-running tasks

### Files Modified:
1. ✅ Created: `worker_slot_manager.py`
2. ✅ Created: `queue_operation_manager.py`
3. ✅ Modified: `__main__.py` (uses coordinated_cleanup, initializes recover_stuck_slots)
4. ✅ Modified: `task_context.py` (uses WorkerSlotManager)
5. ✅ Modified: `task_manager.py` (uses coordinated_cleanup)

### Specific Fixes Verified:

| Issue | Problem | Solution | Status |
|-------|---------|----------|--------|
| Worker Slot Leaks | Slots never released on failure | `release_slot()` with lock + idempotent check | ✅ |
| Race Conditions | Concurrent queue operations | `_operation_lock` serializes operations | ✅ |
| Double Removal | Redundant `remove_task()` calls | `coordinated_cleanup()` single path | ✅ |
| Stuck Tasks | Slots held indefinitely | `recover_stuck_slots()` every 5 min | ✅ |

### Result:
- **No more worker slot leaks**: Robust acquisition/release with lock synchronization
- **No race conditions**: Serialized queue operations prevent interleaving
- **No double removals**: Single `coordinated_cleanup()` path
- **Better reliability**: Error recovery via `recover_stuck_slots()`
- **Easier debugging**: Slot monitoring and logging throughout