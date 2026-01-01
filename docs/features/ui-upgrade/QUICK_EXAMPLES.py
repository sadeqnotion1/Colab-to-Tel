"""
Quick Copy-Paste Examples for Enhanced UI Components
Ready-to-use code snippets for common scenarios
"""

# ============================================================================
# IMPORTS (Copy this section at the top of your files)
# ============================================================================

from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery
import asyncio

# UI Components
from colab_leecher.utility.ui_components import (
    Emoji, Box, ProgressBar, MessageTemplate,
    TimeFormatter, SizeFormatter
)

# Keyboards
from colab_leecher.utility.keyboard_layouts import (
    KeyboardBuilder, CommonKeyboards, MenuKeyboards,
    ProgressKeyboards, quick_menu, quick_cancel
)

# Enhanced Status
from colab_leecher.utility.enhanced_status import (
    StatusDisplay, CompletionMessage, ErrorMessage,
    InfoMessage, create_download_status, create_upload_status
)


# ============================================================================
# EXAMPLE 1: Beautiful Welcome Message
# ============================================================================

async def send_welcome_message(client: Client, message: Message):
    """Send a beautiful welcome message"""

    welcome_text = f"""
<b>{Emoji.ROCKET} Welcome to Advanced Telegram Leecher!</b>

<i>Your all-in-one download and upload solution</i>

{Box.TOP_LEFT}{Emoji.DOWNLOAD} <b>Download</b> from multiple sources
{Box.MIDDLE_LEFT}{Emoji.UPLOAD} <b>Upload</b> to Telegram/GDrive
{Box.MIDDLE_LEFT}{Emoji.COMPRESS} <b>Compress</b> and extract archives
{Box.BOTTOM_LEFT}{Emoji.ROCKET} <b>Fast</b> and reliable transfers

<b>Choose an option below to get started:</b>
"""

    keyboard = quick_menu([
        (f"{Emoji.DOWNLOAD} Download", "action_download"),
        (f"{Emoji.UPLOAD} Upload", "action_upload"),
        (f"{Emoji.PROCESS} Settings", "action_settings"),
        (f"{Emoji.INFO} Help", "action_help")
    ], close=True)

    await message.reply(welcome_text, reply_markup=keyboard)


# ============================================================================
# EXAMPLE 2: Download Command with Progress
# ============================================================================

async def download_file_example(client: Client, message: Message):
    """Complete download flow with progress updates"""

    # Extract URL from message
    try:
        url = message.text.split(maxsplit=1)[1]
    except IndexError:
        await message.reply("❌ Please provide a URL!\n\nUsage: /download <url>")
        return

    # Send initial message
    status_msg = await message.reply(
        InfoMessage.please_wait("Preparing download...")
    )

    # Simulate download (replace with actual download logic)
    filename = "example_movie.mp4"
    total_size = 1_500_000_000  # 1.5 GB
    task_id = "download_001"

    try:
        # Progress loop (0 to 100%)
        for progress in range(0, 101, 5):
            downloaded = int(total_size * (progress / 100))
            speed = 8_500_000  # 8.5 MB/s
            eta = ((100 - progress) / 100) * (total_size / speed)

            # Create beautiful status message
            msg_text, keyboard = create_download_status(
                filename=filename,
                progress=progress,
                speed=speed,
                downloaded=downloaded,
                total_size=total_size,
                eta=eta,
                engine="Aria2",
                task_id=task_id,
                style="modern"  # Try: modern, compact, or classic
            )

            # Update message
            try:
                await status_msg.edit_text(msg_text, reply_markup=keyboard)
            except Exception:
                pass  # Ignore "message not modified" errors

            await asyncio.sleep(0.5)  # Simulate download progress

        # Download complete!
        completion_msg = CompletionMessage.download_complete(
            filename=filename,
            size=total_size,
            duration=180,  # 3 minutes
            engine="Aria2"
        )

        # Add social links keyboard
        social_kb = CommonKeyboards.social_links(
            channel="@YourChannel",
            group="@YourGroup",
            github="https://github.com/yourusername/yourrepo"
        )

        await status_msg.edit_text(completion_msg, reply_markup=social_kb)

    except Exception as e:
        # Handle errors beautifully
        error_msg = ErrorMessage.download_failed(
            filename=filename,
            error=str(e),
            details="An unexpected error occurred during download"
        )
        await status_msg.edit_text(error_msg)


# ============================================================================
# EXAMPLE 3: Upload with Progress
# ============================================================================

async def upload_file_example(client: Client, message: Message, file_path: str):
    """Upload file with beautiful progress tracking"""

    import os
    filename = os.path.basename(file_path)
    total_size = os.path.getsize(file_path)
    task_id = "upload_001"

    # Initial message
    start_msg = InfoMessage.task_started("File Upload", {
        "File": filename,
        "Size": SizeFormatter.format_bytes(total_size),
        "Destination": "Telegram"
    })

    status_msg = await message.reply(start_msg)

    try:
        # Simulate upload progress
        for progress in range(0, 101, 10):
            uploaded = int(total_size * (progress / 100))
            speed = 5_000_000  # 5 MB/s
            eta = ((100 - progress) / 100) * (total_size / speed)

            msg_text, keyboard = create_upload_status(
                filename=filename,
                progress=progress,
                speed=speed,
                uploaded=uploaded,
                total_size=total_size,
                eta=eta,
                destination="Telegram",
                task_id=task_id
            )

            await status_msg.edit_text(msg_text, reply_markup=keyboard)
            await asyncio.sleep(0.5)

        # Success!
        completion_msg = CompletionMessage.upload_complete(
            files=[filename],
            total_size=total_size,
            duration=120,
            destination="Telegram"
        )

        await status_msg.edit_text(completion_msg)

    except Exception as e:
        error_msg = ErrorMessage.upload_failed(filename, str(e))
        await status_msg.edit_text(error_msg)


# ============================================================================
# EXAMPLE 4: Settings Menu
# ============================================================================

async def show_settings_menu(client: Client, message: Message):
    """Display interactive settings menu"""

    # Settings header
    header = MessageTemplate.header("Bot Settings", Emoji.PROCESS)

    # Current settings (example - replace with your actual settings)
    settings_info = {
        "Upload Mode": ("Media", "setting_upload_mode"),
        "Video Quality": ("1080p", "setting_quality"),
        "Split Size": ("2GB", "setting_split"),
        "Thumbnail": ("Enabled", "setting_thumbnail")
    }

    # Build settings display
    settings_text = header + "\n"
    for name, (value, _) in settings_info.items():
        settings_text += f"\n{Emoji.BULLET} <b>{name}:</b> <code>{value}</code>"

    settings_text += "\n\n<i>Click a button below to change:</i>"

    # Create keyboard
    keyboard = MenuKeyboards.settings_menu(
        settings_info,
        navigation=True
    )

    await message.reply(settings_text, reply_markup=keyboard)


# ============================================================================
# EXAMPLE 5: Toggle Settings
# ============================================================================

async def show_toggle_settings(client: Client, message: Message):
    """Settings with ON/OFF toggles"""

    header = MessageTemplate.menu_header(
        "Advanced Settings",
        "Enable or disable features"
    )

    toggles = {
        "Auto Upload": (True, "auto_upload"),
        "Delete After Upload": (False, "delete_after"),
        "Compress Videos": (True, "compress"),
        "Generate Thumbnails": (True, "thumbnails"),
        "Silent Mode": (False, "silent")
    }

    keyboard = MenuKeyboards.toggle_options(
        toggles,
        callback_prefix="toggle"
    )

    # Add back button
    from colab_leecher.utility.keyboard_layouts import UtilityKeyboards
    back_kb = CommonKeyboards.back_close(back_data="settings_main")
    final_kb = UtilityKeyboards.combine(keyboard, back_kb)

    await message.reply(header, reply_markup=final_kb)


# ============================================================================
# EXAMPLE 6: Service Selection Menu
# ============================================================================

async def show_service_selection(client: Client, message: Message):
    """Let user choose download service"""

    header = MessageTemplate.menu_header(
        "Select Download Service",
        "Choose how you want to download"
    )

    options = [
        ("Direct Download", "Fast and simple direct download"),
        ("Debrid Service", "Premium unlocking service for file hosts"),
        ("Torrent", "BitTorrent with DHT support"),
        ("YouTube-DL", "Download from YouTube and 1000+ sites")
    ]

    options_text = MessageTemplate.option_list(options, numbered=True)

    # Create keyboard with icons
    keyboard = quick_menu([
        (f"{Emoji.ROCKET} Direct", "service_direct"),
        (f"{Emoji.STAR} Debrid", "service_debrid"),
        (f"{Emoji.LINK} Torrent", "service_torrent"),
        (f"{Emoji.VIDEO} YouTube-DL", "service_ytdl")
    ], close=True)

    full_message = header + options_text
    await message.reply(full_message, reply_markup=keyboard)


# ============================================================================
# EXAMPLE 7: File List with Pagination
# ============================================================================

async def show_file_list(client: Client, message: Message, page: int = 1):
    """Display files with pagination"""

    # Example file list (replace with your actual files)
    all_files = [
        {"name": "movie1.mp4", "size": "1.5 GB"},
        {"name": "movie2.mp4", "size": "2.1 GB"},
        {"name": "audio.mp3", "size": "5.2 MB"},
        {"name": "document.pdf", "size": "12 MB"},
        {"name": "archive.zip", "size": "850 MB"},
        # ... more files
    ]

    files_per_page = 5
    total_pages = (len(all_files) + files_per_page - 1) // files_per_page

    start_idx = (page - 1) * files_per_page
    end_idx = min(start_idx + files_per_page, len(all_files))
    page_files = all_files[start_idx:end_idx]

    # Build message
    header = f"<b>{Emoji.FOLDER} Available Files</b>\n"
    header += f"<i>Page {page} of {total_pages}</i>\n\n"

    files_list = ""
    for i, file in enumerate(page_files, start=start_idx + 1):
        files_list += f"{i}. <code>{file['name']}</code>\n"
        files_list += f"   {Emoji.SIZE} {file['size']}\n\n"

    # Create selection keyboard
    kb = KeyboardBuilder()
    for i in range(start_idx, end_idx):
        kb.button(
            f"Download #{i+1}",
            callback_data=f"download_file:{i}"
        ).row()

    # Add pagination
    pagination_kb = CommonKeyboards.pagination(
        current_page=page,
        total_pages=total_pages,
        callback_prefix="files_page"
    )

    # Combine keyboards
    from colab_leecher.utility.keyboard_layouts import UtilityKeyboards
    final_kb = UtilityKeyboards.combine(kb.build(), pagination_kb)

    full_message = header + files_list
    await message.reply(full_message, reply_markup=final_kb)


# ============================================================================
# EXAMPLE 8: Callback Query Handler
# ============================================================================

@Client.on_callback_query()
async def handle_callback(client: Client, callback: CallbackQuery):
    """Handle button clicks"""

    data = callback.data

    # Service selection
    if data.startswith("service_"):
        service = data.split("_")[1]
        await callback.answer(f"Selected: {service}")

        # Update message
        new_text = f"{Emoji.SUCCESS} Service selected: <b>{service}</b>\n\n"
        new_text += "Please send the download URL:"

        keyboard = quick_cancel()
        await callback.message.edit_text(new_text, reply_markup=keyboard)

    # Settings toggle
    elif data.startswith("toggle_"):
        setting = data.split("_", 1)[1]
        await callback.answer(f"Toggled: {setting}")

        # Re-show settings with updated value (implement your logic)
        await show_toggle_settings(client, callback.message)

    # Cancel
    elif data.startswith("cancel"):
        await callback.answer("Cancelled!")
        await callback.message.delete()

    # Close
    elif data == "close":
        await callback.message.delete()

    # Page navigation
    elif data.startswith("files_page:"):
        page = int(data.split(":")[1])
        await show_file_list(client, callback.message, page)
        await callback.answer()


# ============================================================================
# EXAMPLE 9: Error Handling
# ============================================================================

async def safe_operation_example(client: Client, message: Message):
    """Example with proper error handling"""

    status_msg = await message.reply(
        InfoMessage.please_wait("Processing...")
    )

    try:
        # Your operation here
        result = await some_risky_operation()

        # Success message
        success_text = MessageTemplate.success_message(
            "Operation Complete",
            {
                "Status": "Success",
                "Result": str(result)
            }
        )
        await status_msg.edit_text(success_text)

    except FileNotFoundError as e:
        error_msg = ErrorMessage.task_failed(
            "File Operation",
            "File not found",
            details=str(e),
            solution="Please check the file path and try again"
        )
        await status_msg.edit_text(error_msg)

    except PermissionError as e:
        error_msg = ErrorMessage.task_failed(
            "File Operation",
            "Permission denied",
            details=str(e),
            solution="Please check file permissions"
        )
        await status_msg.edit_text(error_msg)

    except Exception as e:
        error_msg = ErrorMessage.task_failed(
            "Operation",
            "Unexpected error",
            details=str(e)
        )
        await status_msg.edit_text(error_msg)


# ============================================================================
# EXAMPLE 10: Multi-Step Wizard
# ============================================================================

class DownloadWizard:
    """Multi-step download configuration"""

    @staticmethod
    async def step1_service(message: Message):
        """Step 1: Choose service"""
        await show_service_selection(None, message)

    @staticmethod
    async def step2_quality(message: Message, service: str):
        """Step 2: Choose quality"""
        header = MessageTemplate.menu_header(
            "Select Quality",
            f"Service: {service}"
        )

        qualities = [
            ("4K Ultra HD", "quality_4k"),
            ("1080p Full HD", "quality_1080"),
            ("720p HD", "quality_720"),
            ("480p SD", "quality_480")
        ]

        keyboard = MenuKeyboards.selection_menu(
            qualities,
            selected=None,
            callback_prefix="select"
        )

        await message.reply(header, reply_markup=keyboard)

    @staticmethod
    async def step3_confirm(message: Message, service: str, quality: str):
        """Step 3: Confirm settings"""
        settings = {
            "Service": service,
            "Quality": quality,
            "Format": "MP4"
        }

        msg = MessageTemplate.card(
            "Confirm Download Settings",
            settings,
            emoji_map={
                "Service": Emoji.ROCKET,
                "Quality": Emoji.STAR,
                "Format": Emoji.VIDEO
            }
        )

        msg += "\n\n<i>Proceed with download?</i>"

        keyboard = CommonKeyboards.confirm_cancel(
            confirm_data=f"start_download:{service}:{quality}"
        )

        await message.reply(msg, reply_markup=keyboard)


# ============================================================================
# EXAMPLE 11: Processing with File Progress
# ============================================================================

async def extract_archive_example(client: Client, message: Message):
    """Extract archive with progress"""

    archive_name = "movies.zip"
    total_files = 25
    task_id = "extract_001"

    status = StatusDisplay("Extract", task_id)

    status_msg = await message.reply(
        InfoMessage.task_started("Archive Extraction", {
            "Archive": archive_name,
            "Files": f"{total_files} files"
        })
    )

    try:
        # Simulate extraction
        for i in range(1, total_files + 1):
            progress = (i / total_files) * 100
            current_file = f"movie_{i}.mp4"

            msg_text, keyboard = status.processing_status(
                filename=archive_name,
                operation="Extracting",
                progress=progress,
                current_file=current_file,
                files_done=i,
                total_files=total_files
            )

            await status_msg.edit_text(msg_text, reply_markup=keyboard)
            await asyncio.sleep(0.3)

        # Complete
        completion = CompletionMessage.task_complete(
            "Extraction Complete",
            {
                "Archive": archive_name,
                "Extracted": f"{total_files} files",
                "Time": "1m 30s"
            },
            hashtag="#EXTRACT_COMPLETE"
        )

        await status_msg.edit_text(completion)

    except Exception as e:
        error_msg = ErrorMessage.task_failed(
            "Archive Extraction",
            str(e)
        )
        await status_msg.edit_text(error_msg)


# ============================================================================
# EXAMPLE 12: Custom Branded Messages
# ============================================================================

class MyBrandedMessages:
    """Create your own branded message style"""

    LOGO = "🎬"
    BOT_NAME = "Advanced Leecher"

    @staticmethod
    def branded_header(title: str) -> str:
        """Branded header"""
        line = "━" * 20
        return f"{line}\n<b>{MyBrandedMessages.LOGO} {title}</b>\n{line}\n"

    @staticmethod
    def branded_footer() -> str:
        """Branded footer"""
        return f"\n\n<i>⚡ Powered by {MyBrandedMessages.BOT_NAME}</i>"

    @staticmethod
    def branded_message(title: str, content: str) -> str:
        """Complete branded message"""
        return (
            MyBrandedMessages.branded_header(title) +
            content +
            MyBrandedMessages.branded_footer()
        )


# Usage:
async def send_branded_message(message: Message):
    content = "Your download is ready!\n\nClick below to access your files."

    keyboard = CommonKeyboards.social_links(
        channel="@YourChannel",
        group="@YourGroup"
    )

    branded_msg = MyBrandedMessages.branded_message(
        "Download Complete",
        content
    )

    await message.reply(branded_msg, reply_markup=keyboard)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def some_risky_operation():
    """Placeholder for risky operations"""
    return "Success"


# ============================================================================
# REGISTER HANDLERS (Add to your main bot file)
# ============================================================================

def register_example_handlers(app: Client):
    """Register all example handlers"""

    @app.on_message(filters.command("start"))
    async def start_command(client, message):
        await send_welcome_message(client, message)

    @app.on_message(filters.command("download"))
    async def download_command(client, message):
        await download_file_example(client, message)

    @app.on_message(filters.command("settings"))
    async def settings_command(client, message):
        await show_settings_menu(client, message)

    @app.on_message(filters.command("files"))
    async def files_command(client, message):
        await show_file_list(client, message)


# ============================================================================
# USAGE IN YOUR BOT
# ============================================================================
"""
In your main bot file (__main__.py or similar):

from QUICK_EXAMPLES import (
    send_welcome_message,
    download_file_example,
    show_settings_menu,
    # ... import whatever you need
)

# Then use in your handlers:

@colab_bot.on_message(filters.command("start"))
async def start_handler(client, message):
    await send_welcome_message(client, message)
"""
