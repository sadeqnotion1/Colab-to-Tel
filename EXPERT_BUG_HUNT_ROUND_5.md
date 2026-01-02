# 🌟 Expert Bug Hunt Round 5: Production Observability & Runtime Integrity
**Difficulty:** Master Level
**Focus:** Observability, Subtle Runtime Bugs, Operational Excellence, Long-Running Stability
**Scope:** Bugs that only appear after hours/days of runtime, monitoring gaps, production blind spots

---

## 🎯 Mission Brief

**Rounds 1-4 Recap:**
- ✅ Round 1-2: Fixed obvious bugs (deadlocks, memory leaks, message errors)
- ✅ Round 3: Resolved concurrency bugs (cancellation, aria2, cleanup races)
- ✅ Round 4: Hardened security (zip slip, DoS, injection attacks)

**Round 5 Focus:**
The system now survives attacks and stress tests, but can you **observe** what's happening inside? Can you **debug production issues** when users report "it's slow" or "it crashed yesterday"? This round hunts for:
- **Observability gaps** - Can't debug what you can't see
- **Subtle runtime bugs** - Only appear after hours/days of uptime
- **Resource creep** - Slow leaks that crash the bot after 3 days
- **Silent degradation** - Performance slowly decays without errors
- **Production blind spots** - No way to know system is unhealthy until it's too late

---

## 📋 Investigation Categories

### 🔍 Category A: Observability & Monitoring Gaps
**Expected Findings:** 8-12 critical monitoring gaps
**Impact:** Can't debug production issues, blind to system health

#### A1. No Metrics Collection
**The Problem:** Can you answer these questions without SSH'ing into the server?
- How many tasks are currently running?
- What's the average download speed across all tasks?
- How many tasks failed in the last hour?
- What's the current memory usage?
- How many aria2 processes are alive?
- What's the average task completion time?

**Search Commands:**
```bash
# Find any metrics collection
grep -r "prometheus\|metrics\|gauge\|counter" --include="*.py" colab_leecher/

# Find any health check endpoints
grep -r "health\|status\|ping" --include="*.py" colab_leecher/

# Find any performance logging
grep -r "perf\|timing\|duration\|elapsed" --include="*.py" colab_leecher/
```

**Expected:** No structured metrics, no monitoring hooks
**Impact:** Blind to system health, can't diagnose slow performance

**Fix Example:**
```python
from dataclasses import dataclass
from datetime import datetime
from collections import deque
from typing import Deque

@dataclass
class SystemMetrics:
    """Real-time system health metrics"""
    active_tasks: int = 0
    completed_tasks_total: int = 0
    failed_tasks_total: int = 0
    cancelled_tasks_total: int = 0
    total_bytes_downloaded: int = 0
    total_bytes_uploaded: int = 0
    average_download_speed: float = 0.0  # MB/s
    peak_memory_usage_mb: float = 0.0
    aria2_restarts: int = 0
    telegram_api_errors: int = 0

    # Rolling windows for averages
    recent_speeds: Deque[float] = None
    recent_completion_times: Deque[float] = None

    def __post_init__(self):
        self.recent_speeds = deque(maxlen=100)
        self.recent_completion_times = deque(maxlen=50)

    def record_download_speed(self, speed_mbps: float):
        self.recent_speeds.append(speed_mbps)
        self.average_download_speed = sum(self.recent_speeds) / len(self.recent_speeds)

    def get_health_summary(self) -> str:
        """Human-readable health check"""
        return f"""
🏥 System Health Report
├─ Active Tasks: {self.active_tasks}
├─ Success Rate: {self._success_rate():.1f}%
├─ Avg Speed: {self.average_download_speed:.2f} MB/s
├─ Total Downloaded: {self.total_bytes_downloaded / 1e9:.2f} GB
├─ Total Uploaded: {self.total_bytes_uploaded / 1e9:.2f} GB
├─ Peak Memory: {self.peak_memory_usage_mb:.0f} MB
└─ Aria2 Stability: {self.aria2_restarts} restarts
"""

    def _success_rate(self) -> float:
        total = self.completed_tasks_total + self.failed_tasks_total
        if total == 0:
            return 100.0
        return (self.completed_tasks_total / total) * 100

# Add to TaskManager
class TaskManager:
    def __init__(self):
        self.metrics = SystemMetrics()
        # ... existing code

    async def get_health_check(self) -> dict:
        """Health check endpoint for monitoring"""
        import psutil
        process = psutil.Process()

        return {
            "status": "healthy",
            "uptime_seconds": time.time() - self.start_time,
            "metrics": {
                "active_tasks": len(self.active_tasks),
                "completed": self.metrics.completed_tasks_total,
                "failed": self.metrics.failed_tasks_total,
                "success_rate": self.metrics._success_rate(),
                "memory_mb": process.memory_info().rss / 1024 / 1024,
                "cpu_percent": process.cpu_percent(),
            },
            "aria2": {
                "alive": await self._check_aria2_alive(),
                "restarts": self.metrics.aria2_restarts,
            }
        }
```

**Test:**
```python
# Command: /health
# Expected output:
"""
🏥 System Health Report
├─ Active Tasks: 5
├─ Success Rate: 94.7%
├─ Avg Speed: 12.34 MB/s
├─ Total Downloaded: 245.67 GB
├─ Total Uploaded: 198.32 GB
├─ Peak Memory: 1247 MB
└─ Aria2 Stability: 0 restarts
"""
```

---

#### A2. No Structured Logging
**The Problem:** Logs are unstructured, can't parse or analyze them
- No log levels in many places (everything is INFO?)
- No request IDs to trace operations
- No timing information for slow operations
- Can't filter logs by user, task, or component

**Search Commands:**
```bash
# Find print() statements (should be logger.debug)
grep -r "print(" --include="*.py" colab_leecher/

# Find logger calls without level indication
grep -r "logger\." --include="*.py" colab_leecher/ | grep -v "logger.info\|logger.error\|logger.debug\|logger.warning"

# Find operations without timing logs
grep -r "async def.*download\|async def.*upload" --include="*.py" colab_leecher/
```

**Expected:** Inconsistent logging, no structured data
**Impact:** Can't diagnose "task was slow" or "why did this fail?"

**Fix Example:**
```python
import logging
import time
from contextvars import ContextVar
from functools import wraps

# Request ID for tracing operations across logs
request_id: ContextVar[str] = ContextVar('request_id', default='no-context')

class StructuredLogger:
    """Logger with structured fields and request tracing"""

    def __init__(self, name: str):
        self.logger = logging.getLogger(name)

    def _log(self, level: int, msg: str, **kwargs):
        rid = request_id.get()
        extra_fields = " ".join(f"{k}={v}" for k, v in kwargs.items())
        full_msg = f"[{rid}] {msg} {extra_fields}".strip()
        self.logger.log(level, full_msg)

    def info(self, msg: str, **kwargs):
        self._log(logging.INFO, msg, **kwargs)

    def error(self, msg: str, **kwargs):
        self._log(logging.ERROR, msg, **kwargs)

    def debug(self, msg: str, **kwargs):
        self._log(logging.DEBUG, msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        self._log(logging.WARNING, msg, **kwargs)

def timed_operation(operation_name: str):
    """Decorator to log operation timing"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.time()
            logger = StructuredLogger(func.__module__)
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start
                logger.info(f"{operation_name} completed",
                           duration_ms=f"{duration*1000:.0f}",
                           status="success")
                return result
            except Exception as e:
                duration = time.time() - start
                logger.error(f"{operation_name} failed",
                            duration_ms=f"{duration*1000:.0f}",
                            status="error",
                            error=str(e))
                raise
        return wrapper
    return decorator

# Usage
@timed_operation("download_file")
async def download_with_aria2(task_id: str, url: str):
    # Set request ID for all logs in this context
    request_id.set(f"task-{task_id}")
    logger = StructuredLogger(__name__)

    logger.info("Starting download", url=url, task_id=task_id)
    # ... download logic
    logger.info("Download completed", bytes_downloaded=12345678)
```

**Log Output:**
```
2026-01-02 10:30:15 INFO [task-abc123] Starting download url=https://example.com/file.zip task_id=abc123
2026-01-02 10:35:42 INFO [task-abc123] Download completed bytes_downloaded=12345678
2026-01-02 10:35:42 INFO [task-abc123] download_file completed duration_ms=327000 status=success
```

---

#### A3. No Error Rate Tracking
**The Problem:** Can't answer "Is the system healthy?"
- No tracking of error rates over time
- No alerting when error rate spikes
- Can't distinguish normal failures (user cancel) from bugs (crash)

**Search Commands:**
```bash
# Find exception handlers
grep -A 3 "except" colab_leecher/**/*.py

# Find task failure recording
grep -r "is_failed\|task_failed\|error_count" --include="*.py" colab_leecher/
```

**Fix Example:**
```python
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict

class ErrorTracker:
    """Track error rates and patterns"""

    def __init__(self):
        # Error counts by category in last hour
        self.error_buckets: Dict[str, list] = defaultdict(list)
        self.alert_threshold = 0.15  # Alert if >15% error rate

    def record_error(self, category: str, error: Exception):
        """Record an error with timestamp"""
        now = datetime.now()
        self.error_buckets[category].append({
            'timestamp': now,
            'error': str(error),
            'type': type(error).__name__
        })

        # Clean old errors (>1 hour)
        cutoff = now - timedelta(hours=1)
        self.error_buckets[category] = [
            e for e in self.error_buckets[category]
            if e['timestamp'] > cutoff
        ]

        # Check if we should alert
        self._check_alert_threshold(category)

    def _check_alert_threshold(self, category: str):
        """Alert if error rate too high"""
        total_ops = self.get_total_operations(category)
        errors = len(self.error_buckets[category])

        if total_ops > 10 and errors / total_ops > self.alert_threshold:
            # Alert! Error rate too high
            logger.error(f"🚨 HIGH ERROR RATE ALERT",
                        category=category,
                        error_rate=f"{errors/total_ops*100:.1f}%",
                        errors_last_hour=errors,
                        total_operations=total_ops)

    def get_error_summary(self) -> str:
        """Get human-readable error summary"""
        summary = ["📊 Error Summary (Last Hour):"]
        for category, errors in self.error_buckets.items():
            if errors:
                error_types = {}
                for e in errors:
                    error_types[e['type']] = error_types.get(e['type'], 0) + 1

                summary.append(f"\n{category}: {len(errors)} errors")
                for etype, count in error_types.items():
                    summary.append(f"  └─ {etype}: {count}")

        return "\n".join(summary) if len(summary) > 1 else "✅ No errors in last hour"
```

---

#### A4. No Slow Operation Detection
**The Problem:** Can't find performance bottlenecks
- No tracking of operation durations
- Can't tell if uploads are getting slower over time
- No "this operation is taking unusually long" warnings

**Fix Example:**
```python
from collections import deque
import statistics

class PerformanceMonitor:
    """Detect slow operations and performance degradation"""

    def __init__(self):
        # Rolling window of operation durations
        self.operation_history = defaultdict(lambda: deque(maxlen=100))
        self.slow_operation_threshold = 2.0  # 2x average is "slow"

    def record_duration(self, operation: str, duration_seconds: float):
        """Record operation duration and check for anomalies"""
        history = self.operation_history[operation]
        history.append(duration_seconds)

        if len(history) >= 10:  # Need baseline
            avg = statistics.mean(history)
            stddev = statistics.stdev(history)

            # Detect if current operation is unusually slow
            if duration_seconds > avg * self.slow_operation_threshold:
                logger.warning(f"⚠️  Slow operation detected",
                              operation=operation,
                              duration_sec=f"{duration_seconds:.2f}",
                              average_sec=f"{avg:.2f}",
                              slowdown_factor=f"{duration_seconds/avg:.1f}x")

            # Detect if operations are trending slower
            recent_10 = list(history)[-10:]
            older_10 = list(history)[-20:-10] if len(history) >= 20 else []

            if older_10:
                recent_avg = statistics.mean(recent_10)
                older_avg = statistics.mean(older_10)

                if recent_avg > older_avg * 1.5:
                    logger.warning(f"⚠️  Performance degradation detected",
                                  operation=operation,
                                  recent_avg=f"{recent_avg:.2f}s",
                                  older_avg=f"{older_avg:.2f}s",
                                  degradation=f"{(recent_avg/older_avg-1)*100:.0f}%")

    def get_performance_summary(self) -> str:
        """Get performance summary"""
        summary = ["⚡ Performance Summary:"]
        for op, durations in self.operation_history.items():
            if durations:
                avg = statistics.mean(durations)
                p95 = sorted(durations)[int(len(durations) * 0.95)]
                summary.append(f"\n{op}:")
                summary.append(f"  ├─ Avg: {avg:.2f}s")
                summary.append(f"  └─ P95: {p95:.2f}s")

        return "\n".join(summary)
```

---

### 💾 Category B: Memory & Resource Leaks
**Expected Findings:** 3-5 subtle leaks
**Impact:** Bot crashes after 24-72 hours of uptime

#### B1. Task Context Not Cleaned
**The Problem:** Even after task completes, objects are retained in memory

**Search Commands:**
```bash
# Find task storage without cleanup
grep -r "_active_tasks\|_tasks_by_id\|tasks_dict" --include="*.py" colab_leecher/

# Find circular references
grep -r "self\._.*self\|self\..*parent" --include="*.py" colab_leecher/
```

**Test:**
```python
import gc
import sys

# Track object counts
def find_leaks():
    # Run 100 tasks
    for i in range(100):
        task = TaskContext(user_id=12345, url=f"http://example.com/{i}")
        await task.start()
        await task.complete()

    # Force cleanup
    await task_manager.cleanup_completed()
    gc.collect()

    # Check for leaked TaskContext objects
    leaked_tasks = [obj for obj in gc.get_objects()
                    if isinstance(obj, TaskContext)]

    if leaked_tasks:
        print(f"🔴 LEAK DETECTED: {len(leaked_tasks)} TaskContext objects not freed")
        # Print references keeping them alive
        for task in leaked_tasks[:3]:
            referrers = gc.get_referrers(task)
            print(f"  Task {task.task_id} held by: {[type(r).__name__ for r in referrers]}")
    else:
        print("✅ No leaks detected")
```

**Common Leak Patterns:**
```python
# ❌ BAD: Circular reference
class TaskContext:
    def __init__(self):
        self.manager = task_manager  # Manager holds tasks, task holds manager!
        task_manager.add_task(self)

# ✅ GOOD: Weak reference
import weakref

class TaskContext:
    def __init__(self, manager):
        self._manager_ref = weakref.ref(manager)  # Won't prevent GC

    @property
    def manager(self):
        return self._manager_ref()

# ❌ BAD: Callback holds task reference forever
async def on_complete(task):
    await update_dashboard(task)

task.on_complete_callback = on_complete  # task lives forever if callback does

# ✅ GOOD: Clear callback after use
async def complete_task(task):
    if task.on_complete_callback:
        await task.on_complete_callback(task)
        task.on_complete_callback = None  # Clear reference
```

---

#### B2. File Handles Not Closed
**The Problem:** Accumulate open file descriptors until OS limit hit

**Search Commands:**
```bash
# Find open() without context manager
grep -r "open(" --include="*.py" colab_leecher/ | grep -v "with open"

# Find file operations in async functions
grep -B 2 "async def" colab_leecher/**/*.py | grep -A 10 "open("
```

**Test:**
```python
import psutil
import os

async def check_file_descriptor_leak():
    """Test for file descriptor leaks"""
    process = psutil.Process(os.getpid())

    # Count FDs before
    fds_before = process.num_fds() if hasattr(process, 'num_fds') else len(process.open_files())

    # Run 100 downloads
    for i in range(100):
        await download_file(f"http://example.com/file{i}.zip")

    # Count FDs after
    fds_after = process.num_fds() if hasattr(process, 'num_fds') else len(process.open_files())

    leaked_fds = fds_after - fds_before
    if leaked_fds > 10:
        print(f"🔴 FILE DESCRIPTOR LEAK: {leaked_fds} FDs not closed")
        print(f"   Open files: {process.open_files()}")
    else:
        print(f"✅ No FD leak ({leaked_fds} delta is within normal range)")
```

---

#### B3. Asyncio Task Leaks
**The Problem:** Background tasks created but never awaited or cancelled

**Search Commands:**
```bash
# Find asyncio.create_task without tracking
grep -r "asyncio.create_task\|asyncio.ensure_future" --include="*.py" colab_leecher/

# Find while True loops (daemon tasks)
grep -A 5 "while True:" colab_leecher/**/*.py
```

**Test:**
```python
async def find_leaked_tasks():
    """Find asyncio tasks that are running but orphaned"""
    all_tasks = asyncio.all_tasks()

    # Categorize tasks
    known_tasks = {
        'periodic_cleanup',
        'aria2_monitor',
        'dashboard_updater',
        # ... list all expected background tasks
    }

    orphaned = []
    for task in all_tasks:
        task_name = task.get_name()
        if task_name not in known_tasks and not task.done():
            orphaned.append(task)

    if orphaned:
        print(f"🔴 ORPHANED TASKS: {len(orphaned)} tasks running without tracking")
        for task in orphaned:
            print(f"   {task.get_name()}: {task.get_coro()}")
    else:
        print("✅ All tasks accounted for")
```

**Fix Pattern:**
```python
class TaskManager:
    def __init__(self):
        self.background_tasks: Set[asyncio.Task] = set()

    def create_background_task(self, coro, name: str) -> asyncio.Task:
        """Create tracked background task"""
        task = asyncio.create_task(coro, name=name)
        self.background_tasks.add(task)

        # Remove from set when done
        task.add_done_callback(self.background_tasks.discard)

        return task

    async def shutdown(self):
        """Cancel all background tasks on shutdown"""
        for task in self.background_tasks:
            task.cancel()

        await asyncio.gather(*self.background_tasks, return_exceptions=True)
```

---

### 🔄 Category C: State Corruption Over Time
**Expected Findings:** 2-4 time-based bugs
**Impact:** System becomes inconsistent after hours of runtime

#### C1. Dashboard Summary Desynchronization
**The Problem:** After 50 tasks, summary shows wrong counts

**Test:**
```python
async def test_dashboard_drift():
    """Test if dashboard stays synchronized after many operations"""

    # Run 100 tasks with mixed outcomes
    for i in range(100):
        task = await create_task(f"http://example.com/file{i}")

        # Random outcomes
        if i % 5 == 0:
            await task.cancel()
        elif i % 7 == 0:
            await task.fail("Simulated error")
        else:
            await task.complete()

    # Get dashboard
    dashboard_text = await task_manager.get_dashboard_summary()

    # Parse counts from dashboard
    import re
    active = int(re.search(r'Active: (\d+)', dashboard_text).group(1))
    completed = int(re.search(r'Completed: (\d+)', dashboard_text).group(1))
    failed = int(re.search(r'Failed: (\d+)', dashboard_text).group(1))

    # Calculate actual counts
    actual_active = len([t for t in task_manager.tasks if t.is_active])
    actual_completed = len([t for t in task_manager.tasks if t.is_completed])
    actual_failed = len([t for t in task_manager.tasks if t.is_failed])

    # Verify synchronization
    errors = []
    if active != actual_active:
        errors.append(f"Active mismatch: dashboard={active}, actual={actual_active}")
    if completed != actual_completed:
        errors.append(f"Completed mismatch: dashboard={completed}, actual={actual_completed}")
    if failed != actual_failed:
        errors.append(f"Failed mismatch: dashboard={failed}, actual={actual_failed}")

    if errors:
        print("🔴 DASHBOARD DESYNC:")
        for error in errors:
            print(f"   {error}")
    else:
        print("✅ Dashboard synchronized after 100 tasks")
```

---

#### C2. Stale Message IDs
**The Problem:** After 24 hours, bot tries to edit deleted messages

**Search Commands:**
```bash
# Find message ID storage
grep -r "message_id\|msg_id\|_messages" --include="*.py" colab_leecher/

# Find edit_message calls without error handling
grep -A 5 "edit_message" colab_leecher/**/*.py | grep -v "except"
```

**Fix:**
```python
class MessageTracker:
    """Track message lifecycle and handle stale references"""

    def __init__(self):
        self.message_timestamps = {}  # msg_id -> created_time
        self.max_message_age = timedelta(hours=48)

    async def safe_edit_message(self, chat_id: int, message_id: int, text: str):
        """Edit message with staleness check"""

        # Check if message is too old
        created_time = self.message_timestamps.get(message_id)
        if created_time and datetime.now() - created_time > self.max_message_age:
            logger.debug(f"Skipping edit of stale message",
                        message_id=message_id,
                        age_hours=(datetime.now() - created_time).total_seconds() / 3600)
            return None

        try:
            return await app.edit_message_text(chat_id, message_id, text)
        except MessageIdInvalid:
            # Message was deleted, remove from tracking
            logger.debug(f"Message {message_id} no longer exists, removing from tracker")
            self.message_timestamps.pop(message_id, None)
            return None
        except Exception as e:
            logger.error(f"Failed to edit message",
                        message_id=message_id,
                        error=str(e))
            return None
```

---

### ⚡ Category D: Rare Race Conditions
**Expected Findings:** 2-3 subtle races
**Impact:** Bugs that happen 1 in 1000 operations

#### D1. Double-Click Cancel
**The Problem:** User clicks Cancel button twice very fast

**Test:**
```python
async def test_double_cancel():
    """Simulate rapid double-click on cancel button"""
    task = await create_task("http://example.com/largefile.zip")

    # Simulate two cancel clicks within 10ms
    results = await asyncio.gather(
        task.cancel(),
        task.cancel(),
        return_exceptions=True
    )

    # Check for errors
    errors = [r for r in results if isinstance(r, Exception)]
    if errors:
        print(f"🔴 DOUBLE-CANCEL BUG: {errors}")

    # Check final state is consistent
    if task.is_cancelled and task.is_active:
        print("🔴 INVALID STATE: Task is both cancelled and active")
    elif task.is_cancelled:
        print("✅ Double-cancel handled gracefully")
```

---

#### D2. Upload Starts Before Download Finishes
**The Problem:** Race between download completion and upload start

**Search Commands:**
```bash
# Find download completion handler
grep -A 10 "download.*complete\|on_download_complete" --include="*.py" colab_leecher/

# Find upload start trigger
grep -B 5 "start_upload\|begin_upload" --include="*.py" colab_leecher/
```

**Test:**
```python
async def test_download_upload_race():
    """Test race between download complete and upload start"""

    # Create task that auto-uploads after download
    task = await create_task("http://example.com/file.zip", auto_upload=True)

    # Simulate download completing in background
    download_complete = asyncio.create_task(task._on_download_complete())

    # Immediately try to start upload manually
    manual_upload = asyncio.create_task(task.start_upload())

    # Both should not execute
    await asyncio.gather(download_complete, manual_upload, return_exceptions=True)

    # Check: Was file uploaded twice?
    uploads = await check_telegram_uploads(task.file_name)
    if len(uploads) > 1:
        print(f"🔴 DOUBLE UPLOAD: File uploaded {len(uploads)} times")
    else:
        print("✅ Race handled, single upload")
```

---

### 🌐 Category E: Network Failure Scenarios
**Expected Findings:** 3-5 network edge cases
**Impact:** Hangs or data loss when network is unstable

#### E1. Telegram API Unreachable
**The Problem:** If Telegram API is down, what happens?

**Test:**
```python
async def test_telegram_api_down():
    """Simulate Telegram API being unreachable"""

    # Mock Telegram API to timeout
    with patch('pyrogram.Client.send_message', side_effect=TimeoutError):
        task = await create_task("http://example.com/file.zip")

        # Try to send progress update
        try:
            await task.update_progress(50)
            # Should not hang forever
        except Exception as e:
            print(f"Caught exception: {e}")

    # Check: Is task still functional?
    if task.is_active:
        print("✅ Task survived Telegram API failure")
    else:
        print("🔴 BUG: Task died when Telegram API was down")
```

---

#### E2. Aria2 RPC Becomes Unresponsive
**The Problem:** Aria2 RPC hangs, do we hang forever?

**Search Commands:**
```bash
# Find aria2 RPC calls without timeout
grep -r "aria2.*tell\|aria2.*addUri" --include="*.py" colab_leecher/
```

**Fix:**
```python
async def aria2_rpc_call_with_timeout(method: str, params: list, timeout: float = 5.0):
    """Make aria2 RPC call with timeout"""
    try:
        return await asyncio.wait_for(
            aria2_rpc(method, params),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        logger.error(f"Aria2 RPC timeout",
                    method=method,
                    timeout_sec=timeout)
        # Try to restart aria2?
        await restart_aria2_if_unhealthy()
        raise
```

---

### 🔧 Category F: Configuration & Deployment Issues
**Expected Findings:** 4-6 config bugs
**Impact:** Fails in production but works in dev

#### F1. Hardcoded Paths
**The Problem:** Bot expects files in /tmp, but Windows has different temp dir

**Search Commands:**
```bash
# Find hardcoded paths
grep -r '"/tmp\|/home\|C:\\' --include="*.py" colab_leecher/

# Find os.path without platform checks
grep -r "os.path.join" --include="*.py" colab_leecher/
```

---

#### F2. No Graceful Shutdown
**The Problem:** SIGTERM kills bot mid-upload, file corrupted

**Test:**
```python
async def test_graceful_shutdown():
    """Test shutdown during active operations"""

    # Start 5 downloads
    tasks = [await create_task(f"http://example.com/file{i}.zip") for i in range(5)]

    # Simulate SIGTERM
    import signal
    os.kill(os.getpid(), signal.SIGTERM)

    # Wait for shutdown
    await asyncio.sleep(5)

    # Check: Were tasks cancelled cleanly?
    for task in tasks:
        if task.is_active:
            print(f"🔴 BUG: Task {task.task_id} still active after shutdown")

    # Check: Were temp files cleaned?
    temp_files = glob.glob("/tmp/aria2_*")
    if temp_files:
        print(f"🔴 BUG: {len(temp_files)} temp files not cleaned")
```

**Fix:**
```python
import signal
import asyncio

class GracefulShutdown:
    """Handle graceful shutdown on SIGTERM/SIGINT"""

    def __init__(self, task_manager):
        self.task_manager = task_manager
        self.shutdown_timeout = 30  # seconds

    def setup_handlers(self):
        """Register signal handlers"""
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        """Handle shutdown signal"""
        logger.info(f"Received signal {signum}, starting graceful shutdown")
        asyncio.create_task(self._graceful_shutdown())

    async def _graceful_shutdown(self):
        """Perform graceful shutdown"""
        logger.info("Starting graceful shutdown...")

        # 1. Stop accepting new tasks
        await self.task_manager.stop_accepting_new_tasks()

        # 2. Cancel active downloads
        active_tasks = self.task_manager.get_active_tasks()
        logger.info(f"Cancelling {len(active_tasks)} active tasks")

        cancel_tasks = [task.cancel() for task in active_tasks]
        await asyncio.gather(*cancel_tasks, return_exceptions=True)

        # 3. Wait for uploads to finish (with timeout)
        uploading_tasks = [t for t in active_tasks if t.is_uploading]
        if uploading_tasks:
            logger.info(f"Waiting for {len(uploading_tasks)} uploads to finish...")
            try:
                await asyncio.wait_for(
                    asyncio.gather(*[t.wait_for_upload() for t in uploading_tasks]),
                    timeout=self.shutdown_timeout
                )
            except asyncio.TimeoutError:
                logger.warning(f"Upload timeout, forcing shutdown")

        # 4. Cleanup
        await self.task_manager.cleanup_all()

        logger.info("Graceful shutdown complete")
        exit(0)
```

---

### 📊 Category G: Data Integrity Edge Cases
**Expected Findings:** 3-4 data edge cases
**Impact:** Subtle data corruption

#### G1. Filename Encoding Issues
**The Problem:** File with emoji/unicode in name fails to save on some filesystems

**Test:**
```python
test_filenames = [
    "file_with_emoji_🚀.zip",
    "файл_на_русском.zip",
    "文件_中文.zip",
    "file\x00null_byte.zip",
    "file:with:colons.zip",
    "file<with>pipes.zip",
]

for filename in test_filenames:
    try:
        # Try to create file
        path = os.path.join(workspace, filename)
        open(path, 'w').close()
        os.remove(path)
        print(f"✅ {filename}")
    except Exception as e:
        print(f"🔴 {filename}: {e}")
```

---

#### G2. Partial Upload Recovery
**The Problem:** Upload fails at 90%, can we resume or do we restart from 0%?

**Search Commands:**
```bash
# Find upload implementation
grep -A 20 "def.*upload\|async def.*upload" --include="*.py" colab_leecher/

# Find upload error handling
grep -B 5 -A 10 "upload" colab_leecher/**/*.py | grep -A 5 "except"
```

---

## 🎯 Stress Test Scenarios

### Test 1: 7-Day Uptime Test
```python
async def seven_day_uptime_test():
    """Run bot for 7 days with continuous load"""

    start_time = time.time()
    task_count = 0
    errors = []

    while time.time() - start_time < 7 * 24 * 3600:  # 7 days
        # Create new task every 10 minutes
        try:
            task = await create_random_task()
            task_count += 1

            # Check system health every hour
            if task_count % 6 == 0:
                health = await task_manager.get_health_check()
                print(f"Health at {task_count} tasks: {health}")

                # Check for memory growth
                import psutil
                process = psutil.Process()
                mem_mb = process.memory_info().rss / 1024 / 1024
                if mem_mb > 2000:  # >2GB is suspicious
                    errors.append(f"High memory: {mem_mb}MB at task {task_count}")

        except Exception as e:
            errors.append(f"Task {task_count} failed: {e}")

        await asyncio.sleep(600)  # 10 minutes

    print(f"\n7-Day Test Results:")
    print(f"  Tasks completed: {task_count}")
    print(f"  Errors: {len(errors)}")
    if errors:
        print("\n  Error log:")
        for err in errors[:10]:
            print(f"    - {err}")
```

---

### Test 2: Chaos Monkey Test
```python
async def chaos_monkey_test():
    """Randomly kill processes and connections during operation"""

    import random

    # Start 10 tasks
    tasks = [await create_task(f"http://example.com/file{i}.zip") for i in range(10)]

    # Randomly cause chaos
    chaos_events = [
        lambda: os.kill(aria2_pid, signal.SIGKILL),  # Kill aria2
        lambda: asyncio.sleep(0),  # Simulate network drop (TODO: actual impl)
        lambda: os.kill(os.getpid(), signal.SIGSTOP),  # Pause bot
    ]

    for _ in range(20):
        await asyncio.sleep(random.uniform(5, 30))
        event = random.choice(chaos_events)

        try:
            print(f"🔥 Chaos: {event.__name__}")
            event()
        except:
            pass

    # Check: Did any tasks complete despite chaos?
    completed = [t for t in tasks if t.is_completed]
    print(f"✅ {len(completed)}/10 tasks survived chaos")
```

---

## 📈 Success Criteria

The system is production-ready when:

### Observability ✅
- [ ] Can view real-time metrics without SSH (health endpoint)
- [ ] Can trace any operation through logs (request IDs)
- [ ] Can diagnose "slow" issues (performance monitoring)
- [ ] Can see error rates and patterns (error tracking)
- [ ] Can detect performance degradation (trending analysis)

### Stability ✅
- [ ] No memory leaks after 7 days uptime
- [ ] No file descriptor leaks after 10,000 operations
- [ ] No asyncio task leaks (all tasks accounted for)
- [ ] Dashboard stays synchronized after 1000+ tasks
- [ ] Graceful shutdown preserves data integrity

### Resilience ✅
- [ ] Survives Telegram API downtime
- [ ] Survives aria2 crashes (auto-restart)
- [ ] Survives network interruptions
- [ ] Survives disk full gracefully
- [ ] Survives chaos monkey test (random failures)

### Data Integrity ✅
- [ ] No data loss on shutdown
- [ ] No double uploads/downloads
- [ ] No state corruption after 1000 operations
- [ ] Unicode filenames handled correctly
- [ ] Partial uploads can resume

---

## 🔍 Quick Audit Commands

```bash
# Memory leak check
grep -r "self\._.*self\|circular" --include="*.py" colab_leecher/

# File handle leak check
grep -r "open(" --include="*.py" colab_leecher/ | grep -v "with open"

# Asyncio task leak check
grep -r "asyncio.create_task" --include="*.py" colab_leecher/ | grep -v "add_done_callback"

# Missing timeout check
grep -r "await.*rpc\|await.*send_message" --include="*.py" colab_leecher/ | grep -v "wait_for"

# Hardcoded path check
grep -r '"/tmp\|/home\|C:\\' --include="*.py" colab_leecher/

# No metrics check
grep -r "prometheus\|metrics\|health_check" --include="*.py" colab_leecher/

# Blocking I/O in async check
grep -r "def " colab_leecher/**/*.py | grep -v "async def" | xargs grep "await"
```

---

## 📋 Expected Findings Summary

| Category | Expected Bugs | Severity |
|----------|---------------|----------|
| Observability Gaps | 8-12 | High |
| Memory/Resource Leaks | 3-5 | Critical |
| State Corruption | 2-4 | High |
| Race Conditions | 2-3 | Medium |
| Network Failures | 3-5 | High |
| Config/Deployment | 4-6 | Medium |
| Data Integrity | 3-4 | High |
| **Total** | **25-39 bugs** | **Mixed** |

---

## 🎓 Round 5 Philosophy

**Previous rounds asked:** "Does it work?"
**This round asks:** "Can you **see** that it works? Can you **prove** it works after 7 days?"

Production bugs are different:
- They don't appear in tests
- They happen after hours/days of runtime
- They're triggered by rare conditions
- They're invisible without monitoring
- They corrupt data silently

**This round focuses on:** Observability-first development, defensive programming, and proving correctness under stress.

---

## 🚀 Next Steps

1. Run audit commands to identify gaps
2. Implement metrics collection
3. Add structured logging with request tracing
4. Run 7-day uptime test
5. Run chaos monkey test
6. Measure and fix any findings

The system should not just work - it should be **observable, debugable, and provably stable** in production. 🏆
