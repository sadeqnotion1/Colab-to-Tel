# Implementation Plan - Bot Enhancements

**Created:** 2025-12-24
**Status:** Ready for Implementation
**Priority:** High Impact Features First

---

## 📋 Executive Summary

This plan outlines the implementation of enhancements identified during bot testing and research. Focus is on:
- ✅ **Completed:** SABnzbd log import fixes, development warnings
- 🔄 **In Progress:** TeraBox and YTDL improvements
- 📅 **Planned:** Performance optimizations, reliability improvements

---

## 🎯 Implementation Phases

### Phase 1: Quick Wins (1-2 days) - PRIORITY
**Goal:** Fix critical bugs and easy improvements

#### Task 1.1: Fix YTDL Concurrent Fragments ✅ Ready
**File:** `colab_leecher/downlader/ytdl.py:103`
**Difficulty:** Easy (1 line change)
**Impact:** Medium (faster downloads)

**Current Code:**
```python
"--concurrent-fragments": 4,  # ❌ Wrong parameter name
```

**Fixed Code:**
```python
"concurrent_fragment_downloads": 4,  # ✅ Correct parameter
```

**Steps:**
1. Open `colab_leecher/downlader/ytdl.py`
2. Find line 103
3. Replace `--concurrent-fragments` with `concurrent_fragment_downloads`
4. Test with YouTube playlist
5. Verify concurrent downloads work

**Testing:**
```python
# Test URL
test_url = "https://www.youtube.com/playlist?list=..."
# Should see multiple fragment downloads
```

**Estimated Time:** 10 minutes

---

#### Task 1.2: Update YTDL Configuration ⚡ High Impact
**File:** `colab_leecher/downlader/ytdl.py:98-111`
**Difficulty:** Medium
**Impact:** High (better downloads, metadata, subtitles)

**Enhancements:**
```python
ydl_opts = {
    # Better format selection
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",

    # Performance
    "concurrent_fragment_downloads": 4,  # Fixed!
    "http_chunk_size": 10485760,  # 10MB chunks

    # Reliability
    "retries": 10,
    "fragment_retries": 10,
    "skip_unavailable_fragments": True,

    # Subtitles (auto-download)
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitleslangs": ["en", "ar"],
    "subtitlesformat": "srt/best",

    # Metadata
    "writethumbnail": True,
    "embedthumbnail": True,
    "addmetadata": True,
    "embedmetadata": True,

    # Post-processing
    "postprocessors": [
        {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
        {"key": "FFmpegMetadata", "add_metadata": True},
        {"key": "EmbedThumbnail", "already_have_thumbnail": False}
    ],

    # Existing options
    "allow_multiple_video_streams": True,
    "allow_multiple_audio_streams": True,
    "allow_playlist_files": True,
    "overwrites": True,
    "progress_hooks": [my_hook],
    "logger": MyLogger(),
}
```

**Testing:**
- [ ] Test single video download
- [ ] Test playlist download
- [ ] Verify subtitle download
- [ ] Check metadata embedding
- [ ] Test thumbnail embedding

**Estimated Time:** 1 hour

---

#### Task 1.3: Add YTDL Retry Logic 🔄
**File:** `colab_leecher/downlader/ytdl.py:14`
**Difficulty:** Medium
**Impact:** High (reliability)

**Implementation:**
```python
async def YTDL_Status(link, num, max_retries=3):
    """Enhanced with retry logic"""
    for attempt in range(max_retries):
        try:
            name = await get_YT_Name(link)
            Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{name}</code>\n"

            YTDL_Thread = Thread(target=YouTubeDL, name="YouTubeDL", args=(link,))
            YTDL_Thread.start()

            while YTDL_Thread.is_alive():
                # ... existing status update code ...
                await sleep(2.5)

            break  # Success, exit retry loop

        except yt_dlp.utils.DownloadError as e:
            if attempt < max_retries - 1:
                log.warning(f"Download failed (attempt {attempt+1}/{max_retries}): {e}")
                await sleep(5)  # Wait before retry
            else:
                await cancelTask(f"Download failed after {max_retries} attempts: {e}")

        except Exception as e:
            log.error(f"Unexpected error in YTDL_Status: {e}", exc_info=True)
            await cancelTask(f"YouTube download error: {e}")
            break
```

**Testing:**
- [ ] Test with valid URL (should work)
- [ ] Test with invalid URL (should retry then fail)
- [ ] Test with network interruption simulation
- [ ] Verify retry delays work

**Estimated Time:** 1 hour

---

### Phase 2: TeraBox Enhancement (2-3 days)

#### Task 2.1: Install TeraboxDL Package 📦
**Difficulty:** Easy
**Impact:** High (reliability)

**Steps:**
1. Add to `requirements.txt`:
   ```
   terabox-downloader>=1.0.0
   ```

2. Test installation:
   ```bash
   pip install terabox-downloader
   python -c "from TeraboxDL import TeraboxDL; print('OK')"
   ```

**Estimated Time:** 15 minutes

---

#### Task 2.2: Update credentials.json Schema 🔐
**Difficulty:** Easy
**Impact:** Medium

**Add to credentials.json:**
```json
{
  "TERABOX_COOKIE": "lang=en; ndus=YOUR_VALUE_HERE;"
}
```

**Documentation for users:**
```markdown
## How to Get TeraBox Cookie:

1. Open Edge browser
2. Log into terabox.com
3. Click padlock icon in address bar
4. Go to "Cookies and site data"
5. Find `lang` and `ndus` cookies
6. Copy values
7. Format: "lang=value1; ndus=value2;"
8. Add to credentials.json
```

**Estimated Time:** 30 minutes (including docs)

---

#### Task 2.3: Create TeraBox Wrapper Class 🏗️
**File:** `colab_leecher/downlader/terabox_enhanced.py` (new)
**Difficulty:** Medium
**Impact:** High

**Implementation:**
```python
"""
Enhanced TeraBox Downloader using TeraboxDL package
"""
import logging
from TeraboxDL import TeraboxDL
from ..utility.variables import BOT, Paths, TRANSFER, TaskError
from ..utility.helper import status_bar, sizeUnit

log = logging.getLogger(__name__)


class TeraBoxDownloader:
    """
    TeraBox downloader using official TeraboxDL package
    Falls back to old API method if needed
    """

    def __init__(self, client, message, task_ctx=None):
        self.client = client
        self.message = message
        self.task_ctx = task_ctx

        # Get cookie from settings
        self.cookie = BOT.Setting.terabox_cookie if hasattr(BOT.Setting, 'terabox_cookie') else ""

        # Download directory
        if task_ctx:
            self.download_dir = task_ctx.down_path
        else:
            self.download_dir = Paths.down_path

        log.info(f"TeraBox downloader initialized (cookie: {bool(self.cookie)})")

    async def download(self, url: str, index: int = 0) -> bool:
        """
        Download file from TeraBox URL

        Args:
            url: TeraBox share link
            index: Link index for tracking

        Returns:
            bool: True if successful, False otherwise
        """
        if not self.cookie:
            log.warning("No TeraBox cookie configured, falling back to API method")
            return await self._fallback_download(url, index)

        try:
            # Initialize TeraboxDL
            terabox = TeraboxDL(self.cookie)

            # Get file info
            log.info(f"Fetching TeraBox file info for link {index}")
            file_info = terabox.get_file_info(url)

            if "error" in file_info:
                raise Exception(f"Failed to get file info: {file_info['error']}")

            filename = file_info.get('file_name', f'terabox_file_{index}')
            file_size = file_info.get('sizebytes', 0)

            log.info(f"TeraBox file: {filename} ({sizeUnit(file_size)})")

            # Download with progress tracking
            result = terabox.download(
                file_info,
                save_path=self.download_dir,
                callback=lambda downloaded, total, pct: self._progress_callback(
                    filename, downloaded, total, pct
                )
            )

            if "error" in result:
                raise Exception(f"Download failed: {result['error']}")

            # Track successful download
            TRANSFER.successful_downloads.append({
                'url': url,
                'filename': filename,
                'size': file_size
            })

            log.info(f"✅ TeraBox download completed: {filename}")
            return True

        except Exception as e:
            log.error(f"TeraBox download error: {e}")

            # Track failure
            TaskError.failed_links.append({
                "link": url,
                "filename": filename if 'filename' in locals() else "Unknown",
                "index": index,
                "reason": str(e)
            })

            # Try fallback
            log.info("Attempting fallback download method...")
            return await self._fallback_download(url, index)

    async def _progress_callback(self, filename, downloaded, total, percentage):
        """Update bot progress display"""
        try:
            await status_bar(
                down_msg=f"<b>📥 DOWNLOADING TERABOX FILE</b>\n\n<code>{filename}</code>\n",
                speed="N/A",
                percentage=percentage,
                eta="N/A",
                done=sizeUnit(downloaded),
                left=sizeUnit(total),
                engine="TeraboxDL 📦"
            )
        except Exception as e:
            log.debug(f"Progress update error: {e}")

    async def _fallback_download(self, url: str, index: int) -> bool:
        """
        Fallback to old API-based method
        Uses the current terabox.py implementation
        """
        log.info(f"Using fallback TeraBox API method for link {index}")

        # Import old method
        from .terabox import terabox_download

        return await terabox_download(url, index, self.task_ctx)
```

**Testing:**
- [ ] Test with valid TeraBox link + cookie
- [ ] Test without cookie (fallback)
- [ ] Test with invalid link
- [ ] Verify progress tracking
- [ ] Check file integrity after download

**Estimated Time:** 3 hours

---

#### Task 2.4: Integrate New TeraBox Downloader 🔌
**File:** `colab_leecher/downlader/manager.py`
**Difficulty:** Medium
**Impact:** High

**Find where TeraBox is called and replace:**

**Old:**
```python
from .terabox import terabox_download
result = await terabox_download(link, index, task_ctx)
```

**New:**
```python
from .terabox_enhanced import TeraBoxDownloader
downloader = TeraBoxDownloader(client, message, task_ctx)
result = await downloader.download(link, index)
```

**Keep old file as backup:**
```bash
# Rename old implementation
mv colab_leecher/downlader/terabox.py colab_leecher/downlader/terabox_legacy.py
```

**Testing:**
- [ ] Test with cookie configured
- [ ] Test fallback mechanism
- [ ] Verify error handling
- [ ] Check bot status messages

**Estimated Time:** 1 hour

---

### Phase 3: Credentials & Configuration (1 day)

#### Task 3.1: Update credentials.json Schema 📝
**File:** Update `credentials.json.example` (if exists) or create it
**Difficulty:** Easy
**Impact:** Medium

**Complete Schema:**
```json
{
  "_comment": "Telegram Bot Credentials",
  "API_ID": "YOUR_API_ID",
  "API_HASH": "YOUR_API_HASH",
  "BOT_TOKEN": "YOUR_BOT_TOKEN",
  "USER_ID": "YOUR_USER_ID",
  "DUMP_ID": "YOUR_DUMP_CHANNEL_ID",

  "_comment_instagram": "Instagram Authentication (choose one method)",
  "INSTAGRAM_USERNAME": "",
  "INSTAGRAM_PASSWORD": "",
  "INSTAGRAM_SESSIONID": "your_sessionid_cookie",
  "INSTAGRAM_COOKIES_FILE": "",

  "_comment_terabox": "TeraBox Cookie Authentication",
  "TERABOX_COOKIE": "lang=en; ndus=YOUR_COOKIE;",

  "_comment_usenet": "Usenet/NZB Provider Configuration",
  "NZB_PROVIDERS": {
    "sunnyusenet": {
      "host": "news.sunnyusenet.com",
      "port": 563,
      "username": "your_username",
      "password": "your_password",
      "ssl": true,
      "connections": 20
    },
    "newshosting": {
      "host": "news.newshosting.com",
      "port": 563,
      "username": "your_username",
      "password": "your_password",
      "ssl": true,
      "connections": 30
    }
  },
  "NZB_DEFAULT_PROVIDER": "sunnyusenet",

  "_comment_downloaders": "Optional Downloader Cookies",
  "NZBCLOUD_CF_CLEARANCE": "",
  "BITSO_IDENTITY_COOKIE": "",
  "BITSO_PHPSESSID_COOKIE": "",

  "_comment_ytdl": "YouTube-DL Settings (optional)",
  "YTDL_SETTINGS": {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
    "subtitle_languages": ["en", "ar"],
    "max_retries": 10,
    "concurrent_fragments": 4
  }
}
```

**Steps:**
1. Create `credentials.json.example` with template
2. Update README with configuration guide
3. Add validation to `__init__.py`

**Estimated Time:** 1 hour

---

#### Task 3.2: Load TeraBox Cookie in __init__.py 🔧
**File:** `colab_leecher/__init__.py`
**Difficulty:** Easy
**Impact:** Medium

**Add after Instagram credentials:**
```python
# --- Load TeraBox Authentication ---
log.info("Loading TeraBox authentication...")
BOT.Setting.terabox_cookie = credentials.get("TERABOX_COOKIE", "")

if BOT.Setting.terabox_cookie:
    log.info("TeraBox Cookie: Configured")
else:
    log.info("TeraBox Cookie: Not Configured (will use API fallback)")
```

**Testing:**
- [ ] Verify cookie loads from credentials
- [ ] Check log messages
- [ ] Test with and without cookie

**Estimated Time:** 15 minutes

---

### Phase 4: Session Management (1 day)

#### Task 4.1: Session File Cleanup 🧹
**File:** `colab_leecher/run_local.py`
**Difficulty:** Medium
**Impact:** Low (maintenance)

**Add cleanup function:**
```python
import glob
from datetime import datetime, timedelta

def cleanup_old_sessions(max_age_days=7):
    """Remove session files older than max_age_days"""
    log.info("Cleaning up old session files...")
    pattern = "colab_bot_*.session*"  # Include .session-journal files
    cutoff = datetime.now() - timedelta(days=max_age_days)

    removed = 0
    for session_file in glob.glob(pattern):
        try:
            file_time = os.path.getmtime(session_file)
            if datetime.fromtimestamp(file_time) < cutoff:
                os.remove(session_file)
                log.info(f"Removed old session: {session_file}")
                removed += 1
        except Exception as e:
            log.warning(f"Could not remove {session_file}: {e}")

    if removed > 0:
        log.info(f"✅ Cleaned up {removed} old session file(s)")
    else:
        log.info("No old session files to clean")

def main():
    # ... existing code ...

    # Clean old sessions before starting
    cleanup_old_sessions(max_age_days=7)

    # ... rest of startup ...
```

**Testing:**
- [ ] Create test session files with old dates
- [ ] Run cleanup
- [ ] Verify only old files removed
- [ ] Check current session still works

**Estimated Time:** 1 hour

---

#### Task 4.2: Improve Credentials Path Detection 📍
**File:** `colab_leecher/run_local.py`
**Difficulty:** Easy
**Impact:** Low (UX)

**Replace check_credentials():**
```python
def check_credentials():
    """Verify credentials.json exists and is valid - checks multiple locations"""

    # Try multiple locations
    possible_paths = [
        "credentials.json",  # Same directory as script
        "../credentials.json",  # Parent directory
        os.path.join(os.path.dirname(__file__), "credentials.json"),
        os.path.join(os.path.dirname(__file__), "..", "credentials.json"),
    ]

    creds_path = None
    for path in possible_paths:
        if os.path.exists(path):
            creds_path = path
            log.info(f"✅ Found credentials at: {os.path.abspath(path)}")
            break

    if not creds_path:
        log.error(f"❌ credentials.json not found!")
        log.error(f"   Searched locations:")
        for path in possible_paths:
            log.error(f"   - {os.path.abspath(path)}")
        return False

    try:
        with open(creds_path, 'r') as f:
            creds = json.load(f)

        required = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'USER_ID', 'DUMP_ID']
        missing = [key for key in required if not creds.get(key)]

        if missing:
            log.error(f"❌ Missing required credentials: {', '.join(missing)}")
            return False

        log.info("✅ All required credentials present")

        # Check optional configurations
        if creds.get('INSTAGRAM_USERNAME') and creds.get('INSTAGRAM_PASSWORD'):
            log.info(f"✅ Instagram Login: {creds['INSTAGRAM_USERNAME']}")
        elif creds.get('INSTAGRAM_SESSIONID'):
            log.info("✅ Instagram Session Cookie configured")
        elif creds.get('INSTAGRAM_COOKIES_FILE'):
            log.info(f"✅ Instagram Cookie File: {creds['INSTAGRAM_COOKIES_FILE']}")
        else:
            log.warning("⚠️  Instagram authentication not configured")

        if creds.get('TERABOX_COOKIE'):
            log.info("✅ TeraBox Cookie configured")
        else:
            log.info("ℹ️  TeraBox Cookie not configured (will use API fallback)")

        return True

    except json.JSONDecodeError as e:
        log.error(f"❌ Invalid JSON in credentials.json: {e}")
        return False
    except Exception as e:
        log.error(f"❌ Error reading credentials: {e}")
        return False
```

**Testing:**
- [ ] Test with credentials in different locations
- [ ] Test with missing credentials
- [ ] Test with invalid JSON
- [ ] Verify all log messages

**Estimated Time:** 30 minutes

---

### Phase 5: Testing & Validation (2-3 days)

#### Task 5.1: Create Test Suite 🧪
**File:** `tests/test_downloaders.py` (new)
**Difficulty:** Hard
**Impact:** High (quality assurance)

**Structure:**
```python
"""
Test suite for downloader modules
Run with: python -m pytest tests/test_downloaders.py
"""
import pytest
import asyncio
from colab_leecher.downlader.ytdl import YTDL_Status, get_YT_Name
from colab_leecher.downlader.terabox_enhanced import TeraBoxDownloader

class TestYTDL:
    """Test YouTube downloader"""

    @pytest.mark.asyncio
    async def test_get_video_name(self):
        """Test video name extraction"""
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        name = await get_YT_Name(url)
        assert name != "UNKNOWN DOWNLOAD NAME"
        assert len(name) > 0

    @pytest.mark.asyncio
    async def test_invalid_url(self):
        """Test error handling for invalid URL"""
        with pytest.raises(Exception):
            await get_YT_Name("https://invalid.url/xyz")

    # Add more tests...

class TestTeraBox:
    """Test TeraBox downloader"""

    def test_initialization(self):
        """Test downloader initialization"""
        downloader = TeraBoxDownloader(None, None)
        assert downloader is not None

    # Add more tests...

# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v"])
```

**Testing Checklist:**
- [ ] YTDL single video
- [ ] YTDL playlist
- [ ] YTDL with subtitles
- [ ] TeraBox with cookie
- [ ] TeraBox without cookie (fallback)
- [ ] Instagram downloads
- [ ] NZB downloads
- [ ] Error handling
- [ ] Progress tracking

**Estimated Time:** 4-6 hours

---

#### Task 5.2: Integration Testing 🔗
**Difficulty:** Medium
**Impact:** High

**Test Scenarios:**
1. **Complete workflow test:**
   - Send YouTube URL to bot
   - Verify download
   - Check upload to Telegram
   - Verify file integrity

2. **Multi-download test:**
   - Send multiple links (different types)
   - Verify all download correctly
   - Check error handling for failures

3. **Large file test:**
   - Download file >2GB
   - Verify splitting works
   - Check upload success

4. **Error recovery test:**
   - Simulate network interruption
   - Verify retry mechanism
   - Check graceful failure

**Testing Matrix:**
| Downloader | Small File | Large File | Playlist | Error Handling |
|------------|-----------|-----------|----------|----------------|
| YouTube | ⬜ | ⬜ | ⬜ | ⬜ |
| TeraBox | ⬜ | ⬜ | N/A | ⬜ |
| Instagram | ⬜ | ⬜ | ⬜ | ⬜ |
| NZB | ⬜ | ⬜ | N/A | ⬜ |

**Estimated Time:** 4 hours

---

### Phase 6: Documentation (1 day)

#### Task 6.1: Update User Guide 📚
**Files:**
- `README.md`
- `docs/tutorials/` (new)

**Sections to add:**
1. TeraBox Cookie Setup Guide
2. YTDL Configuration Options
3. Troubleshooting Guide
4. Performance Tips
5. FAQ

**Estimated Time:** 2 hours

---

#### Task 6.2: Create Developer Documentation 💻
**Files:**
- `docs/development/ARCHITECTURE.md`
- `docs/development/CONTRIBUTING.md`

**Content:**
- Code structure overview
- How to add new downloaders
- Testing guidelines
- Code style guide

**Estimated Time:** 2 hours

---

## 📊 Priority Matrix

### High Priority (Do First)
1. ✅ Fix YTDL concurrent fragments (10 min)
2. ✅ Update YTDL configuration (1 hour)
3. ✅ Add YTDL retry logic (1 hour)
4. ⬜ Install TeraboxDL (15 min)
5. ⬜ Create TeraBox wrapper (3 hours)

**Total: ~5.5 hours**

### Medium Priority (Do Next)
6. ⬜ Update credentials schema (1 hour)
7. ⬜ Load TeraBox cookie (15 min)
8. ⬜ Integrate TeraBox downloader (1 hour)
9. ⬜ Session cleanup (1 hour)
10. ⬜ Credentials path detection (30 min)

**Total: ~3.5 hours**

### Low Priority (Nice to Have)
11. ⬜ Create test suite (4-6 hours)
12. ⬜ Integration testing (4 hours)
13. ⬜ Update documentation (4 hours)

**Total: ~12-14 hours**

---

## 🚀 Quick Start Implementation

### Day 1: YTDL Fixes (High Impact, Low Effort)
```bash
# Morning (2-3 hours)
1. Fix concurrent fragments parameter
2. Update YTDL configuration
3. Add retry logic
4. Test with real URLs

# Afternoon (1-2 hours)
5. Install TeraboxDL
6. Update credentials.json
7. Test TeraboxDL package
```

### Day 2: TeraBox Integration
```bash
# Morning (3-4 hours)
1. Create TeraBoxDownloader class
2. Implement progress tracking
3. Add fallback mechanism

# Afternoon (2-3 hours)
4. Integrate into manager.py
5. Test with cookie
6. Test fallback
7. Verify error handling
```

### Day 3: Polish & Test
```bash
# Morning (2-3 hours)
1. Session cleanup
2. Credentials path detection
3. Update schema

# Afternoon (2-3 hours)
4. Integration testing
5. Fix any bugs found
6. Update documentation
```

---

## 🔄 Rollback Procedures

### If YTDL Changes Cause Issues:
```bash
# Revert ytdl.py
git checkout HEAD -- colab_leecher/downlader/ytdl.py

# Or manually restore:
# 1. Change concurrent_fragment_downloads back to --concurrent-fragments
# 2. Remove new configuration options
# 3. Remove retry logic from YTDL_Status
```

### If TeraBox Integration Fails:
```bash
# Switch back to legacy
mv colab_leecher/downlader/terabox_legacy.py colab_leecher/downlader/terabox.py
rm colab_leecher/downlader/terabox_enhanced.py

# Update manager.py imports back to:
from .terabox import terabox_download
```

### If Credentials Schema Breaks:
```bash
# Keep backup
cp credentials.json credentials.json.backup

# Restore minimal schema if needed
# Only keep: API_ID, API_HASH, BOT_TOKEN, USER_ID, DUMP_ID
```

---

## ✅ Success Criteria

### Phase 1 Complete When:
- [ ] YouTube downloads are faster
- [ ] Concurrent fragments working
- [ ] Subtitles auto-download
- [ ] Metadata embedded
- [ ] No new errors in logs

### Phase 2 Complete When:
- [ ] TeraBox downloads with cookie work
- [ ] Fallback to API works
- [ ] Progress tracking accurate
- [ ] Error handling graceful
- [ ] No regressions in old functionality

### Overall Success:
- [ ] All tests passing
- [ ] Documentation updated
- [ ] No critical bugs
- [ ] Performance improved
- [ ] User experience better

---

## 📞 Support & Resources

**Documentation:**
- Enhancement Guide: `DOWNLOADER_ENHANCEMENTS.md`
- Issue Report: `POTENTIAL_ISSUES_REPORT.md`
- This Plan: `IMPLEMENTATION_PLAN.md`

**External Resources:**
- yt-dlp: https://github.com/yt-dlp/yt-dlp
- TeraboxDL: https://github.com/Damantha126/TeraboxDL
- Pyrogram: https://docs.pyrogram.org

**Testing URLs:**
```python
# YouTube
test_urls = {
    "single_video": "https://www.youtube.com/watch?v=...",
    "playlist": "https://www.youtube.com/playlist?list=...",
    "shorts": "https://www.youtube.com/shorts/..."
}

# TeraBox
terabox_test = "https://terabox.com/s/..."

# Instagram
instagram_test = "https://www.instagram.com/p/..."
```

---

## 📈 Progress Tracking

### Completed ✅
- [x] SABnzbd log import fix
- [x] Development warnings added
- [x] Issue analysis documentation
- [x] Enhancement research
- [x] Implementation plan created

### In Progress 🔄
- [ ] YTDL improvements
- [ ] TeraBox integration

### Not Started ⬜
- [ ] Testing suite
- [ ] Documentation updates
- [ ] Performance optimization

---

## 🎯 Next Steps

**Immediate Action (Next 30 minutes):**
1. Open `colab_leecher/downlader/ytdl.py`
2. Fix line 103: `concurrent_fragment_downloads`
3. Test with single YouTube video
4. Commit changes

**This Week:**
1. Complete Phase 1 (YTDL fixes)
2. Install and test TeraboxDL
3. Start Phase 2 (TeraBox integration)

**This Month:**
1. Complete all high priority tasks
2. Basic testing
3. Update user documentation

---

**Last Updated:** 2025-12-24
**Created By:** Claude Code Assistant
**Status:** Ready for Implementation
**Estimated Total Time:** 21-25 hours (3-4 working days)
