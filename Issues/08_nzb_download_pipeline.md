# NZB Download Pipeline - Detailed Fix Prompt

## Problem Description
The NZB (Usenet) download pipeline is fundamentally broken when using the custom NNTP downloader (`NZBDownloader`). Multiple critical bugs prevent files from being downloaded correctly:

1. **Binary data corruption**: Downloaded files are garbled/empty because article data line framing is destroyed during processing
2. **Bot freezes**: All synchronous `nntplib` calls block the asyncio event loop, making the bot unresponsive to ALL users during any NNTP operation
3. **Wrong status messages**: The SABnzbd fallback path ignores task context, updating global status instead of the correct task's status
4. **NZB URL filenames broken**: URLs with query parameters produce wrong output filenames
5. **Argument mismatch**: `NZBDownloader.download_nzb()` didn't accept `download_dir` parameter (partially fixed, but the fix needs integration)

**User-facing symptoms**: Files download as 0 bytes or corrupted data. Bot becomes completely unresponsive during downloads. Status messages appear on wrong tasks. NZB URL downloads silently fail or produce misnamed files.

## Root Cause Analysis

### Bug 1: Binary Data Corruption (`nzb.py:316-319`)
```python
# nzb.py:316-319
response, info = connection.article(message_id)
# Extract article body (skip headers)
article_data = b'\n'.join(info.lines)
```
`nntplib._getline()` strips the `\r\n` line terminators from every line in `info.lines`. Rejoining with `b'\n'` (LF only) permanently destroys the original CRLF framing. For yEnc binary content, this corrupts the encoded data before it reaches either decoder:
- sabyenc receives incorrectly-framed input
- The pure Python decoder inherits the corrupted framing

### Bug 2: Blocking I/O in Async Context (`nzb.py:221-337`)
```python
# nzb.py:258-265 (blocking calls inside async function)
connection = nntplib.NNTP_SSL(host, port=port, timeout=30)
connection.login(username, password)
connection.group('alt.binaries.test')

# nzb.py:316 (blocking call in async function)
response, info = connection.article(message_id)
```
All NNTP operations are synchronous `nntplib` calls executed from async functions. Since `asyncio` runs in a single thread, every blocking socket I/O call freezes the entire event loop. With 8 connections and potentially hundreds of segments, the bot is frozen for minutes during each download.

### Bug 3: SABnzbdDownloader Missing task_ctx (`sabnzbd_downloader.py:29-97`)
```python
# sabnzbd_downloader.py:29 — no task_ctx parameter
def __init__(self, client, message, sabnzbd_config: dict):

# sabnzbd_downloader.py:67 — uses global MSG instead of task context
if not MSG.status_msg:
    return

# sabnzbd_downloader.py:89-97 — missing task_ctx in status_bar call
await status_bar(
    down_msg=status_head,
    speed=speed,
    percentage=percentage,
    eta=eta if eta != "unknown" else "N/A",
    done=status_text,
    total_size=sizeUnit(self.total_size) if self.total_size > 0 else "Unknown",
    engine="SABnzbd"
    # task_ctx parameter is MISSING
)
```
Compare with `NZBDownloader` which correctly accepts and uses `task_ctx`:
```python
# nzb.py:35 — accepts task_ctx
def __init__(self, client, message: Message, task_ctx: TaskContext = None):

# nzb.py:605-614 — passes task_ctx to status_bar
await status_bar(
    ...
    engine=f"NZB (NNTP)",
    task_ctx=self.task_ctx  # correctly passed
)
```

### Bug 4: NZB URL Filename Extraction (`__main__.py:4458-4460`)
```python
nzb_filename = nzb_url.split('/')[-1]
if not nzb_filename.endswith('.nzb'):
    nzb_filename = "download.nzb"
```
URLs like `https://example.com/file.nzb?token=abc123` produce `file.nzb?token=abc123` which doesn't end with `.nzb`, so it becomes `download.nzb`. The query string should be stripped first.

### Bug 5: Group Selection Contradiction (`nzb.py:270-283` vs `698-700`)
`connect_nntp` selects `alt.binaries.test` on every connection (line 273), but the download loop explicitly avoids selecting the article's actual newsgroup (line 698-700 comment). Some servers require the correct group to be selected before `article()` will work.

## Step-by-Step Solution

### Phase 1: Fix Binary Data Corruption
1. Replace `b'\n'.join(info.lines)` with proper article body extraction
2. Use `connection.body(message_id)` to get only the article body without headers
3. Pass raw body lines directly to decoders instead of re-joining

### Phase 2: Fix Blocking I/O
1. Wrap all synchronous `nntplib` calls with `asyncio.get_event_loop().run_in_executor()`
2. Create a dedicated `ThreadPoolExecutor` for NNTP operations (bounded to `max_connections`)
3. Apply executor wrapping to: `connect_nntp`, `download_article`, and connection cleanup

### Phase 3: Fix SABnzbdDownloader task_ctx
1. Add `task_ctx` parameter to `SABnzbdDownloader.__init__`
2. Use `task_ctx.status_msg` instead of global `MSG.status_msg`
3. Pass `task_ctx=self.task_ctx` to `status_bar()` calls
4. Update caller in `__main__.py` to pass `task_ctx`

### Phase 4: Fix URL Filename and Cleanup
1. Use `urllib.parse.urlparse` + `os.path.basename` to strip query params
2. Add file existence check after `message.download()`
3. Fix connection pool off-by-one (`seg_idx` starts at 1, skip index 0)

## Specific Code Changes Needed

### 1. Fix `download_article` in `nzb.py:302-337`
```python
# OLD (corrupts data):
def download_article(self, connection, message_id, segment_number):
    response, info = connection.article(message_id)
    article_data = b'\n'.join(info.lines)
    return article_data

# NEW (preserves framing):
def download_article(self, connection, message_id, segment_number):
    response, info = connection.body(message_id)
    # info.lines already has correct framing from nntplib
    # Pass lines directly — do NOT re-join
    return info.lines
```

### 2. Fix `decode_yenc` in `nzb.py:404-436`
```python
# OLD:
def decode_yenc(self, article_data: bytes):
    decoded, filename, crc, crc_expected, crc_correct = sabyenc.decode_usenet_chunks([article_data], None)

# NEW (pass lines list directly):
def decode_yenc(self, article_data):
    # article_data is now a list of bytes lines from body()
    decoded, filename, crc, crc_expected, crc_correct = sabyenc.decode_usenet_chunks(article_data, None)
```

### 3. Fix `_decode_yenc_pure_python` in `nzb.py:438-499`
```python
# OLD:
def _decode_yenc_pure_python(self, article_data: bytes):
    lines = article_data.split(b'\n')

# NEW (accept lines list directly):
def _decode_yenc_pure_python(self, article_lines):
    # article_lines is already a list of bytes
    for line in article_lines:
        line = line.strip()
        # ... rest of logic unchanged
```

### 4. Fix Blocking I/O in `nzb.py` — Add executor wrapper
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

# At class level or module level:
_nntp_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="nntp")

# Wrap blocking connect_nntp:
async def connect_nntp(self, provider_config=None):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        self._nntp_executor,
        self._connect_nntp_sync,
        provider_config
    )

def _connect_nntp_sync(self, provider_config):
    # Move existing connect_nntp logic here (synchronous)
    # ... existing code ...

# Wrap blocking download_article:
async def download_article(self, connection, message_id, segment_number):
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        self._nntp_executor,
        self._download_article_sync,
        connection, message_id, segment_number
    )

def _download_article_sync(self, connection, message_id, segment_number):
    # Move existing download_article logic here (synchronous)
    # ... existing code ...
```

### 5. Fix SABnzbdDownloader in `sabnzbd_downloader.py:26-97`
```python
# OLD:
def __init__(self, client, message, sabnzbd_config: dict):
    self.client = client
    self.message = message

# NEW:
def __init__(self, client, message, sabnzbd_config: dict, task_ctx=None):
    self.client = client
    self.message = message
    self.task_ctx = task_ctx

# OLD (line 67):
if not MSG.status_msg:
    return

# NEW:
status_msg = self.task_ctx.status_msg if self.task_ctx else MSG.status_msg
if not status_msg:
    return

# OLD (line 89-97): missing task_ctx
await status_bar(
    ...
    engine="SABnzbd"
)

# NEW:
await status_bar(
    ...
    engine="SABnzbd",
    task_ctx=self.task_ctx
)
```

### 6. Fix NZB URL Filename in `__main__.py:4458-4460`
```python
# OLD:
nzb_filename = nzb_url.split('/')[-1]
if not nzb_filename.endswith('.nzb'):
    nzb_filename = "download.nzb"

# NEW:
from urllib.parse import urlparse
parsed = urlparse(nzb_url)
nzb_filename = os.path.basename(parsed.path)
if not nzb_filename or not nzb_filename.endswith('.nzb'):
    nzb_filename = "download.nzb"
```

### 7. Fix Caller in `__main__.py:5196-5207`
```python
# OLD:
if sabnzbd_config:
    downloader = SABnzbdDownloader(client, message, sabnzbd_config)
else:
    downloader = NZBDownloader(client, message, task_ctx)

# NEW:
if sabnzbd_config:
    downloader = SABnzbdDownloader(client, message, sabnzbd_config, task_ctx=task_ctx)
else:
    downloader = NZBDownloader(client, message, task_ctx)
```

### 8. Fix Group Selection Contradiction in `nzb.py:270-283`
```python
# OLD: Selects a random group that has nothing to do with the articles
connection.group('alt.binaries.test')

# NEW: Don't select any group — article(message_id) works without group() on most servers
# If a server requires group selection, select the article's actual group before fetching
# For now, remove the group() call entirely — the comment at line 698-700 is correct
```

## Testing Considerations

### Unit Tests
1. **yEnc decode test**: Create a known yEnc-encoded buffer, verify round-trip decode with both sabyenc and pure Python paths
2. **Article body extraction test**: Mock `nntplib.NNTP.body()` response, verify lines are passed through without corruption
3. **URL filename parsing test**: Test with URLs containing query params, fragments, and no filename
4. **task_ctx propagation test**: Verify SABnzbdDownloader uses task_ctx.status_msg when provided

### Integration Tests
1. **End-to-end NZB download**: Download a small known NZB file, verify output matches expected checksum
2. **Multi-task concurrent NZB**: Start 2+ NZB downloads simultaneously, verify each updates its own status message
3. **Bot responsiveness during download**: While NZB is downloading, send another command and verify bot responds promptly (async fix)
4. **SABnzbd vs NNTP fallback**: Test both code paths produce identical output for same NZB

### Manual Testing
1. Send `/nzb`, upload a small .nzb file, verify file downloads correctly (not 0 bytes)
2. Send `/nzb`, paste an NZB URL with query parameters, verify correct filename
3. During NZB download, send `/help` or another command, verify bot responds immediately
4. Start 2 NZB downloads in parallel, verify status messages update on correct tasks
5. Test with SABnzbd configured and unconfigured — both paths should work

### Performance Tests
1. Measure event loop responsiveness during NNTP operations (should be <100ms blocked)
2. Test with 8 concurrent NNTP connections downloading simultaneously
3. Compare download speed before/after async fix (should be similar or better)

## Files to Modify
1. **Modify**: `colab_leecher/downlader/nzb.py` — Fix data corruption, blocking I/O, group selection
2. **Modify**: `colab_leecher/downlader/sabnzbd_downloader.py` — Add task_ctx support
3. **Modify**: `colab_leecher/__main__.py` — Fix URL filename, pass task_ctx to SABnzbdDownloader

## Expected Outcomes
1. **Binary data integrity**: Downloaded files are valid, not corrupted — both sabyenc and pure Python decoders receive correctly-framed data
2. **Non-blocking bot**: Bot remains responsive to all users during NZB downloads — async executor handles NNTP I/O
3. **Correct multi-task status**: Each NZB download updates its own status message, not the global one
4. **Proper URL handling**: NZB URLs with query parameters produce correctly-named output files
5. **Both backends work**: SABnzbd and direct NNTP paths both function correctly with task context
6. **Group compatibility**: Removing the unnecessary group selection eliminates potential 412/423 errors on strict servers
