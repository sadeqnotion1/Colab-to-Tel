# Downloader Enhancement Recommendations

## Overview
This document provides recommendations for enhancing the TeraBox and YouTube downloaders with proven implementations from the GitHub community.

---

## Development Status Warnings

### Files in Development Mode
The following modules are marked as **NOT PRODUCTION READY**:
- `colab_leecher/downlader/nzb.py` - NZB/Usenet downloader
- `colab_leecher/downlader/sabnzbd_downloader.py` - SABnzbd integration

These files contain development warnings and should be used with caution.

---

## 1. TeraBox Downloader Enhancement

### Current Implementation
**File:** `colab_leecher/downlader/terabox.py`

**Current Approach:**
- Uses external API: `ytshorts.savetube.me/api/v1/terabox-downloader`
- Falls back to slow download if fast download fails
- Basic error tracking
- Relies on aria2 for actual downloading

**Limitations:**
- Dependency on third-party API (may be unreliable)
- No direct TeraBox authentication
- Limited metadata extraction
- No progress callback support

### Recommended Enhancement Options

#### Option 1: TeraboxDL Package (Recommended)
**Source:** https://github.com/Damantha126/TeraboxDL

**Benefits:**
- Official Python package (`pip install terabox-downloader`)
- Direct TeraBox API integration
- Built-in progress tracking with callbacks
- Better metadata extraction (filename, size, thumbnail)
- Cookie-based authentication (more reliable)
- No dependency on external APIs

**Implementation Example:**
```python
from TeraboxDL import TeraboxDL

# Initialize with cookie
cookie = "lang=en; ndus=YOUR_COOKIE_VALUE;"
terabox = TeraboxDL(cookie)

# Get file info
file_info = terabox.get_file_info(url)

# Download with progress callback
def progress_callback(downloaded, total_size, percentage):
    # Update bot status message
    pass

result = terabox.download(file_info,
                         save_path="downloads/",
                         callback=progress_callback)
```

**Cookie Configuration:**
Add to `credentials.json`:
```json
{
  "TERABOX_COOKIE": "lang=en; ndus=YOUR_VALUE;"
}
```

#### Option 2: r0ld3x Implementation
**Source:** https://github.com/r0ld3x/terabox-downloader-bot/blob/main/terabox.py

**Benefits:**
- Proven Telegram bot implementation
- Multiple domain support (mirrobox, nephobox, freeterabox, etc.)
- Better URL validation
- File size parsing
- Still uses external API but with better error handling

**Key Features:**
```python
def get_data(url: str):
    # Returns comprehensive file info:
    return {
        "file_name": "filename.ext",
        "link": "video_url",
        "direct_link": "download_url",
        "thumb": "thumbnail_url",
        "size": "1.5 GB",
        "sizebytes": 1610612736
    }
```

### Migration Path
1. **Phase 1:** Add TeraboxDL as optional dependency
2. **Phase 2:** Implement cookie-based auth in credentials.json
3. **Phase 3:** Replace current API with TeraboxDL
4. **Phase 4:** Add progress tracking integration with bot status messages
5. **Phase 5:** Keep current implementation as fallback

---

## 2. YouTube Downloader Enhancement

### Current Implementation
**File:** `colab_leecher/downlader/ytdl.py`

**Current Approach:**
- Uses `yt_dlp` library
- Custom progress hooks
- Subtitle support
- Playlist handling
- FFmpeg post-processing

**Current Features:**
- Format: `best`
- Concurrent fragments: 4
- Thumbnail download
- Subtitle extraction (SRT)
- Video conversion to MP4

### Recommended Enhancements

#### Option 1: Upgrade to Latest yt-dlp (Strongly Recommended)
**Source:** https://github.com/yt-dlp/yt-dlp

**Important Updates:**
- **Python 3.10+ Required** (as of 2025)
- **External JS Runtime** may be needed for YouTube (Deno recommended)
- Active development (youtube-dl is stagnant)
- Faster multi-threaded downloads
- Better format selection
- Enhanced subtitle support

**Recommended Configuration:**
```python
ydl_opts = {
    # Format selection - better quality/size balance
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",

    # Performance improvements
    "concurrent_fragment_downloads": 4,  # Fixed: was using wrong key
    "http_chunk_size": 10485760,  # 10MB chunks

    # Retry configuration
    "retries": 10,
    "fragment_retries": 10,
    "skip_unavailable_fragments": True,

    # Better error handling
    "ignoreerrors": False,  # Fail fast on errors
    "no_warnings": False,

    # Subtitle improvements
    "writesubtitles": True,
    "writeautomaticsub": True,
    "subtitleslangs": ["en", "ar"],  # Configurable
    "subtitlesformat": "srt/best",

    # Thumbnail
    "writethumbnail": True,
    "embedthumbnail": True,  # Embed in video

    # Metadata
    "addmetadata": True,
    "embedmetadata": True,

    # Post-processing
    "postprocessors": [
        {
            "key": "FFmpegVideoConvertor",
            "preferedformat": "mp4"
        },
        {
            "key": "FFmpegMetadata",
            "add_metadata": True
        },
        {
            "key": "EmbedThumbnail",
            "already_have_thumbnail": False
        }
    ],

    # Progress hooks
    "progress_hooks": [my_hook],
    "logger": MyLogger(),

    # Playlist settings
    "allow_playlist_files": True,
    "noplaylist": False,  # Allow playlists by default

    # Output template - more robust
    "outtmpl": {
        "default": "%(title).200s.%(ext)s",  # Limit filename length
        "thumbnail": "%(id)s.%(ext)s"
    },

    # Overwrites
    "overwrites": True,
}
```

**Key Bug Fixes:**
1. **Line 103:** Changed `"--concurrent-fragments": 4` to `"concurrent_fragment_downloads": 4`
2. **Added** retry logic for network failures
3. **Added** metadata embedding
4. **Added** automatic subtitle download
5. **Added** better filename handling (truncate to 200 chars)

#### Option 2: Enhanced Error Handling
**Current Issues:**
- Generic exception catching
- No retry logic
- Limited error reporting

**Recommended Improvements:**
```python
async def YTDL_Status(link, num, max_retries=3):
    """Enhanced with retry logic"""
    for attempt in range(max_retries):
        try:
            name = await get_YT_Name(link)
            Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{name}</code>\n"

            YTDL_Thread = Thread(target=YouTubeDL, name="YouTubeDL", args=(link,))
            YTDL_Thread.start()

            # ... existing code ...
            break  # Success

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

#### Option 3: Support for More Sites
yt-dlp supports 1000+ websites. Consider adding explicit support for:
- Instagram (already have dedicated module)
- Twitter/X
- TikTok
- Vimeo
- Dailymotion
- Reddit videos
- And many more

**Implementation:**
```python
# In helper.py
YTDL_SUPPORTED_SITES = [
    'youtube.com', 'youtu.be',
    'twitter.com', 'x.com',
    'tiktok.com',
    'vimeo.com',
    'dailymotion.com',
    'reddit.com',
    # ... more sites
]

def is_ytdl_compatible(url):
    """Check if URL is compatible with yt-dlp"""
    return any(site in url for site in YTDL_SUPPORTED_SITES)
```

---

## 3. Integration Plan

### Phase 1: Preparation
- [ ] Update yt-dlp to latest version
- [ ] Install TeraboxDL package
- [ ] Update credentials.json schema
- [ ] Test on Python 3.10+

### Phase 2: TeraBox Enhancement
- [ ] Implement TeraboxDL cookie authentication
- [ ] Create TeraBox class wrapper
- [ ] Add progress callback integration
- [ ] Implement fallback to current API
- [ ] Update error handling

### Phase 3: YTDL Enhancement
- [ ] Fix concurrent_fragment_downloads parameter
- [ ] Add retry logic
- [ ] Implement better format selection
- [ ] Add metadata embedding
- [ ] Improve playlist handling
- [ ] Add automatic subtitle download

### Phase 4: Testing
- [ ] Test TeraBox with various file types
- [ ] Test YouTube with playlists
- [ ] Test YTDL with other supported sites
- [ ] Verify progress tracking
- [ ] Load testing

### Phase 5: Documentation
- [ ] Update user guide
- [ ] Add cookie extraction guide
- [ ] Document supported sites
- [ ] Create troubleshooting guide

---

## 4. Dependencies Update

### Current Requirements
```
yt_dlp
aiohttp
```

### Recommended Additions
```
# For enhanced TeraBox support
terabox-downloader>=1.0.0

# For yt-dlp enhancements
yt-dlp>=2024.11.0  # Latest version
ffmpeg-python>=0.2.0  # Better FFmpeg integration

# Optional: For YouTube JS bypass (if needed)
# deno or nodejs runtime
```

### Python Version
**Upgrade to Python 3.10+** for full yt-dlp support (3.12 recommended)

---

## 5. Configuration Schema Updates

### Enhanced credentials.json
```json
{
  "API_ID": "...",
  "API_HASH": "...",
  "BOT_TOKEN": "...",
  "USER_ID": "...",
  "DUMP_ID": "...",

  "INSTAGRAM_SESSIONID": "...",

  "TERABOX_COOKIE": "lang=en; ndus=YOUR_VALUE;",

  "YTDL_SETTINGS": {
    "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best",
    "subtitle_languages": ["en", "ar"],
    "max_retries": 10,
    "concurrent_fragments": 4
  },

  "NZB_PROVIDERS": {...}
}
```

---

## 6. Expected Benefits

### TeraBox Enhancements
- ✅ More reliable downloads (no third-party API dependency)
- ✅ Better authentication (cookie-based)
- ✅ Accurate progress tracking
- ✅ Better metadata extraction
- ✅ Faster downloads

### YTDL Enhancements
- ✅ Better quality selection
- ✅ Faster downloads (multi-threading)
- ✅ Automatic retries
- ✅ Better error messages
- ✅ Support for more websites
- ✅ Embedded metadata and thumbnails
- ✅ Automatic subtitle download

---

## 7. References

### GitHub Repositories
- **yt-dlp:** https://github.com/yt-dlp/yt-dlp
- **TeraboxDL:** https://github.com/Damantha126/TeraboxDL
- **r0ld3x TeraBox Bot:** https://github.com/r0ld3x/terabox-downloader-bot

### Documentation
- yt-dlp docs: https://github.com/yt-dlp/yt-dlp#readme
- TeraboxDL PyPI: https://pypi.org/project/terabox-downloader/

---

## Notes
- Always test enhancements in development environment first
- Keep current implementations as fallback options
- Monitor GitHub repos for updates
- Consider rate limiting for API calls
- Add proper logging for debugging
- Implement graceful degradation if dependencies fail

---

**Last Updated:** 2025-12-24
**Author:** Claude Code Assistant
**Status:** Recommendations for Implementation
