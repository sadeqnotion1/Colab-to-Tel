# Migration Examples - Before & After

This guide shows you **exactly** how to upgrade your existing code to use the new UI components.

## Table of Contents
- [Progress/Status Messages](#progressstatus-messages)
- [Keyboards](#keyboards)
- [Error Messages](#error-messages)
- [Success Messages](#success-messages)
- [Menu Messages](#menu-messages)

---

## Progress/Status Messages

### ❌ Before (Old Way)

```python
# In your existing code (helper.py style)
async def status_bar(down_msg, speed, percentage, eta, done, total_size, engine,
                     use_custom_text: bool = False, task_ctx: TaskContext = None):

    # Manual string building
    elapsed = time.time() - start_time
    bar_length = 12
    filled_length = int(bar_length * percentage / 100)
    bar = '█' * filled_length + '░' * (bar_length - filled_length)

    # Manual formatting
    final_text = f"<b>📥 DOWNLOADING</b>\n\n"
    final_text += f"<b>🏷️ Name » </b><code>{filename}</code>\n\n"
    final_text += f"╭「{bar}」 **»** __{percentage:.1f}%__\n"
    final_text += f"├⚡️ **Speed »** **{speed:.2f} MB/s**\n"
    final_text += f"├⚙️ **Engine »** **{engine}**\n"
    final_text += f"├⏳ **ETA »** __{eta}__\n"
    final_text += f"├⏱️ **Elapsed »** __{elapsed_time}__\n"
    final_text += f"├✅ **Done »** **{done_size}**\n"
    final_text += f"╰📦 **Total »** **{total_size}**"

    # Manual keyboard
    kb_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Cancel ❌", callback_data=f"cancel:{task_id}")]
    ])

    # Update message
    if hasattr(status_msg, 'photo'):
        await status_msg.edit_caption(caption=final_text, reply_markup=kb_markup)
    else:
        await status_msg.edit_text(text=final_text, reply_markup=kb_markup)
```

### ✅ After (New Way)

```python
# Import once at the top
from colab_leecher.utility.enhanced_status import create_download_status

# In your function - ONE LINE!
message, keyboard = create_download_status(
    filename=filename,
    progress=percentage,
    speed=speed_bytes,  # Pass bytes per second, not MB/s
    downloaded=done_bytes,
    total_size=total_bytes,
    eta=eta_seconds,
    engine=engine,
    task_id=task_id,
    style="modern"  # or "compact" or "classic"
)

# Update message - handles both photo and text automatically
await status_msg.edit_text(message, reply_markup=keyboard)
```

**Benefits:**
- ✅ 90% less code
- ✅ Automatic formatting
- ✅ Multiple style options
- ✅ Consistent appearance
- ✅ Built-in size/time formatters

---

## Keyboards

### ❌ Before (Old Way)

```python
# Creating a simple menu
keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Aria", callback_data='service_direct'),
     InlineKeyboardButton("Debrid", callback_data='service_Debrid')],
    [InlineKeyboardButton("Bitso", callback_data='service_bitso')],
    [InlineKeyboardButton("Cancel ❌", callback_data="cancel")]
])
```

### ✅ After (New Way)

```python
from colab_leecher.utility.keyboard_layouts import quick_menu

keyboard = quick_menu([
    ("Aria", "service_direct"),
    ("Debrid", "service_Debrid"),
    ("Bitso", "service_bitso")
], close=False)  # Will add "Cancel ❌" automatically if you want

# Or even simpler for 2-column grid:
from colab_leecher.utility.keyboard_layouts import CommonKeyboards

keyboard = CommonKeyboards.grid([
    ("Aria", "service_direct"),
    ("Debrid", "service_Debrid"),
    ("Bitso", "service_bitso"),
    ("Direct", "service_http")
], columns=2)
```

**Benefits:**
- ✅ Cleaner code
- ✅ Easy to modify layout
- ✅ Reusable patterns
- ✅ Less indentation hell

---

### ❌ Before (Settings Keyboard)

```python
# From your existing helper.py send_settings function
up_mode_display = BOT.Setting.stream_upload
next_up_mode = "Document" if up_mode_display == "Media" else "Media"
next_up_mode_action = f"upload-doc" if up_mode_display == "Media" else "upload-vid"

keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton(f"Upload As: {up_mode_display}", callback_data=next_up_mode_action),
     InlineKeyboardButton("Video Settings", callback_data="video")],
    [InlineKeyboardButton("Caption Font", callback_data="caption"),
     InlineKeyboardButton("Thumbnail", callback_data="thumb")],
    [InlineKeyboardButton("Set Suffix", callback_data="set-suffix"),
     InlineKeyboardButton("Set Prefix", callback_data="set-prefix")],
    [InlineKeyboardButton("Close ✘", callback_data="close")],
])
```

### ✅ After (New Way)

```python
from colab_leecher.utility.keyboard_layouts import MenuKeyboards

settings = {
    f"Upload As: {up_mode_display}": (up_mode_display, next_up_mode_action),
    "Video Settings": ("", "video"),
    "Caption Font": ("", "caption"),
    "Thumbnail": ("", "thumb"),
    "Set Suffix": ("", "set-suffix"),
    "Set Prefix": ("", "set-prefix")
}

keyboard = MenuKeyboards.settings_menu(settings, navigation=True)
# Automatically adds "Close ✘" button
```

**Or even better with toggles:**

```python
from colab_leecher.utility.keyboard_layouts import KeyboardBuilder

kb = KeyboardBuilder()

# Row 1
kb.button(f"Upload As: {up_mode_display}", callback_data=next_up_mode_action)
kb.button("Video Settings", callback_data="video")
kb.row()

# Row 2
kb.button("Caption Font", callback_data="caption")
kb.button("Thumbnail", callback_data="thumb")
kb.row()

# Row 3
kb.button("Set Suffix", callback_data="set-suffix")
kb.button("Set Prefix", callback_data="set-prefix")
kb.row()

# Close button
kb.button("Close ✘", callback_data="close")

keyboard = kb.build()
```

---

## Error Messages

### ❌ Before (Old Way)

```python
# Scattered error formatting throughout your code
error_message = f"<b>❌ Download Failed!</b>\n\n"
error_message += f"<b>Error:</b> <code>{error_text}</code>\n"
error_message += f"<b>File:</b> {filename}\n"
error_message += f"<b>Time:</b> {elapsed}\n\n"
error_message += "<i>Please try again</i>"

await message.reply(error_message)
```

### ✅ After (New Way)

```python
from colab_leecher.utility.enhanced_status import ErrorMessage

error_msg = ErrorMessage.download_failed(
    filename=filename,
    error=error_text,
    details=f"Elapsed time: {elapsed}",
    task_id=task_id
)

await message.reply(error_msg)
```

**The ErrorMessage class automatically:**
- ✅ Formats errors beautifully
- ✅ Uses proper icons and styling
- ✅ Suggests solutions based on error type
- ✅ Maintains consistent layout

---

## Success Messages

### ❌ Before (Old Way)

```python
# From your handler.py SendLogs function
final_text = f"#LEECH_COMPLETED 🔥\n\n"
final_text += f"╭📛 <b>Name »</b> <code>{filename}</code>\n"
final_text += f"├📦 <b>Downloaded »</b> **{total_size}**\n"
final_text += f"├☘️ <b>File Count »</b> {file_count} Files\n"
final_text += f"╰⏱️ <b>Time Taken »</b> {time_taken}\n\n"

if uploaded_files:
    final_text += "<b>📤 Uploaded Files:</b>\n"
    for idx, file_msg in enumerate(uploaded_files, 1):
        final_text += f"{idx}. <a href='{file_msg.link}'>{file_msg.file.file_name}</a>\n"

keyboard = InlineKeyboardMarkup([
    [InlineKeyboardButton("Git Repo 🪲", url="https://github.com/...")],
    [InlineKeyboardButton("Channel 📣", url="https://t.me/Colab_Leecher"),
     InlineKeyboardButton("Group 💬", url="https://t.me/Colab_Leecher_Discuss")]
])

await status_msg.edit_text(final_text, reply_markup=keyboard)
```

### ✅ After (New Way)

```python
from colab_leecher.utility.enhanced_status import CompletionMessage
from colab_leecher.utility.keyboard_layouts import CommonKeyboards

# Create completion message
completion = CompletionMessage.upload_complete(
    files=[f.file.file_name for f in uploaded_files],
    total_size=total_size_bytes,
    duration=time_taken_seconds,
    destination="Telegram",
    links=[f.link for f in uploaded_files]
)

# Create social links keyboard
keyboard = CommonKeyboards.social_links(
    github="https://github.com/XronTrix10/Telegram-Leecher",
    channel="Colab_Leecher",
    group="Colab_Leecher_Discuss"
)

await status_msg.edit_text(completion, reply_markup=keyboard)
```

**Benefits:**
- ✅ Cleaner, more readable
- ✅ Automatic hashtag
- ✅ Proper formatting
- ✅ Easy to modify

---

## Menu Messages

### ❌ Before (Old Way)

```python
# From your __main__.py ask_leech_type function
try:
    leech_text = await client.send_message(
        chat_id=message.chat.id,
        text="Choose how to process the download:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Regular", callback_data="leechtype_normal")],
            [InlineKeyboardButton("Compress", callback_data="leechtype_zip"),
             InlineKeyboardButton("Extract", callback_data="leechtype_unzip")],
            [InlineKeyboardButton("UnDoubleZip", callback_data="leechtype_undzip")]
        ])
    )
except Exception as e:
    logger.error(f"Error in ask_leech_type: {e}")
    return None
```

### ✅ After (New Way)

```python
from colab_leecher.utility.ui_components import MessageTemplate, Emoji
from colab_leecher.utility.keyboard_layouts import quick_menu

# Create beautiful header with description
header = MessageTemplate.menu_header(
    "Processing Options",
    "Choose how to process your download",
    emoji=Emoji.PROCESS
)

# Add option descriptions
options = [
    ("Regular", "Download files without any processing"),
    ("Compress", "Download and compress into a ZIP archive"),
    ("Extract", "Download and extract archive contents"),
    ("UnDoubleZip", "Extract nested/double-zipped archives")
]

options_text = MessageTemplate.option_list(options, numbered=True)

# Create keyboard
keyboard = quick_menu([
    ("Regular", "leechtype_normal"),
    ("Compress", "leechtype_zip"),
    ("Extract", "leechtype_unzip"),
    ("UnDoubleZip", "leechtype_undzip")
], close=True)

try:
    leech_text = await client.send_message(
        chat_id=message.chat.id,
        text=header + options_text,
        reply_markup=keyboard
    )
except Exception as e:
    logger.error(f"Error in ask_leech_type: {e}")
    return None
```

**Benefits:**
- ✅ More informative for users
- ✅ Better visual hierarchy
- ✅ Cleaner code
- ✅ Easy to add/remove options

---

## Real Migration Example: Update status_bar Function

### ❌ OLD (`helper.py` - Line ~1397)

```python
async def status_bar(down_msg, speed, percentage, eta, done, total_size, engine,
                     use_custom_text: bool = False, task_ctx: TaskContext = None):
    # ~60 lines of manual formatting code
    try:
        if task_ctx:
            transfer = task_ctx.transfer
            started_at = task_ctx.started_at
        else:
            transfer = Transfer
            started_at = BOT.task_started_at

        elapsed_time = TimeFormatter().format_seconds(time.time() - started_at)

        size_done = SizeFormatter().format_bytes(done)
        size_total = SizeFormatter().format_bytes(total_size)

        bar_length = 12
        filled_length = int(bar_length * percentage / 100)
        bar = '█' * filled_length + '░' * (bar_length - filled_length)

        final_text = f"<b>📥 DOWNLOADING</b>\n\n"
        final_text += f"<b>🏷️ Name » </b><code>{transfer.name}</code>\n\n"
        # ... many more lines

        kb_markup = keyboard(task_ctx.task_id if task_ctx else None)

        status_msg = task_ctx.status_msg if task_ctx else down_msg

        if hasattr(status_msg, 'photo') and status_msg.photo:
            await status_msg.edit_caption(caption=final_text, reply_markup=kb_markup)
        else:
            await status_msg.edit_text(text=final_text, disable_web_page_preview=True,
                                      reply_markup=kb_markup)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error updating status bar: {e}")
```

### ✅ NEW (Much Simpler!)

```python
from colab_leecher.utility.enhanced_status import create_download_status

async def status_bar(down_msg, speed, percentage, eta, done, total_size, engine,
                     use_custom_text: bool = False, task_ctx: TaskContext = None):
    """Updated to use enhanced status display"""

    try:
        # Get task info
        if task_ctx:
            transfer = task_ctx.transfer
            task_id = task_ctx.task_id
            status_msg = task_ctx.status_msg
        else:
            transfer = Transfer
            task_id = None
            status_msg = down_msg

        # Create beautiful status message - ONE FUNCTION CALL!
        message_text, keyboard = create_download_status(
            filename=transfer.name,
            progress=percentage,
            speed=speed,
            downloaded=done,
            total_size=total_size,
            eta=eta,
            engine=engine,
            task_id=task_id,
            style="modern"  # Choose: modern, compact, or classic
        )

        # Update message
        await status_msg.edit_text(message_text, reply_markup=keyboard)

    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error updating status bar: {e}")
```

**What changed:**
- ✅ 60+ lines → 15 lines
- ✅ No manual formatting
- ✅ Automatic time/size formatting
- ✅ Better progress bar
- ✅ Cleaner, more maintainable

---

## Step-by-Step Migration Plan

### Phase 1: Add New Files (Already Done!)
- ✅ `ui_components.py`
- ✅ `keyboard_layouts.py`
- ✅ `enhanced_status.py`

### Phase 2: Update Imports

Add to `helper.py`:
```python
from colab_leecher.utility.enhanced_status import create_download_status, create_upload_status
from colab_leecher.utility.keyboard_layouts import quick_cancel, quick_menu
```

### Phase 3: Replace Functions One-by-One

1. **Start with `status_bar()` in `helper.py`**
   - Replace with new version above
   - Test with downloads

2. **Update `send_settings()` in `helper.py`**
   - Use `MenuKeyboards.settings_menu()`
   - Test settings menu

3. **Update menus in `__main__.py`**
   - Replace `ask_leech_type()`
   - Replace `ask_upload_destination()`
   - Replace `ask_filename_option()`
   - Use `MessageTemplate.menu_header()` and `quick_menu()`

4. **Update `SendLogs()` in `handler.py`**
   - Use `CompletionMessage.upload_complete()`
   - Use `CommonKeyboards.social_links()`

5. **Add error handling**
   - Use `ErrorMessage` class throughout
   - Replace manual error messages

### Phase 4: Test Everything

- [ ] Download with progress updates
- [ ] Upload with progress updates
- [ ] Settings menu
- [ ] Error messages
- [ ] Success messages
- [ ] All command menus

---

## Quick Migration Checklist

Use this checklist to migrate your code:

- [ ] Import new modules in files that need them
- [ ] Replace `status_bar()` function
- [ ] Replace keyboard creation with builders
- [ ] Replace menu messages with templates
- [ ] Replace error messages with `ErrorMessage`
- [ ] Replace success messages with `CompletionMessage`
- [ ] Test all features
- [ ] Remove old commented code
- [ ] Update any documentation

---

## Need Help?

If you're stuck during migration:

1. **Check `QUICK_EXAMPLES.py`** - Has copy-paste ready code
2. **Check `UI_COMPONENTS_GUIDE.md`** - Complete documentation
3. **Look at existing code** - All components have examples
4. **Test incrementally** - Migrate one function at a time

**Remember:** You can mix old and new code during migration. The new components are designed to work alongside your existing code!
