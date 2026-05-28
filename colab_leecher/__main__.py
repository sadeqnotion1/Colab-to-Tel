# /content/Telegram-Leecher/colab_leecher/__main__.py

from . import aliases  # registers /mirror,/leech,/ytdl,/count,/del,/stats
import logging, os, math
import asyncio
import re # Import regex module
import aiohttp # Import aiohttp
import random # Import random for thumbnail selection
import aiofiles # Import aiofiles for async file writing
from pyrogram import enums, filters, Client, ContinuePropagation
from datetime import datetime
from asyncio import sleep, get_event_loop
from colab_leecher import ConfigError, DUMP_ID, OWNER, colab_bot, ensure_runtime_config  # Absolute import
from .utility.handler import cancelTask
from .utility.variables import BOT, MSG, BotTimes, Paths, TRANSFER, TaskError, Aria2c
from .utility.task_context import TaskContext, TASK_QUEUE, create_task_context
from .utility.task_dashboard import update_summary_dashboard, force_update_summary
from .utility.task_manager import taskScheduler, task_starter
from .utility.rate_limiter import RATE_LIMITER
from .utility.message_safety import user_error, mask_secret
from .utility.reply_state import (
    clear_password_reply_waiting,
    get_password_reply_waiting,
)
from .utility.helper import (
    isLink, setThumbnail, message_deleter, send_settings,
    clean_filename, extract_filename_from_url, apply_dot_style, sizeUnit # Import sizeUnit if needed
)
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
# Example import line in __main__.py
from .utility.helper import (
    isLink, setThumbnail, message_deleter, send_settings,
    clean_filename, extract_filename_from_url, apply_dot_style, sizeUnit,
    keyboard, fetch_links_from_url, fetch_filenames_from_url,
    is_instagram, is_nzbcloud, is_m3u8_url, is_mindvalley_url
)
# Enhanced UI Components
from .utility.ui_components import MessageTemplate, Emoji
from .utility.keyboard_layouts import quick_menu
from .utility.ui_copy import (
    build_cannot_start_task_message,
    build_cancel_task_button_label,
    build_directory_path_prompt,
    build_extract_archive_prompt,
    build_filename_option_prompt,
    build_help_text,
    build_invalid_provider_configuration_error,
    build_link_prompt,
    build_mindvalley_prompt,
    build_manual_filenames_prompt,
    build_nzb_prompt,
    build_pending_task_warning,
    build_raw_gist_warning,
    build_start_welcome_text,
    build_tiktok_bulk_gist_prompt,
    build_upload_destination_prompt,
    build_usenet_not_configured_error,
)
from .downlader.mindvalley import MindvalleyDownloader
from .uploader.telegram import upload_file
from .utility.handler import SendLogs


logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger(__name__)

# Custom filter to exclude command messages (messages starting with /)
def not_command(_, __, message):
    return not (message.text and message.text.startswith('/'))

not_command_filter = filters.create(not_command)

log.info(f"--> MERGED V1: colab_bot instance used in __main__.py: ID = {id(colab_bot)}")
DEBUG_MESSAGE_PREVIEW = os.getenv("DEBUG_MESSAGE_PREVIEW", "").strip().lower() in {"1", "true", "yes", "on"}


async def _reply_with_generic_error(message: Message, action: str, *, quote: bool = False) -> None:
    """Send sanitized error feedback to users without leaking exception details."""
    try:
        await message.reply_text(user_error(action), quote=quote)
    except Exception as reply_err:
        log.debug(f"Failed to send generic error reply: {reply_err}")


async def _send_generic_error(client: Client, chat_id: int, action: str) -> None:
    """Send sanitized error feedback to a chat without leaking internals."""
    try:
        await client.send_message(chat_id, user_error(action))
    except Exception as send_err:
        log.debug(f"Failed to send generic error message to chat {chat_id}: {send_err}")

source_waiting_prompts = {}
source_waiting_lock = asyncio.Lock()
setup_sessions = {}
setup_sessions_lock = asyncio.Lock()
mindvalley_waiting_users = set()
mindvalley_waiting_lock = asyncio.Lock()
nzb_waiting_users = set()
nzb_waiting_lock = asyncio.Lock()

# Flag to ensure background tasks start only once
_background_tasks_started = False

# NEW: Per-user task registry for parallel task support
# Maps user_id -> TaskContext for pending tasks (waiting for URLs)
user_tasks = {}  # Track when waiting for extract path input
user_tasks_lock = asyncio.Lock()  # Thread-safety for concurrent access

# Per-user extract prompt state to avoid cross-user collisions in /extract setup.
# Maps user_id -> prompt_message_id.
extract_waiting_prompts = {}
extract_waiting_lock = asyncio.Lock()


def _clone_setup_session(state: dict | None) -> dict | None:
    """Return a defensive copy of per-user setup session state."""
    if not state:
        return None
    return {
        "mode": state.get("mode"),
        "source_links": list(state.get("source_links", [])),
        "service_type": state.get("service_type"),
        "filenames": list(state.get("filenames", [])),
        "custom_name": state.get("custom_name", ""),
        "zip_pswd": state.get("zip_pswd", ""),
        "unzip_pswd": state.get("unzip_pswd", ""),
        "archive_format": state.get("archive_format", "7z"),
    }


async def _get_setup_session(user_id: int) -> dict | None:
    """Fetch per-user setup session state."""
    async with setup_sessions_lock:
        return _clone_setup_session(setup_sessions.get(user_id))


async def _update_setup_session(user_id: int, **updates) -> dict:
    """Create/update per-user setup session state."""
    async with setup_sessions_lock:
        current = setup_sessions.get(user_id, {})
        merged = {
            "mode": current.get("mode"),
            "source_links": list(current.get("source_links", [])),
            "service_type": current.get("service_type"),
            "filenames": list(current.get("filenames", [])),
            "custom_name": current.get("custom_name", ""),
            "zip_pswd": current.get("zip_pswd", ""),
            "unzip_pswd": current.get("unzip_pswd", ""),
            "archive_format": current.get("archive_format", "7z"),
        }
        for key, value in updates.items():
            if key in {"source_links", "filenames"}:
                merged[key] = list(value or [])
            else:
                merged[key] = value
        setup_sessions[user_id] = merged
        return _clone_setup_session(merged) or {}


async def _clear_setup_session(user_id: int) -> dict | None:
    """Clear per-user setup session state."""
    async with setup_sessions_lock:
        state = setup_sessions.pop(user_id, None)
    return _clone_setup_session(state)


def _build_task_paths(task_ctx: TaskContext):
    """Build a Paths-like object expected by legacy scheduler internals."""
    return type('obj', (object,), {
        'down_path': task_ctx.down_path,
        'work_path': task_ctx.work_path,
        'WORK_PATH': task_ctx.work_path,
        'temp_zpath': f"{task_ctx.work_path}/temp_zip",
        'temp_unzip': f"{task_ctx.work_path}/temp_unzip",
        'temp_unzip_path': f"{task_ctx.work_path}/temp_unzip",
        'temp_dirleech_path': f"{task_ctx.work_path}/dir_leech_temp",
        'temp_files_dir': f"{task_ctx.work_path}/leech_temp",
        'thumbnail_ytdl': f"{task_ctx.work_path}/ytdl_thumbnails",
        'HERO_IMAGE': task_ctx.hero_image,
        'THMB_PATH': Paths.THMB_PATH,
        'DEFAULT_HERO': Paths.DEFAULT_HERO,
        'VIDEO_FRAME': f"{task_ctx.work_path}/video_frame.jpg"
    })()


def _build_task_bot(
    task_ctx: TaskContext,
    source_links: list[str],
    filenames: list[str],
    custom_name: str,
    zip_pswd: str,
    unzip_pswd: str,
    archive_format: str,
):
    """Build a BOT-like object expected by taskScheduler(task_ctx)."""
    is_ytdl = task_ctx.service_type == "ytdl"
    return type('obj', (object,), {
        'Mode': type('obj', (object,), {
            'mode': task_ctx.mode,
            'ytdl': is_ytdl,
            'type': task_ctx.mode_type
        })(),
        'Options': type('obj', (object,), {
            'service_type': task_ctx.service_type,
            'filenames': list(filenames or []),
            'custom_name': custom_name or '',
            'zip_pswd': zip_pswd or '',
            'unzip_pswd': unzip_pswd or '',
            'archive_format': archive_format or '7z'
        })(),
        'SOURCE': list(source_links or []),
        'Setting': BOT.Setting
    })()


def _prepare_task_context(
    task_ctx: TaskContext,
    source_links: list[str],
    filenames: list[str] | None = None,
    custom_name: str = "",
    zip_pswd: str = "",
    unzip_pswd: str = "",
    archive_format: str = "7z",
) -> None:
    """Populate task_ctx with compatibility objects for taskScheduler(task_ctx)."""
    task_ctx.source_urls = list(source_links or [])
    task_ctx.filenames = list(filenames or [])
    task_ctx.bot = _build_task_bot(
        task_ctx=task_ctx,
        source_links=task_ctx.source_urls,
        filenames=task_ctx.filenames,
        custom_name=custom_name,
        zip_pswd=zip_pswd,
        unzip_pswd=unzip_pswd,
        archive_format=archive_format,
    )
    task_ctx.paths = _build_task_paths(task_ctx)
    task_ctx.msg = type('obj', (object,), {
        'status_msg': task_ctx.status_msg,
        'sent_msg': task_ctx.sent_msg
    })()


def _attach_task_exception_handler(async_task: asyncio.Task, task_ctx: TaskContext) -> None:
    """Attach uniform exception logging for launched background tasks."""
    def _handle_task_exception(task):
        try:
            task.result()
        except asyncio.CancelledError:
            log.info(f"Task {task_ctx.get_short_id()} was cancelled")
        except Exception as e:
            log.exception(f"Unhandled exception in background task {task_ctx.get_short_id()}: {e}")

    async_task.add_done_callback(_handle_task_exception)


def _extract_user_id(message: Message) -> int:
    """Return a stable user key for extract waiting state."""
    return message.from_user.id if message.from_user else message.chat.id


async def _set_extract_waiting(user_id: int, prompt_message_id: int | None) -> None:
    """Mark user as waiting for /extract path input and store prompt message id."""
    async with extract_waiting_lock:
        extract_waiting_prompts[user_id] = prompt_message_id


async def _is_extract_waiting(user_id: int) -> bool:
    """Check whether a user is currently expected to send /extract path input."""
    async with extract_waiting_lock:
        return user_id in extract_waiting_prompts


async def _clear_extract_waiting(client: Client, chat_id: int, user_id: int) -> None:
    """Clear extract-waiting state for one user and delete the pending prompt if present."""
    prompt_message_id = None
    async with extract_waiting_lock:
        prompt_message_id = extract_waiting_prompts.pop(user_id, None)

    if prompt_message_id:
        try:
            prompt_msg = await client.get_messages(chat_id, prompt_message_id)
            if prompt_msg:
                await prompt_msg.delete()
        except Exception as delete_prompt_err:
            log.debug(f"Could not delete extract prompt message {prompt_message_id}: {delete_prompt_err}")


async def _set_source_waiting(user_id: int, chat_id: int, prompt_message_id: int | None) -> None:
    """Store or clear per-user source-input prompt state."""
    async with source_waiting_lock:
        if prompt_message_id:
            source_waiting_prompts[user_id] = {
                "chat_id": chat_id,
                "prompt_message_id": prompt_message_id,
            }
        else:
            source_waiting_prompts.pop(user_id, None)


async def _clear_source_waiting(client: Client | None, user_id: int) -> None:
    """Clear per-user source-input prompt state and delete its prompt message."""
    state = None
    async with source_waiting_lock:
        state = source_waiting_prompts.pop(user_id, None)

    if not state or not client:
        return

    chat_id = state.get("chat_id")
    prompt_message_id = state.get("prompt_message_id")
    if not chat_id or not prompt_message_id:
        return

    try:
        prompt_msg = await client.get_messages(chat_id, prompt_message_id)
        if prompt_msg:
            await prompt_msg.delete()
    except Exception as delete_prompt_err:
        log.debug(f"Could not delete source prompt message {prompt_message_id}: {delete_prompt_err}")


async def _set_mindvalley_waiting(user_id: int, waiting: bool) -> None:
    """Set per-user waiting state for Mindvalley URL input."""
    async with mindvalley_waiting_lock:
        if waiting:
            mindvalley_waiting_users.add(user_id)
        else:
            mindvalley_waiting_users.discard(user_id)


async def _is_mindvalley_waiting(user_id: int) -> bool:
    """Check whether user is currently expected to provide Mindvalley URLs."""
    async with mindvalley_waiting_lock:
        return user_id in mindvalley_waiting_users


async def _set_nzb_waiting(user_id: int, waiting: bool) -> None:
    """Set per-user waiting state for NZB URL/file input."""
    async with nzb_waiting_lock:
        if waiting:
            nzb_waiting_users.add(user_id)
        else:
            nzb_waiting_users.discard(user_id)


async def _is_nzb_waiting(user_id: int) -> bool:
    """Check whether user is currently expected to provide NZB URL/file."""
    async with nzb_waiting_lock:
        return user_id in nzb_waiting_users

# Per-user manual filename-reply state to avoid global prompt collisions.
# Maps user_id -> {"prompt_message_id", "service_type", "expected_count", "source_links"}.
filename_reply_prompts = {}
filename_reply_lock = asyncio.Lock()
settings_reply_prompts = {}
settings_reply_lock = asyncio.Lock()


def _normalize_filename_service(service_type: str | None) -> str:
    """Normalize service name from callback payload to canonical internal value."""
    service_key = (service_type or "").strip().lower()
    if service_key == "debrid":
        return "Debrid"
    if service_key == "nzbcloud":
        return "nzbcloud"
    if service_key == "bitso":
        return "bitso"
    return service_key


def _filename_mode_label(service_type: str) -> str:
    """Return user-facing label for filename reply logs/messages."""
    normalized = _normalize_filename_service(service_type)
    if normalized == "Debrid":
        return "DebridLeech"
    if normalized == "nzbcloud":
        return "NZBCloud"
    if normalized == "bitso":
        return "bitso"
    return normalized or "unknown"


async def _set_filename_reply_waiting(
    user_id: int,
    prompt_message_id: int,
    service_type: str,
    source_links: list[str],
) -> None:
    """Store per-user filename-reply prompt context."""
    async with filename_reply_lock:
        filename_reply_prompts[user_id] = {
            "prompt_message_id": prompt_message_id,
            "service_type": _normalize_filename_service(service_type),
            "expected_count": len(source_links),
            "source_links": list(source_links),
        }


async def _get_filename_reply_waiting(user_id: int) -> dict | None:
    """Get per-user filename-reply context."""
    async with filename_reply_lock:
        state = filename_reply_prompts.get(user_id)
        if not state:
            return None
        return {
            "prompt_message_id": state.get("prompt_message_id"),
            "service_type": state.get("service_type"),
            "expected_count": state.get("expected_count", 0),
            "source_links": list(state.get("source_links", [])),
        }


async def _is_filename_reply_waiting(user_id: int) -> bool:
    """Check whether user is currently expected to reply with filenames."""
    async with filename_reply_lock:
        return user_id in filename_reply_prompts


async def _clear_filename_reply_waiting(client: Client | None, chat_id: int | None, user_id: int) -> None:
    """Clear per-user filename-reply context and delete prompt message if available."""
    state = None
    async with filename_reply_lock:
        state = filename_reply_prompts.pop(user_id, None)

    if not state:
        return

    prompt_message_id = state.get("prompt_message_id")
    if client and chat_id and prompt_message_id:
        try:
            prompt_msg = await client.get_messages(chat_id, prompt_message_id)
            if prompt_msg:
                await prompt_msg.delete()
        except Exception as delete_prompt_err:
            log.debug(f"Could not delete filename prompt message {prompt_message_id}: {delete_prompt_err}")


async def _clear_password_reply_prompt(client: Client | None, user_id: int) -> None:
    """Clear per-user password reply context and delete prompt message if available."""
    state = await clear_password_reply_waiting(user_id)
    if not state or not client:
        return

    chat_id = state.get("chat_id")
    prompt_message_id = state.get("prompt_message_id")
    if not chat_id or not prompt_message_id:
        return

    try:
        prompt_msg = await client.get_messages(chat_id, prompt_message_id)
        if prompt_msg:
            await prompt_msg.delete()
    except Exception as delete_prompt_err:
        log.debug(f"Could not delete password prompt message {prompt_message_id}: {delete_prompt_err}")


async def _set_settings_reply_waiting(
    user_id: int,
    prompt_message_id: int,
    setting_key: str,
    settings_message_id: int | None,
) -> None:
    """Store per-user settings-reply prompt context."""
    async with settings_reply_lock:
        settings_reply_prompts[user_id] = {
            "prompt_message_id": prompt_message_id,
            "setting_key": setting_key,
            "settings_message_id": settings_message_id,
        }


async def _get_settings_reply_waiting(user_id: int) -> dict | None:
    """Get per-user settings-reply context."""
    async with settings_reply_lock:
        state = settings_reply_prompts.get(user_id)
        if not state:
            return None
        return {
            "prompt_message_id": state.get("prompt_message_id"),
            "setting_key": state.get("setting_key"),
            "settings_message_id": state.get("settings_message_id"),
        }


async def _clear_settings_reply_waiting(client: Client | None, chat_id: int | None, user_id: int) -> None:
    """Clear per-user settings-reply context and delete prompt message if available."""
    state = None
    async with settings_reply_lock:
        state = settings_reply_prompts.pop(user_id, None)

    if not state:
        return

    prompt_message_id = state.get("prompt_message_id")
    if client and chat_id and prompt_message_id:
        try:
            prompt_msg = await client.get_messages(chat_id, prompt_message_id)
            if prompt_msg:
                await prompt_msg.delete()
        except Exception as delete_prompt_err:
            log.debug(f"Could not delete settings prompt message {prompt_message_id}: {delete_prompt_err}")

# --- Helper function to ask for leech type (normal/zip/unzip) ---
async def ask_leech_type(client, chat_id, mode_name, reply_to_message_id=None):
    log.info(f"Asking leech type (Mode: {mode_name}) for chat {chat_id}")

    # 🎨 Beautiful header with description
    header = MessageTemplate.menu_header(
        "Select Processing Type",
        "Choose how you want to process your download",
        emoji=Emoji.PROCESS
    )

    # 📝 Option descriptions
    options = [
        ("Regular", "Normal file upload without processing"),
        ("Compress", "Compress files into a ZIP archive before upload"),
        ("Extract", "Extract archive contents before upload"),
        ("UnDoubleZip", "Extract nested archives, then compress")
    ]

    options_text = MessageTemplate.option_list(options, numbered=True)

    # ⌨️ Beautiful keyboard
    keyboard = quick_menu([
        (f"{Emoji.DOCUMENT} Regular", "leechtype_normal"),
        (f"{Emoji.COMPRESS} Compress", "leechtype_zip"),
        (f"{Emoji.EXTRACT} Extract", "leechtype_unzip"),
        (f"{Emoji.ARCHIVE} UnDoubleZip", "leechtype_undzip")
    ], close=False)

    # Add cancel button manually
    from pyrogram.types import InlineKeyboardButton
    keyboard.inline_keyboard.append([
        InlineKeyboardButton(f"{Emoji.ERROR} Cancel", callback_data="cancel")
    ])

    text = header + options_text

    try:
        await client.send_message(chat_id, text, reply_markup=keyboard)
    except Exception as e:
        log.error(f"Failed send leech type prompt: {e}", exc_info=True)

# --- Helper function to ask for filename option (Debrid/bitso) ---
async def ask_filename_option(client, chat_id, service_name):
    log.info(f"Asking filename option for {service_name}")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Extract from URLs", callback_data=f'fn_{service_name.lower()}_extract')],
        [InlineKeyboardButton("Enter Names Manually", callback_data=f'fn_{service_name.lower()}_manual')],
        [InlineKeyboardButton("Cancel", callback_data='cancel')]
    ])
    await client.send_message(
        chat_id,
        build_filename_option_prompt(service_name),
        parse_mode=enums.ParseMode.HTML,
        reply_markup=keyboard,
    )

# --- Helper function to ask for manual filenames ---
async def ask_manual_filenames(client, chat_id, service_name, count, user_id=None, source_links=None):
    log.info(f"Asking for {count} manual filenames for {service_name}")
    prompt_msg = await client.send_message(
        chat_id,
        build_manual_filenames_prompt(service_name, count),
        parse_mode=enums.ParseMode.HTML,
    )
    await _set_filename_reply_waiting(
        user_id=user_id if user_id is not None else chat_id,
        prompt_message_id=prompt_msg.id,
        service_type=service_name,
        source_links=list(source_links or []),
    )

# --- Helper function to ask for upload destination (Google Drive or Local Mirror) ---
async def ask_upload_destination(client, chat_id):
    log.info(f"Asking upload destination for chat {chat_id}")
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Google Drive", callback_data="destination_gdrive")],
        [InlineKeyboardButton("Local Mirror (Colab)", callback_data="destination_mirror")],
        [InlineKeyboardButton("Cancel", callback_data="cancel")]
    ])
    text = build_upload_destination_prompt()
    try:
        await client.send_message(
            chat_id,
            text,
            parse_mode=enums.ParseMode.HTML,
            reply_markup=keyboard,
        )
    except Exception as e:
        log.error(f"Failed to send upload destination prompt: {e}", exc_info=True)

# --- Periodic Cleanup Functions ---
async def periodic_cleanup_task():
    """
    Background task to periodically clean up old completed tasks.
    Runs every hour to prevent memory leaks.
    """
    while True:
        try:
            await asyncio.sleep(3600)  # Every 1 hour

            log.info("Running periodic cleanup of old completed tasks...")
            await TASK_QUEUE.clear_completed_tasks(max_age_hours=2)

            # Also cleanup old workspace directories
            await cleanup_old_workspaces()

            log.info("Periodic cleanup completed")
        except Exception as e:
            log.error(f"Error in periodic cleanup: {e}")


async def cleanup_old_workspaces():
    """
    Clean up workspace directories older than 24 hours.
    Handles case where tasks crashed without cleanup.
    Now checks active tasks to prevent race conditions.
    """
    import shutil
    import time
    from .utility.variables import Paths

    try:
        work_base = Paths.WORK_PATH
        if not os.path.exists(work_base):
            return

        # Get active workspaces to avoid deleting running tasks
        active_tasks = await TASK_QUEUE.get_all_tasks()
        active_paths = {ctx.work_path for ctx in active_tasks.values()}
        
        now = time.time()
        cleaned_count = 0

        for item in os.listdir(work_base):
            item_path = os.path.join(work_base, item)

            # Skip if not a directory
            if not os.path.isdir(item_path):
                continue
                
            # SAFETY CHECK: Skip if currently active
            if item_path in active_paths:
                continue

            # Check if directory is older than 24 hours
            try:
                mtime = os.path.getmtime(item_path)
                age_hours = (now - mtime) / 3600

                if age_hours > 24:
                    log.info(f"Removing old workspace (age: {age_hours:.1f}h): {item_path}")
                    shutil.rmtree(item_path, ignore_errors=True)
                    cleaned_count += 1
            except Exception as e:
                log.warning(f"Could not check/remove {item_path}: {e}")

        if cleaned_count > 0:
            log.info(f"Cleaned up {cleaned_count} old workspace directories")

    except Exception as e:
        log.error(f"Error cleaning old workspaces: {e}")


# --- Parallel Task Runner ---
from .utility.logger import request_id, timed_operation, get_logger
slog = get_logger(__name__)

async def _execute_tiktok_bulk(client, message, task_ctx):
    """Internal execution logic for TikTok Bulk download (parent and workers)"""
    from colab_leecher.downlader.tiktok_bulk import TikTokBulkDownloader
    from colab_leecher.utility.handler import Leech, SendLogs
    from colab_leecher.utility.enhanced_status import CompletionMessage, StatusDisplay
    from colab_leecher.utility.ui_components import Emoji, Box
    from datetime import datetime

    # Initialize downloader
    downloader = TikTokBulkDownloader(client, message, task_ctx)

    # Helper function to safely update status message (text or photo caption)
    async def _safe_edit(text: str):
        try:
            if not task_ctx.status_msg:
                return
            if hasattr(task_ctx.status_msg, 'photo') and task_ctx.status_msg.photo:
                await task_ctx.status_msg.edit_caption(
                    caption=text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=keyboard(task_ctx.task_id)
                )
            else:
                await task_ctx.status_msg.edit_text(
                    text=text,
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=keyboard(task_ctx.task_id),
                    disable_web_page_preview=True
                )
        except Exception as edit_err:
            if "message is not modified" not in str(edit_err).lower():
                log.debug(f"Safe edit failed: {edit_err}")

    try:
        # Get Gist URL or pre-split chunk
        metadata = getattr(task_ctx, 'metadata', {})
        chunk = metadata.get('tiktok_chunk')
        gist_url = message.text.strip() if message.text else ""
        
        # Determine if this is a sub-task (worker)
        is_subtask = bool(chunk)
        urls = chunk if is_subtask else []
        success = True  # Default to True for subtasks (urls already provided)

        # Initialize dump channel message if not a subtask
        if not is_subtask and DUMP_ID:
            try:
                from colab_leecher.utility.ui_copy import get_src_text
                
                src_link = gist_url
                task_ctx.messages.src_link = src_link
                src_text = get_src_text(src_link)
                
                task_ctx.sent_msg = await colab_bot.send_message(
                    chat_id=DUMP_ID,
                    text=src_text[0],
                    disable_web_page_preview=True
                )
                log.info(f"Initialized dump channel message for TikTok Bulk: {task_ctx.get_short_id()}")
            except Exception as dump_err:
                log.error(f"Failed to initialize dump channel for TikTok Bulk: {dump_err}")

        # Get thumbnail path
        if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
            thumb_path = Paths.THMB_PATH
        elif os.path.exists(Paths.DEFAULT_HERO):
            thumb_path = Paths.DEFAULT_HERO
        else:
            thumb_path = None

        # If it's a sub-task or doesn't have a status message yet, create one
        if not task_ctx.status_msg:
            # Create status message
            status_text = f"{Emoji.LOADING} <b>Initializing TikTok Bulk...</b>"
            if is_subtask:
                status_text = f"{Emoji.LOADING} <b>Initializing TikTok Worker...</b>"

            try:
                if thumb_path:
                    task_ctx.status_msg = await client.send_photo(
                        chat_id=message.chat.id,
                        photo=thumb_path,
                        caption=status_text,
                        reply_markup=keyboard(task_ctx.task_id)
                    )
                else:
                    task_ctx.status_msg = await client.send_message(
                        chat_id=message.chat.id,
                        text=status_text,
                        reply_markup=keyboard(task_ctx.task_id)
                    )
            except Exception as msg_err:
                log.error(f"Failed to create status message: {msg_err}")
                # Fallback: if send_photo fails, try send_message
                if thumb_path:
                    try:
                        task_ctx.status_msg = await client.send_message(
                            chat_id=message.chat.id,
                            text=status_text,
                            reply_markup=keyboard(task_ctx.task_id)
                        )
                    except: pass

            if not is_subtask:
                if not gist_url:
                    await _safe_edit(f"{Emoji.ERROR} Error: No Gist URL provided.")
                    return

                success, urls = await downloader.fetch_gist_urls(gist_url)
            if not success or not urls:
                await _safe_edit(
                    f"<b>{Emoji.ERROR} TikTok Bulk Download Failed</b>\n\n"
                    "Could not fetch TikTok URLs from the gist."
                )
                return

            # === PARALLEL SPLITTING LOGIC ===
            worker_limit = TASK_QUEUE.get_worker_limit()
            if not is_subtask and len(urls) >= 30 and worker_limit > 1:
                num_workers = min(worker_limit, math.ceil(len(urls) / 20))
                avg = len(urls) // num_workers
                rem = len(urls) % num_workers
                chunks = []
                start = 0
                for i in range(num_workers):
                    end = start + avg + (1 if i < rem else 0)
                    chunks.append(urls[start:end])
                    start = end
                
                log.info(f"Splitting TikTok Bulk ({len(urls)} URLs) into {num_workers} parallel workers")
                await _safe_edit(f"{Emoji.ROCKET} <b>Turbo Mode:</b> Splitting work into {num_workers} parallel workers...")
                await asyncio.sleep(1.5)
                
                worker_tasks = []
                sub_contexts = []
                for i, chunk_urls in enumerate(chunks):
                    sub_ctx = create_task_context(message.from_user.id, message.chat.id, mode="leech")
                    sub_ctx.service_type = "tiktokbulk"
                    sub_ctx.metadata['tiktok_chunk'] = chunk_urls
                    sub_ctx.messages.download_name = f"{task_ctx.messages.download_name or 'TikTok'}_Worker{i+1}"
                    sub_contexts.append(sub_ctx)
                    
                    worker_task = TASK_QUEUE.create_background_task(
                        run_parallel_task(client, message, sub_ctx),
                        name=f"tiktok-worker-{sub_ctx.get_short_id()}"
                    )
                    worker_tasks.append(worker_task)
                
                await _safe_edit(f"{Emoji.SUCCESS} <b>Turbo Mode Active:</b> Running {num_workers} parallel workers. Tracking progress in dashboard.")
                
                # Wait for all workers to complete
                await asyncio.gather(*worker_tasks)
                
                # Consolidate results
                total_success = 0
                total_failed = 0
                for s_ctx in sub_contexts:
                    total_success += s_ctx.metadata.get('success_count', 0)
                    total_failed += s_ctx.metadata.get('failed_count', 0)
                    # Merge transfer stats for SendLogs
                    task_ctx.transfer.sent_file.extend(s_ctx.transfer.sent_file)
                    task_ctx.transfer.sent_file_names.extend(s_ctx.transfer.sent_file_names)
                    if isinstance(s_ctx.transfer.up_bytes, list):
                        if isinstance(task_ctx.transfer.up_bytes, list):
                            task_ctx.transfer.up_bytes.extend(s_ctx.transfer.up_bytes)
                        else:
                            task_ctx.transfer.up_bytes = [task_ctx.transfer.up_bytes] + s_ctx.transfer.up_bytes
                    else:
                        if isinstance(task_ctx.transfer.up_bytes, list):
                            task_ctx.transfer.up_bytes.append(s_ctx.transfer.up_bytes)
                        else:
                            task_ctx.transfer.up_bytes += s_ctx.transfer.up_bytes

                report = CompletionMessage.task_complete(
                    "TikTok Bulk Complete",
                    {
                        "Total URLs": str(len(urls)),
                        "Success": str(total_success),
                        "Failed": str(total_failed),
                        "Workers": str(num_workers)
                    },
                    hashtag="#TIKTOK_BULK"
                )
                await _safe_edit(report)
                
                # Call SendLogs for final summary (bot + dump channel)
                await SendLogs(is_leech=True, task_ctx=task_ctx)
                return

        # Main Download Loop
        TARGET_BATCH_SIZE = 500 * 1024 * 1024 
        total_urls = len(urls)
        current_urls = urls
        part_num = 1
        all_successful = 0
        all_failed = 0

        while current_urls:
            if task_ctx.is_cancelled or (task_ctx.error and task_ctx.error.state):
                log.info(f"TikTok bulk: task cancelled, stopping at part {part_num}")
                break

            import shutil as _shutil
            if os.path.exists(downloader.download_dir):
                _shutil.rmtree(downloader.download_dir)
            os.makedirs(downloader.download_dir, exist_ok=True)

            status_text = (
                f"<b>{Emoji.DOWNLOAD} Downloading TikTok - Batch {part_num}</b>\n"
                f"{Box.TOP_LEFT}{Emoji.SIZE} <b>Target:</b> <code>{sizeUnit(TARGET_BATCH_SIZE)}</code>\n"
                f"{Box.BOTTOM_LEFT}{Emoji.INFO} <b>Remaining:</b> <code>{len(current_urls)}</code> URLs"
            )
            await _safe_edit(status_text)

            download_success, summary, current_urls = await downloader.download_bulk(current_urls, size_limit=TARGET_BATCH_SIZE)

            if task_ctx.is_cancelled or (task_ctx.error and task_ctx.error.state):
                log.info(f"TikTok bulk: task cancelled after download of part {part_num}, stopping")
                break

            if not download_success:
                await _safe_edit(f"<b>{Emoji.ERROR} Batch Failed (Part {part_num})</b>\n\n{summary}\n\nSkipping...")
                part_num += 1
                continue

            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            zip_name = f"TikTok_Bulk_{timestamp}_Batch{part_num}"
            task_ctx.messages.download_name = zip_name
            task_ctx.messages.src_link = gist_url if not is_subtask else "TikTok Sub-task"

            zip_success, zip_path = await downloader.create_zip_archive(zip_name)
            
            # Check for ZIP existence (handle .001 split suffix)
            if zip_success and zip_path and not os.path.exists(zip_path):
                if os.path.exists(zip_path + ".001"):
                    zip_path = zip_path + ".001"
                    log.info(f"Using split volume for upload: {zip_path}")
                else:
                    log.warning(f"ZIP path reported by downloader doesn't exist: {zip_path}")

            if not zip_success or not zip_path or not os.path.exists(zip_path):
                await _safe_edit(f"<b>{Emoji.ERROR} ZIP Creation Failed (Batch {part_num})</b>")
                part_num += 1
                continue

            user_summary = downloader.get_batch_user_summary()
            zip_size = os.path.getsize(zip_path)
            status_text = (
                f"<b>{Emoji.UPLOAD} Uploading Batch {part_num}</b>\n"
                f"{Box.TOP_LEFT}{Emoji.ARCHIVE} <b>ZIP:</b> <code>{zip_name}</code>\n"
                f"{Box.BOTTOM_LEFT}{Emoji.INFO} <b>Size:</b> <code>{sizeUnit(zip_size)}</code>"
            )
            await _safe_edit(status_text)

            await Leech(path=zip_path, remove_source=False, task_ctx=task_ctx)
            all_successful = len(downloader.successful_downloads)
            all_failed = len(downloader.failed_downloads)
            part_num += 1

        # Final Summary
        if is_subtask:
            # Subtasks store results and finish silently
            task_ctx.metadata['success_count'] = all_successful
            task_ctx.metadata['failed_count'] = all_failed
            log.info(f"Subtask {task_ctx.get_short_id()} finished. S:{all_successful} F:{all_failed}")
            return
        else:
            # Single non-turbo task completion
            report = CompletionMessage.task_complete(
                "TikTok Bulk Complete",
                {
                    "Total URLs": str(total_urls),
                    "Success": str(all_successful),
                    "Failed": str(all_failed)
                },
                hashtag="#TIKTOK_BULK"
            )
            await _safe_edit(report)
            
            # Call SendLogs for final summary (bot + dump channel)
            await SendLogs(is_leech=True, task_ctx=task_ctx)

        # Upload failed log if any
        if all_failed and not is_subtask:
            failed_log = downloader.get_failed_urls_log()
            if failed_log:
                log_path = os.path.join(downloader.download_dir, "failed_urls.txt")
                with open(log_path, "w", encoding="utf-8") as f: f.write(failed_log)
                await client.send_document(chat_id=message.chat.id, document=log_path, 
                                        caption=f"❌ Failed URLs Log [{task_ctx.get_short_id()}]")

    except Exception as e:
        log.exception(f"Critical error in _execute_tiktok_bulk: {e}")
        await _safe_edit(f"{Emoji.ERROR} <b>Critical Error:</b> {str(e)[:100]}")

@timed_operation("parallel_task")
async def run_parallel_task(client, message, task_ctx, skip_registration=False):
    """
    Run a download/upload task in parallel mode.

    This function wraps taskScheduler() or _execute_tiktok_bulk() to enable parallel execution.
    """
    # master-level addition: Set request context for structured logging
    request_id.set(f"task-{task_ctx.get_short_id()}")

    task_id_str = f"[{task_ctx.get_short_id()}]"
    slog.info(f"Starting parallel task", user_id=message.from_user.id, task_id=task_ctx.task_id)

    try:
        # Mark task as started
        task_ctx.mark_started()

        # ... setup aliases ...

        # Register in global task queue (unless already registered)
        if not skip_registration:
            await TASK_QUEUE.add_task(task_ctx)
            slog.info(f"Task registered in TASK_QUEUE", active_count=TASK_QUEUE.get_task_count())
        else:
            slog.info(f"Task already registered (skip_registration=True)", active_count=TASK_QUEUE.get_task_count())

        # ===== NEW: WAIT FOR WORKER SLOT (CONCURRENCY LIMIT) =====
        # This enforces the 3-worker (pure tiktok) or 2-worker (mixed) limit
        await TASK_QUEUE.acquire_worker_slot(task_ctx.task_id)

        try:
            # Route to specialized worker or generic scheduler
            if task_ctx.service_type == "tiktokbulk":
                slog.info(f"Calling _execute_tiktok_bulk")
                await _execute_tiktok_bulk(client, message, task_ctx)
            else:
                # Run the task via taskScheduler (already supports task_ctx)
                slog.info(f"Calling taskScheduler")
                await taskScheduler(task_ctx)
                slog.info(f"taskScheduler completed")
        finally:
            # Always release the worker slot when done
            await TASK_QUEUE.release_worker_slot(task_ctx.task_id)

    except asyncio.CancelledError:
        slog.warning(f"Task was cancelled by user")
        task_ctx.error.set_error("Task cancelled by user")
        # ... notify user ...
        raise

    except Exception as e:
        slog.error(f"Task failed with critical exception", error=str(e))
        task_ctx.error.set_error(str(e))
        # ... notify user ...

    finally:
        # ... cleanup logic ...
        slog.info(f"Task execution finished", status="cleanup")

        # ===== NEW: CLEANUP TASK WORKSPACE =====
        import shutil
        import os
        cleanup_success = False
        try:
            if os.path.exists(task_ctx.work_path):
                # Only cleanup if task failed or was cancelled
                # Successful uploads already cleanup in handler.py
                if getattr(task_ctx, "keep_files_decision", False):
                    log.info(f"Bypassing workspace cleanup because keep_files_decision is True: {task_ctx.work_path}")
                elif task_ctx.error.state or task_ctx.is_cancelled:
                    log.info(f"Cleaning up workspace for failed/cancelled task: {task_ctx.work_path}")
                    shutil.rmtree(task_ctx.work_path, ignore_errors=True)
                    cleanup_success = True
                    log.info(f"Successfully cleaned up {task_ctx.work_path}")
                else:
                    # Successful task - handler.py should have cleaned up
                    # But verify and cleanup if files still exist
                    try:
                        if os.listdir(task_ctx.work_path):
                            log.warning(f"Workspace not empty after successful task, cleaning up: {task_ctx.work_path}")
                            shutil.rmtree(task_ctx.work_path, ignore_errors=True)
                            cleanup_success = True
                    except FileNotFoundError:
                        pass  # Already cleaned up
        except Exception as cleanup_err:
            log.error(f"Failed to cleanup workspace {task_ctx.work_path}: {cleanup_err}")

        if cleanup_success:
            log.info(f"Task {task_id_str} workspace cleanup complete")
        # ===== END CLEANUP =====

        # Update dashboard
        await TASK_QUEUE.remove_task(task_ctx.task_id)
        await force_update_summary()

        log.info(f"Task {task_id_str} cleanup complete")


# --- Existing Command Handlers ---
@colab_bot.on_message(filters.command("start") & filters.private)
async def start(client, message):
    log.info(f"Received /start from {message.from_user.id}")
    try:
        await message.delete()
    except Exception as delete_err:
        log.debug(f"Could not delete /start command message: {delete_err}")

    text = build_start_welcome_text()
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Repo", url="https://github.com/thesadeq/Telegram-Leecher")]]
    )
    await message.reply_text(
        text,
        reply_markup=keyboard,
        parse_mode=enums.ParseMode.HTML,
    )

@colab_bot.on_message(filters.command("tupload") & filters.private)
async def telegram_upload(client, message):
    global BOT, user_tasks
    user_id = message.from_user.id
    log.info(f"Received /tupload from {user_id}")

    # ===== NEW: RATE LIMIT CHECK =====
    allowed, rate_reason = RATE_LIMITER.can_proceed(user_id)
    if not allowed:
        await message.reply_text(f"❌ {rate_reason}")
        return
    # ===== END RATE LIMIT CHECK =====

    # ===== NEW: CHECK TASK LIMITS =====
    can_start, reason = await TASK_QUEUE.can_start_task(user_id)
    if not can_start:
        await message.reply_text(
            build_cannot_start_task_message(reason),
            parse_mode=enums.ParseMode.HTML,
        )
        return
    # ===== END CHECK =====

    # ===== CHECK FOR DUPLICATE /tupload =====
    # If user already has a pending task waiting for URLs, don't create another one
    async with user_tasks_lock:
        existing_task = user_tasks.get(user_id)
        if existing_task:
            log.info(f"User {user_id} already has pending task {existing_task.get_short_id()}, ignoring duplicate /tupload")
            await message.delete()
            # Reply to existing status message to remind user
            if existing_task.status_msg:
                try:
                    await existing_task.status_msg.reply_text(
                        build_pending_task_warning(existing_task.get_short_id()),
                        parse_mode=enums.ParseMode.HTML,
                    )
                except Exception as e:
                    log.warning(f"Could not reply to existing status message: {e}")
            return
    # ===== END DUPLICATE CHECK =====

    # NEW: Parallel task mode - create TaskContext immediately
    task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="leech"
    )
    task_ctx.service_type = None  # Will be determined from URLs
    task_ctx.mode_type = "normal"  # Default to normal (user can change later)

    # Store in user_tasks registry (waiting for URLs)
    async with user_tasks_lock:
        user_tasks[user_id] = task_ctx
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for /tupload, stored in user_tasks for user {user_id}")

    # Delete user's command message
    try:
        await message.delete()
    except Exception as e:
        log.warning(f"Could not delete command message: {e}")

    # Send prompt for URLs
    text = build_link_prompt("Leech to Telegram", task_id=task_ctx.get_short_id())

    try:
        prompt_msg = await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
        task_ctx.status_msg = prompt_msg  # Store prompt message in task context
        log.info(f"Sent URL prompt for task {task_ctx.get_short_id()}")
    except Exception as e:
        log.error(f"Failed to send URL prompt: {e}")
        # Clean up on failure
        async with user_tasks_lock:
            if user_id in user_tasks:
                del user_tasks[user_id]
        await _reply_with_generic_error(message, "start the task")


@colab_bot.on_message(filters.command("gdupload") & filters.private)
async def drive_upload(client, message):
    global BOT, user_tasks
    user_id = message.from_user.id
    log.info(f"Received /gdupload from {user_id}")

    # ===== NEW: RATE LIMIT CHECK =====
    allowed, rate_reason = RATE_LIMITER.can_proceed(user_id)
    if not allowed:
        await message.reply_text(f"❌ {rate_reason}")
        return
    # ===== END RATE LIMIT CHECK =====

    # ===== NEW: CHECK TASK LIMITS =====
    can_start, reason = await TASK_QUEUE.can_start_task(user_id)
    if not can_start:
        await message.reply_text(
            build_cannot_start_task_message(reason),
            parse_mode=enums.ParseMode.HTML,
        )
        return
    # ===== END CHECK =====

    # ===== CHECK FOR DUPLICATE /gdupload =====
    async with user_tasks_lock:
        existing_task = user_tasks.get(user_id)
        if existing_task:
            log.info(f"User {user_id} already has pending task {existing_task.get_short_id()}, ignoring duplicate /gdupload")
            # Send warning BEFORE deleting the command message
            await client.send_message(
                chat_id=message.chat.id,
                text=build_pending_task_warning(existing_task.get_short_id()),
                parse_mode=enums.ParseMode.HTML,
            )
            await message.delete()
            return
    # ===== END DUPLICATE CHECK =====

    # NEW: Parallel task mode - create TaskContext immediately
    task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="leech"  # Will be changed to mirror if user selects GDrive
    )
    task_ctx.service_type = None  # Will be set after destination selection
    task_ctx.mode_type = "normal"  # Default to normal

    # Store in user_tasks registry (waiting for destination choice, then URLs)
    async with user_tasks_lock:
        user_tasks[user_id] = task_ctx
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for /gdupload, stored in user_tasks for user {user_id}")

    # Ask user to choose upload destination (Google Drive or Local Mirror)
    await message.delete()
    await ask_upload_destination(client, message.chat.id)
    log.debug(f"/gdupload: Asked user for upload destination choice (Task ID: {task_ctx.get_short_id()})")

    # NOTE: Callback handler will retrieve task_ctx from user_tasks
    # This requires Phase 4 callback refactoring for full parallel support

@colab_bot.on_message(filters.command("drupload") & filters.private)
async def directory_upload(client, message):
    global BOT, user_tasks
    user_id = message.from_user.id
    log.info(f"Received /drupload from {user_id}")

    # ===== NEW: RATE LIMIT CHECK =====
    allowed, rate_reason = RATE_LIMITER.can_proceed(user_id)
    if not allowed:
        await message.reply_text(f"❌ {rate_reason}")
        return
    # ===== END RATE LIMIT CHECK =====

    # ===== NEW: CHECK TASK LIMITS =====
    can_start, reason = await TASK_QUEUE.can_start_task(user_id)
    if not can_start:
        await message.reply_text(
            build_cannot_start_task_message(reason),
            parse_mode=enums.ParseMode.HTML,
        )
        return
    # ===== END CHECK =====

    # ===== CHECK FOR DUPLICATE /drupload =====
    async with user_tasks_lock:
        existing_task = user_tasks.get(user_id)
        if existing_task:
            log.info(f"User {user_id} already has pending task {existing_task.get_short_id()}, ignoring duplicate /drupload")
            # Send warning BEFORE deleting the command message
            await client.send_message(
                chat_id=message.chat.id,
                text=build_pending_task_warning(existing_task.get_short_id()),
                parse_mode=enums.ParseMode.HTML,
            )
            await message.delete()
            return
    # ===== END DUPLICATE CHECK =====

    # NEW: Parallel task mode - create TaskContext immediately
    task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="dir-leech"
    )
    task_ctx.service_type = "local"  # Local directory service
    task_ctx.mode_type = "normal"  # Default to normal

    # Store in user_tasks registry (waiting for paths)
    async with user_tasks_lock:
        user_tasks[user_id] = task_ctx
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for /drupload, stored in user_tasks for user {user_id}")

    # Delete user's command message
    try:
        await message.delete()
    except Exception as e:
        log.warning(f"Could not delete command message: {e}")

    # Send prompt for directory path
    text = build_directory_path_prompt(task_ctx.get_short_id())

    try:
        prompt_msg = await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
        task_ctx.status_msg = prompt_msg  # Store prompt message in task context
        log.info(f"Sent path prompt for task {task_ctx.get_short_id()}")
    except Exception as e:
        log.error(f"Failed to send path prompt: {e}")
        # Clean up on failure
        async with user_tasks_lock:
            if user_id in user_tasks:
                del user_tasks[user_id]
        await _reply_with_generic_error(message, "start the task")

@colab_bot.on_message(filters.command("ytupload") & filters.private)
async def yt_upload(client, message):
    global BOT, user_tasks
    user_id = message.from_user.id
    log.info(f"Received /ytupload from {user_id}")

    # ===== NEW: RATE LIMIT CHECK =====
    allowed, rate_reason = RATE_LIMITER.can_proceed(user_id)
    if not allowed:
        await message.reply_text(f"❌ {rate_reason}")
        return
    # ===== END RATE LIMIT CHECK =====

    # ===== NEW: CHECK TASK LIMITS =====
    can_start, reason = await TASK_QUEUE.can_start_task(user_id)
    if not can_start:
        await message.reply_text(
            build_cannot_start_task_message(reason),
            parse_mode=enums.ParseMode.HTML,
        )
        return
    # ===== END CHECK =====

    # NEW: Parallel task mode - create TaskContext immediately
    task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="leech"
    )
    task_ctx.service_type = "ytdl"  # YouTube/yt-dlp service
    task_ctx.mode_type = "normal"  # Default to normal

    # Store in user_tasks registry (waiting for URLs)
    async with user_tasks_lock:
        user_tasks[user_id] = task_ctx
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for /ytupload, stored in user_tasks for user {user_id}")

    # Delete user's command message
    try:
        await message.delete()
    except Exception as e:
        log.warning(f"Could not delete command message: {e}")

    # Send prompt for URLs
    text = (
        "<b>YTDL Source Links</b>\n\n"
        "<i>Supported: YouTube, X/Twitter, Instagram, TikTok, and other yt-dlp sources.</i>\n\n"
        "<code>https://youtube.com/watch?v=example</code>\n\n"
        f"<i>Task ID: <code>{task_ctx.get_short_id()}</code></i>"
    )

    try:
        prompt_msg = await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
        task_ctx.status_msg = prompt_msg  # Store prompt message in task context
        log.info(f"Sent URL prompt for task {task_ctx.get_short_id()}")
    except Exception as e:
        log.error(f"Failed to send URL prompt: {e}")
        # Clean up on failure
        async with user_tasks_lock:
            if user_id in user_tasks:
                del user_tasks[user_id]
        await _reply_with_generic_error(message, "start the task")

@colab_bot.on_message(filters.command("igupload") & filters.private)
async def instagram_upload(client, message):
    global BOT, user_tasks
    user_id = message.from_user.id
    log.info(f"Received /igupload from {user_id}")

    # ===== NEW: RATE LIMIT CHECK =====
    allowed, rate_reason = RATE_LIMITER.can_proceed(user_id)
    if not allowed:
        await message.reply_text(f"❌ {rate_reason}")
        return
    # ===== END RATE LIMIT CHECK =====

    # ===== NEW: CHECK TASK LIMITS =====
    can_start, reason = await TASK_QUEUE.can_start_task(user_id)
    if not can_start:
        await message.reply_text(
            build_cannot_start_task_message(reason),
            parse_mode=enums.ParseMode.HTML,
        )
        return
    # ===== END CHECK =====

    # NEW: Parallel task mode - create TaskContext immediately
    task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="leech"
    )
    task_ctx.service_type = "instagram"  # Instagram service
    task_ctx.mode_type = "normal"  # Default to normal

    # Store in user_tasks registry (waiting for URLs)
    async with user_tasks_lock:
        user_tasks[user_id] = task_ctx
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for /igupload, stored in user_tasks for user {user_id}")

    # Delete user's command message
    try:
        await message.delete()
    except Exception as e:
        log.warning(f"Could not delete command message: {e}")

    # Send prompt for URLs
    text = (
        "<b>Instagram Source Links</b>\n\n"
        "<i>Send post, reel, story, or carousel URLs.</i>\n\n"
        "<code>https://instagram.com/p/example\n"
        "https://instagram.com/reel/example</code>\n\n"
        f"<i>Task ID: <code>{task_ctx.get_short_id()}</code></i>"
    )

    try:
        prompt_msg = await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
        task_ctx.status_msg = prompt_msg  # Store prompt message in task context
        log.info(f"Sent URL prompt for task {task_ctx.get_short_id()}")
    except Exception as e:
        log.error(f"Failed to send URL prompt: {e}")
        # Clean up on failure
        async with user_tasks_lock:
            if user_id in user_tasks:
                del user_tasks[user_id]
        await _reply_with_generic_error(message, "start the task")

@colab_bot.on_message(filters.command("tiktokbulk") & filters.private)
async def tiktok_bulk_upload(client, message):
    """TikTok Bulk Download - Download multiple TikTok videos from a Gist and create ZIP"""
    global user_tasks
    user_id = message.from_user.id
    log.info(f"Received /tiktokbulk from {user_id}")

    # ===== RATE LIMIT CHECK =====
    allowed, rate_reason = RATE_LIMITER.can_proceed(user_id)
    if not allowed:
        await message.reply_text(f"❌ {rate_reason}")
        return

    # ===== CHECK TASK LIMITS =====
    can_start, reason = await TASK_QUEUE.can_start_task(user_id)
    if not can_start:
        await message.reply_text(
            build_cannot_start_task_message(reason),
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Create TaskContext for parallel task mode
    task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="leech"
    )
    task_ctx.service_type = "tiktokbulk"  # TikTok Bulk service
    task_ctx.mode_type = "normal"

    # Store in user_tasks registry (waiting for Gist URL)
    async with user_tasks_lock:
        user_tasks[user_id] = task_ctx
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for /tiktokbulk, stored in user_tasks for user {user_id}")

    # Delete user's command message
    try:
        await message.delete()
    except Exception as e:
        log.warning(f"Could not delete command message: {e}")

    # Send prompt for Gist URL
    text = build_tiktok_bulk_gist_prompt(task_ctx.get_short_id())

    try:
        prompt_msg = await message.reply_text(text, parse_mode=enums.ParseMode.HTML)
        task_ctx.status_msg = prompt_msg
        log.info(f"Sent Gist URL prompt for task {task_ctx.get_short_id()}")
    except Exception as e:
        log.error(f"Failed to send URL prompt: {e}")
        # Clean up on failure
        async with user_tasks_lock:
            if user_id in user_tasks:
                del user_tasks[user_id]
        await _reply_with_generic_error(message, "start the task")

# --- REMOVED /nzbclouddownload, /Debriddownload, /bitsodownload handlers ---

@colab_bot.on_message(filters.command("settings") & filters.private)
async def settings(client, message):
    log.info(f"Received /settings from {message.from_user.id}")
    if message.chat.id == OWNER:
        await message.delete()
        await send_settings(client, message, message.id, True)
    else:
        log.warning(f"Unauthorized /settings from {message.from_user.id}")
        await message.reply_text("❌ Unauthorized.")

# --- Reply Handler: Simplified for filenames only ---
@colab_bot.on_message(filters.reply & filters.private)
async def handle_reply(client: Client, message: Message):
    """Handle user replies for filename selection and other prompt-driven inputs."""
    global BOT
    user_id = _extract_user_id(message)
    log.debug(f"Received reply (ID: {message.id}) from user {user_id}")

    filename_ctx = await _get_filename_reply_waiting(user_id)
    filename_prompt_id = filename_ctx.get("prompt_message_id") if filename_ctx else None
    password_ctx = await get_password_reply_waiting(user_id)
    password_prompt_id = password_ctx.get("prompt_message_id") if password_ctx else None
    settings_ctx = await _get_settings_reply_waiting(user_id)
    settings_prompt_id = settings_ctx.get("prompt_message_id") if settings_ctx else None
    valid_prompt_ids = {
        prompt_id
        for prompt_id in (filename_prompt_id, password_prompt_id, settings_prompt_id)
        if prompt_id
    }

    if not valid_prompt_ids or not message.reply_to_message_id or message.reply_to_message_id not in valid_prompt_ids:
        log.debug(
            f"Reply (ID: {message.id}) is not for expected prompts "
            f"{sorted(valid_prompt_ids) if valid_prompt_ids else []}. Ignoring."
        )
        return

    # Try to get the original prompt message (optional, for deletion/context)
    original_prompt_msg = None
    try:
        if message.reply_to_message_id:
            original_prompt_msg = await client.get_messages(message.chat.id, message.reply_to_message_id)
    except Exception as get_err:
        log.warning(f"Could not get original prompt message {message.reply_to_message_id}: {get_err}")

    state_handled = False
    handled_filename_reply = False
    handled_password_reply = False
    handled_settings_reply = False

    try:
        # --- Handle per-user filename replies ---
        if filename_ctx and message.reply_to_message_id == filename_prompt_id:
            current_service = _normalize_filename_service(filename_ctx.get("service_type"))
            expected_count = filename_ctx.get("expected_count", 0)
            source_links = filename_ctx.get("source_links", [])

            log.info(f"Processing filename reply for service: {current_service} (user={user_id})")
            user_input = message.text.strip() if message.text else ""
            log.debug(f"HANDLE_REPLY: Expecting {expected_count} filenames from per-user prompt state.")

            filenames_to_use = []
            input_processed = False

            is_potential_url = False
            if user_input.lower().startswith(("http://", "https://")):
                if (
                    "pastebin.com" in user_input
                    or "gist.githubusercontent.com" in user_input
                    or "rentry.co" in user_input
                    or user_input.lower().endswith(".txt")
                ):
                    is_potential_url = True

            if is_potential_url:
                log.info(f"Detected potential filename URL: {user_input}")
                raw_lines_list = await fetch_filenames_from_url(user_input)
                fetched_count = len(raw_lines_list) if raw_lines_list is not None else -1
                log.debug(
                    f"HANDLE_REPLY (URL): Comparing Counts -> Fetched: {fetched_count}, Expected: {expected_count}"
                )

                if raw_lines_list is None:
                    await message.reply_text(
                        "Error: Failed to fetch filenames from the provided URL or it's unsupported. "
                        "Please provide a direct reply or a valid raw link (Gist/Pastebin/Rentry/.txt).",
                        quote=True,
                    )
                    log.warning(f"fetch_filenames_from_url returned None for: {user_input}")
                elif fetched_count != expected_count:
                    log.warning("Raw filename line count mismatch.")
                    await message.reply_text(
                        f"Error: Found {fetched_count} non-empty lines in the URL, but expected {expected_count} filenames "
                        "(matching the number of links). Please check the file content and reply again.",
                        quote=True,
                    )
                else:
                    log.info(f"Raw line count matches expected count ({expected_count}). Cleaning/styling filenames...")
                    all_valid_after_cleaning = True
                    for i, raw_line in enumerate(raw_lines_list):
                        cleaned = clean_filename(raw_line)
                        if cleaned:
                            styled = apply_dot_style(cleaned)
                            filenames_to_use.append(styled)
                        else:
                            log.warning(
                                f"Filename at line {i + 1} ('{raw_line[:50]}...') became invalid after cleaning. Aborting."
                            )
                            await message.reply_text(
                                f"Error: Filename at line {i + 1} ('{raw_line[:50]}...') is invalid after cleaning. "
                                "Please check your list and reply again.",
                                quote=True,
                            )
                            all_valid_after_cleaning = False
                            break

                    if all_valid_after_cleaning:
                        input_processed = True
                        log.info(f"Successfully cleaned and stored {len(filenames_to_use)} filenames from URL.")
            else:
                log.info("Processing input as direct filename list.")
                filenames_raw = [fn.strip() for fn in user_input.splitlines() if fn.strip()]
                fetched_count = len(filenames_raw)
                log.debug(
                    f"HANDLE_REPLY (Direct): Comparing Counts -> Fetched: {fetched_count}, Expected: {expected_count}"
                )

                if fetched_count != expected_count:
                    log.warning("Filename count mismatch (direct input).")
                    await message.reply_text(
                        f"Error: Expected {expected_count} filenames, but got {fetched_count}. "
                        "Reply again with the correct number of filenames.",
                        quote=True,
                    )
                else:
                    log.info(f"Direct input count matches expected count ({expected_count}). Cleaning/styling filenames...")
                    all_valid_after_cleaning = True
                    for i, raw_line in enumerate(filenames_raw):
                        cleaned = clean_filename(raw_line)
                        if cleaned:
                            styled = apply_dot_style(cleaned)
                            filenames_to_use.append(styled)
                        else:
                            log.warning(
                                f"Direct filename at line {i + 1} ('{raw_line[:50]}...') became invalid after cleaning. Aborting."
                            )
                            await message.reply_text(
                                f"Error: Filename at line {i + 1} ('{raw_line[:50]}...') is invalid after cleaning. "
                                "Please check your input and reply again.",
                                quote=True,
                            )
                            all_valid_after_cleaning = False
                            break

                    if all_valid_after_cleaning:
                        input_processed = True
                        log.info(f"Successfully cleaned and stored {len(filenames_to_use)} filenames from direct input.")

            if input_processed:
                await _update_setup_session(
                    user_id,
                    source_links=source_links,
                    service_type=current_service,
                    filenames=filenames_to_use,
                )
                mode_name = _filename_mode_label(current_service)
                log.info(f"Received valid filenames for {mode_name} ({'URL' if is_potential_url else 'Direct'}).")

                state_handled = True
                handled_filename_reply = True
                await ask_leech_type(client, message.chat.id, BOT.Mode.mode)

        # --- Handle Settings Prefix/Suffix replies ---
        elif settings_ctx and message.reply_to_message_id == settings_prompt_id:
            setting_key = settings_ctx.get("setting_key")
            new_value = message.text.strip() if message.text else ""
            if new_value == "-":
                new_value = ""
            settings_message_id = settings_ctx.get("settings_message_id")
            state_handled = True
            handled_settings_reply = True

            if setting_key == "prefix":
                log.info(f"Processing prefix reply (user={user_id})...")
                BOT.Setting.prefix = new_value
            elif setting_key == "suffix":
                log.info(f"Processing suffix reply (user={user_id})...")
                BOT.Setting.suffix = new_value
            else:
                log.warning(f"Unknown settings reply key '{setting_key}' for user {user_id}")
                await message.reply_text("Error: Unknown settings reply type.", quote=True)
                return

            if settings_message_id:
                try:
                    settings_msg = await client.get_messages(message.chat.id, settings_message_id)
                    if settings_msg:
                        await send_settings(client, settings_msg, settings_message_id, False)
                    else:
                        await message.reply_text(f"{setting_key.title()} set!")
                except Exception as send_err:
                    log.error(f"Failed to refresh settings after {setting_key}: {send_err}")
                    await message.reply_text(f"{setting_key.title()} set!")
            else:
                await message.reply_text(f"{setting_key.title()} set!")

        elif password_ctx and message.reply_to_message_id == password_prompt_id:
            log.info("Processing password reply for archive extraction...")
            user_password = message.text.strip() if message.text else ""

            if not user_password:
                await message.reply_text("Error: Password cannot be empty. Please reply with a valid password.", quote=True)
                return  # Keep waiting for valid password

            # Get the extraction context
            retry_ctx = password_ctx.get("retry_context")
            if not retry_ctx:
                log.error("Password reply received but no retry context found!")
                await message.reply_text("Error: Extraction context lost. Please restart the download.", quote=True)
                state_handled = True
                handled_password_reply = True
                return

            state_handled = True
            handled_password_reply = True

            # Send confirmation message
            status_msg = await message.reply_text("Password received. Retrying extraction...", quote=True)

            try:
                # Import converters to access extract functions
                from colab_leecher.utility.converters import extract_rar_streaming, extract, extract_and_upload_streaming

                # Update the password in BOT.Options
                BOT.Options.unzip_pswd = user_password

                # Determine which extraction method to retry based on context
                function_name = retry_ctx.get('function')

                if function_name == 'extract_and_upload_streaming':
                    # RAR extract-and-upload streaming
                    log.info(f"Retrying RAR extract-and-upload streaming with provided password...")
                    success = await extract_and_upload_streaming(
                        rar_filepath=retry_ctx['rar_filepath'],
                        password=user_password,  # Use the provided password
                        file_filter=retry_ctx.get('file_filter'),
                        task_ctx=retry_ctx.get('task_ctx')
                    )
                elif 'rar_filepath' in retry_ctx:
                    # RAR streaming extraction
                    log.info(f"Retrying RAR streaming extraction with provided password...")
                    success = await extract_rar_streaming(
                        rar_filepath=retry_ctx['rar_filepath'],
                        extract_to=retry_ctx['extract_to'],
                        remove=retry_ctx['remove'],
                        password=user_password,  # Use the provided password
                        file_filter=retry_ctx.get('file_filter'),
                        chunk_size=retry_ctx.get('chunk_size', 1024*1024),
                        resume_state_file=retry_ctx.get('resume_state_file'),
                        memory_limit_mb=retry_ctx.get('memory_limit_mb', 800),
                        task_ctx=retry_ctx.get('task_ctx')
                    )
                else:
                    # Command-line extraction
                    log.info(f"Retrying command-line extraction with provided password...")
                    success = await extract(
                        zip_filepath=retry_ctx['zip_filepath'],
                        remove=retry_ctx['remove'],
                        task_ctx=retry_ctx.get('task_ctx')
                    )

                if success:
                    await status_msg.edit_text("Extraction completed successfully with the provided password!")
                    log.info("Password-protected extraction succeeded.")
                else:
                    await status_msg.edit_text("Extraction failed. The password might be incorrect or there's another issue. Check logs for details.")
                    log.error("Password-protected extraction failed even with user-provided password.")

            except Exception as extract_err:
                log.error(f"Error during password-retry extraction: {extract_err}", exc_info=True)
                await status_msg.edit_text(user_error("complete extraction"))

        else:
            log.warning(
                f"Received reply for prompt {message.reply_to_message_id} but no matching active reply state was found."
            )

    except Exception as e:
        log.error(f"Error processing reply: {e}", exc_info=True)
        # Inform user about the error
        try:
            await _reply_with_generic_error(message, "process your reply", quote=True)
        except Exception as reply_err:
            log.debug(f"Could not send reply-processing error message: {reply_err}")

    finally:
        # --- Final cleanup inside handle_reply ---
        if state_handled:
            log.debug(f"State handled for reply {message.id}. Resetting prompt state.")
            if handled_filename_reply:
                await _clear_filename_reply_waiting(client, message.chat.id, user_id)
            elif handled_password_reply:
                await _clear_password_reply_prompt(client, user_id)
            elif handled_settings_reply:
                await _clear_settings_reply_waiting(client, message.chat.id, user_id)
            else:
                await _clear_settings_reply_waiting(client, message.chat.id, user_id)
            try:
                # Check if message exists before deleting
                if message: await message.delete() # Delete user's reply
            except Exception as del_err:
                 log.warning(f"Could not delete user reply message {message.id if message else 'N/A'}: {del_err}")
        else:
            # Only log if we were actually expecting a reply (prompt ID was set)
            expected_msg_id = filename_prompt_id or password_prompt_id or settings_prompt_id
            if expected_msg_id == message.reply_to_message_id:
                 log.debug(f"State not handled for reply {message.id}. Prompt ID {expected_msg_id} remains active.")
            # No need to log if the reply wasn't for our prompt anyway


def parse_session_capture_gist(lines: list[str]) -> dict:
    """
    Parses a session capture gist and extracts:
    - url: The target download URL
    - headers: Dict of headers (User-Agent, Referer, etc.)
    - cookies: Dict of cookies
    - title: Optional title / filename
    """
    result = {
        "url": None,
        "headers": {},
        "cookies": {},
        "title": None
    }
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        if line.upper().startswith("TITLE="):
            result["title"] = line.split("=", 1)[1].strip()
        elif line.upper().startswith("DOWNLOAD_TYPE="):
            pass
        elif line.upper().startswith("URL="):
            result["url"] = line.split("=", 1)[1].strip()
        elif line.upper().startswith("COOKIE="):
            cookie_str = line.split("=", 1)[1].strip()
            for item in cookie_str.split(";"):
                if "=" in item:
                    k, v = item.split("=", 1)
                    result["cookies"][k.strip()] = v.strip()
        elif line.upper().startswith("USER_AGENT="):
            result["headers"]["User-Agent"] = line.split("=", 1)[1].strip()
        elif line.upper().startswith("REFERER="):
            result["headers"]["Referer"] = line.split("=", 1)[1].strip()
        elif line.upper().startswith("HEADER="):
            header_line = line.split("=", 1)[1].strip()
            if ":" in header_line:
                k, v = header_line.split(":", 1)
                result["headers"][k.strip()] = v.strip()
            elif "=" in header_line:
                k, v = header_line.split("=", 1)
                result["headers"][k.strip()] = v.strip()
                
    if not result["url"]:
        for line in lines:
            line_strip = line.strip()
            if line_strip.lower().startswith(("http://", "https://")) and not any(line_strip.upper().startswith(prefix) for prefix in ["TITLE=", "DOWNLOAD_TYPE=", "URL=", "COOKIE=", "USER_AGENT=", "REFERER=", "HEADER="]):
                result["url"] = line_strip
                break
                
    return result


async def resolve_host_direct_url(target_url: str, headers: dict, cookies: dict) -> str:
    """
    If the target URL is a hoster page (like playmogo.com) or if the referer is a
    playmogo.com page (when target_url is an IP-locked CDN link), fetches the HTML page
    using the premium cookies from the current bot IP (Google Colab), parses the
    direct CDN download link, and returns it. Otherwise returns the original URL.
    """
    import re
    import logging
    log = logging.getLogger(__name__)
    
    resolve_url = None
    if "playmogo.com" in target_url.lower():
        resolve_url = target_url
    else:
        if headers:
            for k, v in headers.items():
                if k.lower() == "referer" and "playmogo.com" in v.lower():
                    resolve_url = v
                    break
                    
    if resolve_url:
        log.info(f"Resolving Playmogo host page: {resolve_url}")
        
        req_headers = dict(headers) if headers else {}
        if "User-Agent" not in req_headers:
            req_headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            
        html_text = None
        
        # Try using curl_cffi for Cloudflare bypass if available (default on Colab)
        try:
            from curl_cffi.requests import AsyncSession
            log.info("Using curl_cffi AsyncSession for Playmogo fetch (impersonating Chrome)...")
            async with AsyncSession() as session:
                response = await session.get(
                    resolve_url, 
                    headers=req_headers, 
                    cookies=cookies, 
                    impersonate="chrome110",
                    timeout=20
                )
                if response.status_code == 200:
                    html_text = response.text
                else:
                    log.error(f"Failed to fetch Playmogo page via curl_cffi: HTTP {response.status_code}")
        except Exception as curl_err:
            log.warning(f"curl_cffi fetch not available or failed: {curl_err}. Falling back to aiohttp.")
            
        # Fallback to standard aiohttp
        if not html_text:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(resolve_url, headers=req_headers, cookies=cookies, timeout=20) as response:
                        if response.status == 200:
                            html_text = await response.text()
                        else:
                            log.error(f"Failed to fetch Playmogo page via aiohttp: HTTP {response.status}")
            except Exception as aio_err:
                log.error(f"aiohttp fallback failed: {aio_err}")
                
        if html_text:
            try:
                # Look for cloudatacdn.com links or general direct video links
                cdn_match = re.search(r'https?://[a-zA-Z0-9.-]+\.cloudatacdn\.com/[^\s"\'>]+', html_text)
                if cdn_match:
                    resolved_url = cdn_match.group(0).replace('&amp;', '&').strip()
                    log.info(f"Successfully resolved Playmogo direct CDN link: {resolved_url[:100]}...")
                    return resolved_url
                
                # Fallback direct video search
                video_links = re.findall(r'https?://[^\s"\'>]+\.(?:mp4|mkv|zip|rar|7z)(?:\?[^\s"\'>]*)?', html_text, re.IGNORECASE)
                if video_links:
                    resolved_url = video_links[0].replace('&amp;', '&').strip()
                    log.info(f"Resolved Playmogo fallback direct link: {resolved_url[:100]}...")
                    return resolved_url
                
                log.warning("No direct download links found in Playmogo page HTML.")
            except Exception as parse_err:
                log.error(f"Error parsing page content: {parse_err}")
                
    return target_url


async def fetch_and_parse_links(url: str) -> list[str] | None:
    """
    Fetches content from supported raw text URLs (Pastebin, Gist, Rentry)
    and parses valid links (http/https/magnet).
    Returns a list of links or None on failure or if URL is not supported.
    """
    log = logging.getLogger(__name__) # Get logger instance
    # Ensure necessary modules are imported where this function is defined
    import re
    import aiohttp

    raw_url = None
    cleaned_url = url.strip() # Clean input URL

    # --- Identify supported services and get raw URL ---
    if "pastebin.com" in cleaned_url:
        match = re.match(r"https?://pastebin\.com/raw/(\w+)", cleaned_url)
        if match:
            raw_url = cleaned_url
        else:
            match = re.match(r"https?://pastebin\.com/(\w+)", cleaned_url)
            if match:
                raw_url = f"https://pastebin.com/raw/{match.group(1)}"
    elif "gist.githubusercontent.com" in cleaned_url and "/raw" in cleaned_url:
         # Directly handle raw gist URLs
         raw_url = cleaned_url
    elif "rentry.co" in cleaned_url:
        match = re.match(r"https?://rentry\.co/(\w+)", cleaned_url.split('/raw')[0]) # Get base code
        if match:
            raw_url = f"https://rentry.co/{match.group(1)}/raw" # Ensure /raw

    # Add simple check for direct .txt links
    elif cleaned_url.lower().startswith(('http://', 'https://')) and cleaned_url.lower().endswith(".txt"):
         raw_url = cleaned_url

    if not raw_url:
        # log.debug(f"URL not recognized as a supported raw paste/gist/rentry/txt link: {cleaned_url}")
        return None # Indicate not a supported URL type for fetching

    log.info(f"Attempting to fetch links from detected raw URL: {raw_url}")
    try:
        async with aiohttp.ClientSession() as session:
            # Add headers to potentially mimic a browser
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
            async with session.get(raw_url, timeout=20, headers=headers) as response: # Increased timeout
                log.debug(f"Fetching URL status: {response.status}")
                response.raise_for_status() # Raise exception for bad status codes
                text_content = await response.text()

                if not text_content:
                    log.warning(f"Fetched empty content from {raw_url}")
                    return []

                # Parse links - one per line, basic validation
                links = []
                for line in text_content.splitlines():
                    line = line.strip()
                    # Basic check for http/https/magnet/ftp links - refine regex if needed
                    if re.match(r"^(https?://|magnet:\?|ftps?://)", line):
                        links.append(line)
                    elif line: # Log non-empty lines that don't look like links
                         log.debug(f"Ignoring non-link line: {line[:100]}...")


                log.info(f"Parsed {len(links)} links from {raw_url}")
                return links

    except aiohttp.ClientError as e:
        log.error(f"HTTP Client Error fetching links from {raw_url}: {e}")
        # Optionally: Inform user fetch failed
        # await client.send_message(chat_id=OWNER, text=f"⚠️ Failed to fetch links from {url}: {e}")
        return None # Return None on fetch errors
    except Exception as e:
        log.error(f"Unexpected error fetching/parsing links from {raw_url}: {e}", exc_info=True)
        # Optionally: Inform user fetch failed
        # await client.send_message(chat_id=OWNER, text=f"⚠️ Failed to parse links from {url}: {e}")
        return None # Return None on other errors

# --- End of function definition ---
# URL Handler: Modified to handle external link lists
# URL Handler: Modified to handle external link lists AND failed parsing
# Add this function definition inside __main__.py
async def ask_mode_selection(client, message):
    """Send a menu asking for the download mode when a link is sent without an active task."""
    from colab_leecher import OWNER
    log = logging.getLogger(__name__)
    log.info(f"Asking user {message.from_user.id} to select mode for raw link input...")
    
    keyboard_markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Leech", callback_data="modepick_leech"),
            InlineKeyboardButton("♻️ Mirror", callback_data="modepick_mirror")
        ],
        [
            InlineKeyboardButton("🎬 Mindvalley", callback_data="modepick_mindvalley"),
            InlineKeyboardButton("📱 TikTok Bulk", callback_data="modepick_tiktokbulk")
        ],
        [
            InlineKeyboardButton("🎥 YTDL Leech", callback_data="modepick_ytdl")
        ],
        [
            InlineKeyboardButton("❌ Cancel", callback_data="cancel")
        ]
    ])
    
    text = (
        "<b>No Active Task!</b>\n\n"
        "I detected that you sent a link or Gist, but you haven't started a task yet.\n\n"
        "<b>What would you like to do with this input?</b>"
    )
    
    try:
        await message.reply_text(
            text,
            reply_markup=keyboard_markup,
            parse_mode=enums.ParseMode.HTML,
            quote=True,
        )
    except Exception as e:
        log.error(f"Failed to ask mode selection: {e}")


async def ask_service_type(client, message):
    """Send a menu asking for the download service type."""
    from colab_leecher import OWNER

    log = logging.getLogger(__name__)
    log.info("Asking user to select download service...")
    keyboard_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("Aria", callback_data="service_direct"), InlineKeyboardButton("Debrid", callback_data="service_Debrid")],
        [InlineKeyboardButton("Bitso", callback_data="service_bitso")],
        [InlineKeyboardButton("Cancel", callback_data="cancel")],
    ])
    try:
        if message and hasattr(message, "reply_text"):
            await message.reply_text(
                "Select the download service for these links:",
                reply_markup=keyboard_markup,
                quote=True,
            )
        else:
            log.warning("ask_service_type: Message context lost, sending to OWNER.")
            await client.send_message(
                OWNER,
                "Select the download service for the provided links:",
                reply_markup=keyboard_markup,
            )
    except Exception as e:
        log.error(f"Failed to ask service type: {e}", exc_info=True)
        try:
            await _send_generic_error(client, OWNER, "show the service selection menu")
        except Exception as owner_notify_err:
            log.debug(f"Could not notify owner about service-type error: {owner_notify_err}")
# --- End ask_service_type function ---

# --- Replace the entire handle_url function ---
@colab_bot.on_message(filters.create(isLink) & ~filters.photo & filters.private)
async def handle_url(client: Client, message: Message):
    global BOT, user_tasks
    user_id = message.from_user.id

    # === NEW: Check for Parallel Task Mode First ===
    # If user has a pending task in user_tasks, process it in parallel mode
    async with user_tasks_lock:
        task_ctx = user_tasks.pop(user_id, None)  # Remove from registry

    if task_ctx:
        log.info(f"Found pending parallel task {task_ctx.get_short_id()} for user {user_id}")

        # === TIKTOK BULK DOWNLOAD HANDLING ===
        if task_ctx.service_type == "tiktokbulk":
            log.info(f"Launching TikTok Bulk task {task_ctx.get_short_id()}")
            
            # Delete the prompt message
            if task_ctx.status_msg:
                try:
                    await task_ctx.status_msg.delete()
                    task_ctx.status_msg = None
                except Exception as e:
                    log.debug(f"Could not delete TikTok prompt: {e}")

            # Use run_parallel_task to handle concurrency and execution
            async_task = TASK_QUEUE.create_background_task(
                run_parallel_task(client, message, task_ctx),
                name=f"tiktok-parent-{task_ctx.get_short_id()}"
            )
            task_ctx.async_task = async_task
            _attach_task_exception_handler(async_task, task_ctx)
            
            return
        # === END TIKTOK BULK DOWNLOAD HANDLING ===

        # Delete the prompt message
        if task_ctx.status_msg:
            try:
                await task_ctx.status_msg.delete()
            except Exception as e:
                log.warning(f"Failed to delete prompt message for task {task_ctx.get_short_id()}: {e}")

        try:
            input_text = message.text.strip() if message.text else ""
            if not input_text:
                await message.reply_text("❌ Input cannot be empty.")
                return

            # Check if input is a Gist and if it contains session capture metadata
            if any(x in input_text for x in ['gist.github', 'pastebin.com', 'rentry.co']):
                try:
                    gist_lines = await fetch_filenames_from_url(input_text)
                    if gist_lines:
                        is_session_capture = False
                        for line in gist_lines[:5]:
                            line_upper = line.strip().upper()
                            if "DOWNLOAD_TYPE=SESSION-CAPTURE" in line_upper or "DOWNLOAD_TYPE=SESSION_CAPTURE" in line_upper or line_upper.startswith("URL="):
                                is_session_capture = True
                                break
                        
                        if is_session_capture:
                            log.info(f"Session capture Gist detected for pending task {task_ctx.get_short_id()}")
                            parsed_session = parse_session_capture_gist(gist_lines)
                            target_url = parsed_session.get("url")
                            if target_url:
                                task_ctx.service_type = "direct"
                                task_ctx.session_capture_headers = parsed_session.get("headers", {})
                                task_ctx.session_capture_cookies = parsed_session.get("cookies", {})
                                # Resolve IP-locked direct link if needed
                                target_url = await resolve_host_direct_url(target_url, task_ctx.session_capture_headers, task_ctx.session_capture_cookies)
                                task_ctx.source_urls = [target_url]
                                title = parsed_session.get("title")
                                if title:
                                    task_ctx.filenames = [title]
                                input_text = target_url  # Replace input_text with parsed direct URL so downstream uses it!
                                log.info(f"Successfully processed session capture for pending task. Target URL: {target_url[:100]}...")
                except Exception as detect_err:
                    log.error(f"Error checking session capture for pending task Gist: {detect_err}")

            # === NEW: Check if input is a gist/pastebin with multiple links ===
            parsed_links = None
            try:
                parsed_links = await fetch_links_from_url(input_text)
            except Exception as fetch_err:
                log.error(f"Error fetching links from URL: {fetch_err}")

            if parsed_links and len(parsed_links) > 1:
                # Multiple links detected - ask user if they want parallel downloads
                from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

                keyboard_parallel = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🚀 All Parallel", callback_data=f"parallel_all:{task_ctx.get_short_id()}"),
                        InlineKeyboardButton("⏸️ One by One", callback_data=f"parallel_seq:{task_ctx.get_short_id()}")
                    ]
                ])

                choice_msg = await message.reply_text(
                    f"<b>Found {len(parsed_links)} links in your gist/paste.</b>\n\n"
                    "<b>How do you want to download them?</b>\n\n"
                    f"🚀 <b>All Parallel</b> - Download all {len(parsed_links)} files at the same time\n"
                    "⏸️ <b>One by One</b> - Download sequentially in batches\n\n"
                    f"<i>Task ID: {task_ctx.get_short_id()}</i>",
                    reply_markup=keyboard_parallel,
                    parse_mode=enums.ParseMode.HTML,
                )

                # Store parsed links and choice message in task context for callback handler
                task_ctx.source_urls = parsed_links  # Store parsed links
                task_ctx.status_msg = choice_msg  # Update status message

                # Re-add task to user_tasks (waiting for user choice)
                async with user_tasks_lock:
                    user_tasks[user_id] = task_ctx
                log.info(f"Waiting for parallel/sequential choice for task {task_ctx.get_short_id()} with {len(parsed_links)} links")
                return  # Exit - callback will handle the choice

            # Store raw input for processing (single link or gist with 1 link)
            task_ctx.source_urls = [input_text]  # Store raw text (will be parsed by taskScheduler)

            # Send processing message
            processing_msg = await message.reply_text(
                "<b>Processing your request...</b>\n\n"
                f"<b>Task ID:</b> <code>{task_ctx.get_short_id()}</code>\n"
                "<b>Mode:</b> Leech (Telegram Upload)\n\n"
                "<i>Please wait while we prepare your download...</i>",
                parse_mode=enums.ParseMode.HTML,
            )
            task_ctx.status_msg = processing_msg

            _prepare_task_context(
                task_ctx=task_ctx,
                source_links=[input_text],
                filenames=task_ctx.filenames,
                custom_name=BOT.Options.custom_name if hasattr(BOT.Options, 'custom_name') else '',
                zip_pswd=BOT.Options.zip_pswd if hasattr(BOT.Options, 'zip_pswd') else '',
                unzip_pswd=BOT.Options.unzip_pswd if hasattr(BOT.Options, 'unzip_pswd') else '',
                archive_format=BOT.Options.archive_format if hasattr(BOT.Options, 'archive_format') else '7z',
            )

            # Launch task in parallel (NON-BLOCKING!)
            # Tracked background task to prevent leaks
            async_task = TASK_QUEUE.create_background_task(
                run_parallel_task(client, message, task_ctx),
                name=f"task-{task_ctx.get_short_id()}"
            )
            task_ctx.async_task = async_task

            _attach_task_exception_handler(async_task, task_ctx)

            log.info(f"Launched parallel task {task_ctx.get_short_id()} - returning immediately!")

            # Return immediately - task runs in background!
            return

        except Exception as e:
            log.exception(f"Error launching parallel task for user {user_id}")
            await _reply_with_generic_error(message, "start the task")
            return

    # === END Parallel Task Mode ===

    # --- Initial State Checks ---
    # Handle extract waiting state FIRST (before command check)
    extract_user_id = _extract_user_id(message)
    if await _is_extract_waiting(extract_user_id):
        log.info(f"extract_waiting=True for user {extract_user_id}, processing path input: {message.text[:50] if message.text else 'None'}...")
        await _handle_extract_input(client, message)
        return

    # --- Safety Check: Ignore command messages (but allow file paths like /content/) ---
    if message.text and message.text.startswith('/'):
        # Check if it's actually a command (word followed by space or end of string)
        # vs a file path like /content/drive/...
        parts = message.text.split(None, 1)
        first_part = parts[0]
        has_more_slashes = '/' in first_part[1:]
        if len(parts[0]) <= 20 and not has_more_slashes:  # Commands are short, paths have more slashes
            log.debug("handle_url: Ignoring command message.")
            raise ContinuePropagation

    # Ignore if waiting for per-user filename reply or waiting for mindvalley/NZB URLs
    if (
        await _is_filename_reply_waiting(user_id)
        or await _is_mindvalley_waiting(user_id)
        or await _is_nzb_waiting(user_id)
    ):
        log.debug("handle_url: Ignoring link/path message - waiting for other input.")
        raise ContinuePropagation

    setup_session = await _get_setup_session(user_id)
    if not setup_session:
        # === AUTO-DETECT GIST CONTENT OR SHOW MENU ===
        input_text = message.text.strip() if message.text else ""
        
        # Check if it's a known link paste service
        if any(x in input_text for x in ['gist.github', 'pastebin.com', 'rentry.co']):
            try:
                # Use helper to fetch raw lines for detection
                gist_lines = await fetch_filenames_from_url(input_text)
                if gist_lines:
                    first_line = gist_lines[0].strip().upper()
                    
                    # Detection 1: Session Capture (DOWNLOAD_TYPE=SESSION-CAPTURE)
                    is_session_capture = False
                    for line in gist_lines[:5]:
                        line_upper = line.strip().upper()
                        if "DOWNLOAD_TYPE=SESSION-CAPTURE" in line_upper or "DOWNLOAD_TYPE=SESSION_CAPTURE" in line_upper:
                            is_session_capture = True
                            break
                        if line_upper.startswith("URL="):
                            is_session_capture = True
                            break

                    if is_session_capture:
                        log.info(f"Auto-detected Session-Capture mode for gist: {input_text}")
                        parsed_session = parse_session_capture_gist(gist_lines)
                        target_url = parsed_session.get("url")
                        
                        if not target_url:
                            log.error("Session capture Gist did not contain a valid download URL.")
                            await message.reply_text("❌ Error: Gist does not contain a valid URL= link.")
                            return
                            
                        # Setup task context
                        task_ctx = create_task_context(user_id, message.chat.id, mode="leech")
                        task_ctx.service_type = "direct"
                        task_ctx.session_capture_headers = parsed_session.get("headers", {})
                        task_ctx.session_capture_cookies = parsed_session.get("cookies", {})
                        
                        # Resolve IP-locked direct link if needed
                        target_url = await resolve_host_direct_url(target_url, task_ctx.session_capture_headers, task_ctx.session_capture_cookies)
                        task_ctx.source_urls = [target_url]
                        
                        title = parsed_session.get("title")
                        if title:
                            task_ctx.filenames = [title]
                            
                        # Delete the source prompt message (if any)
                        await _clear_source_waiting(client, user_id)
                        
                        # Send initial status message
                        processing_msg = await message.reply_text(
                            "<b>Processing Session-Captured Request...</b>\n\n"
                            f"<b>Task ID:</b> <code>{task_ctx.get_short_id()}</code>\n"
                            "<b>Mode:</b> Leech (Telegram Upload)\n\n"
                            "<i>Authentication credentials loaded successfully! Starting download...</i>",
                            parse_mode=enums.ParseMode.HTML,
                        )
                        task_ctx.status_msg = processing_msg
                        
                        # Initialize isolated configuration
                        _prepare_task_context(
                            task_ctx=task_ctx,
                            source_links=[target_url],
                            filenames=task_ctx.filenames,
                            custom_name=title if title else (BOT.Options.custom_name if hasattr(BOT.Options, 'custom_name') else ''),
                            zip_pswd=BOT.Options.zip_pswd if hasattr(BOT.Options, 'zip_pswd') else '',
                            unzip_pswd=BOT.Options.unzip_pswd if hasattr(BOT.Options, 'unzip_pswd') else '',
                            archive_format=BOT.Options.archive_format if hasattr(BOT.Options, 'archive_format') else '7z',
                        )
                        
                        task_ctx.bot.Options.service_type = "direct"
                        if title:
                            task_ctx.bot.Options.filenames = [title]
                        
                        # Launch task in background
                        async_task = TASK_QUEUE.create_background_task(
                            run_parallel_task(client, message, task_ctx),
                            name=f"task-{task_ctx.get_short_id()}"
                        )
                        task_ctx.async_task = async_task
                        _attach_task_exception_handler(async_task, task_ctx)
                        
                        raise ContinuePropagation

                    # Detection 2: Mindvalley (TITLE=)
                    elif first_line.startswith("TITLE="):
                        log.info(f"Auto-detected Mindvalley mode for gist: {input_text}")
                        await _update_setup_session(user_id, mode="leech", service_type="mindvalley")
                        await _set_mindvalley_waiting(user_id, True)
                        raise ContinuePropagation
                    
                    # Detection 3: TikTok Bulk (tiktok.com)
                    elif "TIKTOK.COM" in first_line:
                        log.info(f"Auto-detected TikTokBulk mode for gist: {input_text}")
                        # Setup TikTok task context as if /tiktokbulk was run
                        task_ctx = create_task_context(user_id, message.chat.id, mode="leech")
                        task_ctx.service_type = "tiktokbulk"
                        async with user_tasks_lock:
                            user_tasks[user_id] = task_ctx
                        # Re-call handle_url which will now catch the task_ctx at the top
                        return await handle_url(client, message)
            except ContinuePropagation:
                raise
            except Exception as e:
                log.debug(f"Gist auto-detection skipped/failed: {e}")

        # If no setup_session and auto-detection failed, show selection menu
        await ask_mode_selection(client, message)
        return
    # --- End Initial State Checks ---

    active_mode = (setup_session.get("mode") if setup_session else None) or BOT.Mode.mode
    log.info(f"Handling URL/Path message from user {user_id}. Current Mode: {active_mode}")
    # Save currently set options (from /setname, /zippswd, /archivetype, etc.) before processing new input
    saved_custom_name = BOT.Options.custom_name
    saved_zip_pswd = BOT.Options.zip_pswd
    saved_unzip_pswd = BOT.Options.unzip_pswd
    saved_archive_format = BOT.Options.archive_format if hasattr(BOT.Options, 'archive_format') else '7z'

    # Delete the initial source prompt message for this user.
    await _clear_source_waiting(client, user_id)

    try:
        input_text = message.text.strip() if message.text else ""
        if not input_text:
             await message.reply_text("❌ Input cannot be empty."); await _clear_setup_session(user_id); return

        current_service_type = setup_session.get("service_type") if setup_session else None
        current_filenames = list(setup_session.get("filenames", [])) if setup_session else []
        current_mode = active_mode

        # --- === Handle Directory Leech Path === ---
        if current_mode == "dir-leech":
            log.info(f"Processing input as directory path for dir-leech: '{input_text}'")
            # Check if path exists
            if not os.path.exists(input_text):
                 log.error(f"Dir-leech path does not exist: {input_text}")
                 await message.reply_text(
                     f"❌ Path not found or invalid: <code>{input_text}</code>",
                     parse_mode=enums.ParseMode.HTML,
                 )
                 await _clear_setup_session(user_id)
                 return

            source_links = [input_text]
            current_service_type = "local"
            current_filenames = []
            await _update_setup_session(
                user_id,
                mode=current_mode,
                source_links=source_links,
                service_type=current_service_type,
                filenames=current_filenames,
                custom_name=saved_custom_name,
                zip_pswd=saved_zip_pswd,
                unzip_pswd=saved_unzip_pswd,
                archive_format=saved_archive_format,
            )
            log.info(f"Stored valid path for dir-leech. Source: {source_links}")

            # Dir-leech doesn't need service selection, proceed to leech type selection
            await ask_leech_type(client, message.chat.id, current_mode) # Ask normal/zip/unzip
            # The task will be scheduled after leech type is selected via callback

        # --- === Handle Normal Link Processing (Leech/Mirror Modes) === ---
        else:
            log.info("Processing input as URL(s) for leech/mirror mode...")
            urls = []
            parsed_links = None
            extracted_args = {"custom_name": "", "zip_pswd": "", "unzip_pswd": ""}

            # Try fetching external links first
            try: parsed_links = await fetch_links_from_url(input_text) # Ensure fetch_links_from_url is imported
            except Exception as fetch_err: log.error(f"Error during fetch_links_from_url call: {fetch_err}", exc_info=True)

            if parsed_links is not None: # Recognized as potential external list URL
                if not parsed_links:
                     log.warning(f"External URL '{input_text}' contained no valid links.")
                     await message.reply_text(f"❌ Found 0 valid links in the provided URL: {input_text}")
                     await _clear_setup_session(user_id)
                     return
                log.info(f"Using {len(parsed_links)} links fetched from external URL: {input_text}")
                urls = parsed_links

                # Check if service_type was pre-selected (e.g., via /nzbcloud command)
                service_already_selected = current_service_type is not None

                # AUTO-DETECT service type based on fetched links (only if not already selected)
                if urls and len(urls) > 0 and not service_already_selected:
                    # Check if ALL links are from the same service
                    all_nzbcloud = all(is_nzbcloud(link) for link in urls)
                    all_instagram = all(is_instagram(link) for link in urls)
                    all_m3u8 = all(is_m3u8_url(link) or is_mindvalley_url(link) for link in urls)

                    if all_nzbcloud:
                        log.info(f"🔍 AUTO-DETECTED: All {len(urls)} links are from NZBcloud, setting service_type to 'nzbcloud'")
                        current_service_type = "nzbcloud"
                    elif all_instagram:
                        log.info(f"🔍 AUTO-DETECTED: All {len(urls)} links are from Instagram, setting service_type to 'direct' (Instagram auto-handled)")
                        current_service_type = "direct"
                    elif all_m3u8:
                        log.info(f"🔍 AUTO-DETECTED: All {len(urls)} links are M3U8/Mindvalley, setting service_type to 'mindvalley'")
                        current_service_type = "mindvalley"
                        await _set_mindvalley_waiting(user_id, True)
                    else:
                        log.info(f"Mixed or unrecognized link types, will ask for service selection")

                # If service is NZBcloud (auto-detected OR pre-selected), extract TITLE= filenames
                if current_service_type == "nzbcloud":
                    try:
                        log.info(f"Parsing TITLE= filenames from gist URL for NZBcloud: {input_text}")
                        filenames_from_gist = await fetch_filenames_from_url(input_text)
                        if filenames_from_gist and len(filenames_from_gist) > 0:
                            # Parse TITLE=filename format
                            parsed_filenames = []
                            for line in filenames_from_gist:
                                if line.startswith("TITLE="):
                                    filename = line[6:].strip()  # Remove "TITLE=" prefix
                                    if filename:
                                        parsed_filenames.append(filename)
                                        log.debug(f"Extracted filename: {filename}")

                            if len(parsed_filenames) == len(urls):
                                current_filenames = parsed_filenames
                                log.info(f"✅ Extracted {len(parsed_filenames)} filenames from TITLE= lines")
                            else:
                                log.warning(f"Filename count mismatch: {len(parsed_filenames)} filenames vs {len(urls)} URLs")
                                current_filenames = []
                        else:
                            log.warning("Could not fetch content from gist for filename extraction")
                            current_filenames = []
                    except Exception as e:
                        log.error(f"Error parsing TITLE= filenames: {e}")
                        current_filenames = []

            else:
                # Fallback: Process message directly for links and args
                log.info("Input not recognized as external list URL, processing directly.")
                # ... (existing logic for parsing links/args from message text) ...
                temp_source = [line.strip() for line in input_text.splitlines() if line.strip()]
                args_to_remove = 0
                for line in reversed(temp_source):
                     is_arg = False
                     if line.startswith("[") and line.endswith("]"): extracted_args["custom_name"] = line[1:-1]; is_arg = True
                     elif line.startswith("{") and line.endswith("}"): extracted_args["zip_pswd"] = line[1:-1]; is_arg = True
                     elif line.startswith("(") and line.endswith(")"): extracted_args["unzip_pswd"] = line[1:-1]; is_arg = True
                     if is_arg: args_to_remove += 1
                     else: break
                urls = temp_source[:-args_to_remove] if args_to_remove > 0 else temp_source

            current_custom_name = extracted_args["custom_name"] if extracted_args["custom_name"] else saved_custom_name
            current_zip_pswd = extracted_args["zip_pswd"] if extracted_args["zip_pswd"] else saved_zip_pswd
            current_unzip_pswd = extracted_args["unzip_pswd"] if extracted_args["unzip_pswd"] else saved_unzip_pswd
            current_archive_format = saved_archive_format
            if current_service_type != "nzbcloud":
                current_filenames = []

            if not urls:
                log.warning("No valid URLs found after processing."); await message.reply_text("❌ No valid URLs found in the message."); await _clear_setup_session(user_id); return

            # Basic validation check (similar to previous version)
            standard_download_pattern = re.compile(r"^(https?://|magnet:\?|ftps?://)")
            paste_site_pattern = re.compile(r"pastebin\.com|gist\.github|rentry\.co|pastes\.io|pastie\.org")
            if parsed_links is None and len(urls) == 1 and urls[0] == input_text:
                if not standard_download_pattern.match(urls[0]) or paste_site_pattern.search(urls[0]):
                     log.error(f"Input '{input_text}' was not parsed and is not a direct download link.")
                     await message.reply_text(f"❌ Input is not a direct download link or a supported raw list URL: {input_text}")
                     await _clear_setup_session(user_id)
                     return

            source_links = list(urls)
            await _update_setup_session(
                user_id,
                mode=current_mode,
                source_links=source_links,
                service_type=current_service_type,
                filenames=current_filenames,
                custom_name=current_custom_name,
                zip_pswd=current_zip_pswd,
                unzip_pswd=current_unzip_pswd,
                archive_format=current_archive_format,
            )
            log.info(f"Received {len(source_links)} URLs for mode {current_mode} in handle_url.")

            # Check if service was auto-detected
            if current_service_type is not None:
                log.info(f"✅ Service auto-detected as '{current_service_type}', skipping service selection")

                # Route to appropriate next step based on auto-detected service
                if current_service_type == "nzbcloud":
                    # NZBcloud filenames should already be extracted from TITLE= lines
                    if current_filenames and len(current_filenames) > 0:
                        log.info(f"✅ NZBcloud filenames already extracted, proceeding to leech type selection")
                        await message.reply_text(f"☁️ Detected {len(source_links)} NZBcloud files with filenames!\n\nProceeding...")
                        await ask_leech_type(client, message.chat.id, current_mode)
                    else:
                        log.warning("NZBcloud detected but no filenames found")
                        await message.reply_text(
                            "⚠️ NZBcloud links detected but no TITLE= filenames found.\n\n"
                            "<b>Required Format:</b>\n"
                            "<code>TITLE=filename.mkv\nhttps://files.nzbcloud.com/...</code>\n\n"
                            "<b>Tip:</b> Use the extension's \"Create Gist\" button to generate the correct format!",
                            parse_mode=enums.ParseMode.HTML,
                        )
                        await _clear_setup_session(user_id)
                        return
                elif current_service_type == "mindvalley":
                    # Mindvalley is already handled by mindvalley_waiting state
                    # Just set the SOURCE and let the mindvalley handler process it
                    log.info("Mindvalley auto-detected, URLs stored in setup session for processing")
                    await message.reply_text(f"🎬 Detected {len(source_links)} Mindvalley M3U8 URL(s)!\n\nProcessing...")
                    # The mindvalley handler will process these URLs
                elif current_service_type in ["direct", "instagram"]:
                    # Direct/Instagram can go straight to leech type
                    await ask_leech_type(client, message.chat.id, current_mode)
                else:
                    # Fallback to asking for service
                    await ask_service_type(client, message)
            else:
                # No auto-detection, ask user for service type
                await ask_service_type(client, message) # Ensure ask_service_type is imported

    except Exception as e:
        log.error(f"Error handling URL/Path message: {e}", exc_info=True)
        await _reply_with_generic_error(message, "process your input")
        await _clear_setup_session(user_id)
# --- End handle_url ---

@colab_bot.on_callback_query()
async def handle_options(client: Client, callback_query: CallbackQuery):
    global BOT, MSG, TaskError, TRANSFER, OWNER, DUMP_ID
    user_id = callback_query.from_user.id
    message = callback_query.message
    query_data = callback_query.data
    # Use message context safely
    msg_id = message.id if message else None
    chat_id = message.chat.id if message and hasattr(message, 'chat') and message.chat else OWNER # Default to OWNER if chat missing

    # Authorization Checks (ensure correct indentation)
    # Note: Cancel actions are authorized inside the specific handlers below to allow users to cancel their own tasks.
    if user_id != OWNER and (
        query_data == "cancel_all_tasks"
        or query_data == "cancel_all_tasks_confirm"
        or query_data == "cancel_all_tasks_abort"
    ):
        await callback_query.answer("Only owner can cancel all.", show_alert=True)
        return
    # Assuming settings callbacks start with "setting_" or similar prefixes handled later
    # Example check (adjust if needed):
    if query_data.startswith(("setting_", "video", "caption", "thumb", "set-suffix", "set-prefix", "close", "back")) and user_id != OWNER:
         await callback_query.answer("Owner only settings.", show_alert=True)
         return
    if not message:
        await callback_query.answer("Original message lost?", show_alert=True)
        log.error("Callback query failed: Message context lost.")
        return

    log.info(f"Handling callback query: {query_data} from user {user_id}")

    try: # Main try block starts here
        # === NEW: Handle Dashboard Pagination ===
        if query_data.startswith("dash_page:") or query_data.startswith("dash_refresh"):
            try:
                page_num = None
                if ":" in query_data:
                    page_num = int(query_data.split(":")[1])

                if query_data.startswith("dash_refresh"):
                    await callback_query.answer("Refreshing Dashboard... 🔄")
                else:
                    await callback_query.answer()

                # Persist page to backend BEFORE rendering so the renderer
                # reads the authoritative value from TASK_QUEUE, not the markup.
                if page_num is not None:
                    await TASK_QUEUE.set_dashboard_page(page_num)

                # Use move_to_bottom=False to prevent photo re-uploading and session disconnects
                await force_update_summary(client, move_to_bottom=False)
            except Exception as e:
                log.error(f"Dashboard update error: {e}")
            return


        # === MODE PICKER HANDLER ===
        if query_data.startswith("modepick_"):
            choice = query_data.split("_")[1]
            orig_msg = callback_query.message.reply_to_message
            if not orig_msg:
                await callback_query.answer("❌ Original message not found. Please resend the link.", show_alert=True)
                return
            
            await callback_query.answer(f"Selected: {choice.capitalize()}")
            try: await callback_query.message.delete()
            except: pass
            
            # Setup the session based on choice
            if choice == "leech":
                await _update_setup_session(user_id, mode="leech")
            elif choice == "mirror":
                await _update_setup_session(user_id, mode="mirror")
            elif choice == "mindvalley":
                await _update_setup_session(user_id, mode="leech", service_type="mindvalley")
                await _set_mindvalley_waiting(user_id, True)
            elif choice == "tiktokbulk":
                # Special handling for tiktokbulk
                task_ctx = create_task_context(user_id, chat_id, mode="leech")
                task_ctx.service_type = "tiktokbulk"
                async with user_tasks_lock:
                    user_tasks[user_id] = task_ctx
            elif choice == "ytdl":
                await _update_setup_session(user_id, mode="leech", service_type="ytdl")
            
            # Process the original message
            if choice == "mindvalley":
                await handle_text_input(client, orig_msg)
            else:
                await handle_url(client, orig_msg)
            return

        # --- Handle Parallel Task Choice ---
        if ":" in query_data and not query_data.startswith("cancel:"):
            # Acknowledge
            await callback_query.answer()
            parts = query_data.split(":", 1)
            if len(parts) != 2:
                await client.send_message(chat_id, "❌ Invalid parallel task action.")
                return
            choice, task_short_id = parts

            # Retrieve task from user_tasks
            async with user_tasks_lock:
                task_ctx = user_tasks.pop(user_id, None)

            if not task_ctx:
                await client.send_message(
                    chat_id,
                    "❌ Task expired. Please start over with /tupload",
                )
                return
            if task_ctx.get_short_id() != task_short_id:
                # Stale button press: do not run actions against a newer pending task.
                async with user_tasks_lock:
                    user_tasks[user_id] = task_ctx
                await client.send_message(
                    chat_id,
                    "❌ This selection is stale. Please use the latest task prompt.",
                )
                return

            links = task_ctx.source_urls  # List of parsed links

            # Delete choice message
            try:
                await message.delete()
            except Exception as delete_msg_err:
                log.debug(f"Could not delete callback command message: {delete_msg_err}")

            if choice == "parallel_all":
                # User wants parallel downloads!
                log.info(f"User chose PARALLEL downloads for {len(links)} links")

                # Create ONE shared status message for all tasks
                # IMPORTANT: Use HTML parse mode to match dashboard formatting
                shared_status_msg = await message.reply_text(
                    f"🚀 <b>Parallel Downloads</b> ({len(links)} files)\n\n"
                    f"📊 Initializing tasks...\n\n"
                    f"<i>Please wait...</i>",
                    parse_mode=enums.ParseMode.HTML
                )

                # Store in TASK_QUEUE for dashboard updates
                TASK_QUEUE.summary_msg = shared_status_msg
                log.info(f"Created initial dashboard message (ID: {shared_status_msg.id})")

                # Start background task to update the shared message periodically
                async def update_shared_message_loop():
                    """Periodically update the shared message with all task progress"""
                    while TASK_QUEUE.get_task_count() > 0:
                        await asyncio.sleep(5)  # Update every 5 seconds
                        try:
                            await update_summary_dashboard(client)  # Pass client to allow message creation
                        except Exception as e:
                            # Silently skip if message not modified (no changes)
                            if "MESSAGE_NOT_MODIFIED" not in str(e):
                                log.error(f"Error updating shared message: {e}")

                TASK_QUEUE.create_background_task(update_shared_message_loop(), name="shared-dashboard-updater")

                # Create a separate TaskContext for EACH link and launch them
                launched_tasks = []

                # Use filenames carried by this task context (if provided by setup parsing).
                filenames_from_task = list(task_ctx.filenames) if getattr(task_ctx, "filenames", None) else []
                has_filenames = len(filenames_from_task) == len(links)
                if has_filenames:
                    log.info(f"Using {len(filenames_from_task)} TITLE= filenames for parallel tasks")

                for idx, link in enumerate(links, 1):
                    # Create new TaskContext for this link
                    sub_task = create_task_context(
                        user_id=user_id,
                        chat_id=message.chat.id,
                        mode=task_ctx.mode
                    )
                    sub_task.source_urls = [link]  # Single link per task
                    sub_task.mode_type = task_ctx.mode_type
                    sub_task.service_type = task_ctx.service_type

                    # Get the corresponding filename for this task (if available)
                    task_filenames = [filenames_from_task[idx-1]] if has_filenames else []
                    log.info(f"Task {idx}/{len(links)} assigned filename: {task_filenames[0] if task_filenames else 'None'}")

                    # Share the single status message across all tasks
                    sub_task.status_msg = shared_status_msg

                    _prepare_task_context(
                        task_ctx=sub_task,
                        source_links=[link],
                        filenames=task_filenames,
                        custom_name='',
                        zip_pswd='',
                        unzip_pswd='',
                        archive_format='7z',
                    )

                    # Register task BEFORE launching to prevent race condition with dashboard update
                    # (Dashboard needs to see all tasks immediately when force_update_summary is called)
                    await TASK_QUEUE.add_task(sub_task)

                    # Launch task asynchronously
                    log.info(f"Launching parallel task {idx}/{len(links)}: {sub_task.get_short_id()}")
                    launched_tasks.append(sub_task.get_short_id())

                    # Launch parallel task (Tracked)
                    # Note: skip_registration=True to avoid double-add inside run_parallel_task
                    TASK_QUEUE.create_background_task(
                        run_parallel_task(client, message, sub_task, skip_registration=True),
                        name=f"task-{sub_task.get_short_id()}"
                    )

                log.info(f"✅ Launched {len(launched_tasks)} parallel tasks: {launched_tasks}")

                # Update dashboard to show all newly launched tasks with progress bars
                log.info(f"📊 Calling force_update_summary() to display dashboard (tasks registered: {TASK_QUEUE.get_task_count()})")
                result = await force_update_summary(client)
                if result:
                    log.info(f"✅ Dashboard updated successfully (message ID: {result.id})")
                else:
                    log.warning(f"⚠️ Dashboard update returned None (no tasks to display?)")

            elif choice == "parallel_seq":
                # User wants sequential (one by one) - continue with normal flow
                log.info(f"User chose SEQUENTIAL downloads for {len(links)} links")

                # ... setup task_ctx ...

                # Launch parallel task (Tracked)
                TASK_QUEUE.create_background_task(
                    run_parallel_task(client, message, task_ctx),
                    name=f"task-{task_ctx.get_short_id()}"
                )

            return  # Exit callback handler

        # --- Service Selection ---
        if query_data.startswith("service_"):
            await callback_query.answer() # Acknowledge first
            service = query_data.split("_", 1)[1]
            log.info(f"User selected service: {service}")
            setup_session = await _update_setup_session(user_id, service_type=service)
            current_mode = setup_session.get("mode") or BOT.Mode.mode

            # Delete the service selection message AFTER processing choice
            try:
                await message.delete()
            except Exception as e:
                log.warning(f"Could not delete service selection message: {e}")


            filenames_needed_choice = service in ["Debrid", "bitso", "nzbcloud"]
            # Downloadly and direct don't need filename choice, will auto-extract

            if filenames_needed_choice:
                log.info(f"Asking filename option for {service.capitalize()}")
                await ask_filename_option(client, chat_id, service.capitalize()) # Pass chat_id
            else:
                # No filename choice needed for this service
                log.info(f"Service '{service}' selected. Proceeding to ask leech type.")
                await ask_leech_type(client, chat_id, current_mode)

        # --- Upload Destination Selection (Google Drive or Local Mirror) ---
        elif query_data.startswith("destination_"):
            await callback_query.answer()
            destination = query_data.split("_", 1)[1]
            log.info(f"User selected upload destination: {destination}")

            # Set the mode based on user's choice
            if destination == "gdrive":
                selected_mode = "gdrive"
                log.info("Mode set to 'gdrive' for Google Drive upload")
            elif destination == "mirror":
                selected_mode = "mirror"
                log.info("Mode set to 'mirror' for local Colab mirror")
            else:
                log.error(f"Unknown destination: {destination}")
                await callback_query.answer("Unknown destination!", show_alert=True)
                return

            pending_service = None
            pending_short_id = None
            async with user_tasks_lock:
                pending_task = user_tasks.get(user_id)
                if pending_task:
                    pending_task.mode = selected_mode
                    pending_service = pending_task.service_type
                    pending_short_id = pending_task.get_short_id()

            if destination == "gdrive":
                text = build_link_prompt("Upload to Google Drive", task_id=pending_short_id)
            else:
                text = build_link_prompt("Upload to Local Mirror", task_id=pending_short_id)

            await _update_setup_session(
                user_id,
                mode=selected_mode,
                source_links=[],
                service_type=pending_service,
                filenames=[],
                custom_name=BOT.Options.custom_name,
                zip_pswd=BOT.Options.zip_pswd,
                unzip_pswd=BOT.Options.unzip_pswd,
                archive_format=BOT.Options.archive_format if hasattr(BOT.Options, "archive_format") else "7z",
            )

            # Delete the destination selection message
            try:
                await message.delete()
            except Exception as e:
                log.warning(f"Could not delete destination selection message: {e}")

            # Send prompt message to collect links (similar to task_starter behavior)
            try:
                await _clear_source_waiting(client, user_id)
                prompt_msg = await client.send_message(
                    chat_id,
                    text,
                    parse_mode=enums.ParseMode.HTML,
                )
                await _set_source_waiting(user_id, chat_id, prompt_msg.id)
                log.info(f"Link collection prompt sent for {destination} destination")
            except Exception as e:
                log.error(f"Failed to send link prompt: {e}", exc_info=True)
                await _clear_setup_session(user_id)
                await _send_generic_error(client, chat_id, "send the prompt")

        # --- Filename Options ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE 'if' ABOVE >>>
        elif query_data.startswith("fn_"):
            await callback_query.answer()
            # Make sure service_type and fn_choice parsing is correct
            parts = query_data.split("_")
            if len(parts) < 3:
                 log.error(f"Invalid fn_ query data format: {query_data}")
                 await callback_query.answer("Internal error parsing choice.", show_alert=True)
                 return

            service_type = parts[1] # e.g., 'Debrid' or 'bitso'
            fn_choice = parts[2]    # e.g., 'extract' or 'manual'
            normalized_service = _normalize_filename_service(service_type)
            setup_session = await _get_setup_session(user_id) or {}
            source_links = list(setup_session.get("source_links", []))
            current_mode = setup_session.get("mode") or BOT.Mode.mode

            if fn_choice == "extract":
                log.info(f"User chose extract filenames for {normalized_service}.")
                await _clear_filename_reply_waiting(client, chat_id, user_id)
                extracted_filenames = []
                if not source_links:
                    await message.edit_text("❌ Error: No links found.")
                    await _clear_setup_session(user_id)
                    return

                log.info(f"Extracting filenames for {len(source_links)} links...")
                all_extracted = True # Flag to track success
                for i, link in enumerate(source_links):
                    extracted_name = await extract_filename_from_url(link) # Use await
                    if extracted_name:
                        cleaned = apply_dot_style(clean_filename(extracted_name))
                        if cleaned: # Ensure cleaning didn't result in None
                             extracted_filenames.append(cleaned)
                             log.debug(f"Extracted and cleaned name for link {i+1}: {cleaned}")
                        else:
                             log.warning(f"Filename invalid after cleaning for link {i+1}: {link}. Aborting.")
                             await message.edit_text(f"❌ Error: Invalid filename after cleaning link #{i+1}. Task Cancelled.")
                             all_extracted = False; break # Stop loop
                    else:
                        log.warning(f"Failed to extract filename for link {i+1}: {link}. Aborting.")
                        await message.edit_text(f"❌ Error extracting filename for link #{i+1}. Task Cancelled.")
                        all_extracted = False; break # Stop loop

                if all_extracted:
                    await _update_setup_session(
                        user_id,
                        service_type=normalized_service,
                        source_links=source_links,
                        filenames=extracted_filenames,
                    )
                    log.info(f"Extraction success: {len(extracted_filenames)} filenames.")
                    # Check if message still exists before deleting
                    if message: await message.delete() # Delete filename option message
                    await ask_leech_type(client, chat_id, current_mode) # Ask next step
                else:
                    # Extraction failed, reset relevant states
                    TaskError.reset()
                    TRANSFER.reset()
                    await _clear_setup_session(user_id)

            elif fn_choice == "manual":
                log.info(f"User chose manual filenames for {normalized_service}.")
                expected_count = len(source_links)
                if expected_count == 0:
                    await message.edit_text("❌ Error: No links found.")
                    await _clear_setup_session(user_id)
                    return
                prompt_text = build_manual_filenames_prompt(normalized_service, expected_count)
                try:
                    # Send the prompt
                    await _clear_filename_reply_waiting(client, chat_id, user_id)
                    prompt_msg = await client.send_message(
                        chat_id,
                        prompt_text,
                        parse_mode=enums.ParseMode.HTML,
                    )
                    await _set_filename_reply_waiting(
                        user_id=user_id,
                        prompt_message_id=prompt_msg.id,
                        service_type=normalized_service,
                        source_links=source_links,
                    )
                    # Check if message still exists before deleting
                    if message: await message.delete() # Delete the button message
                except Exception as e:
                    log.error(f"Failed to send manual filename prompt: {e}")
                    if message: await _send_generic_error(client, chat_id, "ask for filenames")  # Use message if possible

            else:
                log.warning(f"Unknown filename choice: {fn_choice}")
                if message: await message.edit_text("⚠️ Unknown filename option.")

        # --- Leech Type Selection ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE 'if' AND 'elif' ABOVE >>>
        elif query_data.startswith("leechtype_"):
            await callback_query.answer()
            leech_type = query_data.split("_", 1)[1]
            log.info(f"User selected leech type: {leech_type}")
            setup_session = await _get_setup_session(user_id)
            source_links = list(setup_session.get("source_links", [])) if setup_session else []
            if not source_links:
                await client.send_message(chat_id, "❌ Setup state expired. Start again with /tupload, /gdupload, or /drupload.")
                await _clear_setup_session(user_id)
                return

            task_ctx = create_task_context(
                user_id=user_id,
                chat_id=chat_id,
                mode=setup_session.get("mode") if setup_session else "leech"
            )
            task_ctx.mode_type = leech_type
            task_ctx.service_type = setup_session.get("service_type") if setup_session else None

            if message: await message.delete() # Delete leech type selection message

            log.info("Proceeding to start task via TaskContext...")
            try:
                status_msg_obj = await client.send_message(
                    OWNER,
                    "<code>#STARTING_TASK</code>\n\n<b>Task commencing...</b>",
                    reply_markup=keyboard(),
                    parse_mode=enums.ParseMode.HTML,
                )
                task_ctx.status_msg = status_msg_obj
            except Exception as start_err:
                log.error(f"Failed send status msg: {start_err}", exc_info=True)
                if message: await client.send_message(chat_id, "❌ Failed initialize task status.")
                await _clear_setup_session(user_id)
                return

            _prepare_task_context(
                task_ctx=task_ctx,
                source_links=source_links,
                filenames=list(setup_session.get("filenames", [])) if setup_session else [],
                custom_name=setup_session.get("custom_name", "") if setup_session else "",
                zip_pswd=setup_session.get("zip_pswd", "") if setup_session else "",
                unzip_pswd=setup_session.get("unzip_pswd", "") if setup_session else "",
                archive_format=setup_session.get("archive_format", "7z") if setup_session else "7z",
            )

            await _clear_filename_reply_waiting(client, chat_id, user_id)
            await _clear_password_reply_prompt(client, user_id)
            await _clear_settings_reply_waiting(client, chat_id, user_id)
            await _clear_setup_session(user_id)

            async_task = TASK_QUEUE.create_background_task(
                run_parallel_task(client, message, task_ctx),
                name=f"task-{task_ctx.get_short_id()}"
            )
            task_ctx.async_task = async_task
            _attach_task_exception_handler(async_task, task_ctx)

        # --- REMOVED Password Skipping Callbacks ---
        # Assuming passwords are now handled via commands only

        # --- Settings Callbacks ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE PREVIOUS BLOCKS >>>
        # Add settings callbacks here with correct indentation
        # Example:
        elif query_data == "setting_refresh":
             await callback_query.answer("Refreshing settings...")
             await send_settings(client, message, msg_id, False)
        elif query_data == "media":
             BOT.Options.stream_upload = True; BOT.Setting.stream_upload = "Media"
             await callback_query.answer("Uploading As Media", show_alert=False)
             await send_settings(client, message, msg_id, False)
        elif query_data == "document":
             BOT.Options.stream_upload = False; BOT.Setting.stream_upload = "Document"
             await callback_query.answer("Uploading As Document", show_alert=False)
             await send_settings(client, message, msg_id, False)
        elif query_data == "video":
             await callback_query.answer("Video toggles are not available in this menu yet.", show_alert=True)
        elif query_data == "caption":
             await callback_query.answer("Caption style is fixed in this build.", show_alert=True)
        elif query_data == "thumb":
             await callback_query.answer("Send a photo in this chat to set thumbnail.", show_alert=True)
        elif query_data == "set-prefix":
             await callback_query.answer()
             await _clear_settings_reply_waiting(client, chat_id, user_id)
             prompt_msg = await client.send_message(
                 chat_id,
                 "Reply to this message with the new prefix text.\nReply with '-' to clear it.",
             )
             await _set_settings_reply_waiting(
                 user_id=user_id,
                 prompt_message_id=prompt_msg.id,
                 setting_key="prefix",
                 settings_message_id=msg_id,
             )
        elif query_data == "set-suffix":
             await callback_query.answer()
             await _clear_settings_reply_waiting(client, chat_id, user_id)
             prompt_msg = await client.send_message(
                 chat_id,
                 "Reply to this message with the new suffix text.\nReply with '-' to clear it.",
             )
             await _set_settings_reply_waiting(
                 user_id=user_id,
                 prompt_message_id=prompt_msg.id,
                 setting_key="suffix",
                 settings_message_id=msg_id,
             )
        # ... add other settings callbacks like "video", "caption", "thumb", "set-prefix", "set-suffix", "close", "back" ...
        # Ensure they all start with 'elif' and have the same indentation as the main 'if'/'elif' blocks
        elif query_data == "close":
            await callback_query.answer("Settings closed")
            await message.delete()
        elif query_data == "back":
            await callback_query.answer()
            await send_settings(client, message, msg_id, False)
        elif query_data == "settings_back":
            await callback_query.answer()
            await send_settings(client, message, msg_id, False)
        elif query_data == "page_info":
            await callback_query.answer("Page info", show_alert=False)
        elif query_data == "pause" or query_data.startswith("pause:"):
            await callback_query.answer("Pause is not implemented yet.", show_alert=True)

        # --- Task Cancellation ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE PREVIOUS BLOCKS >>>
        elif query_data == "cancel" or query_data.startswith("cancel:"):
            # Parse callback data
            task_ctx = None
            if query_data.startswith("cancel:"):
                # Multi-task cancellation: accept either short ID or full task UUID.
                task_token = query_data.split(":", 1)[1].strip()

                # Find task by short ID or full ID for backward compatibility.
                all_tasks = await TASK_QUEUE.get_all_tasks()
                for task_id, task in all_tasks.items():
                    short_id = task.get_short_id()
                    full_id = str(task.task_id)
                    if (
                        task_token == short_id
                        or task_token == full_id
                        or full_id.startswith(task_token)
                        or task_token.startswith(short_id)
                    ):
                        task_ctx = task
                        break

                if not task_ctx:
                    log.warning(
                        f"Cancel requested for token '{task_token}' but no direct task match found; trying context fallback."
                    )

                if task_ctx:
                    log.info(
                        f"Multi-task cancellation requested for task {task_ctx.get_short_id()}"
                    )
            else:
                # Legacy single-task cancellation
                log.info("Legacy task cancellation requested by user via button.")

            try:
                await callback_query.answer("Cancelling...")
            except Exception:
                pass

            if task_ctx:
                # Multi-task mode: cancel specific task
                log.info(f"Calling cancelTask for task {task_ctx.get_short_id()}")
                await cancelTask("User pressed Cancel button.", task_ctx=task_ctx)
                # Remove from queue
                await TASK_QUEUE.remove_task(task_ctx.task_id)
                # Update summary dashboard
                await force_update_summary(client)
            else:
                setup_session = await _get_setup_session(user_id)
                all_tasks = await TASK_QUEUE.get_all_tasks()
                matched_task = None
                for candidate in all_tasks.values():
                    if user_id != OWNER and candidate.user_id != user_id:
                        continue
                    if candidate.status_msg and message and candidate.status_msg.id == message.id:
                        matched_task = candidate
                        break

                if matched_task:
                    log.info(f"Cancelling inferred task from callback message: {matched_task.get_short_id()}")
                    await cancelTask("User pressed Cancel button.", task_ctx=matched_task)
                    await TASK_QUEUE.remove_task(matched_task.task_id)
                    await force_update_summary(client)
                elif setup_session:
                    log.info("Cancelling task during setup phase (setup session present).")
                    if message: await message.delete()
                    TaskError.reset(); TRANSFER.reset()
                    await _clear_setup_session(user_id)
                    await _clear_filename_reply_waiting(client, chat_id, user_id)
                else:
                    user_active_tasks = [
                        candidate for candidate in all_tasks.values()
                        if candidate.user_id == user_id or user_id == OWNER
                    ]
                    if len(user_active_tasks) == 1:
                        only_task = user_active_tasks[0]
                        log.info(f"Cancelling single active task for user: {only_task.get_short_id()}")
                        await cancelTask("User pressed Cancel button.", task_ctx=only_task)
                        await TASK_QUEUE.remove_task(only_task.task_id)
                        await force_update_summary(client)
                    elif len(user_active_tasks) > 1:
                        log.info("Cancel pressed with multiple active tasks; requiring explicit selection.")
                        await client.send_message(chat_id, "Multiple active tasks found. Use /cancel to select one.")
                    else:
                        log.info("Cancel pressed but no task/setup active.")
                        if message: await message.delete()

            # Reset extract waiting state for this user if active
            if await _is_extract_waiting(user_id):
                log.info(f"Resetting extract waiting state for user {user_id}")
                await _clear_extract_waiting(client, chat_id, user_id)
            await _set_mindvalley_waiting(user_id, False)
            await _set_nzb_waiting(user_id, False)
            await _clear_source_waiting(client, user_id)
            await _clear_filename_reply_waiting(client, chat_id, user_id)
            await _clear_password_reply_prompt(client, user_id)
            await _clear_settings_reply_waiting(client, chat_id, user_id)
            await _clear_setup_session(user_id)
        elif query_data == "cancel_all_tasks":
            all_tasks = await TASK_QUEUE.get_all_tasks()
            if not all_tasks:
                await callback_query.answer("No active tasks to cancel.", show_alert=True)
                return
            await callback_query.answer()
            confirm_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Confirm Cancel All", callback_data="cancel_all_tasks_confirm"),
                    InlineKeyboardButton("Keep Running", callback_data="cancel_all_tasks_abort"),
                ]
            ])
            await client.send_message(
                chat_id,
                f"Cancel all active tasks ({len(all_tasks)})?",
                reply_markup=confirm_keyboard,
            )
        elif query_data == "cancel_all_tasks_abort":
            await callback_query.answer("No tasks were canceled.", show_alert=True)
            if message:
                try:
                    await message.delete()
                except Exception:
                    pass
        elif query_data == "cancel_all_tasks_confirm":
            all_tasks = await TASK_QUEUE.get_all_tasks()
            if not all_tasks:
                await callback_query.answer("No active tasks to cancel.", show_alert=True)
                return
            await callback_query.answer("Cancelling all tasks...", show_alert=True)

            log.info(f"Bulk cancel requested: {len(all_tasks)} tasks")
            for task_ctx in list(all_tasks.values()):
                try:
                    await cancelTask("User pressed Cancel All.", task_ctx=task_ctx)
                except Exception as cancel_err:
                    log.warning(f"Failed to cancel task {task_ctx.get_short_id()}: {cancel_err}")
                await TASK_QUEUE.remove_task(task_ctx.task_id)

            await force_update_summary(client)

            # Reset extract waiting state for this user if active
            if await _is_extract_waiting(user_id):
                log.info(f"Resetting extract waiting state for user {user_id}")
                await _clear_extract_waiting(client, chat_id, user_id)
            await _set_mindvalley_waiting(user_id, False)
            await _set_nzb_waiting(user_id, False)
            await _clear_source_waiting(client, user_id)
            await _clear_filename_reply_waiting(client, chat_id, user_id)
            await _clear_password_reply_prompt(client, user_id)
            await _clear_settings_reply_waiting(client, chat_id, user_id)
            await _clear_setup_session(user_id)
            if message:
                try:
                    await message.delete()
                except Exception:
                    pass

        # --- Fallback for Unknown Callbacks ---
        # <<< THIS BLOCK'S INDENTATION MUST MATCH THE PREVIOUS BLOCKS >>>
        else:
            log.warning(f"Unhandled callback query data: {query_data}")
            await callback_query.answer("Unknown action!", show_alert=True)

    # This 'except' MUST be aligned with the 'try' block at the start of the function
    except Exception as e:
        log.error(f"Error handling callback {query_data}: {e}", exc_info=True)
        try:
            await callback_query.answer("An error occurred!", show_alert=True)
        except Exception as callback_answer_err:
            log.debug(f"Could not send callback error answer: {callback_answer_err}")
        # Reset shared runtime objects used by legacy code paths.
        if TaskError: TaskError.reset()
        if TRANSFER: TRANSFER.reset()
        await _clear_setup_session(user_id)
        await _set_mindvalley_waiting(user_id, False)
        await _set_nzb_waiting(user_id, False)
        await _clear_source_waiting(client, user_id)
        await _clear_filename_reply_waiting(client, chat_id, user_id)
        await _clear_password_reply_prompt(client, user_id)
        await _clear_settings_reply_waiting(client, chat_id, user_id)

# --- End handle_options function ---
# Image Handler (handle_image - remains the same)
@colab_bot.on_message(filters.photo & filters.private)
async def handle_image(client, message):
    log.info(f"Received photo from user {message.from_user.id}, setting thumbnail.")
    msg = await message.reply_text("<i>Trying To Save Thumbnail...</i>", parse_mode=enums.ParseMode.HTML)
    success = await setThumbnail(message)
    if success: await msg.edit_text("<b>Thumbnail Updated</b> ✅", parse_mode=enums.ParseMode.HTML); await message.delete()
    else: await msg.edit_text("Could not set thumbnail.", parse_mode=enums.ParseMode.HTML)
    await sleep(5); await message_deleter(None, msg)

# Other Command Handlers (setname, zipaswd, unzipaswd, help - remain the same)
@colab_bot.on_message(filters.command("setname") & filters.private)
async def custom_name(client, message):
    global BOT; log.info("Received /setname command.")
    if len(message.command) != 2: msg = await message.reply_text("Send\n/setname <code>custom_filename.extension</code>", quote=True, parse_mode=enums.ParseMode.HTML)
    else: BOT.Options.custom_name = message.command[1]; msg = await message.reply_text("Custom Name Set!"); log.info(f"Custom name: {BOT.Options.custom_name}")
    await sleep(15); await message_deleter(message, msg)
@colab_bot.on_message(filters.command("zipaswd") & filters.private)
async def zip_pswd(client, message):
    global BOT; log.info("Received /zipaswd command.")
    if len(message.command) != 2: msg = await message.reply_text("Send\n/zipaswd <code>password</code>", quote=True, parse_mode=enums.ParseMode.HTML)
    else: BOT.Options.zip_pswd = message.command[1]; msg = await message.reply_text("Zip Password Set!"); log.info("Zip password set.")
    await sleep(15); await message_deleter(message, msg)
@colab_bot.on_message(filters.command("unzipaswd") & filters.private)
async def unzip_pswd(client, message):
    global BOT; log.info("Received /unzipaswd command.")
    if len(message.command) != 2: msg = await message.reply_text("Send\n/unzipaswd <code>password</code>", quote=True, parse_mode=enums.ParseMode.HTML)
    else: BOT.Options.unzip_pswd = message.command[1]; msg = await message.reply_text("Unzip Password Set!"); log.info("Unzip password set.")
    await sleep(15); await message_deleter(message, msg)
@colab_bot.on_message(filters.command("archivetype") & filters.private)
async def archive_type(client, message):
    global BOT; log.info("Received /archivetype command.")
    if len(message.command) != 2:
        msg = await message.reply_text("Send\n/archivetype <code>zip</code>, <code>rar</code>, or <code>7z</code>", quote=True, parse_mode=enums.ParseMode.HTML)
    else:
        format_choice = message.command[1].lower()
        if format_choice in ["zip", "rar", "7z"]:
            BOT.Options.archive_format = format_choice
            msg = await message.reply_text(
                f"Archive format set to <code>{format_choice.upper()}</code>.",
                parse_mode=enums.ParseMode.HTML,
            )
            log.info(f"Archive format set to: {format_choice}")
        else:
            msg = await message.reply_text("Invalid format! Use <code>zip</code>, <code>rar</code>, or <code>7z</code>", quote=True, parse_mode=enums.ParseMode.HTML)
    await sleep(15); await message_deleter(message, msg)

# Helper function to perform extraction
async def _perform_extraction(archive_path, file_filter=None, task_ctx=None):
    """
    Core extraction logic with streaming upload - returns (success: bool, message: str)
    Extracts files one-by-one, uploads to Telegram, then deletes temp file
    """
    from .utility.converters import extract_and_upload_streaming
    import os

    # Determine archive type
    ext = os.path.splitext(archive_path)[1].lower()
    filename = os.path.basename(archive_path)

    # Start extraction based on archive type
    try:
        if ext == ".rar" or ".part" in filename.lower():
            log.info(f"Starting streaming extract+upload for RAR: {archive_path}")

            # Use streaming extract+upload (extracts one file, uploads it, deletes temp file)
            success = await extract_and_upload_streaming(
                rar_filepath=archive_path,
                password=BOT.Options.unzip_pswd if BOT.Options.unzip_pswd else None,
                file_filter=file_filter,
                task_ctx=task_ctx
            )

            if success:
                msg = (
                    f"✅ Extraction + Upload complete!\n\n"
                    f"📁 Archive: <code>{filename}</code>\n"
                    f"⬆️ All files uploaded to Telegram\n"
                    f"🗑️ Temp files cleaned up"
                )
                log.info(f"Streaming extract+upload successful: {archive_path}")
                return True, msg
            else:
                log.error(f"Streaming extract+upload failed: {archive_path}")
                return False, f"❌ Extraction/Upload failed!\n\nCheck logs for details."

        elif ext == ".zip":
            log.error(f"ZIP streaming not yet implemented: {archive_path}")
            return False, f"❌ ZIP streaming extract+upload not yet implemented\n\nUse RAR archives for now"
        else:
            return False, f"❌ Unsupported format: {ext}\n\nSupported: .rar (streaming), .zip (coming soon)"

    except Exception as e:
        log.error(f"Extraction error: {e}", exc_info=True)
        return False, f"❌ Extraction error: {str(e)[:100]}"

# Helper function to process reply-to-document extraction
async def _process_extract_reply(client, message):
    """Handle extraction when user replies to a document"""
    global BOT, Paths
    import os
    import random
    import aiohttp
    import aiofiles
    from .utility.task_manager import thumbnail_urls
    from .utility.helper import keyboard

    # Parse file filter from command if provided
    file_filter = None
    if len(message.command) > 1:
        extensions_str = ' '.join(message.command[1:])
        extensions = [ext.strip() for ext in extensions_str.split(',')]
        file_filter = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext.strip()]
        log.info(f"File filter applied: {file_filter}")

    try:
        reply_msg = await message.reply_text("⬇️ Downloading archive...")
        file_path = await message.reply_to_message.download(
            file_name=os.path.join(Paths.down_path, message.reply_to_message.document.file_name)
        )

        # Download random thumbnail
        hero_image_path = Paths.HERO_IMAGE
        download_success = False

        if thumbnail_urls:
            try:
                chosen_url = random.choice(thumbnail_urls)
                log.info(f"Downloading thumbnail for extraction: {chosen_url}")

                async with aiohttp.ClientSession() as session:
                    async with session.get(chosen_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                        if response.status == 200:
                            async with aiofiles.open(hero_image_path, mode='wb') as f:
                                while True:
                                    chunk = await response.content.read(1024)
                                    if not chunk:
                                        break
                                    await f.write(chunk)
                            download_success = True
            except Exception as e:
                log.warning(f"Thumbnail download failed: {e}")

        # Determine thumbnail path
        if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
            thumb_path = Paths.THMB_PATH
        elif download_success and os.path.exists(Paths.HERO_IMAGE):
            thumb_path = Paths.HERO_IMAGE
        elif os.path.exists(Paths.DEFAULT_HERO):
            thumb_path = Paths.DEFAULT_HERO
        else:
            thumb_path = None

        # Create extraction status message
        user_id = message.from_user.id if message.from_user else message.chat.id
        extract_task_ctx = create_task_context(
            user_id=user_id,
            chat_id=message.chat.id,
            mode="leech"
        )
        extract_task_ctx.service_type = "extract"
        extract_task_ctx.mode_type = "extract"

        filename = os.path.basename(file_path)
        filter_text = f" (filter: {', '.join(file_filter)})" if file_filter else ""

        status_text = (
            f"<b>📂 Archive Extraction »</b>\n\n"
            f"<b>📦 Archive:</b> <code>{filename}</code>\n"
            f"<b>📂 Output:</b> <code>{Paths.temp_unzip_path}</code>{filter_text}\n\n"
            f"<i>Initializing...</i>"
        )

        # Replace reply message with photo message
        await reply_msg.delete()

        if thumb_path and os.path.exists(thumb_path):
            status_msg = await client.send_photo(
                message.chat.id,
                photo=thumb_path,
                caption=status_text,
                reply_markup=keyboard()
            )
        else:
            status_msg = await message.reply_text(status_text)

        # Use per-task status message to avoid global cross-user collisions
        extract_task_ctx.status_msg = status_msg

        success, result_msg = await _perform_extraction(file_path, file_filter, task_ctx=extract_task_ctx)

        # Update final message
        if hasattr(status_msg, 'photo') and status_msg.photo:
            await status_msg.edit_caption(caption=result_msg)
        else:
            await status_msg.edit_text(result_msg)

    except Exception as e:
        log.error(f"Failed to download/extract replied file: {e}")
        await _reply_with_generic_error(message, "extract the replied archive")

# Helper function to handle extract path input from user
async def _handle_extract_input(client, message):
    """Process user's path input after /extract command"""
    global BOT, Paths
    import os
    import re
    import random
    import aiohttp
    import aiofiles
    from .utility.task_manager import thumbnail_urls
    from .utility.helper import keyboard

    # Reset waiting state for this user and clean up their prompt.
    await _clear_extract_waiting(client, message.chat.id, _extract_user_id(message))

    # Parse input: "<path>" or "<path> <filter>"
    input_text = message.text.strip() if message.text else ""
    if not input_text:
        await message.reply_text("❌ Input cannot be empty. Use /extract to try again.")
        return

    # Split into path and optional filter
    parts = input_text.split(None, 1)  # Split on first whitespace
    archive_path = parts[0]
    file_filter = None

    if len(parts) > 1:
        # User provided filter
        extensions_str = parts[1]
        extensions = [ext.strip() for ext in extensions_str.split(',')]
        file_filter = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext.strip()]
        log.info(f"File filter applied: {file_filter}")

    # Validate path exists
    if not os.path.exists(archive_path) or not os.path.isfile(archive_path):
        await message.reply_text(
            f"❌ File not found: <code>{archive_path}</code>\n\nUse /extract to try again.",
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # Auto-detect first part for multi-part RAR (handles formats like part01.rar or part01_Downloadly.ir.rar)
    if '.part' in archive_path.lower() and archive_path.lower().endswith('.rar'):
        # Extract base name and suffix (e.g., "_Downloadly.ir.rar" or ".rar")
        match = re.search(r'(.*)\.part\d+(.*\.rar)$', archive_path, flags=re.IGNORECASE)
        if match:
            base = match.group(1)
            suffix = match.group(2)  # Captures everything after partXX (e.g., ".rar" or "_Downloadly.ir.rar")

            potential_first_parts = [
                f"{base}.part01{suffix}",
                f"{base}.part001{suffix}",
                f"{base}.part1{suffix}"
            ]
            for first_part in potential_first_parts:
                if os.path.exists(first_part):
                    archive_path = first_part
                    log.info(f"Multi-part RAR detected, using first part: {archive_path}")
                    break

    # Download random thumbnail (following Mindvalley pattern)
    hero_image_path = Paths.HERO_IMAGE
    download_success = False

    if thumbnail_urls:
        try:
            chosen_url = random.choice(thumbnail_urls)
            log.info(f"Downloading thumbnail for extraction: {chosen_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(chosen_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        async with aiofiles.open(hero_image_path, mode='wb') as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                await f.write(chunk)
                        download_success = True
                        log.info(f"Thumbnail downloaded to {hero_image_path}")
        except Exception as e:
            log.warning(f"Thumbnail download failed: {e}")

    # Determine thumbnail path (priority: custom > random > default)
    if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
        thumb_path = Paths.THMB_PATH
    elif download_success and os.path.exists(Paths.HERO_IMAGE):
        thumb_path = Paths.HERO_IMAGE
    elif os.path.exists(Paths.DEFAULT_HERO):
        thumb_path = Paths.DEFAULT_HERO
    else:
        thumb_path = None

    # Create status message
    user_id = message.from_user.id if message.from_user else message.chat.id
    extract_task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="leech"
    )
    extract_task_ctx.service_type = "extract"
    extract_task_ctx.mode_type = "extract"

    filename = os.path.basename(archive_path)
    filter_text = f" (filter: {', '.join(file_filter)})" if file_filter else ""

    status_text = (
        f"<b>📂 Archive Extraction »</b>\n\n"
        f"<b>📦 Archive:</b> <code>{filename}</code>\n"
        f"<b>📂 Output:</b> <code>{Paths.temp_unzip_path}</code>{filter_text}\n\n"
        f"<i>Initializing...</i>"
    )

    # Send message with thumbnail
    if thumb_path and os.path.exists(thumb_path):
        status_msg = await client.send_photo(
            message.chat.id,
            photo=thumb_path,
            caption=status_text,
            reply_markup=keyboard()
        )
    else:
        status_msg = await message.reply_text(status_text)

    # Use per-task status message to avoid global cross-user collisions
    extract_task_ctx.status_msg = status_msg

    # Perform extraction
    success, result_msg = await _perform_extraction(archive_path, file_filter, task_ctx=extract_task_ctx)

    # Update final message
    if hasattr(status_msg, 'photo') and status_msg.photo:
        await status_msg.edit_caption(caption=result_msg)
    else:
        await status_msg.edit_text(result_msg)

@colab_bot.on_message(filters.command("extract") & filters.private)
async def extract_archive(client, message):
    """
    Extract RAR/ZIP archive with optional file filtering

    Usage:
        /extract - Prompt for archive path
        /extract .mkv - Extract only .mkv files from recent download
        /extract .mkv,.mp4,.avi - Extract multiple file types
        /extract /path/to/file.rar - Extract from specific path
        /extract /path/to/file.rar .mkv - Extract specific path with filter
        Reply to archive: Reply to RAR/ZIP file with /extract [filter]
    """
    global BOT, Paths
    from .utility.converters import extract_rar_streaming, extract_zip_streaming
    from .utility.task_manager import thumbnail_urls
    from .utility.helper import keyboard
    import os
    import random
    import aiohttp
    import aiofiles

    log.info(f"Received /extract from {message.from_user.id}")

    # Check if user is replying to a document (takes priority)
    if message.reply_to_message and message.reply_to_message.document:
        # Process reply-to-document immediately with optional filter from command
        await _process_extract_reply(client, message)
        return

    # If no arguments provided, ask for path
    if len(message.command) == 1:
        log.info("No arguments provided, setting extract_waiting=True and prompting for path")
        help_text = build_extract_archive_prompt()
        prompt_msg = await message.reply_text(
            help_text,
            parse_mode=enums.ParseMode.HTML,
        )
        await _set_extract_waiting(_extract_user_id(message), prompt_msg.id)
        return

    # Parse command arguments (file path and/or filters)
    file_filter = None
    explicit_path = None

    if len(message.command) > 1:
        # Check if first argument is a file path
        first_arg = message.command[1]

        # Detect if it's a file path (contains / or \ or ends with archive extension)
        if ('/' in first_arg or '\\' in first_arg or
            first_arg.lower().endswith(('.rar', '.zip', '.part01.rar', '.part001.rar', '.part1.rar'))):
            explicit_path = first_arg
            log.info(f"Explicit path provided: {explicit_path}")

            # Check if there are additional arguments for file filter
            if len(message.command) > 2:
                # Remaining arguments are file filters
                extensions_str = ' '.join(message.command[2:])
                extensions = [ext.strip() for ext in extensions_str.split(',')]
                file_filter = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext.strip()]
                log.info(f"File filter applied: {file_filter}")
        else:
            # First argument is a file filter, not a path
            extensions_str = ' '.join(message.command[1:])
            extensions = [ext.strip() for ext in extensions_str.split(',')]
            file_filter = [ext if ext.startswith('.') else f'.{ext}' for ext in extensions if ext.strip()]
            log.info(f"File filter applied: {file_filter}")

    # Try to find archive file
    archive_path = None

    # Method 0: Check if explicit path was provided
    if explicit_path:
        if os.path.exists(explicit_path) and os.path.isfile(explicit_path):
            archive_path = explicit_path
            log.info(f"Using explicit path: {archive_path}")

            # If it's a multi-part RAR but not the first part, try to find part01 (handles Downloadly format)
            if '.part' in archive_path.lower() and archive_path.lower().endswith('.rar'):
                # Extract base name and suffix (e.g., "_Downloadly.ir.rar" or ".rar")
                import re
                match = re.search(r'(.*)\.part\d+(.*\.rar)$', archive_path, flags=re.IGNORECASE)
                if match:
                    base = match.group(1)
                    suffix = match.group(2)  # Captures everything after partXX

                    # Try different naming conventions
                    potential_first_parts = [
                        f"{base}.part01{suffix}",
                        f"{base}.part001{suffix}",
                        f"{base}.part1{suffix}"
                    ]

                    for first_part in potential_first_parts:
                        if os.path.exists(first_part):
                            archive_path = first_part
                            log.info(f"Multi-part RAR detected, using first part: {archive_path}")
                            break
        else:
            await message.reply_text(
                f"❌ File not found: <code>{explicit_path}</code>",
                parse_mode=enums.ParseMode.HTML,
            )
            return

    # Method 1: Check for most recent archive in download directory
    if not archive_path and os.path.exists(Paths.down_path):
        try:
            # Find most recent .rar or .zip file
            archive_files = []
            for f in os.listdir(Paths.down_path):
                if f.lower().endswith(('.rar', '.zip', '.part01.rar', '.part001.rar', '.part1.rar')):
                    full_path = os.path.join(Paths.down_path, f)
                    if os.path.isfile(full_path):
                        archive_files.append((full_path, os.path.getmtime(full_path)))

            if archive_files:
                # Sort by modification time (most recent first)
                archive_files.sort(key=lambda x: x[1], reverse=True)
                archive_path = archive_files[0][0]
                log.info(f"Using most recent archive: {archive_path}")
        except Exception as e:
            log.error(f"Error finding archive: {e}")

    if not archive_path:
        # No archive found - prompt user to send path manually
        help_text = (
            "<b>No recent archive found in downloads.</b>\n\n"
            f"{build_extract_archive_prompt()}"
        )
        prompt_msg = await message.reply_text(
            help_text,
            parse_mode=enums.ParseMode.HTML,
        )
        await _set_extract_waiting(_extract_user_id(message), prompt_msg.id)
        return

    # Download random thumbnail
    hero_image_path = Paths.HERO_IMAGE
    download_success = False

    if thumbnail_urls:
        try:
            chosen_url = random.choice(thumbnail_urls)
            log.info(f"Downloading thumbnail for extraction: {chosen_url}")

            async with aiohttp.ClientSession() as session:
                async with session.get(chosen_url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status == 200:
                        async with aiofiles.open(hero_image_path, mode='wb') as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                await f.write(chunk)
                        download_success = True
                        log.info(f"Thumbnail downloaded to {hero_image_path}")
        except Exception as e:
            log.warning(f"Thumbnail download failed: {e}")

    # Determine thumbnail path (priority: custom > random > default)
    if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
        thumb_path = Paths.THMB_PATH
    elif download_success and os.path.exists(Paths.HERO_IMAGE):
        thumb_path = Paths.HERO_IMAGE
    elif os.path.exists(Paths.DEFAULT_HERO):
        thumb_path = Paths.DEFAULT_HERO
    else:
        thumb_path = None

    # Create status message
    user_id = message.from_user.id if message.from_user else message.chat.id
    extract_task_ctx = create_task_context(
        user_id=user_id,
        chat_id=message.chat.id,
        mode="leech"
    )
    extract_task_ctx.service_type = "extract"
    extract_task_ctx.mode_type = "extract"

    filename = os.path.basename(archive_path)
    filter_text = f" (filter: {', '.join(file_filter)})" if file_filter else ""

    status_text = (
        f"<b>📂 Archive Extraction »</b>\n\n"
        f"<b>📦 Archive:</b> <code>{filename}</code>\n"
        f"<b>📂 Output:</b> <code>{Paths.temp_unzip_path}</code>{filter_text}\n\n"
        f"<i>Initializing...</i>"
    )

    # Send message with thumbnail
    if thumb_path and os.path.exists(thumb_path):
        status_msg = await client.send_photo(
            message.chat.id,
            photo=thumb_path,
            caption=status_text,
            reply_markup=keyboard()
        )
    else:
        status_msg = await message.reply_text(status_text)

    # Use per-task status message to avoid global cross-user collisions
    extract_task_ctx.status_msg = status_msg

    # Perform extraction using helper function
    success, result_msg = await _perform_extraction(archive_path, file_filter, task_ctx=extract_task_ctx)

    # Update final message
    if hasattr(status_msg, 'photo') and status_msg.photo:
        await status_msg.edit_caption(caption=result_msg)
    else:
        await status_msg.edit_text(result_msg)

@colab_bot.on_message(filters.command("mindvalley") & filters.private)
async def mindvalley_download(client, message):
    """
    Download Mindvalley course streams from M3U8 URLs
    Usage: /mindvalley then send URLs on separate lines
    """
    global BOT
    log.info(f"Received /mindvalley from {message.from_user.id}")

    # Set bot state and mode
    BOT.Mode.mode = "leech"  # Use leech mode for proper completion message
    BOT.Mode.ytdl = False
    user_id = _extract_user_id(message)
    await _set_mindvalley_waiting(user_id, True)
    await _update_setup_session(
        user_id,
        mode="leech",
        service_type="mindvalley",
        source_links=[],
        filenames=[],
    )

    help_text = build_mindvalley_prompt()
    await _clear_source_waiting(client, user_id)
    prompt_msg = await task_starter(message, help_text)
    if prompt_msg:
        await _set_source_waiting(user_id, message.chat.id, prompt_msg.id)
    log.debug("/mindvalley: task_starter called, source prompt tracked per user")


# Handler for Mindvalley URLs and NZB URLs (when user sends URLs after commands)
# Exclude commands so they can be handled by specific command handlers
@colab_bot.on_message(filters.text & not_command_filter & filters.private)
async def handle_text_input(client, message):
    """Handle text input: Mindvalley M3U8 URLs, NZB URLs, etc."""
    global BOT, MSG, Messages, BotTimes

    input_user_id = _extract_user_id(message)

    # Check if waiting for NZB URL
    if await _is_nzb_waiting(input_user_id):
        log.info(f"Received NZB URL from {message.from_user.id}")

        # Check if message contains .nzb URL
        text = message.text.strip()
        if '.nzb' in text.lower():
            await _set_nzb_waiting(input_user_id, False)
            await _clear_setup_session(input_user_id)

            # Delete per-user help message.
            await _clear_source_waiting(client, _extract_user_id(message))

            # Extract URL (take first line if multiple)
            nzb_url = text.split('\n')[0].strip()

            # Validate URL format
            if not (nzb_url.startswith('http://') or nzb_url.startswith('https://')):
                await message.reply_text(
                    "❌ Invalid URL!\n\n"
                    "Please send a valid NZB download link starting with http:// or https://\n\n"
                    "Or upload a .nzb file instead.",
                    quote=True
                )
                await _set_nzb_waiting(input_user_id, False)
                return

            log.info(f"Downloading NZB from URL: {nzb_url}")

            try:
                # Download .nzb file from URL
                task_ctx = create_task_context(
                    user_id=message.from_user.id,
                    chat_id=message.chat.id,
                    mode="leech"
                )

                nzb_filename = nzb_url.split('/')[-1]
                if not nzb_filename.endswith('.nzb'):
                    nzb_filename = "download.nzb"

                nzb_path = os.path.join(task_ctx.down_path, nzb_filename)

                # Download file
                status_msg = await message.reply_text("⏳ Downloading .nzb file from URL...", quote=True)

                async with aiohttp.ClientSession() as session:
                    async with session.get(nzb_url, timeout=60) as response:
                        if response.status == 200:
                            content = await response.read()
                            with open(nzb_path, 'wb') as f:
                                f.write(content)
                            log.info(f"Downloaded .nzb file to: {nzb_path}")

                            # Delete status message
                            try:
                                await status_msg.delete()
                            except Exception as delete_err:
                                log.warning(f"Failed to delete NZB status message: {delete_err}")

                            # Process the downloaded NZB file
                            await handle_nzb_file(client, message, nzb_file_path=nzb_path)
                        else:
                            await status_msg.edit_text(f"❌ Failed to download NZB: HTTP {response.status}")
                            log.error(f"Failed to download NZB: HTTP {response.status}")

            except Exception as e:
                log.exception("Error downloading NZB from URL")
                await _reply_with_generic_error(message, "download NZB", quote=True)

            return  # Don't process further

        else:
            await message.reply_text(
                "❌ Please send a valid .nzb URL\n"
                "Example: https://example.com/file.nzb",
                quote=True
            )
            return

    # Check if we're waiting for Mindvalley URLs
    if not await _is_mindvalley_waiting(input_user_id):
        return  # Not in Mindvalley/NZB mode, let other handlers process this

    log.info(f"Received Mindvalley input from {message.from_user.id}")

    # Reset the flag
    await _set_mindvalley_waiting(input_user_id, False)
    await _clear_setup_session(input_user_id)

    # Delete the per-user help/request message.
    await _clear_source_waiting(client, _extract_user_id(message))

    # NEW: Create TaskContext for this download (enables parallel tasks)
    task_ctx = create_task_context(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        mode="leech"
    )
    task_ctx.service_type = "mindvalley"
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for Mindvalley download")

    try:
        input_text = message.text.strip()
        urls = []
        custom_title = None  # Store custom title from TITLE= line
        subtitle_only = False  # NEW: Flag for subtitle-only mode

        # Check if input is a gist URL
        if 'gist.githubusercontent.com' in input_text or 'gist.github.com' in input_text:
            log.info(f"Detected gist URL: {input_text}")

            # Convert to raw URL if needed
            raw_url = input_text
            if 'gist.github.com' in input_text and '/raw' not in input_text:
                # User sent the normal gist URL, convert to raw
                await message.reply_text(
                    f"⚠️ {build_raw_gist_warning()}",
                    quote=True,
                    parse_mode=enums.ParseMode.HTML,
                )
                return

            # Fetch content from gist
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(raw_url, timeout=20) as response:
                        response.raise_for_status()
                        gist_content = await response.text()

                        # Parse M3U8 URLs from gist
                        lines = gist_content.strip().split('\n')
                        for line in lines:
                            line = line.strip()

                            # Check for TITLE= line (case-insensitive)
                            if line.upper().startswith('TITLE='):
                                custom_title = line.split('=', 1)[1].strip()
                                log.info(f"Extracted custom title from gist: {custom_title}")
                                continue  # Skip this line, don't add to URLs

                            # NEW: Check for DOWNLOAD_TYPE=subtitle-only
                            if line.upper().startswith('DOWNLOAD_TYPE='):
                                download_type = line.split('=', 1)[1].strip().lower()
                                if download_type == 'subtitle-only' or download_type == 'subtitle_only':
                                    subtitle_only = True
                                    log.info("Subtitle-only mode enabled via DOWNLOAD_TYPE")
                                continue  # Skip this line, don't add to URLs

                            # Support both direct URLs and KEY=VALUE format
                            # Accept .m3u8 or .webvtt.m3u8 (for subtitles)
                            if '.m3u8' in line.lower() or '.webvtt' in line.lower():
                                if '=' in line:  # Format: VIDEO_URL=https://...
                                    url = line.split('=', 1)[1].strip()
                                else:  # Direct URL format
                                    url = line
                                urls.append(url)

                        log.info(f"Fetched {len(urls)} M3U8 URLs from gist")
            except Exception as fetch_err:
                log.error(f"Failed to fetch gist: {fetch_err}")
                await _reply_with_generic_error(message, "fetch the gist", quote=True)
                return

        # Direct M3U8 URLs input (including .webvtt.m3u8 for subtitles)
        elif '.m3u8' in input_text.lower() or '.webvtt' in input_text.lower() or input_text.upper().startswith('TITLE=') or input_text.upper().startswith('DOWNLOAD_TYPE='):
            lines = input_text.split('\n')
            for line in lines:
                line = line.strip()

                # Check for TITLE= line (case-insensitive)
                if line.upper().startswith('TITLE='):
                    custom_title = line.split('=', 1)[1].strip()
                    log.info(f"Extracted custom title from input: {custom_title}")
                    continue  # Skip this line, don't add to URLs

                # Check for DOWNLOAD_TYPE=subtitle-only
                if line.upper().startswith('DOWNLOAD_TYPE='):
                    download_type = line.split('=', 1)[1].strip().lower()
                    if download_type == 'subtitle-only' or download_type == 'subtitle_only':
                        subtitle_only = True
                        log.info("Subtitle-only mode enabled via DOWNLOAD_TYPE")
                    continue  # Skip this line, don't add to URLs

                # Accept M3U8 URLs (including .webvtt.m3u8 for subtitles)
                if line and ('.m3u8' in line.lower() or '.webvtt' in line.lower()):
                    urls.append(line)

            log.info(f"Parsed {len(urls)} direct M3U8 URLs")

        else:
            await message.reply_text("❌ Please send either M3U8 URLs or a raw gist URL.", quote=True)
            return

        if not urls:
            await message.reply_text("❌ No valid M3U8 URLs found. Please try again.", quote=True)
            return

        # Auto-detect subtitle-only mode if user sends a single subtitle URL
        if not subtitle_only and len(urls) == 1:
            url_lower = urls[0].lower()
            # Check if URL contains subtitle indicators
            if 'subtitle' in url_lower or 'webvtt' in url_lower or url_lower.endswith('.webvtt.m3u8'):
                subtitle_only = True
                log.info("Auto-detected subtitle-only mode from URL pattern")

        # Parse URLs based on mode
        if subtitle_only:
            # Subtitle-only mode: first (and only) URL is subtitle
            subtitle_url = urls[0] if len(urls) > 0 else None
            video_url = None
            audio_url = None

            # Validate subtitle URL (accepts .m3u8 or .webvtt.m3u8)
            if not subtitle_url or ('.m3u8' not in subtitle_url.lower() and '.webvtt' not in subtitle_url.lower()):
                await message.reply_text(
                    "❌ Invalid subtitle URL. Must be a valid M3U8 or WebVTT playlist URL (.m3u8 or .webvtt.m3u8).",
                    quote=True
                )
                return
        else:
            # Normal mode: video, optional audio, optional subtitle
            video_url = urls[0] if len(urls) > 0 else None
            audio_url = urls[1] if len(urls) > 1 else None
            subtitle_url = urls[2] if len(urls) > 2 else None

            # Validate video URL
            if not video_url or ('.m3u8' not in video_url.lower()):
                await message.reply_text(
                    "❌ Invalid video URL. First line must be a valid M3U8 playlist URL.",
                    quote=True
                )
                return

        # NEW: Create unique directories for this task
        os.makedirs(task_ctx.work_path, exist_ok=True)
        os.makedirs(task_ctx.down_path, exist_ok=True)
        log.info(f"Created task-specific directories: {task_ctx.work_path}")

        # Create downloader instance with task context
        downloader = MindvalleyDownloader(client, message, task_ctx)

        # Generate output filename
        if custom_title:
            # Use custom title from TITLE= line
            base_name = clean_filename(custom_title)
            # Apply dot style for consistency with other downloads
            base_name = apply_dot_style(base_name) if base_name else "mindvalley_course"
            # Ensure correct extension based on mode
            if subtitle_only:
                output_filename = base_name if base_name.lower().endswith('.vtt') else f"{base_name}.vtt"
            else:
                output_filename = base_name if base_name.lower().endswith('.mp4') else f"{base_name}.mp4"
            log.info(f"Using custom filename from title: {output_filename}")
        else:
            # Fallback to timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            if subtitle_only:
                output_filename = f"mindvalley_subtitle_{timestamp}.vtt"
            else:
                output_filename = f"mindvalley_course_{timestamp}.mp4"
            log.info(f"Using timestamp filename: {output_filename}")

        # Store URLs in task context
        task_ctx.source_urls = urls
        task_ctx.filenames = [output_filename]

        # Initialize status message for progress tracking
        if subtitle_only:
            status_text = (
                f"<b>Mindvalley Subtitle Download</b> [<code>{task_ctx.get_short_id()}</code>]\n\n"
                "<b>Subtitle:</b> ✅\n"
                "<b>Video:</b> ❌ (subtitle-only mode)\n"
                "<b>Audio:</b> ❌ (subtitle-only mode)\n\n"
                "<i>Download will start shortly...</i>"
            )
        else:
            status_text = (
                f"<b>Mindvalley Download Started</b> [<code>{task_ctx.get_short_id()}</code>]\n\n"
                "<b>Video:</b> ✅\n"
                f"<b>Audio:</b> {'✅' if audio_url else '❌ (using embedded audio)'}\n"
                f"<b>Subtitle:</b> {'✅' if subtitle_url else '❌'}\n\n"
                "<i>Download will start shortly...</i>"
            )

        # Download random thumbnail - use shared pool from task_manager
        # Import the full thumbnail collection (~472 URLs) instead of hardcoded subset
        from .utility.task_manager import thumbnail_urls

        # NEW: Use task-specific hero image path
        hero_image_path = task_ctx.hero_image
        chosen_url = random.choice(thumbnail_urls) if thumbnail_urls else Aria2c.pic_dwn_url

        log.info(f"Downloading random thumbnail for task {task_ctx.get_short_id()}: {chosen_url}")
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(chosen_url, timeout=30) as response:
                    if response.status == 200:
                        async with aiofiles.open(hero_image_path, mode='wb') as f:
                            while True:
                                chunk = await response.content.read(1024)
                                if not chunk:
                                    break
                                await f.write(chunk)
                        if os.path.exists(hero_image_path):
                            log.info(f"Random thumbnail downloaded to {hero_image_path}")
                        else:
                            log.warning(f"Thumbnail download failed: file not found")
                    else:
                        log.warning(f"Thumbnail download failed: HTTP {response.status}")
        except Exception as e:
            log.error(f"Error downloading random thumbnail: {e}")

        # Get thumbnail path (priority: custom > random downloaded > static default)
        if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
            thumb_path = Paths.THMB_PATH  # Use custom thumbnail
        elif os.path.exists(task_ctx.hero_image):
            thumb_path = task_ctx.hero_image  # Use task-specific random thumbnail
        else:
            thumb_path = Paths.DEFAULT_HERO  # Fallback to static default

        # Send status message with thumbnail (store in task_ctx, not global MSG)
        if os.path.exists(thumb_path):
            task_ctx.status_msg = await client.send_photo(
                OWNER,
                photo=thumb_path,
                caption=status_text,
                reply_markup=keyboard(task_ctx.get_short_id()),  # Add cancel button with task short ID
                parse_mode=enums.ParseMode.HTML,
            )
            log.info(f"Sent Mindvalley status with thumbnail: {thumb_path} (task {task_ctx.get_short_id()})")
        else:
            # Fallback to text if no thumbnail exists
            log.warning(f"Thumbnail not found at {thumb_path}, sending text message")
            task_ctx.status_msg = await client.send_message(
                OWNER,
                status_text,
                reply_markup=keyboard(task_ctx.get_short_id()),  # Add cancel button with task short ID
                parse_mode=enums.ParseMode.HTML,
            )

        # Also set global MSG for backward compatibility with status_bar()
        # TODO: Remove this in Phase 3 when status_bar() is refactored
        MSG.status_msg = task_ctx.status_msg

        # Set task message for completion (in task_ctx)
        task_ctx.messages.task_msg = f"<b>TASK MODE » </b><i>Mindvalley Leech</i>\n\n"
        task_ctx.messages.src_link = f"https://gist.githubusercontent.com/..." if 'gist' in input_text else "M3U8 URLs"
        task_ctx.messages.download_name = output_filename

        # Also set globals for backward compat
        MSG.task_msg = task_ctx.messages.task_msg
        MSG.src_link = task_ctx.messages.src_link
        MSG.download_name = output_filename

        # NEW: Define async task function for parallel execution
        async def run_mindvalley_task():
            """Async task function that runs download+upload in the background"""
            try:
                task_ctx.mark_started()
                BotTimes.start_time = datetime.now()
                log.info(f"Task {task_ctx.get_short_id()} started: Mindvalley download")

                # Download based on mode
                vtt_path = None
                srt_path = None
                if subtitle_only:
                    # Returns (success, vtt_path, srt_path) - no final_path for subtitle-only
                    success, vtt_path, srt_path = await downloader.download_subtitle_only(
                        subtitle_url, output_filename
                    )
                    # For subtitle-only, set final_path to vtt_path for backward compatibility
                    final_path = vtt_path if success else None
                else:
                    # Returns (success, mp4_path, vtt_path, srt_path)
                    success, final_path, vtt_path, srt_path = await downloader.download_and_merge(
                        video_url, audio_url, subtitle_url, output_filename
                    )

                if success and final_path:
                    try:
                        # Handle subtitle-only mode differently
                        if subtitle_only:
                            log.info(f"Task {task_ctx.get_short_id()}: Uploading subtitle files...")
                            upload_success = True  # Will be set to False if uploads fail

                            # Upload SRT file (more compatible) using upload_file for proper stats tracking
                            if srt_path and os.path.exists(srt_path):
                                srt_display_name = os.path.basename(srt_path)
                                log.info(f"Uploading SRT subtitle: {srt_display_name}")
                                srt_upload = await upload_file(srt_path, srt_display_name, task_ctx)
                                if srt_upload:
                                    log.info(f"SRT file uploaded successfully: {srt_display_name}")
                                    try:
                                        os.remove(srt_path)
                                        log.info(f"Cleaned up SRT file: {srt_path}")
                                    except Exception as cleanup_err:
                                        log.warning(f"Failed to clean up SRT file: {cleanup_err}")
                                else:
                                    log.error(f"SRT upload failed: {srt_display_name}")
                                    upload_success = False

                            # Upload VTT file (original) using upload_file for proper stats tracking
                            if vtt_path and os.path.exists(vtt_path):
                                vtt_display_name = os.path.basename(vtt_path)
                                log.info(f"Uploading VTT subtitle: {vtt_display_name}")
                                vtt_upload = await upload_file(vtt_path, vtt_display_name, task_ctx)
                                if vtt_upload:
                                    log.info(f"VTT file uploaded successfully: {vtt_display_name}")
                                    try:
                                        os.remove(vtt_path)
                                        log.info(f"Cleaned up VTT file: {vtt_path}")
                                    except Exception as cleanup_err:
                                        log.warning(f"Failed to clean up VTT file: {cleanup_err}")
                                else:
                                    log.error(f"VTT upload failed: {vtt_display_name}")
                                    upload_success = False

                        else:
                            # Normal mode: Upload MP4 video
                            log.info(f"Task {task_ctx.get_short_id()}: Uploading {final_path} to Telegram...")
                            display_name = os.path.basename(final_path)
                            upload_success = await upload_file(final_path, display_name, task_ctx)

                        # If successful and we have subtitle files, upload them using upload_file
                        if upload_success:
                            # Upload SRT file (more widely compatible) using upload_file for proper stats tracking
                            if srt_path and os.path.exists(srt_path):
                                log.info(f"Task {task_ctx.get_short_id()}: Uploading SRT subtitle {srt_path}...")
                                srt_display_name = os.path.basename(srt_path)

                                srt_upload = await upload_file(srt_path, srt_display_name, task_ctx)
                                if srt_upload:
                                    log.info(f"SRT file uploaded successfully: {srt_display_name}")
                                    # Clean up SRT file after upload
                                    try:
                                        os.remove(srt_path)
                                        log.info(f"Cleaned up SRT file: {srt_path}")
                                    except Exception as cleanup_err:
                                        log.warning(f"Failed to clean up SRT file: {cleanup_err}")
                                else:
                                    log.error(f"Failed to upload SRT file: {srt_display_name}")
                                    # Continue to VTT upload

                            # Upload VTT file (original format) using upload_file for proper stats tracking
                            if vtt_path and os.path.exists(vtt_path):
                                log.info(f"Task {task_ctx.get_short_id()}: Uploading VTT subtitle {vtt_path}...")
                                vtt_display_name = os.path.basename(vtt_path)

                                vtt_upload = await upload_file(vtt_path, vtt_display_name, task_ctx)
                                if vtt_upload:
                                    log.info(f"VTT file uploaded successfully: {vtt_display_name}")
                                    # Clean up VTT file after upload
                                    try:
                                        os.remove(vtt_path)
                                        log.info(f"Cleaned up VTT file: {vtt_path}")
                                    except Exception as cleanup_err:
                                        log.warning(f"Failed to clean up VTT file: {cleanup_err}")
                                else:
                                    log.error(f"Failed to upload VTT file: {vtt_display_name}")
                                    # Continue anyway - main file was uploaded

                        if upload_success:
                            # Pass task_ctx to SendLogs for per-task completion tracking
                            await SendLogs(is_leech=True, task_ctx=task_ctx)
                            task_ctx.mark_completed()
                            log.info(f"Task {task_ctx.get_short_id()} completed successfully")
                        else:
                            task_ctx.error.set_error("Upload failed")
                            await message.reply_text(
                                f"<b>Upload Failed</b> [task {task_ctx.get_short_id()}]\n\n"
                                "File downloaded but upload to Telegram failed.\n"
                                f"File saved at: <code>{final_path}</code>",
                                quote=True,
                                parse_mode=enums.ParseMode.HTML,
                            )
                    except Exception as upload_error:
                        log.exception(f"Task {task_ctx.get_short_id()}: Upload error")
                        task_ctx.error.set_error(str(upload_error))
                        await message.reply_text(
                            f"<b>Upload Error</b> [task {task_ctx.get_short_id()}]: {str(upload_error)}\n\n"
                            f"File saved locally at: <code>{final_path}</code>",
                            quote=True,
                            parse_mode=enums.ParseMode.HTML,
                        )
                else:
                    task_ctx.error.set_error("Download failed")
                    await message.reply_text(
                        f"<b>Download Failed</b> [task {task_ctx.get_short_id()}]\n\n"
                        "Please check:\n"
                        "• URLs are valid M3U8 playlists\n"
                        "• Network connection is stable\n"
                        "• Try again with /mindvalley",
                        quote=True,
                        parse_mode=enums.ParseMode.HTML,
                    )

            except Exception as task_error:
                log.exception(f"Task {task_ctx.get_short_id()} error")
                task_ctx.error.set_error(str(task_error))
                task_ctx.mark_completed()  # Mark as completed even on error
                await message.reply_text(
                    f"<b>Task Error</b> [task {task_ctx.get_short_id()}]: {str(task_error)}",
                    quote=True,
                    parse_mode=enums.ParseMode.HTML,
                )
            finally:
                # Clean up: remove from queue and update dashboard
                await TASK_QUEUE.remove_task(task_ctx.task_id)
                await force_update_summary(client)
                log.info(f"Task {task_ctx.get_short_id()} cleanup complete")

        # NEW: Register task and launch it (non-blocking)
        await TASK_QUEUE.add_task(task_ctx)
        task_ctx.async_task = asyncio.create_task(run_mindvalley_task())
        log.info(f"Task {task_ctx.get_short_id()} launched in background")

        # NEW: Update summary dashboard to show new task
        await force_update_summary(client)

        # Return immediately - task runs in background!
        log.info(f"Mindvalley handler returning - task {task_ctx.get_short_id()} continues in background")

    except Exception as e:
        log.exception("Error processing Mindvalley URLs")
        await _reply_with_generic_error(message, "process Mindvalley URLs", quote=True)


# ========== NZB (Usenet) Download Handlers ==========

@colab_bot.on_message(filters.command("nzb") & filters.private)
async def nzb_download(client, message):
    """
    Download files from Usenet using NZB file
    Usage: /nzb then upload .nzb file or send .nzb URL
    """
    global BOT
    log.info(f"Received /nzb from {message.from_user.id}")

    # Set bot state
    BOT.Mode.mode = "leech"  # Upload to Telegram
    BOT.Mode.ytdl = False
    user_id = _extract_user_id(message)
    await _set_nzb_waiting(user_id, True)
    await _update_setup_session(
        user_id,
        mode="leech",
        service_type="nzb",
        source_links=[],
        filenames=[],
    )

    help_text = build_nzb_prompt(BOT.Setting.nzb_active_provider)

    await _clear_source_waiting(client, user_id)
    prompt_msg = await task_starter(message, help_text)
    if prompt_msg:
        await _set_source_waiting(user_id, message.chat.id, prompt_msg.id)
    log.debug("/nzb: task_starter called, source prompt tracked per user")


@colab_bot.on_message(filters.document & filters.private)
async def handle_document_upload(client, message):
    """Handle document uploads (currently .nzb files)"""
    global BOT

    # Check if waiting for NZB file
    if await _is_nzb_waiting(_extract_user_id(message)) and message.document.file_name.lower().endswith('.nzb'):
        log.info(f"Received .nzb file upload: {message.document.file_name}")
        await handle_nzb_file(client, message)
        return

    # Future: Add handlers for other document types (e.g., .torrent)


async def handle_nzb_file(client, message, nzb_file_path=None):
    """Process uploaded .nzb file or downloaded from URL

    Args:
        client: Pyrogram client
        message: Message object
        nzb_file_path: Optional path to .nzb file (if already downloaded from URL)
    """
    global BOT, MSG, BotTimes
    from .downlader.nzb import NZBDownloader
    from .utility.task_context import create_task_context
    from .uploader.telegram import upload_file
    import random
    import aiohttp
    import aiofiles

    await _set_nzb_waiting(_extract_user_id(message), False)

    # Delete per-user help prompt.
    await _clear_source_waiting(client, _extract_user_id(message))

    # Create TaskContext for this NZB download
    task_ctx = create_task_context(
        user_id=message.from_user.id,
        chat_id=message.chat.id,
        mode="leech"
    )
    task_ctx.service_type = "nzb"
    log.info(f"Created TaskContext {task_ctx.get_short_id()} for NZB download")

    try:
        # Determine NZB file path
        if nzb_file_path:
            # Already downloaded from URL
            nzb_path = nzb_file_path
            nzb_filename = os.path.basename(nzb_path)
            log.info(f"Using pre-downloaded NZB file: {nzb_path}")
        elif message.document:
            # Download .nzb file from Telegram
            nzb_filename = message.document.file_name
            nzb_path = os.path.join(task_ctx.down_path, nzb_filename)
            log.info(f"Downloading .nzb file to: {nzb_path}")
            await message.download(file_name=nzb_path)
        else:
            raise ValueError("No NZB file provided (not a document and no path given)")

        # Validate Usenet credentials
        if not BOT.Setting.nzb_providers or not BOT.Setting.nzb_active_provider:
            await message.reply_text(
                build_usenet_not_configured_error(),
                quote=True,
                parse_mode=enums.ParseMode.HTML,
            )
            return

        active_provider = BOT.Setting.nzb_providers.get(BOT.Setting.nzb_active_provider, {})
        if not active_provider.get('host'):
            await message.reply_text(
                build_invalid_provider_configuration_error(BOT.Setting.nzb_active_provider),
                quote=True,
                parse_mode=enums.ParseMode.HTML,
            )
            return

        # Download random thumbnail for status message
        from .utility.task_manager import thumbnail_urls
        hero_image_path = task_ctx.hero_image
        chosen_url = random.choice(thumbnail_urls) if thumbnail_urls else None

        if chosen_url:
            log.info(f"Downloading random thumbnail for task {task_ctx.get_short_id()}: {chosen_url}")
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(chosen_url, timeout=30) as response:
                        if response.status == 200:
                            async with aiofiles.open(hero_image_path, mode='wb') as f:
                                while True:
                                    chunk = await response.content.read(1024)
                                    if not chunk:
                                        break
                                    await f.write(chunk)
                            log.info(f"Thumbnail downloaded successfully to {hero_image_path}")
            except Exception as e:
                log.warning(f"Failed to download thumbnail: {e}")

        # Determine thumbnail to send
        if BOT.Setting.thumbnail and os.path.exists(Paths.THMB_PATH):
            thumb_path = Paths.THMB_PATH
        elif os.path.exists(hero_image_path):
            thumb_path = hero_image_path
        else:
            thumb_path = Paths.DEFAULT_HERO

        # Send initial status with thumbnail
        initial_status = (
            f"<b>📰 NZB Download [{task_ctx.get_short_id()}] »</b>\n\n"
            f"<b>📄 File » </b><code>{nzb_filename}</code>\n"
            f"<b>🔌 Provider » </b><code>{BOT.Setting.nzb_active_provider}</code>\n"
            f"<b>🎯 Status » </b><code>Initializing...</code>\n"
        )

        if os.path.exists(thumb_path):
            task_ctx.status_msg = await client.send_photo(
                OWNER,
                photo=thumb_path,
                caption=initial_status,
                reply_markup=keyboard()
            )
        else:
            task_ctx.status_msg = await client.send_message(
                OWNER,
                initial_status,
                reply_markup=keyboard()
            )

        # Check if SABnzbd is configured (preferred method)
        from .downlader.sabnzbd_downloader import get_sabnzbd_config, SABnzbdDownloader

        sabnzbd_config = get_sabnzbd_config()

        if sabnzbd_config:
            # Use SABnzbd downloader (more reliable)
            log.info("Using SABnzbd backend for NZB download")
            downloader = SABnzbdDownloader(client, message, sabnzbd_config)
        else:
            # Fall back to custom NNTP downloader
            log.info("Using custom NNTP downloader (SABnzbd not configured)")
            downloader = NZBDownloader(client, message, task_ctx)

        # Download NZB
        log.info(f"Starting NZB download for task {task_ctx.get_short_id()}")
        success, output_files = await downloader.download_nzb(nzb_path, task_ctx.down_path)

        if success and output_files:
            log.info(f"NZB download successful: {len(output_files)} file(s)")

            # Upload files to Telegram
            for file_path in output_files:
                filename = os.path.basename(file_path)
                log.info(f"Uploading to Telegram: {filename}")

                # Update status
                if task_ctx.status_msg:
                    try:
                        if hasattr(task_ctx.status_msg, 'photo') and task_ctx.status_msg.photo:
                            await task_ctx.status_msg.edit_caption(
                                caption=f"<b>📰 NZB Download Complete »</b>\n\n"
                                        f"<b>📤 Uploading to Telegram...</b>\n"
                                        f"<code>{filename}</code>"
                            )
                        else:
                            await task_ctx.status_msg.edit_text(
                                text=f"<b>📰 NZB Download Complete »</b>\n\n"
                                     f"<b>📤 Uploading to Telegram...</b>\n"
                                     f"<code>{filename}</code>"
                            )
                    except Exception as e:
                        log.warning(f"Failed to update status: {e}")

                # Upload file
                await upload_file(file_path, filename, task_ctx)

            # Final success message
            if task_ctx.status_msg:
                try:
                    final_text = (
                        f"<b>✅ NZB Download Complete [{task_ctx.get_short_id()}] »</b>\n\n"
                        f"<b>📦 Files Downloaded: </b><code>{len(output_files)}</code>\n"
                        f"<b>📤 Uploaded to Telegram</b>"
                    )
                    if hasattr(task_ctx.status_msg, 'photo') and task_ctx.status_msg.photo:
                        await task_ctx.status_msg.edit_caption(caption=final_text)
                    else:
                        await task_ctx.status_msg.edit_text(text=final_text)
                except Exception as e:
                    log.warning(f"Failed to send final message: {e}")

        else:
            log.error("NZB download failed")
            if task_ctx.status_msg:
                try:
                    error_text = (
                        f"<b>❌ NZB Download Failed [{task_ctx.get_short_id()}] »</b>\n\n"
                        f"Check logs for details."
                    )
                    if hasattr(task_ctx.status_msg, 'photo') and task_ctx.status_msg.photo:
                        await task_ctx.status_msg.edit_caption(caption=error_text)
                    else:
                        await task_ctx.status_msg.edit_text(text=error_text)
                except Exception as e:
                    log.warning(f"Failed to send error message: {e}")

    except Exception as e:
        log.exception("Error processing NZB file")
        await _set_nzb_waiting(_extract_user_id(message), False)
        await _reply_with_generic_error(message, "process the NZB file", quote=True)


@colab_bot.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client, message):
    log.info(f"Received /cancel from {message.from_user.id}")

    # 1. Check for active parallel tasks
    active_tasks = await TASK_QUEUE.get_all_tasks()
    user_id = message.from_user.id

    # Filter tasks for this user
    user_active_tasks = {
        tid: ctx for tid, ctx in active_tasks.items()
        if ctx.user_id == user_id or user_id == OWNER
    }

    if user_active_tasks:
        keyboard = []
        for _, ctx in user_active_tasks.items():
            download_name = ctx.messages.download_name if ctx.messages else None
            source_url = ctx.source_urls[0] if ctx.source_urls else None
            btn_text = build_cancel_task_button_label(
                download_name,
                source_url,
                ctx.get_short_id(),
            )
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"cancel:{ctx.get_short_id()}")])

        # Add owner-only "Cancel All" option when multiple tasks exist.
        if len(user_active_tasks) > 1 and user_id == OWNER:
            keyboard.append([
                InlineKeyboardButton("❌ Cancel All Tasks", callback_data="cancel_all_tasks")
            ])

        await message.reply_text(
            f"<b>Active Tasks ({len(user_active_tasks)})</b>\n\nSelect a task to cancel:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            quote=True,
            parse_mode=enums.ParseMode.HTML,
        )
        return

    # 2. Setup/runtime cancellation fallback
    if await _is_extract_waiting(user_id):
        await _clear_extract_waiting(client, message.chat.id, user_id)
    await _set_mindvalley_waiting(user_id, False)
    await _set_nzb_waiting(user_id, False)
    await _clear_source_waiting(client, user_id)
    await _clear_filename_reply_waiting(client, message.chat.id, user_id)
    await _clear_password_reply_prompt(client, user_id)
    await _clear_settings_reply_waiting(client, message.chat.id, user_id)
    await _clear_setup_session(user_id)
    await message.reply_text("Cleared pending setup/reply state for this user.", quote=True)


@colab_bot.on_message(filters.command("health") & filters.private)
async def health_check(client, message):
    """Observability: Real-time system health report"""
    log.info(f"Received /health from {message.from_user.id}")
    if message.from_user.id != OWNER:
        await message.reply_text("❌ Unauthorized.")
        return
        
    health_text = TASK_QUEUE.get_health_summary()
    await message.reply_text(health_text, quote=True)


@colab_bot.on_message(filters.command("help") & filters.private)
async def help_command(client, message):
    log.info("Received /help command.")
    help_text = build_help_text()
    await message.reply_text(
        help_text,
        quote=True,
        parse_mode=enums.ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Instructions", url="https://github.com/XronTrix10/Telegram-Leecher/wiki/INSTRUCTIONS")],
            [
                InlineKeyboardButton("Channel", url="https://t.me/Colab_Leecher"),
                InlineKeyboardButton("Group", url="https://t.me/Colab_Leecher_Discuss"),
            ],
        ]),
    )

# Send SABnzbd URL on bot startup
async def send_sabnzbd_url_to_telegram():
    """Send SABnzbd web UI URL to owner via Telegram if available"""
    try:
        # Wait for bot to connect
        await asyncio.sleep(3)

        sabnzbd_info_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.sabnzbd_url.txt')
        if os.path.exists(sabnzbd_info_file):
            with open(sabnzbd_info_file, 'r') as f:
                lines = f.readlines()
                if len(lines) >= 2:
                    url = lines[0].strip()
                    api_key = lines[1].strip()
                    masked_api_key = mask_secret(api_key)
                    url_type = lines[2].strip() if len(lines) >= 3 else 'public'  # default to public for backwards compat

                    # Customize message based on URL type
                    if url_type == 'local':
                        icon = "🏠"
                        title = "SABnzbd Web UI Ready (Local Access)"
                        note = "<i>⚠️ Local URL only - accessible from this machine only.</i>"
                    else:
                        icon = "🌐"
                        title = "SABnzbd Web UI Ready!"
                        note = "<i>Click the URL to manage NZB downloads in your browser.</i>"

                    message_text = (
                        f"<b>{icon} {title}</b>\n\n"
                        f"<b>🔗 URL:</b> {url}\n"
                        f"<b>🔑 API Key:</b> <code>{masked_api_key}</code>\n"
                        "<i>Full API key is kept local and is not sent over Telegram.</i>\n\n"
                        f"{note}"
                    )

                    await colab_bot.send_message(OWNER, message_text)
                    log.info(f"✅ Sent SABnzbd {url_type} URL to owner via Telegram")

                    # Delete file after sending
                    os.remove(sabnzbd_info_file)
    except Exception as e:
        log.warning(f"Failed to send SABnzbd URL via Telegram: {e}")

# Startup handler: Start background tasks on first message
@colab_bot.on_message(group=0)
async def startup_handler(client, message):
    """Start background tasks once when bot receives first message"""
    global _background_tasks_started
    if not _background_tasks_started:
        _background_tasks_started = True
        log.info("Starting background tasks...")
        TASK_QUEUE.create_background_task(send_sabnzbd_url_to_telegram(), name="sabnzbd-notifier")
        TASK_QUEUE.create_background_task(periodic_cleanup_task(), name="periodic-cleanup")
        log.info("✅ Background tasks started (sabnzbd-notifier, periodic-cleanup)")
    raise ContinuePropagation  # Allow other handlers to process this message

# DEBUG: Log all messages
@colab_bot.on_message(group=1)
async def debug_all_messages(client, message):
    user_id = message.from_user.id if message.from_user else 'N/A'
    chat_id = message.chat.id if message.chat else 'N/A'
    text_len = len(message.text) if message.text else 0
    has_caption = bool(message.caption)
    media_type = str(message.media) if getattr(message, "media", None) else "none"
    log.info(
        f"DEBUG: Received message from user {user_id}, chat {chat_id}, text_len={text_len}, has_caption={has_caption}, media={media_type}"
    )
    if DEBUG_MESSAGE_PREVIEW and message.text:
        preview = message.text.replace("\n", " ")[:50]
        log.debug(f"DEBUG PREVIEW (opt-in): {preview}")
    raise ContinuePropagation  # Allow other handlers to process this message

# Main Execution Guard
if __name__ == "__main__":
     log.info("Colab Leecher Script Starting as main...")
     try:
          ensure_runtime_config()
     except ConfigError as config_err:
          log.critical(f"Bot configuration error: {config_err}")
     else:
          log.info("colab_bot instance found, attempting run()...")

          # Auto-detect SABnzbd and create notification file if running
          try:
              from .utility.sabnzbd_autodetect import auto_configure_sabnzbd, create_notification_file
              from .downlader.sabnzbd_downloader import set_sabnzbd_config

              sabnzbd_config = auto_configure_sabnzbd()
              if sabnzbd_config:
                  # Configure bot to use SABnzbd
                  set_sabnzbd_config(sabnzbd_config)
                  # Create notification file for Telegram
                  create_notification_file(sabnzbd_config, url_type='local')
                  log.info("✅ SABnzbd auto-configured successfully")
              else:
                  log.info("SABnzbd not detected - will use custom NNTP downloader")
          except Exception as e:
              log.warning(f"SABnzbd auto-detection failed: {e}")

          # Note: Background tasks will be started via on_startup handler
          # to avoid RuntimeError (no running event loop)

          # master-level addition: Register Signal Handlers for Graceful Shutdown
          import signal
          def signal_handler(sig, frame):
              log.warning(f"Received signal {sig}, initiating graceful shutdown...")
              loop.create_task(TASK_QUEUE.shutdown())
              # Exit after shutdown completes (or force exit after timeout)
              loop.call_later(12, lambda: os._exit(0))

          if os.name != 'nt': # Signals differ on Windows
              signal.signal(signal.SIGTERM, signal_handler)
              signal.signal(signal.SIGINT, signal_handler)
          else:
              # Basic support for Ctrl+C on Windows
              signal.signal(signal.SIGINT, signal_handler)

          try:
              colab_bot.run()
          except Exception as run_err: log.critical(f"Bot crashed during run: {run_err}", exc_info=True)


