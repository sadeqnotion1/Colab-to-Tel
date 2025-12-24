# Claude Code Development Guide

## Progress Bar Implementation Pattern

### Overview

All download/upload features in this bot MUST use the standardized progress bar format with thumbnail support. This ensures a consistent user experience across all commands.

### Standard Progress Bar Format

```
🎬 [Service Name] Download »

🎯 Stream » [Type]

╭「████████░░░░」 » 66.7%
├⚡️ Speed » N/A
├⚙️ Engine » [Downloader Name]
├⏳ ETA » 2m 15s
├⏱️ Elapsed » 4m 30s
├✅ Done » Downloading...
╰📦 Total » Unknown
```

### Thumbnail System

#### How Thumbnails Work

1. **Random Thumbnail Pool**: ~472 random images stored in `task_manager.py` (lines 157-631)
2. **Download on Task Start**: `task_starter()` downloads a random thumbnail → saves to `Paths.HERO_IMAGE`
3. **Message Creation**: Initial status message sent via `send_photo()` with thumbnail
4. **Progress Updates**: Use `edit_caption()` (NOT `edit_text()`) to preserve thumbnail

#### Thumbnail Priority

```python
if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
    thumb_path = Paths.THMB_PATH  # 1. Custom thumbnail (user-uploaded)
elif os.path.exists(Paths.HERO_IMAGE):
    thumb_path = Paths.HERO_IMAGE  # 2. Random from pool (downloaded by task_starter)
else:
    thumb_path = Paths.DEFAULT_HERO  # 3. Static fallback
```

### Implementation Checklist for New Features

When adding a new downloader/uploader, follow this pattern:

#### ✅ 1. Initial Status Message with Thumbnail

```python
# Get thumbnail (custom > random > default)
if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
    thumb_path = Paths.THMB_PATH
elif os.path.exists(Paths.HERO_IMAGE):
    thumb_path = Paths.HERO_IMAGE
else:
    thumb_path = Paths.DEFAULT_HERO

# Send with photo (NOT send_message!)
if os.path.exists(thumb_path):
    MSG.status_msg = await client.send_photo(
        OWNER,
        photo=thumb_path,
        caption=initial_status_text,
        reply_markup=keyboard()
    )
else:
    # Fallback to text only if thumbnail doesn't exist
    MSG.status_msg = await client.send_message(
        OWNER,
        initial_status_text,
        reply_markup=keyboard()
    )
```

#### ✅ 2. Progress Updates (Use `status_bar()`)

```python
# helper.py automatically detects photo messages and uses edit_caption()
await status_bar(
    down_msg=status_header,      # Custom header with service name
    speed="N/A",                  # Speed string or "N/A"
    percentage=percentage_float,  # Float 0-100
    eta=eta_string,              # Formatted time string or "N/A"
    done=status_text,            # Current status (e.g., "Downloading...")
    total_size="Unknown",        # Total size or "Unknown"
    engine="Service (downloader)" # Service name and downloader type
)
```

#### ✅ 3. Status Text Updates

**NEVER use `simple_message_update()` or direct message edits during download/upload!**

All status updates MUST go through `update_progress_bar()` or `status_bar()` to maintain format:

```python
# ❌ WRONG - Breaks progress bar format
await message.reply_text("✅ Download complete!")
await self.simple_message_update("Starting download...")

# ✅ CORRECT - Keeps progress bar format
await self.update_progress_bar(100.0, "Complete ✅ 250.5 MiB")
await self.update_progress_bar(0.0, "Starting...")
```

#### ✅ 4. Error Messages in Progress Bar

Even errors should display in progress bar format:

```python
# ✅ Show errors in progress bar
await self.update_progress_bar(self.current_percentage, "❌ Download failed")
await self.update_progress_bar(0.0, "❌ File not found")
```

### Key Implementation Details

#### Progress Tracking Variables

```python
class YourDownloader:
    def __init__(self, client, message):
        self.download_start_time = 0
        self.current_stream_type = ""  # e.g., "video", "audio"
        self.current_percentage = 0.0
```

#### Progress Bar Helper Method

```python
async def update_progress_bar(self, percentage: float, status_text: str = "Downloading..."):
    """Update progress bar using the bot's status_bar system"""
    try:
        if not MSG.status_msg:
            return

        # Calculate elapsed time
        elapsed = time.time() - self.download_start_time

        # Calculate ETA based on percentage
        if percentage > 0 and percentage < 100:
            eta_seconds = (elapsed / percentage) * (100 - percentage)
        else:
            eta_seconds = 0

        eta_str = getTime(eta_seconds) if eta_seconds > 0 else "N/A"

        # Create status header
        stream_emoji = {"video": "🎬", "audio": "🔊", "subtitle": "📝"}.get(
            self.current_stream_type, "⬇️"
        )
        status_head = (
            f"<b>{stream_emoji} Your Service Download »</b>\n\n"
            f"<b>🎯 Stream » </b><code>{self.current_stream_type.capitalize()}</code>\n"
        )

        # Use standard status_bar function
        await status_bar(
            down_msg=status_head,
            speed="N/A",
            percentage=percentage,
            eta=eta_str,
            done=status_text,
            total_size="Unknown",
            engine=f"YourService ({self.downloader})"
        )
    except Exception as e:
        log.warning(f"Failed to update progress bar: {e}")
```

## Mindvalley Implementation Reference

### File Structure

```
colab_leecher/
├── __main__.py                      # Command handlers
│   └── handle_mindvalley_urls()     # Main handler (lines 905-1070)
├── downlader/
│   └── mindvalley.py                # Downloader implementation
│       ├── MindvalleyDownloader class
│       ├── update_progress_bar()    # Progress bar updates
│       ├── _download_with_n_m3u8dl()
│       ├── _download_with_ytdlp()
│       ├── _download_with_ffmpeg()
│       ├── download_subtitle()
│       └── merge_streams()
└── utility/
    ├── helper.py
    │   └── status_bar()             # Progress bar function (lines 1322-1395)
    └── task_manager.py
        └── thumbnail_urls[]         # Random thumbnail pool (lines 157-631)
```

### Progress Bar States in Mindvalley

#### Video/Audio Download
```
0%   → "Downloading..."
33%  → "Downloading..."
66%  → "Downloading..."
100% → "Complete ✅ 250.5 MiB"
```

#### Subtitle Download
```
0%   → "Fetching playlist..."
5%   → "Downloading segments (0/150)"
50%  → "Segments 75/150"
95%  → "Segments 150/150"
100% → "Complete ✅ 125.3 KiB"
```

#### Stream Merging
```
0%   → "Merging streams..."
100% → "Merged ✅ 500.8 MiB"
```

#### Errors
```
[current %] → "❌ Download failed"
[current %] → "❌ File not found"
[current %] → "❌ Error occurred"
```

### Key Code References

#### Initial Message with Thumbnail (__main__.py:1008-1033)
```python
# Get thumbnail path (priority: custom > random > static default)
if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
    thumb_path = Paths.THMB_PATH
elif os.path.exists(Paths.HERO_IMAGE):
    thumb_path = Paths.HERO_IMAGE
else:
    thumb_path = Paths.DEFAULT_HERO

# Send status message with thumbnail
if os.path.exists(thumb_path):
    MSG.status_msg = await client.send_photo(
        OWNER,
        photo=thumb_path,
        caption=status_text,
        reply_markup=keyboard()
    )
```

#### Progress Updates (mindvalley.py:603-639)
```python
async def update_progress_bar(self, percentage: float, status_text: str = "Downloading..."):
    # Calculate ETA
    elapsed = time.time() - self.download_start_time
    if percentage > 0 and percentage < 100:
        eta_seconds = (elapsed / percentage) * (100 - percentage)
    else:
        eta_seconds = 0

    # Build status message
    await status_bar(
        down_msg=status_head,
        speed="N/A",
        percentage=percentage,
        eta=eta_str,
        done=status_text,
        total_size="Unknown",
        engine=f"Mindvalley ({self.downloader})"
    )
```

#### Thumbnail Preservation (helper.py:1376-1384)
```python
# Check if message is a photo (has thumbnail) or plain text
if hasattr(MSG.status_msg, 'photo') and MSG.status_msg.photo:
    # Message has a photo/thumbnail - edit caption to preserve thumbnail
    await MSG.status_msg.edit_caption(caption=final_text, reply_markup=kb_markup)
else:
    # Plain text message - edit text normally
    await MSG.status_msg.edit_text(text=final_text, disable_web_page_preview=True, reply_markup=kb_markup)
```

## Common Mistakes to Avoid

### ❌ WRONG: Using send_message() for initial status
```python
MSG.status_msg = await client.send_message(OWNER, status_text)
# Result: No thumbnail shown!
```

### ✅ CORRECT: Using send_photo()
```python
MSG.status_msg = await client.send_photo(OWNER, photo=thumb_path, caption=status_text)
# Result: Thumbnail shown throughout download/upload
```

---

### ❌ WRONG: Breaking progress bar format
```python
await message.reply_text("✅ Download complete!")
await self.simple_message_update("Starting download...")
# Result: Progress bar disappears, inconsistent UI
```

### ✅ CORRECT: Staying in progress bar format
```python
await self.update_progress_bar(100.0, "Complete ✅ 250.5 MiB")
await self.update_progress_bar(0.0, "Starting...")
# Result: Consistent progress bar format maintained
```

---

### ❌ WRONG: Using edit_text() on photo messages
```python
await MSG.status_msg.edit_text(text=new_text)
# Result: Thumbnail removed!
```

### ✅ CORRECT: Let status_bar() handle it automatically
```python
await status_bar(down_msg=..., speed=..., percentage=..., ...)
# Result: Automatically detects photo and uses edit_caption()
```

## Testing Checklist

When implementing a new feature, verify:

- [ ] Initial message shows thumbnail (not text-only)
- [ ] Progress bar format appears immediately (0%)
- [ ] Progress updates maintain thumbnail
- [ ] Progress updates maintain format
- [ ] Completion shows 100% with checkmark and file size
- [ ] Errors display in progress bar format
- [ ] No intermediate text-only messages break the format
- [ ] Thumbnail persists through entire download/upload cycle
- [ ] ETA calculation works correctly
- [ ] Elapsed time displays properly

## File Paths Reference

```python
# From variables.py
Paths.THMB_PATH = "/content/Telegram-Leecher/colab_leecher/Thumbnail.jpg"  # Custom thumbnail
Paths.HERO_IMAGE = "/content/Telegram-Leecher/BOT_WORK/Hero.jpg"           # Random downloaded
Paths.DEFAULT_HERO = "/content/Telegram-Leecher/custom_thmb.jpg"           # Static fallback
```

## Related Commits

Mindvalley progress bar implementation:
- `6791e64` - Keep all Mindvalley messages in progress bar format
- `feec851` - Fix thumbnail not persisting during progress updates
- `8032bcf` - Fix Mindvalley not showing thumbnail image
- `5c9f2a1` - Use random thumbnail collection for Mindvalley downloads

## Summary: /init Pattern for New Features

When adding ANY new download/upload feature:

1. **Use `task_starter()`** to get random thumbnail → `Paths.HERO_IMAGE`
2. **Send initial message** with `send_photo()` (thumbnail + caption)
3. **Update progress** only via `status_bar()` or `update_progress_bar()`
4. **NEVER break** progress bar format with intermediate text messages
5. **Show completion** as `100%` with checkmark and file size
6. **Display errors** in progress bar format at current percentage

This ensures:
- ✅ Consistent UI across all features
- ✅ Thumbnails displayed throughout
- ✅ Professional progress tracking
- ✅ User can see status at a glance
- ✅ Matches existing bot behavior
