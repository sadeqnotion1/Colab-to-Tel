# Enhanced Telegram Bot UI Components - Usage Guide

Complete guide for using the new UI components in your Telegram bot.

## 📚 Table of Contents

1. [Quick Start](#quick-start)
2. [Message Templates](#message-templates)
3. [Keyboard Layouts](#keyboard-layouts)
4. [Progress & Status](#progress--status)
5. [Real-World Examples](#real-world-examples)
6. [Migration Guide](#migration-guide)

---

## 🚀 Quick Start

### Import the Components

```python
# Message templates and formatting
from colab_leecher.utility.ui_components import (
    Emoji, Box, ProgressBar, MessageTemplate,
    TimeFormatter, SizeFormatter
)

# Keyboards
from colab_leecher.utility.keyboard_layouts import (
    KeyboardBuilder, CommonKeyboards, MenuKeyboards,
    ProgressKeyboards, quick_menu, quick_cancel
)

# Enhanced status displays
from colab_leecher.utility.enhanced_status import (
    StatusDisplay, CompletionMessage, ErrorMessage,
    InfoMessage, create_download_status
)
```

---

## 📝 Message Templates

### 1. Simple Headers

```python
# Basic header
header = MessageTemplate.header("Settings Menu", Emoji.ROCKET)
# Output: <b>🚀 Settings Menu</b>

# Without emoji
header = MessageTemplate.header("Downloads")
```

### 2. Labeled Fields

```python
# Regular field
field = MessageTemplate.field("Speed", "5.2 MB/s", Emoji.SPEED)
# Output: ⚡ <b>Speed:</b> 5.2 MB/s

# Field with code formatting
field = MessageTemplate.field("Filename", "movie.mp4", use_code=True)
# Output: <b>Filename:</b> <code>movie.mp4</code>
```

### 3. Box Lists (Beautiful Layouts)

```python
# Create a beautiful boxed list
items = [
    (Emoji.TAG, "Name", "my_file.zip"),
    (Emoji.SIZE, "Size", "1.5 GB"),
    (Emoji.TIME, "Duration", "2m 30s"),
]

message = MessageTemplate.box_list(items, title="Download Info")

# Output:
# <b>Download Info</b>
# ╭🏷️ <b>Name:</b> my_file.zip
# ├💾 <b>Size:</b> 1.5 GB
# ╰⏱️ <b>Duration:</b> 2m 30s
```

### 4. Card-Style Messages

```python
details = {
    "Type": "Video",
    "Quality": "1080p",
    "Format": "MP4",
    "Duration": "1h 30m"
}

emoji_map = {
    "Type": Emoji.VIDEO,
    "Quality": Emoji.STAR,
    "Format": Emoji.DOCUMENT,
    "Duration": Emoji.TIME
}

message = MessageTemplate.card("Media Information", details, emoji_map)
```

### 5. Status Messages with Progress

```python
message = MessageTemplate.status_message(
    title="Downloading Movie",
    status="In Progress",
    progress=67.5,
    details={
        "Speed": "8.2 MB/s",
        "ETA": "2m 15s",
        "Downloaded": "890 MB",
        "Total": "1.5 GB"
    }
)

# Output includes:
# - Title with emoji
# - Status line
# - Progress bar [████████░░░░] 67.5%
# - All details in box format
```

### 6. Error Messages

```python
error_msg = MessageTemplate.error_message(
    title="Download Failed",
    error="Connection timeout after 30 seconds",
    details="Server did not respond to request",
    solution="Check your internet connection and try again"
)

# Creates a beautifully formatted error with:
# - Error icon and title
# - Error message in code block
# - Details section
# - Suggested solution
```

### 7. Success Messages

```python
summary = {
    "Files": "42 files",
    "Total Size": "3.2 GB",
    "Time Taken": "15m 30s"
}

files_list = ["video1.mp4", "video2.mp4", "audio.mp3"]

message = MessageTemplate.success_message(
    title="Upload Complete",
    summary=summary,
    files=files_list,
    show_hashtag=True  # Adds #UPLOAD_COMPLETE at top
)
```

### 8. Menu Headers with Options

```python
# Menu header
header = MessageTemplate.menu_header(
    "Download Options",
    description="Choose your preferred download method",
    emoji=Emoji.DOWNLOAD
)

# Option list
options = [
    ("Direct Download", "Fastest method, direct from source"),
    ("Torrent", "Peer-to-peer download with resume support"),
    ("Cloud", "Download via cloud service")
]

options_text = MessageTemplate.option_list(options, numbered=True)

full_menu = header + options_text
```

---

## ⌨️ Keyboard Layouts

### 1. Quick Keyboards

```python
# Simple cancel button
kb = quick_cancel(task_id="download_123")

# Confirm/Cancel buttons
kb = quick_confirm(
    confirm_data="proceed_download",
    cancel_data="cancel_download"
)

# Quick menu
kb = quick_menu([
    ("Download", "action_download"),
    ("Upload", "action_upload"),
    ("Settings", "action_settings")
], close=True)  # Adds close button at bottom
```

### 2. Common Keyboard Patterns

```python
# Yes/No buttons
kb = CommonKeyboards.yes_no(
    yes_data="confirm_delete",
    no_data="cancel_delete"
)

# Back and Close buttons
kb = CommonKeyboards.back_close(
    back_data="menu_main",
    close_data="close"
)

# Pagination
kb = CommonKeyboards.pagination(
    current_page=2,
    total_pages=5,
    callback_prefix="files_page"
)
# Creates: « Prev | · 2/5 · | Next »
```

### 3. Grid Layouts

```python
# 2-column grid
items = [
    ("Aria2", "service_aria"),
    ("Debrid", "service_debrid"),
    ("Torrent", "service_torrent"),
    ("Direct", "service_direct")
]

kb = CommonKeyboards.grid(items, columns=2)

# Result:
# [Aria2] [Debrid]
# [Torrent] [Direct]
```

### 4. Numbered Options

```python
options = [
    ("Regular Download", "type_regular"),
    ("Compressed", "type_zip"),
    ("Extract Archive", "type_unzip")
]

kb = CommonKeyboards.numbered_options(
    options,
    callback_prefix="download_type",
    columns=1  # Vertical layout
)

# Creates:
# 1. Regular Download
# 2. Compressed
# 3. Extract Archive
```

### 5. Social/Community Links

```python
kb = CommonKeyboards.social_links(
    github="https://github.com/yourusername/yourrepo",
    channel="@YourChannel",  # or full URL
    group="@YourGroup",
    website="https://yourwebsite.com"
)

# Creates buttons for all provided links
```

### 6. Using KeyboardBuilder (Advanced)

```python
kb = KeyboardBuilder()

# Add buttons to first row
kb.button("Option 1", callback_data="opt1", emoji=Emoji.CHECK)
kb.button("Option 2", callback_data="opt2", emoji=Emoji.CROSS)
kb.row()  # Start new row

# Add full row
kb.add_row(
    InlineKeyboardButton("Settings", callback_data="settings"),
    InlineKeyboardButton("Help", callback_data="help")
)

# Add single button row
kb.button("Cancel", callback_data="cancel", emoji=Emoji.ERROR)

# Build the keyboard
final_kb = kb.build()
```

### 7. Menu Keyboards

```python
# Main menu
options = {
    "📥 Download": "menu_download",
    "📤 Upload": "menu_upload",
    "⚙️ Settings": "menu_settings",
    "ℹ️ Help": "menu_help"
}

kb = MenuKeyboards.main_menu(options, close=True)
```

### 8. Settings Menu with Toggle

```python
# Toggle switches
options = {
    "Auto Upload": (True, "toggle_auto_upload"),  # (current_state, callback)
    "Compress Files": (False, "toggle_compress"),
    "Delete After Upload": (True, "toggle_delete")
}

kb = MenuKeyboards.toggle_options(
    options,
    callback_prefix="setting"
)

# Creates buttons like:
# Auto Upload [🟢 ON]
# Compress Files [🔴 OFF]
# Delete After Upload [🟢 ON]
```

### 9. Selection Menu with Checkmarks

```python
services = [
    ("Aria2", "aria2"),
    ("Direct Download", "direct"),
    ("Torrent", "torrent")
]

kb = MenuKeyboards.selection_menu(
    services,
    selected="aria2",  # Currently selected
    callback_prefix="select_service",
    show_checkmark=True
)

# Shows ✓ next to selected item
```

---

## 📊 Progress & Status

### 1. Progress Bars

```python
# Basic progress bar
bar = ProgressBar.generate(75.5, length=12, style='blocks')
# Output: ████████░░░░

# Different styles
bar = ProgressBar.generate(50, style='circles')  # ●●●●●●○○○○○○
bar = ProgressBar.generate(50, style='squares')  # ■■■■■■□□□□□□
bar = ProgressBar.generate(50, style='arrows')   # ▰▰▰▰▰▰▱▱▱▱▱▱
bar = ProgressBar.generate(50, style='gradient') # ██▓▒░░░░░░░░

# With percentage
bar = ProgressBar.with_percentage(67.8, style='blocks')
# Output: [████████░░░░] 67.8%

# Custom wrapper
bar = ProgressBar.custom(
    75.5,
    prefix="Progress:",
    suffix="75.5%",
    style='blocks'
)
```

### 2. Download Status (Modern Style)

```python
from colab_leecher.utility.enhanced_status import create_download_status

message, keyboard = create_download_status(
    filename="movie_1080p.mp4",
    progress=67.5,
    speed=8_500_000,  # bytes per second
    downloaded=1_200_000_000,  # bytes
    total_size=1_800_000_000,
    eta=120,  # seconds
    engine="Aria2",
    task_id="task_123",
    style="modern"  # or "compact" or "classic"
)

# Send or edit message
await message.edit_text(message, reply_markup=keyboard)
```

### 3. Upload Status

```python
from colab_leecher.utility.enhanced_status import create_upload_status

message, keyboard = create_upload_status(
    filename="video.mp4",
    progress=45.2,
    speed=3_500_000,
    uploaded=800_000_000,
    total_size=1_800_000_000,
    eta=180,
    destination="Google Drive",
    task_id="upload_456"
)
```

### 4. Processing/Extracting Status

```python
status = StatusDisplay("Extract", task_id="extract_789")

message, keyboard = status.processing_status(
    filename="archive.zip",
    operation="Extracting",
    progress=33.3,
    current_file="folder/large_video.mp4",
    files_done=15,
    total_files=45
)
```

### 5. Completion Messages

```python
from colab_leecher.utility.enhanced_status import CompletionMessage

# Download complete
message = CompletionMessage.download_complete(
    filename="movie.mp4",
    size=1_800_000_000,
    duration=450,  # seconds
    engine="Aria2",
    file_count=1
)

# Upload complete with links
message = CompletionMessage.upload_complete(
    files=["video1.mp4", "video2.mp4", "audio.mp3"],
    total_size=3_200_000_000,
    duration=920,
    destination="Telegram",
    links=[
        "https://t.me/c/123/456",
        "https://t.me/c/123/457",
        "https://t.me/c/123/458"
    ]
)
```

### 6. Error Messages

```python
from colab_leecher.utility.enhanced_status import ErrorMessage

# Download failed
error_msg = ErrorMessage.download_failed(
    filename="movie.mp4",
    error="Connection timeout",
    details="Server did not respond after 30 seconds",
    task_id="download_123"
)

# Upload failed
error_msg = ErrorMessage.upload_failed(
    filename="large_file.zip",
    error="File size exceeds limit",
    details="Maximum file size for Telegram is 2GB"
)
```

### 7. Info Messages

```python
from colab_leecher.utility.enhanced_status import InfoMessage

# Task started
message = InfoMessage.task_started(
    "Batch Download",
    details={
        "Files": "15 files",
        "Total Size": "5.2 GB",
        "Service": "Aria2"
    }
)

# Task queued
message = InfoMessage.task_queued("Download Movie", position=3)

# Please wait
message = InfoMessage.please_wait("Preparing download...")
```

---

## 🎯 Real-World Examples

### Example 1: Complete Download Flow

```python
from pyrogram import Client, filters
from pyrogram.types import Message
from colab_leecher.utility.enhanced_status import (
    InfoMessage, create_download_status, CompletionMessage, ErrorMessage
)
from colab_leecher.utility.keyboard_layouts import ProgressKeyboards

@Client.on_message(filters.command("download"))
async def download_handler(client: Client, message: Message):
    url = message.text.split(maxsplit=1)[1]

    # Send initial message
    status_msg = await message.reply(
        InfoMessage.please_wait("Starting download...")
    )

    try:
        # Simulate download with progress updates
        for progress in range(0, 101, 10):
            msg_text, keyboard = create_download_status(
                filename="example_file.mp4",
                progress=progress,
                speed=5_000_000,
                downloaded=progress * 10_000_000,
                total_size=1_000_000_000,
                eta=(100 - progress) * 2,
                engine="Aria2",
                task_id="dl_001",
                style="modern"
            )

            await status_msg.edit(msg_text, reply_markup=keyboard)
            await asyncio.sleep(1)

        # Success message
        completion_msg = CompletionMessage.download_complete(
            filename="example_file.mp4",
            size=1_000_000_000,
            duration=200,
            engine="Aria2"
        )

        await status_msg.edit(completion_msg)

    except Exception as e:
        # Error message
        error_msg = ErrorMessage.download_failed(
            filename="example_file.mp4",
            error=str(e),
            task_id="dl_001"
        )
        await status_msg.edit(error_msg)
```

### Example 2: Settings Menu

```python
from colab_leecher.utility.ui_components import MessageTemplate, Emoji
from colab_leecher.utility.keyboard_layouts import MenuKeyboards

async def show_settings(message: Message):
    # Create settings display
    current_settings = {
        "Upload Mode": ("Media", "setting_upload_mode"),
        "Video Quality": ("1080p", "setting_video_quality"),
        "Auto Delete": (True, "toggle_auto_delete"),
        "Notifications": (False, "toggle_notifications")
    }

    # Create message
    msg_text = MessageTemplate.menu_header(
        "Settings",
        "Configure your bot preferences",
        emoji=Emoji.PROCESS
    )

    # Add current values
    msg_text += "\n<b>Current Settings:</b>\n"
    for key, (value, _) in current_settings.items():
        if isinstance(value, bool):
            value = "🟢 Enabled" if value else "🔴 Disabled"
        msg_text += f"\n{Emoji.BULLET} <b>{key}:</b> {value}"

    # Create keyboard
    keyboard = MenuKeyboards.settings_menu(
        current_settings,
        navigation=True
    )

    await message.reply(msg_text, reply_markup=keyboard)
```

### Example 3: Interactive Menu with Options

```python
from colab_leecher.utility.ui_components import MessageTemplate
from colab_leecher.utility.keyboard_layouts import quick_menu

async def show_download_menu(message: Message):
    # Header
    header = MessageTemplate.menu_header(
        "Download Options",
        "Choose your download method"
    )

    # Options description
    options = [
        ("Direct Download", "Fastest, uses Aria2 or similar"),
        ("Debrid Service", "Premium unlocking service"),
        ("Torrent", "P2P download with DHT support"),
        ("YouTube-DL", "For YouTube and 1000+ sites")
    ]

    options_text = MessageTemplate.option_list(options, numbered=True)

    # Keyboard
    keyboard = quick_menu([
        ("Direct", "service_direct"),
        ("Debrid", "service_debrid"),
        ("Torrent", "service_torrent"),
        ("YouTube-DL", "service_ytdl")
    ], close=True)

    full_message = header + options_text
    await message.reply(full_message, reply_markup=keyboard)
```

### Example 4: File Selection with Pagination

```python
from colab_leecher.utility.keyboard_layouts import KeyboardBuilder, CommonKeyboards
from colab_leecher.utility.ui_components import Box, Emoji

async def show_files(message: Message, page: int = 1, files_per_page: int = 5):
    all_files = [...]  # Your file list
    total_pages = (len(all_files) + files_per_page - 1) // files_per_page

    start_idx = (page - 1) * files_per_page
    end_idx = start_idx + files_per_page
    page_files = all_files[start_idx:end_idx]

    # Build message
    lines = [f"<b>{Emoji.FOLDER} Available Files</b>\n"]
    lines.append(f"<i>Page {page} of {total_pages}</i>\n")

    for i, file in enumerate(page_files, start=start_idx + 1):
        lines.append(f"{i}. <code>{file['name']}</code> - {file['size']}")

    # Build keyboard with file selection + pagination
    kb = KeyboardBuilder()

    # File selection buttons
    for i, file in enumerate(page_files, start=start_idx):
        kb.button(f"Download #{i+1}", callback_data=f"download_file:{i}").row()

    # Pagination
    pagination_kb = CommonKeyboards.pagination(page, total_pages, "files_page")

    # Combine keyboards
    from colab_leecher.utility.keyboard_layouts import UtilityKeyboards
    final_kb = UtilityKeyboards.combine(kb.build(), pagination_kb)

    await message.reply("\n".join(lines), reply_markup=final_kb)
```

---

## 🔄 Migration Guide

### Migrating from Current Implementation

#### Before (Old Code):
```python
# Old helper.py style
async def status_bar(down_msg, speed, percentage, eta, done, total_size, engine):
    text = f"╭「{'█' * int(percentage/10)}{'░' * (10-int(percentage/10))}」 » __{percentage:.1f}%__\n"
    text += f"├⚡️ **Speed »** **{speed} MB/s**\n"
    # ... more manual formatting

    kb = keyboard(task_id)
    await down_msg.edit_text(text, reply_markup=kb)
```

#### After (New Components):
```python
# New enhanced_status.py style
from colab_leecher.utility.enhanced_status import create_download_status

message, keyboard = create_download_status(
    filename=file_name,
    progress=percentage,
    speed=speed_bytes,
    downloaded=done_bytes,
    total_size=total_bytes,
    eta=eta_seconds,
    engine=engine_name,
    task_id=task_id,
    style="modern"  # Choose your style!
)

await down_msg.edit_text(message, reply_markup=keyboard)
```

### Step-by-Step Migration

1. **Import new modules** in your existing files:
```python
from colab_leecher.utility.enhanced_status import create_download_status
from colab_leecher.utility.keyboard_layouts import quick_menu, CommonKeyboards
```

2. **Replace manual string formatting** with templates:
```python
# Old
msg = f"<b>📥 DOWNLOADING</b>\n\n<b>Name:</b> <code>{name}</code>"

# New
from colab_leecher.utility.ui_components import MessageTemplate, Emoji
msg = MessageTemplate.header("DOWNLOADING", Emoji.DOWNLOAD)
msg += MessageTemplate.field("Name", name, use_code=True)
```

3. **Replace inline keyboard creation**:
```python
# Old
kb = InlineKeyboardMarkup([
    [InlineKeyboardButton("Cancel ❌", callback_data="cancel")]
])

# New
from colab_leecher.utility.keyboard_layouts import quick_cancel
kb = quick_cancel()
```

4. **Update progress displays** incrementally:
   - Start with new downloads
   - Gradually update existing functions
   - Keep both implementations during transition

---

## 🎨 Customization Tips

### 1. Create Your Own Styles

```python
# Custom progress bar style
class CustomProgressBar(ProgressBar):
    @staticmethod
    def gaming_style(percentage: float) -> str:
        chars = ['⬜', '🟩']
        length = 10
        filled = int((percentage / 100) * length)
        return chars[1] * filled + chars[0] * (length - filled)

# Use it
bar = CustomProgressBar.gaming_style(75)
```

### 2. Brand Your Messages

```python
# Create branded templates
class BrandedMessages:
    LOGO = "🎬"  # Your logo emoji
    COLOR = "blue"  # Not used in Telegram but for consistency

    @staticmethod
    def header(title: str) -> str:
        return f"<b>{BrandedMessages.LOGO} {title.upper()}</b>\n"

    @staticmethod
    def footer() -> str:
        return f"\n\n<i>Powered by YourBotName {BrandedMessages.LOGO}</i>"
```

### 3. Theme Variations

```python
# Light vs Dark theme emoji sets
class Theme:
    LIGHT = {
        'success': '✅',
        'error': '❌',
        'progress': '🔵'
    }

    DARK = {
        'success': '🟢',
        'error': '🔴',
        'progress': '⚪'
    }

# Use based on user preference
current_theme = Theme.DARK
success_emoji = current_theme['success']
```

---

## 📖 Additional Resources

- **Pyrogram Documentation**: https://docs.pyrogram.org/
- **Telegram Bot API**: https://core.telegram.org/bots/api
- **Emoji Reference**: https://emojipedia.org/

## 🤝 Contributing

Have ideas for new components? Feel free to extend these utilities!

### Adding New Templates

1. Add to `ui_components.py` in the `MessageTemplate` class
2. Follow existing naming conventions
3. Use type hints
4. Add docstrings with examples

### Adding New Keyboards

1. Add to `keyboard_layouts.py` in appropriate class
2. Use `KeyboardBuilder` for complex layouts
3. Provide both simple and advanced versions

---

## ✅ Best Practices

1. **Always use emojis consistently** - Pick from `Emoji` class
2. **Use box drawing for structure** - Makes messages readable
3. **Keep progress updates < 2 seconds apart** - Avoid rate limits
4. **Use appropriate message styles** - Modern for main features, compact for power users
5. **Add keyboards to interactive messages** - Improve UX
6. **Handle errors gracefully** - Use `ErrorMessage` templates
7. **Provide feedback** - Use `InfoMessage` for state changes

---

**Happy Building! 🚀**
