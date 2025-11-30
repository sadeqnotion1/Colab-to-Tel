# Extract Command Enhancement Plan
## Streaming Extraction + Upload for Large Archives (65GB+)

---

## Problem Statement

### Current Issues:
1. **Standalone `/extract` command has NO progress bars** - Runs silently in background
2. **Large RAR files (65GB) can't be processed** - Requires 2x disk space (archive + extracted = 130GB)
3. **Upload blocked until extraction completes** - No parallelization
4. **Colab free tier has ~100GB disk** - Archives >50GB fail

### User Requirements:
- Extract multi-part RAR files from Google Drive (e.g., 65GB Udemy course)
- Upload extracted files to Telegram WITHOUT storing the full archive
- Show real-time progress during extraction and upload
- Work within Colab's disk space constraints

---

## Solution Architecture

### Two-Track Implementation:

### **Track 1: Fix Standalone `/extract` Progress Bars** (Quick Win)
- Add MSG.status_msg assignment
- Add thumbnail support (following Mindvalley pattern)
- Show real-time extraction progress
- **Estimated Time:** 1-2 hours

### **Track 2: Streaming Extract-Upload** (Solves 65GB Problem)
- Create `extract_and_upload_streaming()` function
- Extract → Upload → Delete (one file at a time)
- Reduce disk usage from 130GB → ~5GB
- **Estimated Time:** 3-4 hours

---

## Track 1: Standalone `/extract` with Progress Bars

### Current Flow (BROKEN):

```python
# __main__.py lines 1004-1072
async def _handle_extract_input(client, message):
    status_msg = await message.reply_text("📂 Starting extraction...")  # ← Local variable

    success, result_msg = await _perform_extraction(archive_path, file_filter)
    #                           ↑ No task_ctx, no MSG.status_msg
    #                           ↓ status_bar() has nothing to update!

    await status_msg.edit_text(result_msg)  # ← Only shows final result
```

**Why Progress Doesn't Show:**
- `MSG.status_msg` is never set (global is None)
- `status_bar()` in converters.py tries to edit `MSG.status_msg` → fails silently
- User only sees "Starting..." then "Complete!" with no intermediate updates

### Fix Implementation:

#### Step 1: Add Thumbnail Support

**File:** `__main__.py` - Modify all three extract entry points

**Entry Point A:** `_handle_extract_input()` (lines 1004+)

```python
async def _handle_extract_input(client, message):
    global BOT, Paths, MSG, extract_request_msg
    import os

    # ... path parsing logic ...

    # ✅ ADD: Download random thumbnail (following Mindvalley pattern)
    hero_image_path = Paths.HERO_IMAGE
    if thumbnail_urls:
        import random, aiohttp, aiofiles
        chosen_url = random.choice(thumbnail_urls)

        async with aiohttp.ClientSession() as session:
            async with session.get(chosen_url, timeout=30) as response:
                if response.status == 200:
                    async with aiofiles.open(hero_image_path, mode='wb') as f:
                        while chunk := await response.content.read(1024):
                            await f.write(chunk)

    # ✅ ADD: Determine thumbnail path (priority: custom > random > default)
    if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
        thumb_path = Paths.THMB_PATH
    elif os.path.exists(Paths.HERO_IMAGE):
        thumb_path = Paths.HERO_IMAGE
    else:
        thumb_path = Paths.DEFAULT_HERO

    # ✅ ADD: Create status header
    status_text = (
        f"<b>📂 Archive Extraction »</b>\n\n"
        f"<b>📦 Archive:</b> <code>{os.path.basename(archive_path)}</code>\n"
        f"<b>📂 Output:</b> <code>{Paths.temp_unzip_path}</code>\n\n"
        f"<i>Initializing...</i>"
    )

    # ✅ CHANGE: Use send_photo() instead of send_message()
    if os.path.exists(thumb_path):
        status_msg = await client.send_photo(
            message.from_user.id,
            photo=thumb_path,
            caption=status_text,
            reply_markup=keyboard()
        )
    else:
        status_msg = await message.reply_text(status_text)

    # ✅ ADD: Link to global MSG.status_msg
    MSG.status_msg = status_msg

    # Extract
    success, result_msg = await _perform_extraction(archive_path, file_filter)

    # Update final message
    await status_msg.edit_caption(caption=result_msg) if hasattr(status_msg, 'photo') and status_msg.photo else await status_msg.edit_text(result_msg)
```

**Entry Point B:** `_process_extract_reply()` (lines 972+) - Same changes
**Entry Point C:** `extract_archive()` (lines 1074+) - Same changes

#### Step 2: Update Messages Class

**File:** `variables.py` - Add extraction message template

```python
class Messages:
    # ... existing fields ...

    # ✅ ADD: Extraction status header
    extract_head = f"<b>📂 EXTRACTING »</b>\n"
```

#### Step 3: Ensure status_bar() Handles Task-less Mode

**File:** `helper.py` - Verify status_bar() works without task_ctx

```python
# Lines 1374-1376 - Already correct:
status_msg = task_ctx.status_msg if task_ctx else MSG.status_msg

# This means: If no task_ctx, use global MSG.status_msg
# ✅ No changes needed - already supports standalone mode!
```

#### Step 4: Update extraction progress messages

**File:** `converters.py` - Improve status messages

**Current** (line 1086):
```python
status_text = f"Extracting file {files_extracted}/{total_files}: {member.filename}"
```

**Enhanced:**
```python
# Add file size and percentage to status
file_size_mb = member.file_size / (1024*1024)
status_text = (
    f"Extracting {files_extracted}/{total_files}\n"
    f"<code>{member.filename}</code> ({file_size_mb:.1f} MB)"
)
```

### Expected Result (Track 1):

**Before:**
```
📂 Starting extraction...
[13 minutes of silence]
✅ Extraction complete! 150 files extracted
```

**After:**
```
[Thumbnail Image]
📂 Archive Extraction »
📦 Archive: course.part01.rar
📂 Output: /Unzipped_Files

╭「████████░░░░」 » 66.7%
├⚡️ Speed » N/A
├⚙️ Engine » Streaming Extractor (rarfile)
├⏳ ETA » 4m 30s
├⏱️ Elapsed » 8m 45s
├✅ Done » Extracting 100/150
│         video_05.mp4 (250.5 MB)
╰📦 Total » Unknown
```

---

## Track 2: Streaming Extract-Upload (65GB Support)

### Current Flow (INEFFICIENT):

```
User: /leech with mode_type="unzip"
    ↓
Do_Leech():
    [Phase 1] Download RAR → /Downloads/ (65 GB)
    ↓
    [Phase 2] Extract ALL files → /Unzipped_Files/ (65 GB)
    │         ↑ Blocks for 10-15 minutes
    │         ↑ Disk usage: 130 GB total!
    ↓
    [Phase 3] Upload ALL files from /Unzipped_Files/
              ↑ Can't start until extraction 100% done

❌ Problem: Colab free tier has ~100GB disk → FAILS
```

### Streaming Flow (EFFICIENT):

```
User: /leech with mode_type="stream_unzip" (new mode)
    ↓
Do_Leech():
    [Phase 1] Download RAR → /Downloads/ (65 GB)
    ↓
    [Phase 2+3 PARALLEL] For each file in archive:
        Extract file → /tmp/file_01.mp4 (500 MB)
            ↓
        Upload file → Telegram
            ↓
        Delete /tmp/file_01.mp4
            ↓
        Extract next file → /tmp/file_02.mp4
        ...

✅ Solution: Peak disk usage = 65GB (archive) + 500MB (temp) = 65.5GB
```

### Implementation:

#### Step 1: Create Streaming Extract-Upload Function

**File:** `converters.py` - Add new function

```python
async def extract_and_upload_streaming(
    rar_filepath: str,
    password: str = None,
    file_filter: list = None,
    task_ctx: TaskContext = None
) -> bool:
    """
    Extract RAR members one-by-one and upload immediately.
    Memory and disk efficient for large archives.

    Args:
        rar_filepath: Path to RAR archive (can be .part01.rar)
        password: Optional password
        file_filter: List of extensions to extract (e.g., ['.mkv', '.mp4'])
        task_ctx: Task context for isolated state

    Returns:
        True if all files extracted and uploaded successfully
    """
    import rarfile
    import os
    import time
    from datetime import datetime
    from .helper import status_bar, getTime, sizeUnit

    # Get context objects
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error
        _msg = task_ctx.msg
        _bot = task_ctx.bot
    else:
        from .variables import Paths, Messages, TaskError, MSG, BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _msg = MSG
        _bot = BOT

    # Validate inputs
    if not ospath.exists(rar_filepath):
        log.error(f"RAR file not found: {rar_filepath}")
        _task_error.state = True
        _task_error.text = f"Archive not found: {rar_filepath}"
        return False

    # Create temp directory for single-file extraction
    temp_extract_dir = "/tmp/streaming_extract"
    os.makedirs(temp_extract_dir, exist_ok=True)

    # Open RAR archive
    try:
        rar_ref = rarfile.RarFile(rar_filepath, pwd=password)
    except rarfile.BadRarFile as e:
        log.error(f"Invalid RAR archive: {e}")
        _task_error.state = True
        return False
    except rarfile.PasswordRequired:
        log.error("Password required for RAR archive")
        _task_error.state = True
        return False

    # Get list of members to extract
    members = rar_ref.infolist()

    # Apply file filter if provided
    if file_filter:
        members_to_extract = [
            m for m in members
            if not m.is_dir() and any(m.filename.lower().endswith(ext.lower()) for ext in file_filter)
        ]
    else:
        members_to_extract = [m for m in members if not m.is_dir()]

    total_files = len(members_to_extract)
    log.info(f"Starting streaming extraction of {total_files} files from {os.path.basename(rar_filepath)}")

    # Statistics
    start_time = time.time()
    files_processed = 0
    bytes_uploaded = 0

    # Status header
    status_head = (
        f"<b>🔄 Streaming Extract + Upload »</b>\n\n"
        f"<b>📦 Archive:</b> <code>{os.path.basename(rar_filepath)}</code>\n"
    )

    # Import upload function
    from ..uploader.telegram import upload_file

    # Process each file
    for idx, member in enumerate(members_to_extract, 1):
        try:
            # Calculate progress
            percentage = (idx / total_files) * 100
            elapsed = time.time() - start_time
            eta_seconds = (elapsed / idx) * (total_files - idx) if idx > 0 else 0
            eta_str = getTime(eta_seconds) if eta_seconds > 0 else "N/A"

            # Extract single file to temp location
            temp_file_path = os.path.join(temp_extract_dir, os.path.basename(member.filename))

            # Update status: Extracting
            status_text = (
                f"📂 Extracting {idx}/{total_files}\n"
                f"<code>{member.filename}</code> ({sizeUnit(member.file_size)})"
            )

            await status_bar(
                down_msg=status_head,
                speed="N/A",
                percentage=percentage - 25,  # 0-25% extraction, 25-75% upload, 75-100% cleanup
                eta=eta_str,
                done=status_text,
                total_size=f"{files_processed}/{total_files} files",
                engine="Streaming Extractor+Uploader",
                task_ctx=task_ctx
            )

            # Extract with streaming
            log.info(f"Extracting {member.filename} ({sizeUnit(member.file_size)})")
            with rar_ref.open(member, 'r') as source:
                with open(temp_file_path, 'wb') as dest:
                    while True:
                        chunk = source.read(1024 * 1024)  # 1 MB chunks
                        if not chunk:
                            break
                        dest.write(chunk)

            log.info(f"Extracted to temp: {temp_file_path}")

            # Update status: Uploading
            status_text = (
                f"⬆️ Uploading {idx}/{total_files}\n"
                f"<code>{member.filename}</code> ({sizeUnit(member.file_size)})"
            )

            await status_bar(
                down_msg=status_head,
                speed="N/A",
                percentage=percentage,
                eta=eta_str,
                done=status_text,
                total_size=f"{files_processed}/{total_files} files",
                engine="Streaming Extractor+Uploader",
                task_ctx=task_ctx
            )

            # Upload file to Telegram
            log.info(f"Uploading {member.filename} to Telegram")
            upload_success = await upload_file(
                file_path=temp_file_path,
                filename=member.filename,
                task_ctx=task_ctx
            )

            if not upload_success:
                log.error(f"Upload failed for {member.filename}")
                _task_error.state = True
                _task_error.text = f"Upload failed: {member.filename}"
                # Don't abort - try to continue with other files
            else:
                bytes_uploaded += member.file_size
                files_processed += 1
                log.info(f"Uploaded {member.filename} successfully")

            # Delete temp file immediately
            try:
                os.remove(temp_file_path)
                log.debug(f"Deleted temp file: {temp_file_path}")
            except OSError as e:
                log.warning(f"Could not delete temp file {temp_file_path}: {e}")

        except Exception as e:
            log.error(f"Error processing {member.filename}: {e}", exc_info=True)
            _task_error.state = True
            # Continue with next file
            continue

    # Cleanup
    try:
        import shutil
        shutil.rmtree(temp_extract_dir)
    except:
        pass

    # Final status
    elapsed_total = time.time() - start_time

    await status_bar(
        down_msg=status_head,
        speed="N/A",
        percentage=100.0,
        eta="Complete",
        done=f"✅ Processed {files_processed}/{total_files} files ({sizeUnit(bytes_uploaded)})",
        total_size=f"{files_processed} files",
        engine="Streaming Extractor+Uploader",
        task_ctx=task_ctx
    )

    log.info(f"Streaming extract-upload completed: {files_processed}/{total_files} files in {getTime(elapsed_total)}")

    rar_ref.close()
    return files_processed == total_files
```

#### Step 2: Add New Mode Type

**File:** `variables.py` - Add stream_unzip mode

```python
# No changes needed - mode types are strings, not enum
# Just document the new mode in comments:

class BotMode:
    """
    Bot operation modes:
    - mode: "leech" | "mirror" | "dir-leech"
    - type: "normal" | "zip" | "unzip" | "undzip" | "stream_unzip" (new!)

    stream_unzip: Extract and upload files one-by-one for large archives
    """
    mode = ""
    type = ""
```

#### Step 3: Integrate into Do_Leech()

**File:** `task_manager.py` - Modify Do_Leech() function

```python
# Lines 1030-1050 - Add new conditional branch

is_dualzip = (_bot.Mode.type == "undzip")
is_unzip = (_bot.Mode.type == "unzip")
is_stream_unzip = (_bot.Mode.type == "stream_unzip")  # ✅ NEW
is_zip = (_bot.Mode.type == "zip")

# ... (existing code for is_dualzip, is_zip) ...

elif is_stream_unzip:  # ✅ NEW BRANCH
    log.debug(">>> Calling Streaming Extract+Upload Handler...")
    from ..utility.converters import extract_and_upload_streaming

    # Find RAR archives in download directory
    items_in_dir = await asyncio.to_thread(listdir, process_path)
    rar_files = [
        f for f in items_in_dir
        if f.lower().endswith(('.rar', '.part01.rar', '.part001.rar'))
    ]

    if not rar_files:
        log.error("No RAR archives found for streaming extraction")
        _task_error.state = True
    else:
        # Process first RAR (or all RARs in directory)
        archive_path = ospath.join(process_path, rar_files[0])

        # Extract + Upload + Delete in streaming mode
        success = await extract_and_upload_streaming(
            rar_filepath=archive_path,
            password=_bot.Options.unzip_pswd if _bot.Options.unzip_pswd else None,
            file_filter=None,  # Extract all files
            task_ctx=task_ctx
        )

        if not success:
            log.error(">>> Streaming extract-upload failed.")
            _task_error.state = True
        else:
            log.info(">>> Streaming extract-upload completed successfully")
            # No need to call Leech() - files already uploaded!
            skip_leech = True  # ✅ Add this flag

elif is_unzip:  # Existing unzip logic
    # ... (unchanged) ...

# Lines 1066+ - Skip Leech if already uploaded
if skip_leech:  # ✅ NEW CHECK
    log.info("Files already uploaded via streaming - skipping Leech()")
elif leech_path and ospath.exists(leech_path):
    # ... (existing Leech call) ...
```

#### Step 4: Add Command Argument for Stream Mode

**File:** `__main__.py` - Update command handlers

```python
# Example: /leech command with stream_unzip mode
@colab_bot.on_message(filters.command("streamleech") & filters.private)
async def stream_leech_handler(client, message):
    """
    Stream extract and upload for large archives.
    Usage: /streamleech [URL or send files]
    """
    BOT.Mode.mode = "leech"
    BOT.Mode.type = "stream_unzip"  # ✅ Set streaming mode
    BOT.State.started = True

    # ... rest of leech command logic ...
```

**OR** - Add as option to existing /leech:

```python
# /leech --stream
if "--stream" in message.command or "-s" in message.command:
    BOT.Mode.type = "stream_unzip"
```

### Expected Result (Track 2):

**Disk Usage:**
- Before: 65GB (archive) + 65GB (extracted) = **130GB** ❌ FAILS on Colab
- After: 65GB (archive) + 500MB (temp file) = **65.5GB** ✅ WORKS on Colab

**Timeline:**
- Before: Extract (15 min) → Upload (20 min) = **35 min total**
- After: Extract+Upload parallel (25 min) = **25 min total** (30% faster)

**Progress Display:**
```
[Thumbnail]
🔄 Streaming Extract + Upload »
📦 Archive: course.part01.rar

╭「█████████░░░」 » 75.0%
├⚡️ Speed » N/A
├⚙️ Engine » Streaming Extractor+Uploader
├⏳ ETA » 6m 15s
├⏱️ Elapsed » 18m 45s
├✅ Done » ⬆️ Uploading 113/150
│         lecture_113_final_project.mp4 (450.2 MB)
╰📦 Total » 113/150 files
```

---

## Implementation Order

### Phase 1: Quick Wins (1-2 hours)
1. ✅ Fix standalone `/extract` progress bars (Track 1)
2. ✅ Test with small RAR file (100MB)
3. ✅ Verify thumbnail persistence

### Phase 2: Core Feature (2-3 hours)
4. ✅ Implement `extract_and_upload_streaming()` (Track 2)
5. ✅ Add `stream_unzip` mode to Do_Leech()
6. ✅ Test with medium RAR (5GB)

### Phase 3: Integration (1 hour)
7. ✅ Add `/streamleech` command
8. ✅ Update CLAUDE.md documentation
9. ✅ Test with large RAR (20GB+)

### Phase 4: Optimization (Optional)
10. Parallel extraction + upload workers
11. Resume support for interrupted stream uploads
12. Auto-detect large archives and suggest stream mode

---

## Testing Checklist

### Track 1 Tests:
- [ ] `/extract` shows thumbnail (not text-only)
- [ ] Progress bar updates every file (0% → 100%)
- [ ] ETA and elapsed time display correctly
- [ ] Final message shows file count and size
- [ ] Works with multi-part RAR (.part01.rar)
- [ ] Works with file filters (`/extract .mkv`)

### Track 2 Tests:
- [ ] Streaming mode uses <2x disk space
- [ ] Files upload during extraction (not after)
- [ ] Temp files deleted after upload
- [ ] Works with 65GB+ archives
- [ ] Progress bar shows current file name
- [ ] Upload failures don't abort entire batch

### Edge Cases:
- [ ] Password-protected RAR
- [ ] Corrupted RAR file
- [ ] Network interruption during upload
- [ ] Colab disconnection (resume capability)
- [ ] Empty archive
- [ ] Single-file archive

---

## File Modifications Summary

| File | Lines | Changes | Complexity |
|------|-------|---------|------------|
| `__main__.py` | 1004-1100+ | Add thumbnail + MSG.status_msg | Low |
| `converters.py` | NEW | Add extract_and_upload_streaming() | Medium |
| `task_manager.py` | 1030-1070 | Add stream_unzip mode handling | Low |
| `variables.py` | 136-146 | Add extract_head message template | Trivial |
| `CLAUDE.md` | NEW | Document streaming pattern | Trivial |

**Total Lines Added:** ~200
**Total Lines Modified:** ~50
**Estimated Time:** 4-6 hours total

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Upload failure leaves temp files | Disk fills up | Add cleanup try/finally block |
| Network timeout during large file upload | Lost progress | Add resume state tracking |
| RAR password not provided | Extraction fails | Prompt user for password |
| Colab timeout during stream | Partial upload | Save upload state, resume on reconnect |
| Parallel uploads saturate network | Slow uploads | Limit to 1-2 parallel uploads |

---

## Success Metrics

### Functional:
- ✅ `/extract` shows real-time progress (not silent)
- ✅ 65GB RAR processes without disk errors
- ✅ Streaming mode uses <70GB disk space
- ✅ Upload starts within 2 minutes of extraction start

### Performance:
- ⏱️ Streaming mode 20-30% faster than batch mode
- 💾 Peak disk usage: archive_size * 1.1 (vs. 2.0 before)
- 🧠 Memory usage: <500MB (vs. <200MB before)

### User Experience:
- 📊 Progress bar updates every 5-10 seconds
- 🖼️ Thumbnail persists throughout process
- ⏳ ETA accuracy within 20% of actual time
- ✅ Clear error messages for failures

---

## Next Steps

1. **Get approval** on implementation plan
2. **Start with Phase 1** (quick wins - standalone extract progress)
3. **Test incrementally** (don't move to Phase 2 until Phase 1 works)
4. **Document as you go** (update CLAUDE.md with new patterns)

---

## Questions for User

1. Should `/leech` auto-detect large archives and switch to streaming mode?
2. Do you want `/extract` to have an option to upload after extraction?
3. Priority: Faster implementation (Track 1 only) or full solution (both tracks)?
4. Test file available? (Need a multi-part RAR to test with)

---

**Status:** Ready for implementation
**Estimated Completion:** Track 1 (2 hours) + Track 2 (4 hours) = **1 day**
