# Parallel Task Support Implementation Plan

**Date:** 2026-01-01
**Goal:** Enable parallel task support for /tupload and other commands
**Based on:** Mindvalley reference implementation (fully working)

---

## Current Architecture Analysis

### How Mindvalley Achieves Parallel Tasks (WORKING ✅)

```python
# 1. Command handler (__main__.py:1683)
@colab_bot.on_message(filters.command("mindvalley") & filters.private)
async def mindvalley_download(client, message):
    BOT.State.mindvalley_waiting = True  # Per-service flag
    src_request_msg = await task_starter(message, help_text)

# 2. URL handler (__main__.py:1817-1840)
@colab_bot.on_message(filters.text & not_command_filter & filters.private)
async def handle_text_input(client, message):
    if not BOT.State.mindvalley_waiting:
        return

    BOT.State.mindvalley_waiting = False

    # KEY: Create TaskContext HERE (not in task_starter)
    task_ctx = create_task_context(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        mode="leech"
    )

    # Register task
    TASK_QUEUE.add_task(task_ctx)

    # Launch async task (NON-BLOCKING!)
    asyncio.create_task(run_mindvalley_task(task_ctx, downloader, ...))

    # Return immediately - allows next task to start!
    return
```

**Why This Works:**
- ✅ `mindvalley_waiting` is a **per-service flag** (doesn't block other services)
- ✅ **No `task_going` check** in Mindvalley path
- ✅ TaskContext created **after** URLs received (not during command)
- ✅ `asyncio.create_task()` launches non-blocking
- ✅ Each task has isolated state (paths, messages, transfer stats)

---

## Current /tupload Architecture (BLOCKING ❌)

```python
# 1. Command handler (__main__.py:138)
@colab_bot.on_message(filters.command("tupload") & filters.private)
async def telegram_upload(client, message):
    BOT.Mode.mode = "leech"  # Global state!
    src_request_msg = await task_starter(message, text)

# 2. task_starter checks task_going (task_manager.py:526)
async def task_starter(message, text):
    if not BOT.State.task_going:  # BLOCKS if any task running!
        BOT.State.started = True
        return await message.reply_text(text)
    else:
        await message.reply_text("Already working!")  # BLOCKS parallel!
        return None

# 3. handle_url processes URLs (main__.py:654)
async def handle_url(client, message):
    if BOT.State.task_going:  # BLOCKS if any task running!
        await message.reply_text("Already working!")
        return

    # Process URLs...
    # Eventually calls taskScheduler()

# 4. taskScheduler sets task_going (task_manager.py:552)
async def taskScheduler(task_ctx=None):
    BOT.State.task_going = True  # Global lock!
    # ... do download/upload ...
    BOT.State.task_going = False  # Release lock
```

**Why This Blocks:**
- ❌ `BOT.State.task_going` is **global** (blocks ALL tasks)
- ❌ `task_starter()` checks `task_going` (rejects parallel commands)
- ❌ `handle_url()` checks `task_going` (rejects parallel URLs)
- ❌ TaskContext only created in `taskScheduler()` (too late)
- ❌ No async task launching (blocks until completion)

---

## Implementation Strategy

### Option A: Minimal Changes (Recommended)

**Create parallel-safe command pattern similar to Mindvalley**

**Step 1:** Add per-command waiting flags to TaskContext
```python
class TaskContext:
    # Add waiting state
    state: Dict[str, bool] = field(default_factory=dict)
    # state['waiting'] = True when expecting URLs
    # state['processing'] = True when task running
```

**Step 2:** Create new `/tupload_parallel` command (test first)
```python
@colab_bot.on_message(filters.command("tupload_parallel") & filters.private)
async def telegram_upload_parallel(client, message):
    # Create TaskContext immediately
    task_ctx = create_task_context(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        mode="leech"
    )
    task_ctx.state['waiting'] = True
    task_ctx.state['service'] = 'telegram_upload'

    # Store in user-specific queue
    user_tasks[message.from_user.id] = task_ctx

    # Send prompt
    await message.reply_text("Send me links...")

    # NO blocking!
```

**Step 3:** Modify `handle_url()` to support parallel mode
```python
async def handle_url(client, message):
    user_id = message.from_user.id

    # Check if user has pending parallel task
    if user_id in user_tasks:
        task_ctx = user_tasks[user_id]
        del user_tasks[user_id]

        # Process URLs with task_ctx
        await process_urls_parallel(client, message, task_ctx)
        return

    # Fall back to legacy single-task mode
    if BOT.State.task_going:
        await message.reply_text("Already working!")
        return

    # ... existing handle_url logic ...
```

**Step 4:** Launch task in parallel
```python
async def process_urls_parallel(client, message, task_ctx):
    # Parse URLs from message
    urls = parse_urls(message.text)

    # Store in task context
    task_ctx.source_urls = urls

    # Register in queue
    TASK_QUEUE.add_task(task_ctx)

    # Launch async (NON-BLOCKING!)
    async_task = asyncio.create_task(
        run_upload_task(client, message, task_ctx)
    )
    task_ctx.async_task = async_task

    # Update dashboard
    await force_update_summary()

    # Return immediately!
```

**Step 5:** Implement task runner
```python
async def run_upload_task(client, message, task_ctx):
    try:
        task_ctx.mark_started()

        # Call existing taskScheduler with task_ctx
        await taskScheduler(task_ctx)

    except Exception as e:
        log.exception(f"Task {task_ctx.get_short_id()} failed")
        task_ctx.error.set_error(str(e))
    finally:
        task_ctx.mark_completed()
        TASK_QUEUE.remove_task(task_ctx.task_id)
        await force_update_summary()
```

---

### Option B: Full Refactor (Comprehensive)

**Completely remove global state, force all commands to use TaskContext**

**Changes Required:**
1. Remove `BOT.State.task_going` entirely
2. Remove `BOT.State.started` entirely
3. Make all commands create TaskContext immediately
4. Update all downloaders to require task_ctx
5. Remove all legacy fallback code

**Pros:**
- Clean architecture
- No dual-mode complexity
- Future-proof

**Cons:**
- High risk (breaks existing code)
- Requires testing all commands
- Takes 2-3 weeks full-time

---

## Recommended Approach: Hybrid (Option A + Incremental Migration)

### Phase 1: Add Parallel Support (This PR)
1. Keep existing `/tupload` working (backward compat)
2. Add NEW `/tupload_parallel` command (parallel mode)
3. Test with 3-5 concurrent uploads
4. Verify dashboard, cancellation, completion

### Phase 2: Migrate Other Commands
1. Once `/tupload_parallel` proven stable
2. Add parallel versions of:
   - `/ytupload_parallel`
   - `/gdupload_parallel`
   - `/drupload_parallel`
3. Test each independently

### Phase 3: Deprecate Legacy (Future)
1. Monitor usage metrics
2. If parallel mode stable for 2+ weeks
3. Deprecate old commands
4. Remove `task_going` checks
5. Force all to use TaskContext

---

## Implementation Checklist

### Part 1: Data Structures
- [ ] Add `user_tasks: Dict[int, TaskContext]` global registry
- [ ] Add `state` dict to TaskContext for waiting flags
- [ ] Import `create_task_context` in __main__.py

### Part 2: Command Handler
- [ ] Create `/tupload_parallel` command handler
- [ ] Create TaskContext immediately
- [ ] Set waiting state
- [ ] Store in user_tasks registry
- [ ] Send URL prompt

### Part 3: URL Handler
- [ ] Modify `handle_url()` to check `user_tasks`
- [ ] Extract parallel URL processing to separate function
- [ ] Keep legacy path intact (backward compat)

### Part 4: Task Runner
- [ ] Create `run_upload_task()` async function
- [ ] Handle task lifecycle (start, execute, complete, cleanup)
- [ ] Register in TASK_QUEUE
- [ ] Update dashboard on changes
- [ ] Proper error handling

### Part 5: Testing
- [ ] Test single upload (backward compat)
- [ ] Test 2 parallel uploads
- [ ] Test 5 parallel uploads
- [ ] Test cancellation
- [ ] Test error handling
- [ ] Test dashboard updates

---

## Code Locations

**Files to Modify:**
1. `colab_leecher/__main__.py` - Add new command + URL handling
2. `colab_leecher/utility/task_manager.py` - Add helper functions

**Files to Create:**
- `docs/development/PARALLEL_TASK_IMPLEMENTATION.md` (this file)

**Reference Files:**
- `colab_leecher/__main__.py:1683-2100` - Mindvalley implementation
- `colab_leecher/downlader/mindvalley.py` - TaskContext usage
- `colab_leecher/utility/task_context.py` - TaskContext definition

---

## Success Criteria

### Must Have ✅
- [ ] `/tupload_parallel` command works
- [ ] 3+ concurrent uploads work without interference
- [ ] Each upload has individual progress message
- [ ] Dashboard shows all active uploads
- [ ] Cancellation works per-task
- [ ] Cleanup works (temp files, memory)
- [ ] Legacy `/tupload` still works (no regression)

### Nice to Have 🌟
- [ ] Per-user task limits (e.g., max 3 per user)
- [ ] Better error messages
- [ ] Task queuing (if user exceeds limit)

---

## Next Steps

1. ✅ Create this document
2. ⏳ Implement Part 1-2 (data structures + command)
3. ⏳ Implement Part 3 (URL handler)
4. ⏳ Implement Part 4 (task runner)
5. ⏳ Test thoroughly
6. ⏳ Document usage
7. ⏳ Create PR

---

**Estimated Time:** 6-8 hours for `/tupload_parallel` + testing
**Risk Level:** Low (doesn't affect existing code)
**Value:** High (enables parallel uploads immediately)
