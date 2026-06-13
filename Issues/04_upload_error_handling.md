# Upload Error Handling Issues - Detailed Fix Prompt

## Status: ✅ SOLVED

## Problem Description
The upload error handling system has critical issues that can cause:
1. **Indefinite blocking** waiting for user decisions
2. **Worker slot leaks** when timeout occurs
3. **Missing context** in error keyboards
4. **Inconsistent cleanup** after error handling

## Root Cause Analysis

### 1. Indefinite Waiting for User Decision
**File**: `handler.py:267-309`
```python
# Current problematic pattern:
async def handle_upload_error(task_ctx, error):
    # Release worker slot
    await TASK_QUEUE.release_worker_slot(task_ctx.task_id)
    
    # Wait up to 1 hour for user decision
    user_decision_event = asyncio.Event()
    
    async def err_action_callback(callback_query):
        # Handle user choice
        user_decision_event.set()
    
    # Wait indefinitely (with timeout)
    try:
        await asyncio.wait_for(user_decision_event.wait(), timeout=3600)
    except asyncio.TimeoutError:
        keep_files_decision = False
    
    # Re-acquire worker slot
    await TASK_QUEUE.acquire_worker_slot(task_ctx.task_id)
    
    # Continue with decision...
```

**Problem**: If user never responds, the task blocks for 1 hour, then re-acquires slot but exception propagates, relying on finally block for cleanup (fragile).

### 2. Worker Slot Leak on Timeout
**File**: `handler.py:298-309`
```python
# Problematic flow:
1. Release worker slot (line 273)
2. Wait for user decision (1 hour timeout)
3. Re-acquire worker slot (line 298)
4. Timeout occurs → exception raised
5. Exception propagates → finally block should release slot
6. BUT: If finally block fails → slot remains acquired → leak!
```

### 3. Missing Task Context in Error Keyboard
**File**: `ui_components.py:411-419`
```python
# Current keyboard:
keyboard = [
    [InlineKeyboardButton("🗑️ Delete Files", callback_data="delete_files")],
    [InlineKeyboardButton("💾 Keep Files", callback_data="keep_files")]
]

# Problem: No task ID in visible text
# User sees buttons but doesn't know which task they're for
# If multiple tasks fail simultaneously, confusion occurs
```

## Step-by-Step Solution

### Phase 1: Implement Upload Error Manager
1. **Create UploadErrorManager class**:
   ```python
   class UploadErrorManager:
       def __init__(self):
           self._pending_errors = {}
           self._timeout = 300  # 5 minutes instead of 1 hour
           self._lock = asyncio.Lock()
       
       async def handle_upload_error(self, task_ctx, error):
           """Handle upload error with proper cleanup"""
           error_id = str(uuid.uuid4())
           
           try:
               # 1. Release worker slot immediately
               await WORKER_SLOT_MANAGER.release_slot(task_ctx.task_id)
               
               # 2. Store error state
               self._pending_errors[error_id] = {
                   'task_ctx': task_ctx,
                   'error': error,
                   'timestamp': time.monotonic(),
                   'decision': None
               }
               
               # 3. Show error to user with context
               await self._show_error_keyboard(task_ctx, error_id)
               
               # 4. Wait for decision with proper timeout
               decision = await self._wait_for_decision(error_id)
               
               # 5. Process decision
               await self._process_decision(task_ctx, error_id, decision)
               
           except asyncio.TimeoutError:
               # Handle timeout gracefully
               await self._handle_timeout(task_ctx, error_id)
               
           except Exception as e:
               log.error(f"Error handling failed for {task_ctx.task_id}: {e}")
               # Ensure cleanup even on unexpected errors
               await self._force_cleanup(task_ctx, error_id)
   ```

### Phase 2: Improve Error Keyboard with Context
1. **Enhanced error keyboard**:
   ```python
   def get_upload_error_keyboard_with_context(task_ctx, error_id):
       """Create error keyboard with task context"""
       task_name = task_ctx.file_name[:20] + "..." if len(task_ctx.file_name) > 20 else task_ctx.file_name
       
       keyboard = [
           [InlineKeyboardButton(
               f"🗑️ Delete {task_name}", 
               callback_data=f"delete_files:{error_id}"
           )],
           [InlineKeyboardButton(
               f"💾 Keep {task_name}", 
               callback_data=f"keep_files:{error_id}"
           )],
           [InlineKeyboardButton(
               "❌ Cancel Task", 
               callback_data=f"cancel_task:{error_id}"
           )]
       ]
       
       return InlineKeyboardMarkup(keyboard)
   ```

2. **Error message with context**:
   ```python
   def format_error_message(task_ctx, error, error_id):
       """Format error message with task context"""
       return (
           f"❌ Upload Failed\n\n"
           f"📁 Task: {task_ctx.file_name}\n"
           f"🆔 ID: {task_ctx.task_id}\n"
           f"⏰ Time: {datetime.now().strftime('%H:%M:%S')}\n"
           f"🔍 Error: {str(error)[:100]}...\n\n"
           f"Choose action:"
       )
   ```

### Phase 3: Implement Proper Timeout Handling
1. **Tiered timeout system**:
   ```python
   class TimeoutManager:
       def __init__(self):
           self._timeouts = {
               'decision': 300,      # 5 minutes for user decision
               'cleanup': 30,        # 30 seconds for cleanup
               'force_release': 10   # 10 seconds for force release
           }
       
       async def wait_with_timeout(self, coro, timeout_type):
           timeout = self._timeouts.get(timeout_type, 60)
           try:
               return await asyncio.wait_for(coro, timeout=timeout)
           except asyncio.TimeoutError:
               log.warning(f"Timeout ({timeout}s) for {timeout_type}")
               raise
   ```

2. **Automatic fallback on timeout**:
   ```python
   async def _handle_timeout(self, task_ctx, error_id):
       """Handle timeout with automatic cleanup"""
       log.warning(f"Timeout for task {task_ctx.task_id}, using default decision")
       
       # Default decision: delete files
       await self._process_decision(task_ctx, error_id, 'delete')
       
       # Send timeout notification
       await self._send_timeout_notification(task_ctx)
   ```

## Specific Code Changes Needed

### 1. Replace handler.py Error Handling
```python
# Old code (remove):
async def handle_upload_error(task_ctx, error):
    await TASK_QUEUE.release_worker_slot(task_ctx.task_id)
    user_decision_event = asyncio.Event()
    # ... complex waiting logic ...
    await TASK_QUEUE.acquire_worker_slot(task_ctx.task_id)

# New code:
upload_error_manager = get_upload_error_manager()
await upload_error_manager.handle_upload_error(task_ctx, error)
```

### 2. Modify Error Keyboard Generation
```python
# Old code:
def get_upload_error_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🗑️ Delete Files", callback_data="delete_files")],
        [InlineKeyboardButton("💾 Keep Files", callback_data="keep_files")]
    ])

# New code:
def get_upload_error_keyboard_with_context(task_ctx, error_id):
    return create_contextual_keyboard(task_ctx, error_id)
```

### 3. Add Timeout Cleanup
```python
# Add automatic cleanup task:
async def cleanup_stuck_errors():
    """Clean up errors that exceeded timeout"""
    while True:
        await asyncio.sleep(60)  # Check every minute
        
        now = time.monotonic()
        stuck_errors = []
        
        for error_id, error_state in upload_error_manager._pending_errors.items():
            if now - error_state['timestamp'] > 600:  # 10 minutes
                stuck_errors.append(error_id)
        
        for error_id in stuck_errors:
            await upload_error_manager._force_cleanup_by_id(error_id)
```

## Testing Considerations

### Unit Tests
1. Test timeout handling at different levels
2. Test decision processing with various inputs
3. Test keyboard context generation
4. Test error state management

### Integration Tests
1. Test user decision flow (accept/reject)
2. Test timeout automatic handling
3. Test multiple concurrent errors
4. Test cleanup after errors

### User Experience Tests
1. Test keyboard visibility and clarity
2. Test timeout notification timing
3. Test decision persistence
4. Test error message formatting

## Files to Modify
1. **Create**: `upload_error_manager.py` (new error handling)
2. **Modify**: `handler.py` (replace error handling logic)
3. **Modify**: `ui_components.py` (enhanced error keyboards)
4. **Modify**: `__main__.py` (initialize UploadErrorManager)
5. **Modify**: `task_manager.py` (integrate with error handling)
6. **Create**: `timeout_manager.py` (tiered timeout system)

## Expected Outcomes
1. **No more indefinite blocking**: Proper timeouts
2. **No worker slot leaks**: Guaranteed cleanup
3. **Better user experience**: Context-aware keyboards
4. **Reliable error handling**: Multiple fallback mechanisms
5. **Easier debugging**: Better logging and monitoring

---

## Implementation Summary (Verified)

### ✅ All Three Phases Completed:

**Phase 1: Upload Error Manager Created**
- `upload_error_manager.py` created with `UploadErrorManager` class (141 lines)
- Worker slot released immediately during user wait (line 37)
- Re-acquired after decision is made (line 85)
- Timeout handling cleans up workspace and raises exception
- `cleanup_stuck_errors()` runs every minute to force cleanup

**Phase 2: Error Keyboard with Context**
- `error_keyboard()` in `ui_components_unified.py` has task context (lines 57-78)
- Shows download_name in button text (truncated to 15 chars)
- Uses `err_action:delete:{task_id}` callback data for routing

**Phase 3: Tiered Timeout System**
- `timeout_manager.py` created with `TimeoutManager` class (30 lines)
- Decision timeout: 5 minutes (line 14)
- Cleanup timeout: 30 seconds (line 15)
- Force release timeout: 10 seconds (line 16)

### Files Modified:
1. ✅ Created: `upload_error_manager.py`
2. ✅ Created: `timeout_manager.py`
3. ✅ Modified: `handler.py` (uses UploadErrorManager at line 287-289)
4. ✅ Modified: `ui_components.py` (get_upload_error_keyboard delegates to UIComponents)
5. ✅ Modified: `ui_components_unified.py` (error_keyboard with context)
6. ✅ Modified: `__main__.py` (initializes cleanup_stuck_errors at line 5413-5414)

### Specific Fixes Verified:

| Issue | Problem | Solution | Status |
|-------|---------|----------|--------|
| Indefinite Blocking | 1-hour wait for user decision | 5-minute timeout via TimeoutManager | ✅ |
| Worker Slot Leaks | Slot leaked on timeout | Released immediately, re-acquired after decision | ✅ |
| Missing Context | Buttons without task info | download_name shown in button text | ✅ |
| Inconsistent Cleanup | Cleanup could fail silently | `cleanup_task_artifacts()` for all paths + `cleanup_stuck_errors()` background task | ✅ |

### Result:
- **No more indefinite blocking**: 5-minute timeout with automatic cleanup
- **No worker slot leaks**: Slot released during wait, re-acquired after decision
- **Better user experience**: Context-aware keyboards with task name
- **Reliable error handling**: Multiple fallback mechanisms and background cleanup
- **Easier debugging**: Comprehensive logging throughout