# 🐛 Bug Hunt: Parallel Task System - Comprehensive Code Review

I need you to perform a thorough bug hunt on a Telegram bot's parallel task download/upload system. This is a critical production system that handles multiple concurrent downloads.

---

## 📋 System Overview

**Purpose:** Allow users to download/upload multiple files in parallel from various sources (direct links, Google Drive, YouTube, etc.) via a Telegram bot.

**Key Components:**
1. **TaskContext** - Isolated state for each task (no shared global state)
2. **TaskQueue** - Global manager for all active tasks (thread-safe with asyncio locks)
3. **Summary Dashboard** - Single Telegram message showing all parallel task statuses
4. **Task Manager** - Main execution loop that creates tasks and manages lifecycle

**Recent Changes:**
- Converted from single-task global state to multi-task isolated contexts
- Added summary dashboard with thumbnail support
- Implemented parallel mode detection to skip individual status messages
- Added thread-safe task queue with asyncio locks

---

## 🔍 Code to Review

### 1. Task Context & Queue Manager (`task_context.py`)

```python
@dataclass
class TaskContext:
    """Isolated context for a single download/upload task"""

    task_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int = 0
    chat_id: int = 0
    mode: str = "leech"
    mode_type: str = "normal"
    service_type: Optional[str] = None
    source_urls: List[str] = field(default_factory=list)
    filenames: List[str] = field(default_factory=list)
    work_path: str = ""
    down_path: str = ""
    hero_image: str = ""
    status_msg: Optional[Message] = None
    sent_msg: Optional[Message] = None
    transfer: TaskTransfer = field(default_factory=TaskTransfer)
    error: TaskError = field(default_factory=TaskError)
    messages: TaskMessages = field(default_factory=TaskMessages)
    bot_times: TaskBotTimes = field(default_factory=TaskBotTimes)
    async_task: Optional[asyncio.Task] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    last_status_update: float = 0.0
    is_cancelled: bool = False
    is_completed: bool = False

    def get_short_id(self) -> str:
        return self.task_id[:8]

    def get_elapsed_time(self) -> float:
        if not self.started_at:
            return 0.0
        end_time = self.completed_at if self.completed_at else datetime.now()
        return (end_time - self.started_at).total_seconds()

class TaskQueue:
    """Global task queue manager for parallel multi-task execution"""

    MAX_TASKS_PER_USER = 5
    MAX_TOTAL_TASKS = 20

    def __init__(self):
        self.active_tasks: Dict[str, TaskContext] = {}
        self.summary_msg: Optional[Message] = None
        self.last_summary_update: float = 0
        self.summary_update_interval: float = 5.0
        self._lock = asyncio.Lock()
        self._summary_lock = asyncio.Lock()

    async def add_task(self, task_ctx: TaskContext):
        async with self._lock:
            self.active_tasks[task_ctx.task_id] = task_ctx

    async def remove_task(self, task_id: str) -> Optional[TaskContext]:
        async with self._lock:
            task_ctx = self.active_tasks.pop(task_id, None)
            return task_ctx

    async def get_task(self, task_id: str) -> Optional[TaskContext]:
        async with self._lock:
            return self.active_tasks.get(task_id)

    async def has_task(self, task_id: str) -> bool:
        async with self._lock:
            return task_id in self.active_tasks

    async def get_all_tasks(self) -> Dict[str, TaskContext]:
        async with self._lock:
            return self.active_tasks.copy()

    def get_task_count(self) -> int:
        return len(self.active_tasks)

    def should_update_summary(self) -> bool:
        return time.time() - self.last_summary_update >= self.summary_update_interval

    def mark_summary_updated(self):
        self.last_summary_update = time.time()

# Global singleton
TASK_QUEUE = TaskQueue()
```

### 2. Summary Dashboard (`task_dashboard.py`)

```python
async def update_summary_dashboard(client=None) -> Optional[Message]:
    """Update or create the summary dashboard showing all active tasks (thread-safe)"""

    if not client:
        client = colab_bot

    async with TASK_QUEUE._summary_lock:
        tasks = await TASK_QUEUE.get_all_tasks()

        # Delete summary if no tasks
        if not tasks:
            if TASK_QUEUE.summary_msg:
                try:
                    await TASK_QUEUE.summary_msg.delete()
                    TASK_QUEUE.summary_msg = None
                except Exception as e:
                    log.warning(f"Failed to delete summary: {e}")
            return None

        # Build summary text
        summary_lines = [f"🚀 **Parallel Downloads** ({len(tasks)} active)\n"]

        for idx, (task_id, task_ctx) in enumerate(tasks.items(), 1):
            short_id = task_ctx.get_short_id()

            # Get filename
            filename = "Unknown"
            if task_ctx.source_urls:
                url = task_ctx.source_urls[0]
                try:
                    from urllib.parse import urlparse, unquote
                    path = urlparse(url).path
                    filename = unquote(path.split('/')[-1]) if path else url[:50]
                except:
                    filename = url[:50]
            elif task_ctx.messages.download_name:
                filename = task_ctx.messages.download_name

            if len(filename) > 35:
                filename = filename[:32] + "..."

            # Calculate progress
            if task_ctx.transfer.up_bytes > 0:
                speed = task_ctx.transfer.get_speed()
                uploaded_count = len(task_ctx.transfer.sent_file_names)
                status_emoji = "⬆️"
                status = f"Uploading ({uploaded_count} files) • {speed}"
            elif task_ctx.transfer.down_bytes > 0:
                speed = task_ctx.transfer.get_speed()
                elapsed = task_ctx.get_elapsed_time()
                elapsed_str = getTime(elapsed) if elapsed > 0 else "0s"
                status_emoji = "⬇️"
                status = f"Downloading • {speed} • {elapsed_str}"
            else:
                status_emoji = "⏳"
                status = "Initializing..."

            task_line = (
                f"{status_emoji} **Task {idx}** [`{short_id}`]\n"
                f"├ 📄 `{filename}`\n"
                f"╰ {status}\n"
            )
            summary_lines.append(task_line)

        summary_text = "\n".join(summary_lines)

        # Get thumbnail
        thumbnail_path = None
        first_task = next(iter(tasks.values()), None) if tasks else None

        if first_task and hasattr(first_task, 'hero_image') and first_task.hero_image and os.path.exists(first_task.hero_image):
            thumbnail_path = first_task.hero_image
        elif os.path.exists(Paths.DEFAULT_HERO):
            thumbnail_path = Paths.DEFAULT_HERO

        # Update or create message
        try:
            if TASK_QUEUE.summary_msg:
                # Update existing
                try:
                    await TASK_QUEUE.summary_msg.edit_caption(summary_text)
                except Exception as edit_err:
                    # Recreate if edit fails
                    if thumbnail_path:
                        TASK_QUEUE.summary_msg = await client.send_photo(
                            OWNER, photo=thumbnail_path, caption=summary_text
                        )
                    else:
                        TASK_QUEUE.summary_msg = await client.send_message(
                            OWNER, text=summary_text, disable_web_page_preview=True
                        )
            else:
                # Create new
                if thumbnail_path:
                    TASK_QUEUE.summary_msg = await client.send_photo(
                        OWNER, photo=thumbnail_path, caption=summary_text
                    )
                else:
                    TASK_QUEUE.summary_msg = await client.send_message(
                        OWNER, text=summary_text, disable_web_page_preview=True
                    )

            TASK_QUEUE.mark_summary_updated()
            return TASK_QUEUE.summary_msg

        except Exception as e:
            log.error(f"Failed to update summary dashboard: {e}")
            return None
```

### 3. Parallel Mode Detection (`task_manager.py`)

```python
# ===== PARALLEL MODE: Skip individual messages, use shared dashboard instead =====
# Check if we're in parallel mode by seeing if we're part of TASK_QUEUE
is_parallel_mode = False
if task_ctx:
    is_parallel_mode = await TASK_QUEUE.has_task(task_ctx.task_id)

# Only create individual status message if NOT in parallel mode
if not _msg.status_msg and not is_parallel_mode:
    # Determine which image to send (Custom > Downloaded/Fallback)
    img_to_send = _paths.THMB_PATH if _bot.Setting.thumbnail and ospath.exists(_paths.THMB_PATH) else final_thumb_path

    # Send initial status message with photo (with fallback to text-only)
    if not img_to_send or not ospath.exists(img_to_send):
        img_to_send = _paths.DEFAULT_HERO
        if not img_to_send or not ospath.exists(img_to_send):
            _msg.status_msg = await colab_bot.send_message(...)
        else:
            try:
                _msg.status_msg = await colab_bot.send_photo(...)
            except Exception as photo_err:
                _msg.status_msg = await colab_bot.send_message(...)
    else:
        try:
            _msg.status_msg = await colab_bot.send_photo(...)
        except Exception as photo_err:
            _msg.status_msg = await colab_bot.send_message(...)
else:
    # Status message already exists (shared message for parallel tasks)
    log.info(f"Skipping status message creation - using existing shared message")
```

---

## 🎯 Bug Categories to Hunt

### 1. **Race Conditions & Concurrency Bugs**
- [ ] Lock acquisition order (deadlock potential)
- [ ] Missing locks on shared state access
- [ ] Lock held during long I/O operations
- [ ] Dictionary iteration while modifying (even with `.copy()`)
- [ ] Concurrent access to `TASK_QUEUE.summary_msg`
- [ ] Multiple tasks calling `update_summary_dashboard()` simultaneously
- [ ] Task removal while iterating in dashboard update

### 2. **Memory Leaks**
- [ ] Tasks not removed from `active_tasks` dict after completion
- [ ] Circular references in TaskContext (async_task holding context)
- [ ] Pyrogram Message objects not garbage collected
- [ ] Growing `active_tasks` dict that's never cleaned
- [ ] `clear_completed_tasks()` never called (line 299-317)
- [ ] File handles left open in task workspaces

### 3. **State Inconsistencies**
- [ ] Task exists in queue but `is_cancelled=True` or `is_completed=True`
- [ ] `summary_msg` pointing to deleted Telegram message
- [ ] Task context modified after removal from queue
- [ ] `last_summary_update` not updated on forced updates
- [ ] Task count limits checked without lock (race condition)
- [ ] `task_ctx.status_msg` set in parallel mode (should be None)

### 4. **Edge Cases & Error Handling**
- [ ] What if `TASK_QUEUE.summary_msg.edit_caption()` fails?
- [ ] What if task removed while dashboard is building text?
- [ ] What if thumbnail file deleted mid-task?
- [ ] What if `client` is None in `update_summary_dashboard()`?
- [ ] Division by zero in speed calculation (`elapsed == 0`)
- [ ] Empty `tasks` dict but summary_msg exists (orphaned message)
- [ ] User cancels task immediately after creation (before added to queue)
- [ ] Task ID collision (UUID should prevent, but verify)

### 5. **Asyncio Issues**
- [ ] `async with` lock not properly released on exception
- [ ] Mixing sync and async operations on same data
- [ ] Long-running operations inside lock (blocking other tasks)
- [ ] `asyncio.Task` cancellation not propagated to task context
- [ ] `async_task` reference prevents garbage collection
- [ ] Lock contention causing performance degradation

### 6. **Message Handling Bugs**
- [ ] Editing caption on text-only message (no caption to edit)
- [ ] Sending photo when file doesn't exist (already checked but verify)
- [ ] Caption exceeds Telegram's 1024 character limit
- [ ] Dashboard not updated when last task completes
- [ ] Dashboard deleted while task still in "Initializing" state
- [ ] Individual messages sent even in parallel mode

### 7. **Data Integrity Issues**
- [ ] `source_urls[0]` accessed without checking list length
- [ ] `task_ctx.messages.download_name` is None but accessed
- [ ] Filename extraction fails with non-standard URLs
- [ ] Task added to queue but paths not created (`work_path`, `down_path`)
- [ ] `hero_image` path exists but file doesn't (broken state)

### 8. **Performance Issues**
- [ ] `get_all_tasks()` returns copy (expensive for large dicts)
- [ ] Dashboard updates too frequently (5-second throttle bypassed?)
- [ ] Lock held while building dashboard text (slow operation)
- [ ] Multiple thumbnails downloaded (one per task) instead of shared
- [ ] O(n) iteration over tasks dict on every update

### 9. **Logic Bugs**
- [ ] `is_parallel_mode` detection happens AFTER task added to queue (timing issue?)
- [ ] Task can be in queue but `has_task()` returns False (race)
- [ ] `clear_completed_tasks()` calls `remove_task()` without await (line 316)
- [ ] `should_update_summary()` not thread-safe (no lock on read)
- [ ] Task limits checked but not enforced atomically

### 10. **Telegram API Issues**
- [ ] `edit_caption()` called on message without photo
- [ ] Photo sent with same `file_id` triggers Telegram cache issues
- [ ] Message deleted externally but `summary_msg` not updated
- [ ] Rate limiting not handled (too many edits per second)
- [ ] `OWNER` chat_id invalid or bot kicked from chat

---

## 🔬 Specific Issues to Investigate

### Issue A: Dashboard Update Race Condition
```python
async with TASK_QUEUE._summary_lock:
    tasks = await TASK_QUEUE.get_all_tasks()  # Acquires _lock
    # What if task removed here?
    for idx, (task_id, task_ctx) in enumerate(tasks.items(), 1):
        # Access task_ctx attributes - are they still valid?
```

**Question:** Is there a race between getting tasks and iterating them?

---

### Issue B: Lock Nesting Deadlock
```python
# In update_summary_dashboard():
async with TASK_QUEUE._summary_lock:
    tasks = await TASK_QUEUE.get_all_tasks()  # Acquires _lock inside _summary_lock

# Can this deadlock if another coroutine has _lock and wants _summary_lock?
```

**Question:** Is lock acquisition order consistent?

---

### Issue C: Memory Leak from Uncalled Cleanup
```python
async def clear_completed_tasks(self, max_age_hours: int = 1):
    # This method exists but is NEVER called in the codebase
    # Tasks accumulate forever in active_tasks dict
```

**Question:** Where should this be called? After each task completion?

---

### Issue D: Orphaned Summary Message
```python
# What if all tasks complete but summary update fails?
if not tasks:
    if TASK_QUEUE.summary_msg:
        await TASK_QUEUE.summary_msg.delete()
        TASK_QUEUE.summary_msg = None
    return None

# But what if delete() throws exception? Message orphaned.
```

---

### Issue E: Edit Caption on Text Message
```python
if TASK_QUEUE.summary_msg:
    await TASK_QUEUE.summary_msg.edit_caption(summary_text)
```

**Question:** What if `summary_msg` was created with `send_message()` (text-only)?
Can you `edit_caption()` on a text message?

---

## 📊 Test Scenarios to Verify

1. **Start 4 parallel tasks, cancel 2 mid-download**
   - Expected: Dashboard updates to show 2 remaining tasks
   - Bug risk: Cancelled tasks still shown, or dashboard deleted

2. **Start 1 task, then start 3 more immediately**
   - Expected: First task gets individual message, next 3 share dashboard
   - Bug risk: All 4 get individual messages (timing issue in parallel detection)

3. **All tasks complete within 1 second**
   - Expected: Dashboard deleted cleanly
   - Bug risk: Dashboard remains with "0 active" or orphaned

4. **Start 20 tasks (system limit)**
   - Expected: 21st task rejected with error message
   - Bug risk: Race allows 21+ tasks to start

5. **User cancels task before it's added to queue**
   - Expected: Task never starts, graceful cancellation
   - Bug risk: Crash or orphaned resources

6. **Thumbnail file deleted while task running**
   - Expected: Fallback to default thumbnail
   - Bug risk: Dashboard update crashes

7. **Edit dashboard while Telegram message deleted externally**
   - Expected: Recreate message gracefully
   - Bug risk: Permanent exception loop

---

## 📝 Your Task

Please analyze the code above and:

1. **Identify all bugs** in each category (1-10)
2. **Rate severity** (Critical/High/Medium/Low)
3. **Explain the bug** (what happens, why it's a problem)
4. **Suggest fix** (code change or architectural fix)
5. **Provide test case** (how to reproduce)

Focus especially on:
- **Concurrency bugs** (race conditions, deadlocks)
- **Memory leaks** (tasks not cleaned up)
- **Message handling** (edit_caption on wrong message type)
- **Edge cases** (empty lists, None values, deleted files)

Format your response as:

```
## Bug #1: [Name]
**Category:** [Race Condition/Memory Leak/etc.]
**Severity:** [Critical/High/Medium/Low]
**Location:** [file:line]

**Description:**
[What's wrong]

**Impact:**
[What happens if triggered]

**Reproduce:**
[Steps to trigger bug]

**Fix:**
[Code change needed]
```

Please be thorough and assume this is production code handling real user data. Every bug could cause data loss, crashes, or security issues.

---

## 🎯 Priority Questions

1. **Is `clear_completed_tasks()` ever called? If not, isn't this a guaranteed memory leak?**
2. **Can `edit_caption()` be called on a text-only message created with `send_message()`?**
3. **Is the lock nesting (`_summary_lock` → `_lock`) safe from deadlocks?**
4. **What happens if a task is removed from the queue while `update_summary_dashboard()` is iterating over the copied dict?**
5. **Is `is_parallel_mode` detection timing correct? Could a task be added to queue after the check but before message creation?**

---

Thank you for the thorough review! This system handles user files worth gigabytes, so correctness is critical.
