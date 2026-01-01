# 🎨 Enhanced Telegram Bot UI Components

**Modern, beautiful, and easy-to-use UI components for your Telegram bot!**

## 📦 What's Included

### ✨ New Files Created

1. **`colab_leecher/utility/ui_components.py`** - Message templates and formatters
2. **`colab_leecher/utility/keyboard_layouts.py`** - Reusable keyboard layouts
3. **`colab_leecher/utility/enhanced_status.py`** - Progress and status displays
4. **`QUICK_EXAMPLES.py`** - Copy-paste ready examples
5. **`UI_COMPONENTS_GUIDE.md`** - Complete documentation
6. **`MIGRATION_EXAMPLES.md`** - Before/after migration guide

---

## 🚀 Quick Start

### 1. Basic Import

```python
# Message templates
from colab_leecher.utility.ui_components import Emoji, MessageTemplate, ProgressBar

# Keyboards
from colab_leecher.utility.keyboard_layouts import quick_menu, CommonKeyboards

# Status displays
from colab_leecher.utility.enhanced_status import create_download_status
```

### 2. Create Your First Beautiful Message

```python
# Beautiful header
header = MessageTemplate.header("Welcome", Emoji.ROCKET)

# Menu with keyboard
keyboard = quick_menu([
    ("Download", "action_download"),
    ("Upload", "action_upload"),
    ("Settings", "action_settings")
], close=True)

await message.reply(header, reply_markup=keyboard)
```

### 3. Show Download Progress

```python
message_text, keyboard = create_download_status(
    filename="movie.mp4",
    progress=67.5,
    speed=8_500_000,  # bytes/sec
    downloaded=1_200_000_000,
    total_size=1_800_000_000,
    eta=120,
    engine="Aria2",
    task_id="dl_001",
    style="modern"
)

await status_msg.edit_text(message_text, reply_markup=keyboard)
```

---

## 📚 Documentation Files

### For Beginners
👉 **Start Here:** `QUICK_EXAMPLES.py`
- Copy-paste ready code snippets
- Real-world examples
- Complete handler implementations

### For Learning
👉 **Read This:** `UI_COMPONENTS_GUIDE.md`
- Complete API documentation
- Usage examples for every component
- Best practices and tips
- Customization guide

### For Migration
👉 **Use This:** `MIGRATION_EXAMPLES.md`
- Before/after comparisons
- Step-by-step migration guide
- Real code from your project
- Migration checklist

---

## 🎯 Key Features

### 🎨 Beautiful Message Templates

```python
# Error message with solution
error_msg = MessageTemplate.error_message(
    title="Download Failed",
    error="Connection timeout",
    solution="Check your internet and try again"
)

# Success message with files list
success_msg = MessageTemplate.success_message(
    title="Upload Complete",
    summary={"Files": "42", "Size": "3.2 GB"},
    files=["file1.mp4", "file2.mp4"],
    show_hashtag=True
)

# Card-style info display
card = MessageTemplate.card(
    "File Information",
    {"Type": "Video", "Quality": "1080p", "Size": "1.5 GB"},
    emoji_map={"Type": Emoji.VIDEO, "Quality": Emoji.STAR}
)
```

### ⌨️ Smart Keyboard Layouts

```python
# Quick cancel button
kb = quick_cancel(task_id="download_123")

# Confirm/Cancel side-by-side
kb = CommonKeyboards.confirm_cancel(
    confirm_data="proceed",
    cancel_data="cancel"
)

# Grid layout (2 columns)
kb = CommonKeyboards.grid([
    ("Option 1", "opt1"),
    ("Option 2", "opt2"),
    ("Option 3", "opt3"),
    ("Option 4", "opt4")
], columns=2)

# Social links
kb = CommonKeyboards.social_links(
    github="https://github.com/you/repo",
    channel="@YourChannel",
    group="@YourGroup"
)

# Pagination
kb = CommonKeyboards.pagination(
    current_page=2,
    total_pages=5,
    callback_prefix="page"
)
```

### 📊 Progress Bars & Status

```python
# Different styles available
bar = ProgressBar.generate(75, style='blocks')   # ████████░░░░
bar = ProgressBar.generate(75, style='circles')  # ●●●●●●●●●○○○
bar = ProgressBar.generate(75, style='gradient') # ██▓▒░░░░░░░░

# Download status (automatic formatting!)
msg, kb = create_download_status(
    filename="file.zip",
    progress=45.2,
    speed=5_000_000,
    downloaded=800_000_000,
    total_size=1_800_000_000,
    eta=180,
    engine="Aria2",
    style="modern"  # or "compact" or "classic"
)

# Upload status
msg, kb = create_upload_status(
    filename="video.mp4",
    progress=67.5,
    speed=3_500_000,
    uploaded=1_200_000_000,
    total_size=1_800_000_000,
    destination="Google Drive"
)
```

---

## 🎨 Visual Styles Comparison

### Modern Style (Recommended)
```
📥 DOWNLOADING

╭🏷️ Name: movie.mp4
├「██████████░░░░」 67.5%
├⚡ Speed: 8.5 MB/s
├💾 Progress: 1.2 GB / 1.8 GB
├⏳ ETA: 2m 15s
├⏱️ Elapsed: 1m 30s
╰⚙️ Engine: Aria2
```

### Compact Style (Space-saving)
```
🚀 DOWNLOADING

movie.mp4

[████████░░░░] 67.5%
⚡ 8.5 MB/s  ⏳ 2m 15s  ⏱️ 1m 30s
💾 1.2 GB/1.8 GB  ⚙️ Aria2
```

### Classic Style (Traditional)
```
📥 DOWNLOADING

🏷️ Name » movie.mp4

╭「████████░░░░」 » 67.5%
├⚡ Speed » 8.5 MB/s
├⚙️ Engine » Aria2
├⏳ ETA » 2m 15s
├⏱️ Elapsed » 1m 30s
├✅ Done » 1.2 GB
╰📦 Total » 1.8 GB
```

---

## 🔧 Integration Examples

### Replace Existing status_bar Function

**Before:** 60+ lines of manual formatting

**After:**
```python
from colab_leecher.utility.enhanced_status import create_download_status

async def status_bar(down_msg, speed, percentage, eta, done, total_size, engine,
                     use_custom_text: bool = False, task_ctx: TaskContext = None):
    message_text, keyboard = create_download_status(
        filename=Transfer.name,
        progress=percentage,
        speed=speed,
        downloaded=done,
        total_size=total_size,
        eta=eta,
        engine=engine,
        task_id=task_ctx.task_id if task_ctx else None,
        style="modern"
    )

    await down_msg.edit_text(message_text, reply_markup=keyboard)
```

### Upgrade Menu Messages

**Before:** Manual keyboard and text building

**After:**
```python
from colab_leecher.utility.ui_components import MessageTemplate
from colab_leecher.utility.keyboard_layouts import quick_menu

header = MessageTemplate.menu_header(
    "Download Options",
    "Choose your preferred method"
)

keyboard = quick_menu([
    ("Direct", "service_direct"),
    ("Debrid", "service_debrid"),
    ("Torrent", "service_torrent")
], close=True)

await message.reply(header, reply_markup=keyboard)
```

---

## 🎓 Learn by Example

### Example 1: Complete Download Flow

See `QUICK_EXAMPLES.py` → `download_file_example()`

Shows:
- Starting download
- Progress updates
- Success message
- Error handling
- Social links

### Example 2: Interactive Settings Menu

See `QUICK_EXAMPLES.py` → `show_settings_menu()`

Shows:
- Settings display
- Toggle switches
- Navigation buttons
- Callback handling

### Example 3: Multi-Step Wizard

See `QUICK_EXAMPLES.py` → `DownloadWizard` class

Shows:
- Step-by-step flow
- State management
- Confirmation dialogs
- Progress tracking

---

## 📖 Components Reference

### Message Templates (`ui_components.py`)

| Function | Purpose | Example |
|----------|---------|---------|
| `MessageTemplate.header()` | Create headers | `header("Settings", Emoji.PROCESS)` |
| `MessageTemplate.field()` | Labeled fields | `field("Speed", "8 MB/s", Emoji.SPEED)` |
| `MessageTemplate.box_list()` | Boxed lists | Beautiful structured data |
| `MessageTemplate.card()` | Card display | Info cards with icons |
| `MessageTemplate.status_message()` | Status updates | Progress with details |
| `MessageTemplate.error_message()` | Error display | Errors with solutions |
| `MessageTemplate.success_message()` | Success display | Completions with hashtags |
| `MessageTemplate.menu_header()` | Menu titles | Headers with descriptions |
| `MessageTemplate.option_list()` | Numbered options | Option descriptions |

### Keyboards (`keyboard_layouts.py`)

| Class | Purpose | Use For |
|-------|---------|---------|
| `KeyboardBuilder` | Fluent builder | Complex custom keyboards |
| `CommonKeyboards` | Common patterns | Cancel, confirm, grids, pagination |
| `MenuKeyboards` | Menu layouts | Settings, selections, toggles |
| `ProgressKeyboards` | Progress actions | Cancel during operations |
| `UtilityKeyboards` | Helpers | Combine keyboards, add footers |

### Status Displays (`enhanced_status.py`)

| Class | Purpose | Use For |
|-------|---------|---------|
| `StatusDisplay` | Status builder | Custom status messages |
| `CompletionMessage` | Success messages | Download/upload complete |
| `ErrorMessage` | Error handling | Beautiful error displays |
| `InfoMessage` | Info display | Task started, queued, waiting |
| `create_download_status()` | Quick download | One-line download status |
| `create_upload_status()` | Quick upload | One-line upload status |

### Utilities (`ui_components.py`)

| Class | Purpose | Example |
|-------|---------|---------|
| `Emoji` | Emoji constants | `Emoji.DOWNLOAD`, `Emoji.SUCCESS` |
| `Box` | Box drawing | `Box.TOP_LEFT`, `Box.HORIZONTAL` |
| `ProgressBar` | Progress bars | `generate(75, style='blocks')` |
| `TimeFormatter` | Format time | `format_seconds(125)` → "2m 5s" |
| `SizeFormatter` | Format sizes | `format_bytes(1500000)` → "1.43 MB" |

---

## ✅ Migration Checklist

- [ ] Read `QUICK_EXAMPLES.py` for inspiration
- [ ] Review `UI_COMPONENTS_GUIDE.md` for full docs
- [ ] Check `MIGRATION_EXAMPLES.md` for your code
- [ ] Import new modules in your files
- [ ] Replace `status_bar()` function first
- [ ] Migrate keyboard creation
- [ ] Update menu messages
- [ ] Replace error messages
- [ ] Replace success messages
- [ ] Test all features
- [ ] Choose your preferred style (modern/compact/classic)
- [ ] Enjoy cleaner code! 🎉

---

## 🎯 Benefits

### Before
- ❌ 60+ lines for status messages
- ❌ Manual emoji/formatting
- ❌ Inconsistent styling
- ❌ Hard to maintain
- ❌ Duplicated code everywhere
- ❌ Difficult to customize

### After
- ✅ One-line status creation
- ✅ Automatic formatting
- ✅ Consistent beautiful UI
- ✅ Easy to maintain
- ✅ Reusable components
- ✅ Multiple style options
- ✅ 90% less code
- ✅ Professional appearance

---

## 🎨 Customization

### Create Your Own Style

```python
# Extend the classes
class MyCustomMessages(MessageTemplate):
    @staticmethod
    def my_special_format(title, data):
        # Your custom formatting
        return f"✨ {title} ✨\n{data}"

# Use it
msg = MyCustomMessages.my_special_format("Hello", "World")
```

### Brand Your Bot

```python
class MyBrand:
    LOGO = "🎬"
    NAME = "MyBot"
    COLORS = {"primary": "🔵", "success": "🟢", "error": "🔴"}

    @staticmethod
    def header(title):
        return f"{MyBrand.LOGO} <b>{title}</b> {MyBrand.LOGO}"
```

---

## 💡 Tips

1. **Start small** - Migrate one function at a time
2. **Test incrementally** - Test each change before moving on
3. **Mix old and new** - New components work with existing code
4. **Choose your style** - Try all three styles, pick your favorite
5. **Use type hints** - All functions have type hints
6. **Read docstrings** - Every function is documented
7. **Check examples** - When stuck, check `QUICK_EXAMPLES.py`

---

## 📞 Support

### Documentation
- **Quick Start:** `QUICK_EXAMPLES.py`
- **Full Guide:** `UI_COMPONENTS_GUIDE.md`
- **Migration:** `MIGRATION_EXAMPLES.md`

### Code Files
- **Templates:** `colab_leecher/utility/ui_components.py`
- **Keyboards:** `colab_leecher/utility/keyboard_layouts.py`
- **Status:** `colab_leecher/utility/enhanced_status.py`

---

## 🚀 Next Steps

1. **Explore** `QUICK_EXAMPLES.py` - See what's possible
2. **Read** `UI_COMPONENTS_GUIDE.md` - Learn all features
3. **Try** migrating one function using `MIGRATION_EXAMPLES.md`
4. **Customize** to match your bot's personality
5. **Enjoy** your beautiful new UI! 🎉

---

**Made with ❤️ for better Telegram Bots**

Happy coding! 🚀
