# Parallel Task System - Fix Implementation Plan
**Created:** January 2, 2026
**Status:** 🟡 Ready for Implementation
**Estimated Time:** 12-16 hours (1.5-2 days)
**Priority:** HIGH - Production Blocker

---

## Overview

This plan addresses the critical and high-priority issues identified in the security audit. Fixes are organized into 4 phases that can be implemented sequentially, with each phase fully tested before moving to the next.

**Phases:**
1. **Phase 1:** Critical Concurrency Fixes (4-5 hours)
2. **Phase 2:** Resource Management & Cleanup (3-4 hours)
3. **Phase 3:** DoS Protection & Limits (2-3 hours)
4. **Phase 4:** Testing & Validation (3-4 hours)

---

## Phase 1: Critical Concurrency Fixes
**Priority:** 🔴 CRITICAL
**Time Estimate:** 4-5 hours
**Goal:** Eliminate race conditions and ensure thread-safe operations

### Task 1.1: Add Lock to user_tasks Dictionary
**File:** `colab_leecher/__main__.py`
**Time:** 1 hour

**Changes:**
```python
# At the top of file, after imports
import asyncio

# Line 56 - Update global declarations
user_tasks = {}
user_tasks_lock = asyncio.Lock()

# Update all write operations (lines 239, 286, 313, 356, 399, 915)
async with user_tasks_lock:
    user_tasks[user_id] = task_ctx

# Update all read/pop operations (line 865-866)
async with user_tasks_lock:
    if user_id in user_tasks:
        task_ctx = user_tasks.pop(user_id)
    else:
        task_ctx = None

if not task_ctx:
    # Handle case where no pending task found
    return

# Continue with task processing...
```

**Files to Modify:**
- `colab_leecher/__main__.py` (8 locations)

**Testing:**
- Test concurrent command submissions from same user
- Test rapid command switching (/tupload → /ytupload)
- Verify no lost tasks or state corruption

---

### Task 1.2: Make TaskQueue Operations Thread-Safe
**File:** `colab_leecher/utility/task_context.py`
**Time:** 2 hours

**Changes:**

```python
# task_context.py - Update TaskQueue class

class TaskQueue:
    def __init__(self):
        self.active_tasks: Dict[str, TaskContext] = {}
        self.summary_msg: Optional[Message] = None
        self.last_summary_update: float = 0
        self.summary_update_interval: float = 5.0
        self._lock = asyncio.Lock()  # Already exists
        self._summary_lock = asyncio.Lock()  # NEW: For summary updates

    async def add_task(self, task_ctx: TaskContext):
        """Register a new task (thread-safe)"""
        async with self._lock:
            self.active_tasks[task_ctx.task_id] = task_ctx
            log.info(f"Task {task_ctx.get_short_id()} added to queue. Total active: {len(self.active_tasks)}")

    async def remove_task(self, task_id: str) -> Optional[TaskContext]:
        """Remove a completed/cancelled task (thread-safe)"""
        async with self._lock:
            task_ctx = self.active_tasks.pop(task_id, None)
            if task_ctx:
                log.info(f"Task {task_ctx.get_short_id()} removed from queue. Remaining: {len(self.active_tasks)}")
            return task_ctx

    async def get_task(self, task_id: str) -> Optional[TaskContext]:
        """Get task by ID (thread-safe)"""
        async with self._lock:
            return self.active_tasks.get(task_id)

    async def get_user_tasks(self, user_id: int) -> List[TaskContext]:
        """Get all tasks for a specific user (thread-safe)"""
        async with self._lock:
            return [
                task_ctx for task_ctx in self.active_tasks.values()
                if task_ctx.user_id == user_id
            ]

    async def get_all_tasks(self) -> Dict[str, TaskContext]:
        """Get all active tasks (thread-safe copy)"""
        async with self._lock:
            return self.active_tasks.copy()

    def get_task_count(self) -> int:
        """Get number of active tasks (no lock needed - atomic operation)"""
        return len(self.active_tasks)
```

**Files to Modify:**
- `colab_leecher/utility/task_context.py` - Update TaskQueue class
- `colab_leecher/__main__.py` - Update all callers (add `await`)
  - Line 177: `await TASK_QUEUE.add_task(task_ctx)`
  - Line 208: `await TASK_QUEUE.remove_task(task_ctx.task_id)`
  - Line 1654: `await TASK_QUEUE.remove_task(task_ctx.task_id)`
- `colab_leecher/utility/task_dashboard.py` - Update callers
  - Line 30: `tasks = await TASK_QUEUE.get_all_tasks()`

**Testing:**
- Launch 5 tasks simultaneously
- Cancel tasks while others are launching
- Verify task count consistency

---

### Task 1.3: Add Summary Dashboard Locking
**File:** `colab_leecher/utility/task_dashboard.py`
**Time:** 1 hour

**Changes:**

```python
# task_dashboard.py

async def update_summary_dashboard(client=None) -> Optional[Message]:
    """Update or create the summary dashboard (thread-safe)"""
    if not client:
        client = colab_bot

    # Use lock to prevent concurrent updates
    async with TASK_QUEUE._summary_lock:
        tasks = await TASK_QUEUE.get_all_tasks()

        # If no active tasks, delete summary message if it exists
        if not tasks:
            if TASK_QUEUE.summary_msg:
                try:
                    await TASK_QUEUE.summary_msg.delete()
                    TASK_QUEUE.summary_msg = None
                    log.info("Summary dashboard deleted (no active tasks)")
                except Exception as e:
                    log.warning(f"Failed to delete summary: {e}")
            return None

        # ... rest of function remains the same
```

**Files to Modify:**
- `colab_leecher/utility/task_dashboard.py`

**Testing:**
- Complete 3 tasks simultaneously
- Verify no duplicate summary messages
- Check for Telegram API errors

---

### Task 1.4: Improve Exception Handling
**File:** `colab_leecher/__main__.py`
**Time:** 30 minutes

**Changes:**

```python
# Line 870-874 - Better exception logging
if task_ctx.status_msg:
    try:
        await task_ctx.status_msg.delete()
    except Exception as e:
        log.warning(f"Failed to delete status message for task {task_ctx.get_short_id()}: {e}")

# Line 979-982 - Add done callback for background tasks
async_task = asyncio.create_task(
    run_parallel_task(client, message, task_ctx)
)
task_ctx.async_task = async_task

# Add exception handler
def handle_task_exception(task):
    try:
        task.result()  # Raises if task had exception
    except asyncio.CancelledError:
        log.info(f"Task cancelled normally")
    except Exception as e:
        log.exception(f"Unhandled exception in background task: {e}")
        # Optionally notify user here

async_task.add_done_callback(handle_task_exception)
```

**Files to Modify:**
- `colab_leecher/__main__.py` (multiple locations)

---

## Phase 2: Resource Management & Cleanup
**Priority:** 🔴 CRITICAL
**Time Estimate:** 3-4 hours
**Goal:** Prevent disk space and memory leaks

### Task 2.1: Add Resource Cleanup in run_parallel_task()
**File:** `colab_leecher/__main__.py`
**Time:** 1.5 hours

**Changes:**

```python
# Line 136 - Update run_parallel_task function

async def run_parallel_task(client, message, task_ctx):
    """
    Run a download/upload task in parallel mode.
    Now includes comprehensive resource cleanup.
    """
    import shutil
    task_id_str = f"[{task_ctx.get_short_id()}]"
    log.info(f"Starting parallel task {task_id_str} for user {message.from_user.id}")

    try:
        # Mark task as started
        task_ctx.mark_started()

        # Setup task_error and paths aliases for compatibility
        # ... existing code ...

        # Register in global task queue
        await TASK_QUEUE.add_task(task_ctx)
        log.info(f"Task {task_id_str} registered in TASK_QUEUE. Total active: {TASK_QUEUE.get_task_count()}")

        # Run the task via taskScheduler
        log.info(f"Task {task_id_str} calling taskScheduler...")
        await taskScheduler(task_ctx)
        log.info(f"Task {task_id_str} taskScheduler completed")

    except asyncio.CancelledError:
        log.warning(f"Task {task_id_str} was cancelled")
        task_ctx.error.set_error("Task cancelled by user")

        # Notify user of cancellation
        try:
            if task_ctx.status_msg:
                await task_ctx.status_msg.edit_text(
                    f"❌ **Task Cancelled**\n\n"
                    f"**Task ID:** `{task_ctx.get_short_id()}`\n"
                    f"**Reason:** User requested cancellation"
                )
        except Exception:
            pass
        raise  # Re-raise to ensure proper cancellation

    except Exception as e:
        log.exception(f"Task {task_id_str} failed with exception")
        task_ctx.error.set_error(str(e))

        # Notify user of error
        try:
            if task_ctx.status_msg:
                await task_ctx.status_msg.edit_text(
                    f"❌ **Task Failed**\n\n"
                    f"**Task ID:** `{task_ctx.get_short_id()}`\n"
                    f"**Error:** {str(e)[:200]}"
                )
        except Exception:
            pass

    finally:
        # Mark as completed
        task_ctx.mark_completed()

        # Remove from queue
        await TASK_QUEUE.remove_task(task_ctx.task_id)
        log.info(f"Task {task_id_str} removed from TASK_QUEUE. Remaining: {TASK_QUEUE.get_task_count()}")

        # ===== NEW: CLEANUP TASK WORKSPACE =====
        cleanup_success = False
        try:
            if os.path.exists(task_ctx.work_path):
                # Only cleanup if task failed or was cancelled
                # Successful uploads already cleanup in handler.py
                if task_ctx.error.state or task_ctx.is_cancelled:
                    log.info(f"Cleaning up workspace for failed/cancelled task: {task_ctx.work_path}")
                    shutil.rmtree(task_ctx.work_path, ignore_errors=True)
                    cleanup_success = True
                    log.info(f"Successfully cleaned up {task_ctx.work_path}")
                else:
                    # Successful task - handler.py should have cleaned up
                    # But verify and cleanup if files still exist
                    if os.listdir(task_ctx.work_path):
                        log.warning(f"Workspace not empty after successful task, cleaning up: {task_ctx.work_path}")
                        shutil.rmtree(task_ctx.work_path, ignore_errors=True)
                        cleanup_success = True
        except Exception as cleanup_err:
            log.error(f"Failed to cleanup workspace {task_ctx.work_path}: {cleanup_err}")

        if cleanup_success:
            log.info(f"Task {task_id_str} workspace cleanup complete")
        # ===== END CLEANUP =====

        # Update dashboard
        await force_update_summary()

        log.info(f"Task {task_id_str} cleanup complete")
```

**Files to Modify:**
- `colab_leecher/__main__.py`

**Testing:**
- Create task that fails during download
- Verify workspace is deleted
- Check disk space isn't accumulating

---

### Task 2.2: Implement Actual Task Cancellation
**File:** `colab_leecher/utility/handler.py`
**Time:** 1.5 hours

**Changes:**

```python
# handler.py - Update cancelTask function

async def cancelTask(Reason: str, task_ctx: TaskContext = None):
    """
    Cancel a task and clean up resources.
    Now actually cancels the asyncio task.
    """
    global BOT, BotTimes, Messages, MSG, TaskError, TRANSFER, Paths, OWNER, colab_bot, log

    # Use task_ctx or fall back to globals
    transfer_obj = task_ctx.transfer if task_ctx else TRANSFER
    error_obj = task_ctx.error if task_ctx else TaskError
    messages_obj = task_ctx.messages if task_ctx else Messages
    start_time = task_ctx.started_at if task_ctx else BotTimes.start_time

    task_failed = error_obj.state
    final_reason = error_obj.text if task_failed and error_obj.text else Reason

    if task_ctx:
        log.warning(f"Task {task_ctx.get_short_id()} cancellation/completion triggered. Reason: {final_reason}")
        task_ctx.mark_cancelled()

        # ===== NEW: ACTUALLY CANCEL THE ASYNCIO TASK =====
        if task_ctx.async_task and not task_ctx.async_task.done():
            log.info(f"Cancelling asyncio task for {task_ctx.get_short_id()}")
            task_ctx.async_task.cancel()

            # Wait for task to acknowledge cancellation
            try:
                await task_ctx.async_task
            except asyncio.CancelledError:
                log.info(f"Task {task_ctx.get_short_id()} successfully cancelled")
            except Exception as e:
                log.error(f"Task {task_ctx.get_short_id()} raised exception during cancellation: {e}")
        # ===== END CANCELLATION =====
    else:
        log.warning(f"Task cancellation/completion triggered. Final Reason: {final_reason}")

    # --- Generate Report String ---
    # ... existing report generation code remains the same ...

    # ... rest of function remains the same ...
```

**Files to Modify:**
- `colab_leecher/utility/handler.py`

**Testing:**
- Start download task
- Press cancel button immediately
- Verify download stops (check network activity)
- Confirm workspace is cleaned up

---

### Task 2.3: Add Periodic Cleanup Task
**File:** `colab_leecher/__main__.py`
**Time:** 1 hour

**Changes:**

```python
# Add new function near run_parallel_task()

async def periodic_cleanup_task():
    """
    Background task to periodically clean up old completed tasks.
    Runs every hour to prevent memory leaks.
    """
    while True:
        try:
            await asyncio.sleep(3600)  # Every 1 hour

            log.info("Running periodic cleanup of old completed tasks...")
            await TASK_QUEUE.clear_completed_tasks(max_age_hours=2)

            # Also cleanup old workspace directories
            cleanup_old_workspaces()

            log.info("Periodic cleanup completed")
        except Exception as e:
            log.error(f"Error in periodic cleanup: {e}")


def cleanup_old_workspaces():
    """
    Clean up workspace directories older than 24 hours.
    Handles case where tasks crashed without cleanup.
    """
    import shutil
    import time
    from .utility.variables import Paths

    try:
        work_base = Paths.WORK_PATH
        if not os.path.exists(work_base):
            return

        now = time.time()
        cleaned_count = 0

        for item in os.listdir(work_base):
            item_path = os.path.join(work_base, item)

            # Skip if not a directory
            if not os.path.isdir(item_path):
                continue

            # Check if directory is older than 24 hours
            try:
                mtime = os.path.getmtime(item_path)
                age_hours = (now - mtime) / 3600

                if age_hours > 24:
                    log.info(f"Removing old workspace (age: {age_hours:.1f}h): {item_path}")
                    shutil.rmtree(item_path, ignore_errors=True)
                    cleaned_count += 1
            except Exception as e:
                log.warning(f"Could not check/remove {item_path}: {e}")

        if cleaned_count > 0:
            log.info(f"Cleaned up {cleaned_count} old workspace directories")

    except Exception as e:
        log.error(f"Error cleaning old workspaces: {e}")


# In the bot startup code (find where bot starts)
# Add after colab_bot initialization:

@colab_bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    # ... existing start code ...

    # Start periodic cleanup task (only once)
    if not hasattr(colab_bot, '_cleanup_task_started'):
        asyncio.create_task(periodic_cleanup_task())
        colab_bot._cleanup_task_started = True
        log.info("Started periodic cleanup background task")
```

**Alternative Startup Location:**
If there's a main bot startup function, add there instead:

```python
# Find the main bot run function and add:
asyncio.create_task(periodic_cleanup_task())
```

**Files to Modify:**
- `colab_leecher/__main__.py`

**Testing:**
- Let bot run for 2+ hours
- Create and complete several tasks
- Verify old tasks are removed from memory
- Check disk space cleanup works

---

## Phase 3: DoS Protection & Limits
**Priority:** 🟠 HIGH
**Time Estimate:** 2-3 hours
**Goal:** Prevent resource exhaustion attacks

### Task 3.1: Implement Task Limits
**File:** `colab_leecher/utility/task_context.py`
**Time:** 1 hour

**Changes:**

```python
# task_context.py - Update TaskQueue class

class TaskQueue:
    # Add constants at class level
    MAX_TASKS_PER_USER = 5
    MAX_TOTAL_TASKS = 20

    def __init__(self):
        # ... existing code ...

    async def can_start_task(self, user_id: int = None) -> tuple[bool, str]:
        """
        Check if a new task can be started.

        Returns:
            (can_start, reason) - True/False and reason message
        """
        async with self._lock:
            # Global limit check
            total_tasks = len(self.active_tasks)
            if total_tasks >= self.MAX_TOTAL_TASKS:
                return False, f"System limit reached ({total_tasks}/{self.MAX_TOTAL_TASKS} tasks active). Please wait."

            # Per-user limit check
            if user_id:
                user_tasks = [
                    task for task in self.active_tasks.values()
                    if task.user_id == user_id
                ]
                user_task_count = len(user_tasks)

                if user_task_count >= self.MAX_TASKS_PER_USER:
                    return False, f"You have {user_task_count}/{self.MAX_TASKS_PER_USER} tasks active. Please wait for some to complete."

            return True, "OK"
```

**Files to Modify:**
- `colab_leecher/utility/task_context.py`

---

### Task 3.2: Enforce Limits in Command Handlers
**File:** `colab_leecher/__main__.py`
**Time:** 1 hour

**Changes:**

```python
# Update ALL command handlers (/tupload, /ytupload, /igupload, /drupload, /gdupload)
# Add this check BEFORE creating TaskContext

@colab_bot.on_message(filters.command("tupload") & filters.private)
async def telegram_upload(client, message):
    global BOT, src_request_msg, user_tasks
    user_id = message.from_user.id
    log.info(f"Received /tupload from {user_id}")

    # ===== NEW: CHECK TASK LIMITS =====
    can_start, reason = await TASK_QUEUE.can_start_task(user_id)
    if not can_start:
        await message.reply_text(
            f"❌ **Cannot Start Task**\n\n"
            f"{reason}\n\n"
            f"Use /tasks to see your active tasks."
        )
        return
    # ===== END CHECK =====

    # NEW: Parallel task mode - create TaskContext immediately
    task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="leech"
    )
    # ... rest of function ...
```

**Repeat for:**
- `telegram_upload()` - Line 224
- `gdrive_upload()` - Line 272
- `dir_upload()` - Line 299
- `yt_upload()` - Line 342
- `ig_upload()` - Line 385

**Files to Modify:**
- `colab_leecher/__main__.py` (5 command handlers)

---

### Task 3.3: Add Rate Limiting (Optional but Recommended)
**File:** `colab_leecher/utility/rate_limiter.py` (NEW FILE)
**Time:** 30 minutes

**Changes:**

```python
# NEW FILE: colab_leecher/utility/rate_limiter.py

"""
Rate limiting for task creation to prevent abuse.
"""

import time
import logging
from collections import defaultdict
from typing import Dict, List

log = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple rate limiter for task creation.
    Prevents users from spamming task creation commands.
    """

    def __init__(self, max_requests: int = 10, window_seconds: int = 60):
        """
        Args:
            max_requests: Maximum requests allowed in window
            window_seconds: Time window in seconds
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.user_requests: Dict[int, List[float]] = defaultdict(list)

    def can_proceed(self, user_id: int) -> tuple[bool, str]:
        """
        Check if user can create a new task.

        Returns:
            (allowed, message) - True/False and reason
        """
        now = time.time()

        # Remove old timestamps outside window
        self.user_requests[user_id] = [
            ts for ts in self.user_requests[user_id]
            if now - ts < self.window_seconds
        ]

        # Check if under limit
        request_count = len(self.user_requests[user_id])
        if request_count >= self.max_requests:
            return False, f"Rate limit exceeded. You can create {self.max_requests} tasks per minute. Please wait."

        # Record this request
        self.user_requests[user_id].append(now)
        return True, "OK"

    def cleanup_old_entries(self):
        """Remove entries for users who haven't made requests recently"""
        now = time.time()
        users_to_remove = []

        for user_id, timestamps in self.user_requests.items():
            # Remove timestamps older than window
            recent = [ts for ts in timestamps if now - ts < self.window_seconds]

            if not recent:
                users_to_remove.append(user_id)
            else:
                self.user_requests[user_id] = recent

        for user_id in users_to_remove:
            del self.user_requests[user_id]


# Global rate limiter instance
RATE_LIMITER = RateLimiter(max_requests=10, window_seconds=60)
```

**Usage in __main__.py:**

```python
# At top of file
from .utility.rate_limiter import RATE_LIMITER

# In each command handler, add BEFORE task limit check:
@colab_bot.on_message(filters.command("tupload") & filters.private)
async def telegram_upload(client, message):
    user_id = message.from_user.id

    # Rate limit check
    allowed, reason = RATE_LIMITER.can_proceed(user_id)
    if not allowed:
        await message.reply_text(f"❌ {reason}")
        return

    # Task limit check
    can_start, reason = await TASK_QUEUE.can_start_task(user_id)
    # ... rest of code ...
```

**Files to Create:**
- `colab_leecher/utility/rate_limiter.py` (NEW)

**Files to Modify:**
- `colab_leecher/__main__.py` (5 command handlers)

---

## Phase 4: Testing & Validation
**Priority:** 🟢 REQUIRED
**Time Estimate:** 3-4 hours
**Goal:** Ensure all fixes work correctly

### Task 4.1: Create Test Suite
**File:** `tests/test_parallel_tasks.py` (NEW)
**Time:** 2 hours

**Changes:**

```python
# NEW FILE: tests/test_parallel_tasks.py

"""
Test suite for parallel task system.
Run with: pytest tests/test_parallel_tasks.py -v
"""

import pytest
import asyncio
from colab_leecher.utility.task_context import TaskQueue, create_task_context, TASK_QUEUE


class TestTaskQueue:
    """Test TaskQueue thread safety"""

    @pytest.mark.asyncio
    async def test_concurrent_add_remove(self):
        """Test adding and removing tasks concurrently"""
        queue = TaskQueue()

        async def add_task(user_id):
            ctx = create_task_context(user_id, user_id, "leech")
            await queue.add_task(ctx)
            return ctx.task_id

        async def remove_task(task_id):
            await asyncio.sleep(0.1)  # Small delay
            await queue.remove_task(task_id)

        # Add 10 tasks concurrently
        task_ids = await asyncio.gather(*[add_task(i) for i in range(10)])

        assert queue.get_task_count() == 10

        # Remove them concurrently
        await asyncio.gather(*[remove_task(tid) for tid in task_ids])

        assert queue.get_task_count() == 0

    @pytest.mark.asyncio
    async def test_task_limits(self):
        """Test task limit enforcement"""
        queue = TaskQueue()
        user_id = 12345

        # Add tasks up to limit
        for i in range(queue.MAX_TASKS_PER_USER):
            ctx = create_task_context(user_id, user_id, "leech")
            await queue.add_task(ctx)

        # Should be at limit
        can_start, reason = await queue.can_start_task(user_id)
        assert not can_start
        assert "limit" in reason.lower()

        # Remove one task
        tasks = await queue.get_user_tasks(user_id)
        await queue.remove_task(tasks[0].task_id)

        # Should now be able to start
        can_start, reason = await queue.can_start_task(user_id)
        assert can_start


class TestRateLimiter:
    """Test rate limiting"""

    def test_rate_limit_enforcement(self):
        """Test rate limiter blocks excessive requests"""
        from colab_leecher.utility.rate_limiter import RateLimiter

        limiter = RateLimiter(max_requests=5, window_seconds=60)
        user_id = 12345

        # First 5 should succeed
        for i in range(5):
            allowed, _ = limiter.can_proceed(user_id)
            assert allowed

        # 6th should fail
        allowed, reason = limiter.can_proceed(user_id)
        assert not allowed
        assert "rate limit" in reason.lower()


class TestResourceCleanup:
    """Test resource cleanup"""

    @pytest.mark.asyncio
    async def test_workspace_cleanup_on_error(self):
        """Test that workspace is cleaned up when task fails"""
        import os
        import shutil

        ctx = create_task_context(12345, 12345, "leech")

        # Create workspace
        os.makedirs(ctx.work_path, exist_ok=True)
        test_file = os.path.join(ctx.work_path, "test.txt")
        with open(test_file, "w") as f:
            f.write("test")

        assert os.path.exists(ctx.work_path)

        # Simulate cleanup
        if os.path.exists(ctx.work_path):
            shutil.rmtree(ctx.work_path, ignore_errors=True)

        assert not os.path.exists(ctx.work_path)


# Integration tests
class TestConcurrentTasks:
    """Test actual concurrent task execution"""

    @pytest.mark.asyncio
    async def test_multiple_tasks_dont_interfere(self):
        """Test that concurrent tasks maintain separate state"""
        task1 = create_task_context(111, 111, "leech")
        task2 = create_task_context(222, 222, "leech")

        # Verify separate paths
        assert task1.work_path != task2.work_path
        assert task1.task_id != task2.task_id

        # Verify separate transfer stats
        task1.transfer.down_bytes = 1000
        task2.transfer.down_bytes = 2000

        assert task1.transfer.down_bytes == 1000
        assert task2.transfer.down_bytes == 2000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Files to Create:**
- `tests/test_parallel_tasks.py` (NEW)
- `tests/__init__.py` (if doesn't exist)

**Dependencies to Add:**
```bash
pip install pytest pytest-asyncio
```

---

### Task 4.2: Manual Testing Checklist
**Time:** 1-2 hours

**Create:** `TESTING_CHECKLIST.md`

```markdown
# Parallel Tasks Testing Checklist

## Concurrency Tests
- [ ] Launch 3 tasks simultaneously from same user
- [ ] Launch 5 tasks from different users simultaneously
- [ ] Cancel task while others are running
- [ ] Start new task while 4 are running

## Resource Management Tests
- [ ] Cancel task midway - verify workspace deleted
- [ ] Let task fail with error - verify workspace deleted
- [ ] Complete task successfully - verify workspace deleted
- [ ] Check disk usage before/after 10 tasks

## Limit Tests
- [ ] Try to create 6th task as same user (should fail)
- [ ] Try to create 21st task globally (should fail)
- [ ] Complete one task, verify can start new one
- [ ] Spam 15 commands in 30 seconds (rate limit should kick in)

## Error Handling Tests
- [ ] Invalid URL - verify error message
- [ ] Network timeout - verify cleanup
- [ ] Download failure - verify workspace cleanup
- [ ] Telegram upload failure - verify error handling

## Dashboard Tests
- [ ] Launch 5 tasks - verify all show in dashboard
- [ ] Complete task - verify dashboard updates
- [ ] Cancel task - verify dashboard updates
- [ ] All tasks complete - verify dashboard deleted

## Long-Running Tests
- [ ] Let bot run for 3+ hours
- [ ] Verify periodic cleanup runs
- [ ] Check memory usage stays stable
- [ ] Verify old workspaces are removed

## Edge Cases
- [ ] User sends /tupload twice rapidly
- [ ] User sends /tupload then /ytupload before providing URL
- [ ] Cancel task that's already completed
- [ ] Delete bot message manually
```

---

### Task 4.3: Performance Testing
**Time:** 1 hour

**Test Scenarios:**

1. **Baseline:** Single task performance (record time)
2. **3 Parallel Tasks:** Same files, measure total time (should be ~3x faster)
3. **5 Parallel Tasks:** Monitor memory usage
4. **10 Sequential Tasks:** Compare to baseline
5. **Stress Test:** 20 tasks total (max limit), verify system stability

**Metrics to Collect:**
- Memory usage (before/after/during)
- Disk space usage
- Task completion times
- Error rates
- Telegram API rate limits hit

---

## Implementation Order & Dependencies

```
Phase 1.1 (user_tasks lock)
  ↓
Phase 1.2 (TaskQueue locks)
  ↓
Phase 1.3 (Summary lock) ← depends on 1.2
  ↓
Phase 1.4 (Exception handling)
  ↓
Phase 2.1 (Resource cleanup) ← depends on 1.2
  ↓
Phase 2.2 (Task cancellation) ← depends on 2.1
  ↓
Phase 2.3 (Periodic cleanup) ← depends on 2.1
  ↓
Phase 3.1 (Task limits) ← depends on 1.2
  ↓
Phase 3.2 (Enforce limits) ← depends on 3.1
  ↓
Phase 3.3 (Rate limiting) ← independent
  ↓
Phase 4.1 (Tests) ← depends on all above
  ↓
Phase 4.2 & 4.3 (Manual testing) ← final validation
```

---

## Files Modified Summary

### Existing Files to Modify:
1. **colab_leecher/__main__.py** - ~15 locations
2. **colab_leecher/utility/task_context.py** - TaskQueue class
3. **colab_leecher/utility/task_dashboard.py** - Add locking
4. **colab_leecher/utility/handler.py** - Update cancelTask

### New Files to Create:
5. **colab_leecher/utility/rate_limiter.py** - Rate limiting
6. **tests/test_parallel_tasks.py** - Test suite
7. **TESTING_CHECKLIST.md** - Manual testing guide

---

## Rollback Plan

If issues arise during implementation:

1. **Git Branch Strategy:**
   ```bash
   git checkout -b fix/parallel-tasks-safety
   # Make changes
   git commit -m "Phase 1.1: Add user_tasks locking"
   # Test thoroughly
   # If OK, continue. If not:
   git checkout master
   ```

2. **Feature Flag (Optional):**
   ```python
   ENABLE_PARALLEL_TASKS = True  # Set to False to disable

   if not ENABLE_PARALLEL_TASKS:
       await message.reply_text("Parallel tasks temporarily disabled")
       return
   ```

3. **Backup Before Starting:**
   ```bash
   git add .
   git commit -m "Pre-fix backup: parallel tasks working state"
   git tag backup-before-safety-fixes
   ```

---

## Success Criteria

### Phase 1 Complete:
- ✅ No race condition errors in logs
- ✅ Concurrent task launches work reliably
- ✅ No duplicate/lost tasks

### Phase 2 Complete:
- ✅ Cancelled tasks actually stop
- ✅ Disk space doesn't grow indefinitely
- ✅ No orphaned processes

### Phase 3 Complete:
- ✅ Cannot create more than 5 tasks per user
- ✅ Cannot create more than 20 tasks total
- ✅ Rate limiting prevents spam

### Phase 4 Complete:
- ✅ All tests pass
- ✅ Manual testing checklist 100% complete
- ✅ Bot runs stable for 24+ hours
- ✅ Memory usage stays under 2GB with 10 tasks

---

## Post-Implementation

### Documentation Updates Needed:
1. Update `README.md` with new limits
2. Document rate limiting for users
3. Add architecture diagram showing task lifecycle
4. Create troubleshooting guide

### Monitoring:
1. Add metrics for:
   - Active task count
   - Task success/failure rate
   - Average task duration
   - Memory usage over time
2. Set up alerts for:
   - Task count > 15
   - Memory > 3GB
   - Disk space < 5GB

---

## Questions for Review

Before starting implementation, confirm:

1. **Task Limits:** Are 5 per user / 20 total appropriate for your use case?
2. **Rate Limiting:** Is 10 tasks/minute reasonable?
3. **Cleanup Timing:** Is 2 hours for completed tasks and 24 hours for workspaces OK?
4. **Testing:** Can you allocate 3-4 hours for thorough testing?
5. **Rollback:** Do you have a staging environment or should we use feature flags?

---

**End of Fix Plan**
**Next Step:** Review this plan, adjust limits/timings as needed, then begin Phase 1.1

Ready to proceed? 🚀
