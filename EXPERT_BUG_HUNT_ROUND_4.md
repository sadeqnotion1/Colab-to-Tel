# 🔥 Expert Bug Hunt Round 4: Production Stress Testing & Security Audit

**Difficulty:** Expert Level
**Focus:** Security, Performance, Data Integrity, Silent Failures
**Scope:** Hostile environment readiness, stress testing, attack resistance

---

## 🎯 Mission Brief

You've fixed **21 bugs** across 3 rounds. The system is stable under normal conditions. But what about:

- **Malicious users** sending crafted input to crash the bot?
- **Resource exhaustion** when 20 tasks download 100GB files simultaneously?
- **Data corruption** when downloads interrupted mid-write?
- **Silent failures** where errors are swallowed without logging?
- **Performance degradation** under sustained high load?
- **Race conditions** that only appear under extreme concurrency?

This round focuses on **production hardening** for a hostile, high-load environment.

---

## 🔍 INVESTIGATION CATEGORIES

### 🔐 Category A: Security Vulnerabilities (CRITICAL)

We haven't done ANY security review. This is a massive gap.

#### A1. Path Traversal Attack
**Scenario:** User sends malicious filename to escape workspace directory.

**Example Attack:**
```python
# User sends URL with malicious filename
url = "https://evil.com/../../etc/passwd"  # Path traversal attempt

# Or via custom filename:
/setname ../../../root/.ssh/id_rsa  # Try to overwrite system files
```

**Questions:**
- [ ] Does `task_ctx.work_path` validation prevent `../` sequences?
- [ ] Can user-controlled filenames escape `task_ctx.down_path`?
- [ ] Are extracted archive paths validated (zip slip vulnerability)?
- [ ] Does aria2 output path sanitize malicious filenames?

**Files to Check:**
- `colab_leecher/utility/task_context.py` (path creation)
- `colab_leecher/downlader/aria2.py` (download paths)
- `colab_leecher/utility/helper.py` (filename extraction)
- Archive extraction code (search for `zipfile`, `rarfile`, `extract`)

**Specific Bug Pattern:**
```python
# VULNERABLE CODE:
filename = urlparse(url).path.split('/')[-1]  # e.g., "../../passwd"
download_path = f"{task_ctx.down_path}/{filename}"  # ❌ NOT SANITIZED!
# Result: /BOT_WORK/task_id/Downloads/../../passwd → /BOT_WORK/passwd

# SAFE CODE:
import os
filename = os.path.basename(urlparse(url).path)  # ✅ Removes directory components
# Also check for null bytes, control characters
```

---

#### A2. Command Injection via Filenames
**Scenario:** Malicious filename with shell metacharacters used in system calls.

**Example Attack:**
```python
# User downloads file: "file.txt; rm -rf /"
# If filename used in shell command without escaping...
os.system(f"cp {filename} /destination")  # ❌ COMMAND INJECTION!
```

**Questions:**
- [ ] Are all `os.system()` calls eliminated (use `subprocess` instead)?
- [ ] Are filenames properly escaped in aria2 arguments?
- [ ] Do any file operations use shell=True?
- [ ] Are filenames validated before use in system commands?

**Search Commands:**
```bash
# Find dangerous patterns
grep -r "os.system" --include="*.py" colab_leecher/
grep -r "shell=True" --include="*.py" colab_leecher/
grep -r "subprocess.call.*shell" --include="*.py" colab_leecher/
```

---

#### A3. Arbitrary Code Execution via Archive Extraction
**Scenario:** Malicious zip/rar file with symlinks or absolute paths.

**Attack Vector:**
```python
# Malicious ZIP contents:
# - symlink: important.txt → /etc/passwd
# - absolute path: /root/.ssh/authorized_keys

# When extracted without validation → overwrites system files
```

**Questions:**
- [ ] Does zip extraction validate member paths?
- [ ] Are symlinks in archives handled safely?
- [ ] Can archives write outside extraction directory?
- [ ] Is there a "zip slip" vulnerability?

**Files to Check:**
```bash
# Find archive extraction code
grep -r "zipfile.ZipFile" --include="*.py" colab_leecher/
grep -r "rarfile.RarFile" --include="*.py" colab_leecher/
grep -r "extractall" --include="*.py" colab_leecher/
```

**Vulnerable Pattern:**
```python
# VULNERABLE:
with zipfile.ZipFile(archive_path) as zf:
    zf.extractall(extract_to)  # ❌ No path validation!

# SAFE:
def safe_extract(zf, extract_to):
    for member in zf.namelist():
        # Normalize path and check it's within extract_to
        member_path = os.path.normpath(os.path.join(extract_to, member))
        if not member_path.startswith(os.path.abspath(extract_to)):
            raise ValueError(f"Unsafe path in archive: {member}")
        zf.extract(member, extract_to)
```

---

#### A4. Denial of Service via Resource Exhaustion
**Scenario:** User sends crafted input to exhaust system resources.

**Attack Vectors:**
1. **Zip Bomb:** 1KB zip expands to 1TB (crashes system)
2. **Billion Laughs:** Nested archives that expand exponentially
3. **Infinite Loop:** Malicious URL redirects in circles
4. **Memory Bomb:** 100GB file download with no size check

**Questions:**
- [ ] Is there a maximum file size limit per download?
- [ ] Is total disk usage monitored across all tasks?
- [ ] Are archive extraction sizes validated before extraction?
- [ ] Is there a timeout for HTTP redirects?
- [ ] Can user create 1000+ tasks to exhaust memory?

**Code to Find:**
```bash
# Check for size limits
grep -r "MAX_FILE_SIZE\|max_size\|size_limit" --include="*.py" colab_leecher/

# Check for disk space checks
grep -r "shutil.disk_usage\|statvfs\|df -h" --include="*.py" colab_leecher/
```

---

#### A5. Session/Token Leakage in Logs
**Scenario:** Sensitive data logged in plaintext.

**What to Check:**
- [ ] Are Telegram API tokens logged anywhere?
- [ ] Are user passwords (Instagram, NZB) logged?
- [ ] Are cookie values logged in debug mode?
- [ ] Are URLs with auth tokens sanitized before logging?

**Search for:**
```bash
# Find logging of sensitive data
grep -r "log.debug.*token\|log.info.*password\|log.warning.*cookie" --include="*.py" colab_leecher/

# Check if secrets in exception messages
grep -r "except.*as e:" --include="*.py" colab_leecher/ | head -20
```

**Vulnerable Pattern:**
```python
# VULNERABLE:
url = "https://api.example.com/download?token=SECRET123"
log.info(f"Downloading from: {url}")  # ❌ Logs secret token!

# SAFE:
from urllib.parse import urlparse, parse_qs
parsed = urlparse(url)
safe_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
log.info(f"Downloading from: {safe_url}")  # ✅ Token hidden
```

---

### ⚡ Category B: Performance & Scalability (HIGH)

#### B1. Memory Spike on Large File Operations
**Scenario:** Downloading/uploading 10GB file loads entire file into memory.

**Questions:**
- [ ] Are file operations streaming (not loading entire file)?
- [ ] Does Pyrogram upload use chunked streaming?
- [ ] Are archive operations memory-efficient?
- [ ] Can 20 tasks × 5GB files = 100GB RAM usage crash system?

**Files to Check:**
```bash
# Find file read operations
grep -r "\.read()" --include="*.py" colab_leecher/ | grep -v "\.read(1024"

# Check for .readlines() or similar (loads entire file)
grep -r "readlines\|read_text" --include="*.py" colab_leecher/
```

**Vulnerable Pattern:**
```python
# MEMORY BOMB:
with open(large_file, 'rb') as f:
    data = f.read()  # ❌ Loads entire 10GB file into RAM!
    await client.send_document(chat_id, data)

# SAFE (STREAMING):
await client.send_document(chat_id, large_file)  # ✅ Pyrogram streams it
```

---

#### B2. O(n²) or Worse Algorithms
**Scenario:** Algorithm complexity degrades with task count.

**What to Check:**
- [ ] Dashboard update iterates over tasks (O(n)) - acceptable
- [ ] Task lookup by short_id uses linear search? (Should be O(1) dict)
- [ ] Are there nested loops over task lists?
- [ ] Is there any sorting/searching that's inefficient?

**Example Issue:**
```python
# O(n²) BUG:
for task_id, task_ctx in tasks.items():  # O(n)
    # For each task, search all tasks again
    for other_id, other_ctx in tasks.items():  # O(n)
        if task_ctx.user_id == other_ctx.user_id:
            # ... do something
# Total: O(n²) → 20 tasks = 400 iterations, 100 tasks = 10,000!

# BETTER:
from collections import defaultdict
users = defaultdict(list)
for task_id, task_ctx in tasks.items():  # O(n)
    users[task_ctx.user_id].append(task_ctx)
# Total: O(n) → 100 tasks = 100 iterations
```

---

#### B3. Blocking I/O in Async Functions
**We checked this briefly in Round 3, but need deeper audit.**

**Find ALL blocking operations:**
```bash
# Blocking file operations
grep -r "shutil\.\|os\.path\.exists\|os\.listdir\|os\.remove" --include="*.py" colab_leecher/

# Blocking HTTP (should use aiohttp)
grep -r "requests\.\|urllib\.request" --include="*.py" colab_leecher/

# Blocking subprocess (should use asyncio.create_subprocess)
grep -r "subprocess\.run\|subprocess\.call" --include="*.py" colab_leecher/
```

**Critical Question:**
- [ ] Does `cleanup_old_workspaces()` block event loop with `shutil.rmtree()`?
- [ ] Does dashboard update block with `os.path.exists()` checks?
- [ ] Are there any synchronous HTTP requests in async functions?

**Fix Pattern:**
```python
# BLOCKING (event loop stalled):
async def cleanup():
    shutil.rmtree(path)  # ❌ Blocks for seconds on large directory

# NON-BLOCKING:
async def cleanup():
    await asyncio.to_thread(shutil.rmtree, path)  # ✅ Runs in thread pool
```

---

#### B4. Lock Contention Under High Load
**Scenario:** 20 tasks all trying to update dashboard simultaneously.

**Questions:**
- [ ] How long is `_summary_lock` held during dashboard update?
- [ ] Does building summary text happen inside lock? (Should be outside)
- [ ] Can we reduce lock hold time by preparing data first?
- [ ] Are there lock-free alternatives (lock-free queues, atomic operations)?

**Optimization Pattern:**
```python
# SLOW (lock held during expensive operation):
async with TASK_QUEUE._summary_lock:
    tasks = await TASK_QUEUE.get_all_tasks()  # Lock held
    summary_text = build_complex_summary(tasks)  # ❌ Expensive, blocks others
    await update_message(summary_text)

# FAST (lock held minimally):
tasks = await TASK_QUEUE.get_all_tasks()  # Lock acquired & released quickly
summary_text = build_complex_summary(tasks)  # ✅ Outside lock
async with TASK_QUEUE._summary_lock:
    await update_message(summary_text)  # Lock held only for update
```

---

### 💾 Category C: Data Integrity & Corruption (CRITICAL)

#### C1. Partial Download Not Cleaned on Crash
**Scenario:** Download 50% complete, bot crashes, partial file left on disk.

**Questions:**
- [ ] Does aria2 clean up `.aria2` control files on crash?
- [ ] Are partial downloads resumed or restarted?
- [ ] What happens to 5GB partial file if disk full?
- [ ] Is there a mechanism to detect and clean corrupt files?

**Check Aria2 Behavior:**
```python
# Does aria2.py handle these?
# - .aria2 control files left behind
# - Partial downloads (.part files)
# - Corrupt files from interrupted downloads
# - Resume capability vs fresh download
```

---

#### C2. Workspace Deletion While Files Still Open
**Scenario:** Upload task has file handles open, cleanup tries to delete workspace.

**Questions:**
- [ ] Does workspace cleanup check for open file handles?
- [ ] Can `shutil.rmtree()` fail mid-delete, leaving partial directory?
- [ ] What happens if Pyrogram is still uploading when cleanup runs?
- [ ] Are file handles properly closed in all error paths?

**Race Condition:**
```python
# Thread A (Upload):
with open(f"{task_ctx.work_path}/large_file.bin", 'rb') as f:
    await client.send_document(chat_id, f)  # ❌ File handle open

# Thread B (Cleanup - simultaneous):
shutil.rmtree(task_ctx.work_path)  # ❌ Tries to delete open file!
# Result: OSError or partial deletion
```

---

#### C3. Task State Inconsistency
**Scenario:** Task marked completed but files not uploaded, or vice versa.

**Invalid State Checks:**
```python
# Can these states exist simultaneously?
if task_ctx.is_completed and task_ctx.is_cancelled:  # Both True?
if task_ctx.is_completed and not task_ctx.transfer.sent_file:  # Completed but no uploads?
if task_ctx.error.state and task_ctx.is_completed:  # Error AND completed?
```

**State Machine Verification:**
- [ ] Is there a clear state transition diagram?
- [ ] Can task be in multiple terminal states?
- [ ] Are state transitions atomic?
- [ ] Is state validated before transitions?

**Proposed States (for comparison):**
```python
class TaskState(Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    DOWNLOADING = "downloading"
    PROCESSING = "processing"  # Extracting, converting, etc.
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# Only ONE state at a time, clear transitions
```

---

#### C4. Database/Persistence Missing
**Scenario:** Bot crashes, all task state lost, users don't know what completed.

**Critical Questions:**
- [ ] Is task state persisted to disk anywhere?
- [ ] If bot restarts, can it resume in-progress tasks?
- [ ] Are completed task records kept for user history?
- [ ] Is there a "recover from crash" mechanism?

**Impact:**
- User starts 10 downloads overnight
- 5 complete, bot crashes at 3 AM
- Bot restarts, no record of which completed
- User has to manually check files and restart

**Recommendation (if missing):**
```python
# Simple SQLite persistence
import sqlite3

class TaskPersistence:
    def save_task_state(self, task_ctx):
        # Save to disk: task_id, state, progress, files uploaded
        pass

    def load_incomplete_tasks(self):
        # On startup, load tasks that were in-progress
        pass
```

---

### 🔇 Category D: Silent Failures (HIGH)

#### D1. Exceptions Swallowed Without Logging
**Scenario:** `except Exception: pass` silently hides critical errors.

**Search for Silent Failures:**
```bash
# Find bare except blocks
grep -r "except:" --include="*.py" colab_leecher/

# Find exception handlers that don't log
grep -r "except.*:" --include="*.py" colab_leecher/ | grep -v "log\."

# Find pass in except blocks
grep -A 1 "except" colab_leecher/**/*.py | grep "pass"
```

**Dangerous Patterns:**
```python
# SILENT FAILURE:
try:
    critical_operation()
except:
    pass  # ❌ Error swallowed, no logging, no recovery

# BETTER:
try:
    critical_operation()
except Exception as e:
    log.error(f"Critical operation failed: {e}", exc_info=True)
    # Maybe retry, or notify user
```

---

#### D2. Background Tasks That Crash Silently
**Scenario:** `periodic_cleanup_task()` crashes, never restarts, memory leaks accumulate.

**Check:**
```python
# In __main__.py startup:
loop.create_task(periodic_cleanup_task())  # ❌ If crashes, stops forever

# Is there exception handling inside?
async def periodic_cleanup_task():
    while True:
        try:
            await asyncio.sleep(3600)
            await cleanup()
        except Exception as e:
            log.error(f"Cleanup failed: {e}")  # ✅ Logged
            # But does it continue the loop? Check!
```

**Questions:**
- [ ] Does periodic cleanup have a try-except INSIDE the while loop?
- [ ] If cleanup crashes, does the loop continue or exit?
- [ ] Are there any other background tasks that could crash silently?
- [ ] Is there monitoring to detect when background tasks stop?

---

#### D3. Telegram API Errors Not Propagated
**Scenario:** `send_document()` fails, file not uploaded, but task marked completed.

**Check Upload Flows:**
```python
# Is this pattern used anywhere?
try:
    await client.send_document(chat_id, file)
except Exception as e:
    log.warning(f"Upload failed: {e}")  # ❌ Logged but not propagated
    # Task continues, marks completed, user thinks file uploaded!

# Should be:
try:
    result = await client.send_document(chat_id, file)
    task_ctx.transfer.sent_file.append(result)  # ✅ Track success
except Exception as e:
    log.error(f"Upload failed: {e}")
    task_ctx.error.set_error(str(e))  # ✅ Propagate error
    raise  # ✅ Fail the task
```

---

#### D4. Aria2 Download Failures Not Detected
**Scenario:** Aria2 returns exit code 1 (error), but code doesn't check it properly.

**Review `aria2.py`:**
```python
# After await proc.wait():
exit_code = proc.returncode

# Is EVERY error exit code handled?
if exit_code != 0:
    # Are all error codes mapped correctly?
    # Is error propagated to task_ctx.error?
    # Or silently ignored?
```

**Question:**
- [ ] Does aria2 wrapper raise exception on download failure?
- [ ] Or does it return False and caller ignores return value?
- [ ] Are there aria2 warnings/errors that don't affect exit code?

---

### 🔄 Category E: State Machine & Lifecycle Bugs (MEDIUM)

#### E1. Task Lifecycle Not Enforced
**Scenario:** Task can transition from DOWNLOADING directly to CANCELLED, skipping cleanup.

**State Transition Matrix:**
Create a table of allowed transitions:

| From State   | To State     | Allowed? | Cleanup Actions Required |
|--------------|--------------|----------|--------------------------|
| CREATED      | DOWNLOADING  | ✅       | Create workspace         |
| DOWNLOADING  | UPLOADING    | ✅       | Validate files           |
| DOWNLOADING  | CANCELLED    | ✅       | Kill aria2, cleanup      |
| DOWNLOADING  | COMPLETED    | ❌       | Must go through UPLOADING|
| UPLOADING    | CANCELLED    | ✅       | Delete partial uploads?  |
| COMPLETED    | CANCELLED    | ❌       | Invalid transition       |

**Questions:**
- [ ] Is this transition matrix enforced in code?
- [ ] Can task skip required cleanup steps?
- [ ] What if task transitions while in inconsistent state?

---

#### E2. Callback Query for Deleted Task
**Scenario:** User presses cancel button for task that already completed.

**Race Condition:**
```python
# T+0: User presses cancel button (callback_data="cancel:abc123")
# T+1: Task completes, removed from queue
# T+2: Callback handler runs, looks up task by short_id
# T+3: Task not found, what happens?

# Current code (line 1901-1904):
if not task_ctx:
    await callback_query.answer("Task not found...", show_alert=True)
    return  # ✅ Handles it

# But are there other callbacks that assume task exists?
```

**Check ALL Callback Handlers:**
- [ ] Do all task-specific callbacks check if task still exists?
- [ ] Are callback data validated (could be from old bot session)?
- [ ] Can malicious user craft callback_data to access other user's tasks?

---

#### E3. Task Removal Not Atomic with Dashboard Update
**Scenario:** Task removed from queue, dashboard shows it as active (stale).

**Current Flow:**
```python
# In run_parallel_task finally block:
await TASK_QUEUE.remove_task(task_ctx.task_id)  # Step 1
# ... cleanup code ...
await force_update_summary(client)  # Step 2 (much later)

# Between step 1 and 2: dashboard shows task that's not in queue!
```

**Question:**
- [ ] Should dashboard update be IMMEDIATELY after removal?
- [ ] Or is delayed update (2 seconds later) acceptable?
- [ ] Can this cause user confusion?

---

### 🔥 Category F: Stress Test Scenarios (EXPERT)

#### F1. Fork Bomb via Nested Archives
**Scenario:** User uploads `bomb.zip` containing 1000 nested zips, each containing 1000 more.

**Attack:**
```
bomb.zip
├── archive1.zip (contains 1000 archives)
│   ├── archive1_1.zip (contains 1000 archives)
│   │   ├── archive1_1_1.zip
│   │   └── ... (999 more)
│   └── ... (999 more)
└── ... (999 more)

Total files: 1000^3 = 1 billion files
```

**Questions:**
- [ ] Is there a maximum recursion depth for extraction?
- [ ] Is there a total extracted file count limit?
- [ ] Does extraction timeout after X seconds?
- [ ] Can this crash the bot with memory exhaustion?

---

#### F2. Simultaneous Task Completion Storm
**Scenario:** 20 tasks all complete within 10ms (test synchronization).

**Stress Test:**
```python
# Simulate by downloading 20 tiny files simultaneously
urls = ["https://example.com/1byte.txt"] * 20

# All complete nearly simultaneously
# Do all these happen atomically?
# - 20× remove_task()
# - 20× force_update_summary()
# - 20× workspace cleanup
# - Dashboard bombarded with updates

# Potential issues:
# - Dashboard update races
# - Lock contention causes delays
# - Cleanup runs while tasks still active
# - Debouncing prevents final update
```

---

#### F3. Disk Full Mid-Download
**Scenario:** 100GB download, disk fills up at 50GB.

**Questions:**
- [ ] Does aria2 detect disk full gracefully?
- [ ] Is error propagated to user?
- [ ] Is partial file cleaned up?
- [ ] Can bot recover and continue other tasks?
- [ ] Does bot check available space before starting downloads?

**Recommended Check:**
```python
import shutil

def check_disk_space(required_bytes):
    usage = shutil.disk_usage("/")
    available = usage.free
    if available < required_bytes:
        raise InsufficientDiskSpaceError(f"Need {required_bytes}, have {available}")
```

---

#### F4. API Rate Limit Death Spiral
**Scenario:** Bot hits Telegram FloodWait(3600), all tasks stalled for 1 hour.

**Current Handling:**
- Pyrogram auto-waits on FloodWait
- But does this block the entire event loop?
- Or just that specific task?

**Questions:**
- [ ] If one upload gets FloodWait(3600), do other tasks continue?
- [ ] Is FloodWait wait time shared across all tasks?
- [ ] Can user cancel tasks during FloodWait?
- [ ] Is there a maximum wait time before giving up?

---

### 🛡️ Category G: Input Validation (CRITICAL)

#### G1. Unsanitized User Input in Messages
**Scenario:** User sends filename with HTML/Markdown injection.

**Attack:**
```python
# User sets filename to:
</b>**ADMIN ACCESS GRANTED**<b>

# Bot sends message:
await message.reply_text(f"Downloading: {filename}")
# Result: Message formatting broken, looks like admin message
```

**Questions:**
- [ ] Are all user inputs HTML-escaped before display?
- [ ] Can user inject Markdown formatting to impersonate bot?
- [ ] Are there length limits on user-provided names?

**Fix:**
```python
from html import escape

filename = escape(user_provided_filename)  # ✅ Sanitize
await message.reply_text(f"Downloading: {filename}")
```

---

#### G2. URL Validation Bypass
**Scenario:** User sends non-HTTP URL to bypass validation.

**Attack Vectors:**
```python
# Local file access:
url = "file:///etc/passwd"

# Server-side request forgery (SSRF):
url = "http://169.254.169.254/latest/meta-data/"  # AWS metadata

# Localhost access:
url = "http://localhost:6800/jsonrpc"  # Aria2 RPC interface
```

**Questions:**
- [ ] Are URLs validated to be http/https only?
- [ ] Are localhost/internal IP ranges blocked?
- [ ] Can user access internal services via SSRF?

**Safe URL Validation:**
```python
from urllib.parse import urlparse

def validate_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError("Only HTTP/HTTPS URLs allowed")

    # Block localhost and internal IPs
    if parsed.hostname in ('localhost', '127.0.0.1', '0.0.0.0'):
        raise ValueError("Localhost access forbidden")

    # Block private IP ranges (10.x, 192.168.x, etc.)
    # ... additional checks
```

---

#### G3. Integer Overflow in Size Calculations
**Scenario:** Malicious server sends `Content-Length: 9999999999999999999`.

**Vulnerable Code:**
```python
# If content_length is parsed as string then converted:
content_length = int(headers['Content-Length'])  # Could overflow
total_size = content_length * num_files  # ❌ Massive number

# Or arithmetic overflow:
percentage = (downloaded_bytes / total_size) * 100  # Division by huge number
```

**Questions:**
- [ ] Are size calculations validated for overflow?
- [ ] Is there a maximum allowed file size constant?
- [ ] Can malicious Content-Length crash the bot?

---

## 🎯 PRIORITY BUG HUNT CHECKLIST

### 🔴 **CRITICAL - Check First:**
- [ ] **Path Traversal** - Can user escape workspace directory?
- [ ] **Command Injection** - Are filenames used in shell commands safely?
- [ ] **Zip Slip** - Can archives write outside extraction dir?
- [ ] **DoS Resource Exhaustion** - Is there size/count limiting?
- [ ] **Data Corruption** - Are partial downloads handled correctly?

### 🟠 **HIGH - Check Second:**
- [ ] **Silent Failures** - Are all exceptions logged?
- [ ] **Memory Leaks** - Are large files streamed, not loaded?
- [ ] **State Inconsistency** - Can task be in multiple terminal states?
- [ ] **Background Task Crashes** - Does periodic cleanup have error handling?

### 🟡 **MEDIUM - Check Third:**
- [ ] **Blocking I/O** - Is event loop blocked by sync operations?
- [ ] **Lock Contention** - Is lock held during expensive operations?
- [ ] **Input Validation** - Are URLs/filenames sanitized?
- [ ] **Callback Validation** - Do handlers check if task exists?

---

## 🧪 STRESS TEST EXECUTION PLAN

### Test 1: Path Traversal Attack
```python
# Send these URLs to bot:
urls = [
    "https://example.com/../../etc/passwd",
    "https://example.com/file%2e%2e%2fpasswd",  # URL encoded
    "https://example.com/file....//passwd",  # Multiple dots
]
# Expected: Bot rejects or sanitizes to safe filename
# Bug if: File created outside workspace
```

### Test 2: Zip Bomb
```python
# Create test zip bomb:
# 1KB file that expands to 1GB
# Upload to bot
# Expected: Extraction fails with size limit error
# Bug if: System crashes or runs out of disk
```

### Test 3: Concurrent Completion Storm
```python
# Start 20 tasks with 1KB files
# All complete within milliseconds
# Expected: Dashboard updates correctly to show 0 tasks
# Bug if: Dashboard shows stale tasks, crashes, or locks up
```

### Test 4: Disk Full Simulation
```python
# Fill disk to 99% capacity
# Start large download
# Expected: Download fails gracefully with clear error
# Bug if: Bot crashes, partial file not cleaned, or no error shown
```

### Test 5: Malicious Filename Injection
```python
# Set filename to:
filename = "<script>alert('XSS')</script>"
# Or: filename = "**FAKE ADMIN MESSAGE**"
# Expected: Filename sanitized/escaped in messages
# Bug if: Formatting broken or injected HTML rendered
```

---

## 📋 EXPERT BUG REPORT FORMAT

```markdown
## Bug #X: [Name]
**Category:** [Security/Performance/Data Integrity/Silent Failure]
**Severity:** [Critical/High/Medium/Low]
**Attack Vector:** [How can this be exploited?]
**Location:** [file:line]

**Vulnerability Description:**
[Clear explanation of security/reliability issue]

**Exploit Scenario:**
[Step-by-step attack or failure scenario]

**Impact:**
- **Confidentiality:** [Data leakage risk]
- **Integrity:** [Data corruption risk]
- **Availability:** [DoS/crash risk]

**Proof of Concept:**
```python
# Code or commands to reproduce
```

**Fix:**
```python
# Secure implementation
```

**Testing:**
[How to verify fix works and vulnerability is closed]
```

---

## 🎯 SUCCESS CRITERIA

Your Round 4 hunt is complete when you can answer YES to:

- [ ] System resists path traversal attacks
- [ ] No command injection vulnerabilities exist
- [ ] Archive extraction is secure (no zip slip)
- [ ] Resource exhaustion is prevented (size/count limits)
- [ ] All exceptions are logged (no silent failures)
- [ ] Large files are streamed (no memory bombs)
- [ ] State machine transitions are validated
- [ ] Background tasks are fault-tolerant
- [ ] Blocking I/O is eliminated from async functions
- [ ] User input is sanitized before use/display
- [ ] System survives stress tests without crashes
- [ ] Data integrity is maintained during failures

---

## 🏆 EXPERT LEVEL EXPECTATIONS

This round should find:
- **5-10 security vulnerabilities** (path traversal, injection, etc.)
- **3-5 silent failure points** (swallowed exceptions)
- **2-4 performance bottlenecks** (blocking I/O, O(n²) algorithms)
- **3-6 data integrity issues** (partial writes, state corruption)
- **2-3 stress test failures** (concurrent completion, disk full, etc.)

**Total Expected:** 15-28 expert-level bugs

Focus on **production readiness for hostile environments** - assume users will try to break, exploit, or abuse the system.

---

**Good hunting! This is the final boss level. 🎮**
