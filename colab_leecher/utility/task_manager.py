from __future__ import annotations
# /content/Telegram-Leecher/colab_leecher/utility/task_manager.py
import pytz
import shutil
import logging
import os
import random
import aiohttp
import aiofiles
import asyncio
from time import time
from datetime import datetime
from asyncio import sleep
from os import makedirs, path as ospath
from pyrogram import enums
from .. import colab_bot
from ..downlader.manager import calDownSize, get_d_name, downloadManager
from .helper import (
    getSize, applyCustomName, keyboard, sysINFO, is_google_drive,
    is_telegram, is_mega, is_terabox, is_torrent,
    clean_filename, sizeUnit, get_max_split_size_mib
)
from .message_safety import user_error
from .ui_copy import build_task_in_progress_notice
from .handler import (
    Leech, Unzip_Handler, Zip_Handler, SendLogs, cancelTask,
)

from .variables import Aria2c

class LegacyGlobalAccessBlocked(RuntimeError):
    pass

class _BlockLegacyGlobal:
    def __getattr__(self, name):
        raise LegacyGlobalAccessBlocked(
            "Strict Isolation Violation: Attempted to access legacy global object in task_manager."
        )
    def __setattr__(self, name, value):
        raise LegacyGlobalAccessBlocked(
            "Strict Isolation Violation: Attempted to modify legacy global object in task_manager."
        )

BOT = _BlockLegacyGlobal()
MSG = _BlockLegacyGlobal()
Paths = _BlockLegacyGlobal()

# Import task context for multi-task support
from .task_context import TASK_QUEUE, TaskContext, cleanup_task_artifacts


log = logging.getLogger(__name__)

# Random thumbnail pool loaded from external file
def _load_thumbnail_urls():
    _file = ospath.join(ospath.dirname(__file__), "thumbnail_urls.txt")
    if ospath.exists(_file):
        with open(_file, "r", encoding="utf-8") as f:
            urls = [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
            log.info(f"Loaded {len(urls)} thumbnail URLs from {_file}")
            return urls
    log.warning(f"Thumbnail URL file not found: {_file}")
    return []

thumbnail_urls = _load_thumbnail_urls()


async def task_starter(message, text):
    """Handles the initial command, replies, and checks queue-based admission under a per-user lock."""
    user_id = message.from_user.id if message.from_user else message.chat.id
    from .variables import BOT as legacy_bot
    log.info(
        f"task_starter called by user {user_id} for mode '{legacy_bot.Mode.mode}'"
    )
    try:
        await message.delete()
        log.debug("User command message deleted.")
    except Exception as e:
        log.error(f"Failed to delete user command message: {e}")

    # Acquire the per-user lock to prevent rapid-fire duplicate commands
    user_lock = TASK_QUEUE.get_user_lock(user_id)
    can_start = False
    error_msg = ""

    async with user_lock:
        can_start, error_msg = await TASK_QUEUE.can_start_task(user_id)
        if can_start:
            log.info(f"Task admission allowed for user {user_id}. Replying to user to send links/path.")
            try:
                src_request_msg = await message.reply_text(
                    text,
                    parse_mode=enums.ParseMode.HTML,
                )
                log.info("Reply prompt sent.")
                return src_request_msg
            except Exception as e:
                log.error(f"Failed reply in task_starter: {e}", exc_info=True)
                try:
                    await message.reply_text(user_error("send the setup prompt"))
                except Exception as reply_err:
                    log.debug(f"Could not send task starter error reply: {reply_err}")
                return None

    # Handle rate-limit sleep and message deletion outside of the per-user lock
    log.warning(f"Task admission denied for user {user_id}: {error_msg}")
    try:
        msg = await message.reply_text(error_msg)
        await sleep(15)
        await msg.delete()
    except Exception as e:
        log.error(f"Failed 'task ongoing/rate limit' message: {e}")
    return None



async def taskScheduler(task_ctx: TaskContext):
    """Main function to orchestrate the download/upload task.

    Args:
        task_ctx: Required. Strictly isolated TaskContext for this execution.
                  Global state is never accessed; all state is sourced from here.
    """
    from .. import OWNER, DUMP_ID

    task_id = task_ctx.task_id
    log.info(
        f"taskScheduler started using TaskContext for task_id: {task_id}"
    )

    _bot = task_ctx.bot
    _msg = task_ctx  # TaskContext carries status_msg and sent_msg directly
    _messages = task_ctx.messages
    _paths = task_ctx.paths
    _transfer = task_ctx.transfer
    _task_error = task_ctx.error

    selected_service = _bot.Options.service_type
    log.info(
        f"taskScheduler entered. Mode: {_bot.Mode.mode}, Type: {_bot.Mode.type}, Service: {selected_service}"
    )
    src_text = []
    is_dualzip = (_bot.Mode.type == "undzip")
    is_unzip = (_bot.Mode.type == "unzip")
    # NEW: Streaming extract+upload for large archives
    is_stream_unzip = (_bot.Mode.type == "stream_unzip")
    current_mode = _bot.Mode.mode
    is_zip = (_bot.Mode.type == "zip") or (current_mode in ["leech", "dir-leech"] and _bot.Mode.type == "normal")
    is_dir = (current_mode == "dir-leech")

    # Store original download path in case it's modified (e.g., for zip mode)
    original_Paths_down_path = _paths.down_path

    from .system_coordinator import get_system_coordinator
    coordinator = get_system_coordinator()
    ctx_mgr = coordinator.guaranteed_cleanup.managed_slot(task_id)
    ctx_mgr.__enter__()

    try:
        # Enclose the complete pipeline orchestration in this strict top-level try block
        _transfer.reset()  # Reset transfer statistics
        log.debug("Transfer state reset.")
        _messages.download_name = ""  # Reset download name context
        _messages.task_msg = "<b> TASK MODE » </b>"
        # Prepare display names for logs/status
        mode_display_name = current_mode.replace(
            "-leech",
            "").replace(
            "-mirror",
            "").capitalize()
        type_display_name = _bot.Mode.type.capitalize()
        upload_display_name = _bot.Setting.stream_upload
        service_str = f" ({selected_service.capitalize()})" if selected_service else ""
        # Construct task description string for dump chat
        dump_task_mode_str = f"<i>{type_display_name} {mode_display_name}{service_str} as {upload_display_name}</i>" if current_mode != "mirror" else f"<i>{type_display_name} {mode_display_name}{service_str}</i>"
        _messages.dump_task = _messages.task_msg + \
            dump_task_mode_str + "\n\n<b>🖇️ SOURCES » </b>"
        _messages.status_head = "<b>📥 DOWNLOADING » </b>\n"  # Initial status header
        _task_error.state = False  # Reset error state
        _task_error.text = ""  # Reset error text

        # --- Source Link Processing & Formatting for Dump Message ---
        if is_dir:
            source_path = _bot.SOURCE[0]
            log.info(f"Dir mode. Path: {source_path}")
            if not ospath.exists(source_path):
                _task_error.state = True
                _task_error.text = "Directory Path Not Found"
                log.error(_task_error.text)
                # No need to explicitly return here, finally block will handle
                # cleanup/cancel if needed
            else:
                # Create temp dir if needed (although not used directly here)
                if not ospath.exists(_paths.temp_dirleech_path):
                    makedirs(_paths.temp_dirleech_path)
                _messages.dump_task += f"\n\n📂 <code>{source_path}</code>"
                _transfer.total_down_size = getSize(
                    source_path)  # Pre-calculate size
                _messages.download_name = ospath.basename(
                    source_path)  # Set initial name
                log.debug(
                    f"Dir size: {sizeUnit(_transfer.total_down_size)}, Name: {_messages.download_name}"
                )
        else:  # Link processing modes
            log.info(f"Link mode. Processing {len(_bot.SOURCE)} sources.")
            for link in _bot.SOURCE:
                # Icon logic based on service type or link type
                ida = "🔗"  # Default icon
                if selected_service == 'delta':
                    ida = "💧"
                elif selected_service == 'nzbcloud':
                    ida = "☁️"
                elif selected_service == 'bitso':
                    ida = "🪙"
                elif selected_service == 'ytdl' or _bot.Mode.ytdl:
                    ida = "🏮"
                elif is_telegram(link):
                    ida = "💬"
                elif is_google_drive(link):
                    ida = "♻️"
                elif is_torrent(link):
                    ida = "🧲"
                    _messages.caution_msg = ""  # No caution for torrents
                elif is_terabox(link):
                    ida = "🍑"
                elif is_mega(link):
                    ida = "💾"
                # Add other auto-detections if needed

                code_link = f"\n\n{ida} <code>{link}</code>"
                # Split dump message if it gets too long
                if len(_messages.dump_task + code_link) >= 4096:
                    src_text.append(_messages.dump_task)
                    _messages.dump_task = code_link  # Start new message part
                else:
                    _messages.dump_task += code_link

        # Append date and final part of dump message
        cdt = datetime.now(pytz.timezone("Asia/Kolkata"))
        dt = cdt.strftime(" %d-%m-%Y")
        _messages.dump_task += f"\n\n<b>📆 Task Date » </b><i>{dt}</i>"
        src_text.append(_messages.dump_task)

        log.info(
            f"Prepared {len(src_text)} message(s) for dump channel (total chars: {sum(len(t) for t in src_text)})"
        )

        # --- Environment Setup & Thumbnail Handling ---
        log.info("Setting up work environment...")
        # Clean work path if it exists, then recreate needed dirs
        if ospath.exists(_paths.WORK_PATH):
            shutil.rmtree(_paths.WORK_PATH)
        makedirs(_paths.WORK_PATH, exist_ok=True)
        makedirs(_paths.down_path, exist_ok=True)

        # Check if parallel mode is active to optimize thumbnail downloading
        is_parallel_mode = await TASK_QUEUE.has_task(task_ctx.task_id)

        # --- Conditional Random Thumbnail Download ---
        default_pic_url = Aria2c.pic_dwn_url  # Get default from Aria2c settings
        chosen_url = None
        hero_image_path = _paths.HERO_IMAGE  # Path where thumbnail will be saved
        download_success = False  # Flag to track if download worked

        need_thumbnail = not is_parallel_mode or _bot.Setting.thumbnail

        if need_thumbnail:
            # Assume 'thumbnail_urls' list is populated earlier (e.g., from
            # Paths.list_hero)
            if thumbnail_urls:  # Check if the random list exists and is not empty
                log.info("Choosing random thumbnail from list.")
                chosen_url = random.choice(thumbnail_urls)
                log.info(f"Randomly selected thumbnail URL: {chosen_url}")
            else:
                # Fallback to default if the random list is empty or not defined
                log.warning(
                    "Random thumbnail URL list is empty or not available. Falling back to default URL.")
                chosen_url = default_pic_url
            # --- End Always Random Choice ---
        else:
            log.info("Skipping random thumbnail download: task is in parallel mode and thumbnail setting is disabled.")

        # --- Download the chosen thumbnail (Your existing download logic) ---
        if chosen_url and need_thumbnail:
            log.info(
                f"Attempting asynchronous download of thumbnail from: {chosen_url}")
            try:
                # Create a single session for potential multiple requests
                # (though only one here)
                async with aiohttp.ClientSession() as session:
                    # Use a timeout for the request to prevent indefinite hangs
                    async with session.get(chosen_url, timeout=30) as response:
                        # Check if the request was successful (HTTP status 200
                        # OK)
                        if response.status == 200:
                            # Open the destination file asynchronously for
                            # binary writing
                            async with aiofiles.open(hero_image_path, mode='wb') as f:
                                # Write the content chunk by chunk for memory
                                # efficiency
                                while True:
                                    # Read 1KB chunks
                                    chunk = await response.content.read(1024)
                                    if not chunk:
                                        break  # Exit loop when download is complete
                                    await f.write(chunk)

                            # Verify file exists and has size after writing
                            # Ensure getSize is available in this scope
                            # (imported from helper likely)
                            if ospath.exists(hero_image_path) and getSize(
                                    hero_image_path) > 0:
                                download_success = True  # Set flag on success
                                log.info(
                                    f"Successfully downloaded thumbnail to {hero_image_path} via aiohttp.")
                            else:
                                log.warning(
                                    f"Thumbnail file missing or empty after writing: {hero_image_path}")
                                # Attempt cleanup if write failed partially
                                try:
                                    if ospath.exists(hero_image_path):
                                        os.remove(hero_image_path)
                                except OSError as cleanup_err:
                                    log.warning(
                                        f"Could not remove partially written thumbnail: {cleanup_err}")
                        else:
                            # Log HTTP errors if the request failed
                            log.warning(
                                f"Failed to download thumbnail. HTTP status: {response.status}. URL: {chosen_url}"
                            )

            # --- Specific Exception Handling for Async Download ---
            except aiohttp.ClientError as http_err:
                log.error(
                    f"Network/HTTP error downloading thumbnail: {http_err}",
                    exc_info=False)
            except asyncio.TimeoutError:
                log.error(
                    f"Timeout error downloading thumbnail from {chosen_url}")
            except Exception as dl_err:
                # Catch any other unexpected errors during download/write
                log.error(
                    f"Generic exception downloading/writing thumbnail: {dl_err}",
                    exc_info=True)
                # Attempt cleanup in case of generic error during write
                try:
                    if ospath.exists(hero_image_path):
                        os.remove(hero_image_path)
                except OSError as cleanup_err:
                    log.warning(
                        f"Could not remove thumbnail after generic error: {cleanup_err}")
            # --- End Specific Exception Handling ---

        else:
            # This else corresponds to 'if chosen_url:'
            log.warning("No chosen_url determined for thumbnail.")
        # --- End Asynchronous Download Logic ---

        # --- Set final thumbnail path (This logic remains the same) ---
        final_thumb_path = hero_image_path
        if not download_success:
            # Fallback if download failed or no URL was chosen
            log.warning(
                f"Thumbnail download failed or no URL. Checking/Using fallback thumbnail: {_paths.DEFAULT_HERO}"
            )
            # Ensure _paths.DEFAULT_HERO points to a valid *local* file path
            if ospath.exists(_paths.DEFAULT_HERO):
                final_thumb_path = _paths.DEFAULT_HERO
            else:
                log.error(
                    f"Fallback thumbnail {_paths.DEFAULT_HERO} also does not exist!"
                )
                final_thumb_path = None  # No thumbnail available
        # --- End Thumbnail Handling ---

        # --- Initial Task Messages ---
        log.info("Sending initial task messages...")
        _messages.link_p = str(DUMP_ID)[4:] if str(
            DUMP_ID).startswith("-100") else str(DUMP_ID)
        try:
            # Send source links to dump chat
            _msg.sent_msg = await colab_bot.send_message(chat_id=DUMP_ID, text=src_text[0], disable_web_page_preview=True)
            if len(src_text) > 1:
                for lin in range(1, len(src_text)):
                    _msg.sent_msg = await _msg.sent_msg.reply_text(text=src_text[lin], quote=True, disable_web_page_preview=True)

            # Construct source link for status message
            if _msg.sent_msg and hasattr(_msg.sent_msg.chat, 'id') and _msg.sent_msg.chat.id != OWNER:
                _messages.src_link = f"https://t.me/c/{_messages.link_p}/{_msg.sent_msg.id}"
            else:
                _messages.src_link = getattr(_msg.sent_msg, 'link', '#')
            task_title = f"{type_display_name} {mode_display_name}{service_str}"
            # Prepend task context to status message base
            _messages.task_msg += f"__[{task_title}]({_messages.src_link})__\n\n"

            # ===== PARALLEL MODE: Skip individual messages, use shared dashboard =====
            # task_ctx is guaranteed non-None; check queue membership directly.
            is_parallel_mode = await TASK_QUEUE.has_task(task_ctx.task_id)

            # Only create individual status message if NOT in parallel mode
            if not _msg.status_msg and not is_parallel_mode:
                # Determine which image to send (Custom > Downloaded/Fallback)
                img_to_send = _paths.THMB_PATH if _bot.Setting.thumbnail and ospath.exists(
                    _paths.THMB_PATH) else final_thumb_path

                # Send initial status message with photo (with fallback to
                # text-only)
                if not img_to_send or not ospath.exists(img_to_send):
                    log.error(
                        f"Thumbnail path to send does not exist: {img_to_send}. Attempting absolute fallback.")
                    img_to_send = _paths.DEFAULT_HERO  # Use defined fallback path first
                    if not img_to_send or not ospath.exists(img_to_send):
                        log.critical(
                            "FATAL: No valid thumbnail image found to send.")
                        _msg.status_msg = await colab_bot.send_message(chat_id=OWNER, text=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__ (Thumbnail Error)" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()))
                    else:
                        try:
                            _msg.status_msg = await colab_bot.send_photo(chat_id=OWNER, photo=img_to_send, caption=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()))
                        except Exception as photo_err:
                            log.warning(
                                f"Failed to send photo (MD5 or other error): {photo_err}. Sending text-only message.")
                            _msg.status_msg = await colab_bot.send_message(chat_id=OWNER, text=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()))
                else:
                    try:
                        _msg.status_msg = await colab_bot.send_photo(chat_id=OWNER, photo=img_to_send, caption=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()))
                    except Exception as photo_err:
                        log.warning(
                            f"Failed to send photo (MD5 or other error): {photo_err}. Sending text-only message.")
                        _msg.status_msg = await colab_bot.send_message(chat_id=OWNER, text=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()))
            elif is_parallel_mode and _msg.status_msg:
                # In parallel mode, keep the individual status message so
                # SendLogs can use it for the final summary.
                log.info(
                    f"Parallel mode detected - keeping existing status message for task {task_ctx.get_short_id()}"
                )
            else:
                # Status message already exists (shared message for parallel tasks)
                log.info(
                    f"Skipping status message creation - using existing shared message for task {task_ctx.get_short_id()}"
                )

        except Exception as msg_err:
            log.error(
                f"Error sending initial task messages: {msg_err}",
                exc_info=True)
            _task_error.state = True
            _task_error.text = f"Failed send status: {msg_err}"
            # Allow finally block to handle cancellation
            pass

        # --- Pre-checks (Size/Name) ---
        # Only run if no error has occurred yet
        if not _task_error.state:
            log.info("Running pre-checks (size/name)...")
            # Skip pre-calc/name guess for certain services or dir mode
            if not is_dir and selected_service not in [
                    'nzbcloud', 'delta', 'bitso', 'ytdl', 'local']:
                try:
                    # Add timeout protection to prevent infinite hangs
                    await asyncio.wait_for(calDownSize(_bot.SOURCE, task_ctx), timeout=30.0)
                    if _bot.SOURCE:
                        await asyncio.wait_for(get_d_name(_bot.SOURCE[0], task_ctx), timeout=30.0)
                    else:
                        _messages.download_name = "Task_No_Sources"
                        log.warning("_bot.SOURCE empty.")
                except asyncio.TimeoutError:
                    log.warning(
                        "Pre-check timeout after 30s - skipping size/name calculation")
                except Exception as precheck_err:
                    log.warning(
                        f"Pre-check error: {precheck_err} - continuing anyway")
            elif not is_dir and selected_service in ['nzbcloud', 'delta', 'bitso']:
                # Name/size handled later or manually provided
                if _msg.status_msg:
                    await _msg.status_msg.edit_caption(caption=_messages.task_msg + _messages.status_head + "\n📝 __Waiting for downloader...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()))

        # --- Adjust Download Path for Zip Mode ---
        # Only if no error has occurred yet
        if not _task_error.state:
            if is_zip:
                zip_base_name = _bot.Options.custom_name if _bot.Options.custom_name else _messages.download_name if _messages.download_name else "Download"
                # Use original_Paths_down_path as the base for the zip
                # subfolder
                _paths.down_path = ospath.join(
                    original_Paths_down_path, clean_filename(zip_base_name))
                makedirs(_paths.down_path, exist_ok=True)
                log.info(
                    f"Zip mode: Download target subfolder: {_paths.down_path}"
                )
            else:
                # Ensure it uses the base path if not zip
                _paths.down_path = original_Paths_down_path

        # --- Execute Main Task ---
        # Only if no error has occurred yet
        if not _task_error.state:
            task_ctx.bot_times.current_time = time()  # Update time before starting main work
            is_ytdl_task = (selected_service == 'ytdl') or _bot.Mode.ytdl
            log.info(
                f"Starting main task execution: Mode={current_mode}, Service={selected_service}, is_ytdl={is_ytdl_task}")
            if current_mode in ["leech", "dir-leech"]:
                await Do_Leech(_bot.SOURCE, is_dir, is_ytdl_task, is_zip, is_unzip, is_dualzip, is_stream_unzip, task_ctx)
            elif current_mode == "mirror":
                await Do_Mirror(_bot.SOURCE, is_ytdl_task, is_zip, is_unzip, is_dualzip, is_stream_unzip, task_ctx)
            elif current_mode == "gdrive":
                await Do_GDrive_Upload(_bot.SOURCE, is_dir, is_ytdl_task, is_zip, is_unzip, is_dualzip, is_stream_unzip, task_ctx)
            else:
                log.error(f"Unknown mode: {current_mode}")
                _task_error.state = True
                _task_error.text = f"Invalid mode: {current_mode}"

    except asyncio.CancelledError:
        log.warning(f"taskScheduler: Task {task_id[:8]} actively cancelled.")
        task_ctx.mark_cancelled()
        # Set task error text to represent cancellation
        if not _task_error.state:
            _task_error.set_error("Task actively cancelled by user.")
        raise
    except Exception as scheduler_err:
        log.error(
            f"Error within taskScheduler main try block: {scheduler_err}",
            exc_info=True)
        # Set error state if one hasn't been set already
        if not _task_error.state:
            _task_error.set_error(f"Scheduler Error: {scheduler_err}")
    finally:
        # Ultimate safety net block. Runs whether exception, cancellation or normal completion occurred.
        log.info(
            f"taskScheduler: Entering safety finally block for task {task_id[:8]}")

        # 1. Restore original download path if it was changed
        try:
            if _paths.down_path != original_Paths_down_path:
                _paths.down_path = original_Paths_down_path
                log.debug("taskScheduler finally: Restored original _paths.down_path")
        except Exception as path_err:
            log.error(f"taskScheduler finally: Failed to restore download path: {path_err}")

        # 2. Dispatch reports/cancellation UI updates safely if task was cancelled or failed
        if _task_error.state or task_ctx.is_cancelled:
            try:
                log.warning(f"taskScheduler finally: Task {task_id[:8]} is failed/cancelled. Dispatching reports.")
                reason_to_report = _task_error.text or "Task stopped unexpectedly."
                # Wrap in wait_for to guarantee it never blocks the slot release
                await asyncio.wait_for(cancelTask(reason_to_report, task_ctx), timeout=15.0)
            except BaseException as cancel_dispatch_err:
                log.error(f"taskScheduler finally: Failed to dispatch reports via cancelTask: {cancel_dispatch_err}", exc_info=True)

        # 3. Clean up isolated task workspace artifacts to prevent disk leaks
        try:
            log.debug(f"taskScheduler finally: Cleaning up task workspace artifacts for {task_id[:8]}")
            cleanup_task_artifacts(task_ctx)
        except Exception as cleanup_err:
            log.error(f"taskScheduler finally: Failed to run cleanup_task_artifacts: {cleanup_err}", exc_info=True)

        # 4, 5, 6. ABSOLUTE GUARANTEES: Release slot, remove task, and update dashboard
        # scheduled safely as a shielded background task so it executes fully outside the cancelled context.
        async def _async_cleanup():
            from .queue_operation_manager import coordinated_cleanup
            await coordinated_cleanup(task_id)

        TASK_QUEUE.create_background_task(_async_cleanup(), name=f"shielded_cleanup_{task_id[:8]}")
        ctx_mgr.__exit__(None, None, None)

       # --- Pipeline Architecture Helper Functions ---

async def async_copy(src, dst, task_ctx: TaskContext = None):
    """Asynchronously copies a file or directory with support for cancellation.

    If src is a directory, it recursively copies files and directories.
    Yields control to the event loop during copies to keep the application responsive.
    """
    if task_ctx and task_ctx.cancel_event.is_set():
        raise asyncio.CancelledError("Copy cancelled actively.")

    if ospath.isdir(src):
        makedirs(dst, exist_ok=True)
        items = await asyncio.to_thread(os.listdir, src)
        for item in items:
            s_item = ospath.join(src, item)
            d_item = ospath.join(dst, item)
            await async_copy(s_item, d_item, task_ctx)
    else:
        if ospath.isdir(dst):
            dst = ospath.join(dst, ospath.basename(src))

        parent_dir = ospath.dirname(dst)
        if parent_dir:
            makedirs(parent_dir, exist_ok=True)

        def _copy_stats(s, d):
            try:
                shutil.copystat(s, d)
            except Exception:
                pass

        with open(src, 'rb') as fsrc, open(dst, 'wb') as fdst:
            while True:
                if task_ctx and task_ctx.cancel_event.is_set():
                    raise asyncio.CancelledError("Copy cancelled actively.")
                chunk = await asyncio.to_thread(fsrc.read, 1 * 1024 * 1024)
                if not chunk:
                    break
                await asyncio.to_thread(fdst.write, chunk)
                await asyncio.sleep(0)

        await asyncio.to_thread(_copy_stats, src, dst)


async def _stage_download(batch_links, task_ctx: TaskContext) -> str | None:
    """Download stage: cleans work paths and downloads a batch of links.

    Args:
        batch_links: List of links to download in this batch.
        task_ctx: The execution TaskContext.

    Returns:
        The download path (str) if successful and not empty, or None.
    """
    _bot = task_ctx.bot
    _paths = task_ctx.paths
    _task_error = task_ctx.error

    # 1. Clean Up Dirs for this batch
    batch_download_path = _paths.down_path
    log.info(f"[Pipeline] Cleaning work directories for batch... Target: {batch_download_path}")
    if ospath.exists(batch_download_path):
        shutil.rmtree(batch_download_path, ignore_errors=True)
    if ospath.exists(_paths.temp_zpath):
        shutil.rmtree(_paths.temp_zpath, ignore_errors=True)
    if ospath.exists(_paths.temp_unzip_path):
        shutil.rmtree(_paths.temp_unzip_path, ignore_errors=True)
    makedirs(batch_download_path, exist_ok=True)

    # 2. Extract batch filenames slice if manual filenames were provided
    full_filenames_list = _bot.Options.filenames if _bot.Options.filenames else []
    manual_filenames_provided = bool(full_filenames_list)
    batch_filenames = []
    if manual_filenames_provided and batch_links:
        try:
            idx = _bot.SOURCE.index(batch_links[0])
            batch_filenames = full_filenames_list[idx : idx + len(batch_links)]
        except ValueError:
            pass

    # 3. Download the current batch
    if task_ctx.cancel_event.is_set():
        log.warning("[Pipeline] Download stage aborted: task actively cancelled.")
        _task_error.set_error("Task actively cancelled.")
        return None

    is_ytdl = (_bot.Options.service_type == 'ytdl') or _bot.Mode.ytdl
    log.info(f"[Pipeline] Downloading batch links... is_ytdl={is_ytdl}")
    _task_error.clear()
    await downloadManager(batch_links, is_ytdl, batch_filenames, task_ctx)

    if task_ctx.cancel_event.is_set():
        log.warning("[Pipeline] Download stage cancelled after download manager returned.")
        _task_error.set_error("Task actively cancelled.")
        return None

    # Check if download succeeded and dir is not empty
    if _task_error.state:
        log.warning(f"[Pipeline] Download had failures: {_task_error.text}")
        return None

    if not ospath.exists(batch_download_path) or not os.listdir(batch_download_path):
        log.warning("[Pipeline] Download path empty after download stage.")
        return None

    # Update smart download name
    from ..utility.helper import update_download_name_from_directory
    log.info(f"[Pipeline] Updating download name from: {batch_download_path}")
    smart_name = update_download_name_from_directory(batch_download_path, task_ctx)
    log.info(f"[Pipeline] Smart name determined: {smart_name}")
    task_ctx.messages.download_name = smart_name

    return batch_download_path


async def _handle_streaming_extraction(download_path: str, task_ctx: TaskContext) -> str | None:
    """Handles streaming extraction and direct upload.

    Returns:
        None (as files are uploaded directly via streaming), or raises exception/sets error on failure.
    """
    _bot = task_ctx.bot
    _task_error = task_ctx.error

    log.info(f"[Process] Starting streaming extraction for: {download_path}")
    if not ospath.exists(download_path):
        _task_error.set_error(f"Source path missing for streaming extraction: {download_path}")
        return None

    items_in_dir = await asyncio.to_thread(os.listdir, download_path) if ospath.isdir(download_path) else [ospath.basename(download_path)]
    rar_files = [f for f in items_in_dir if f.lower().endswith(
        ('.rar', '.part01.rar', '.part001.rar', '.part1.rar'))]

    if not rar_files:
        _task_error.set_error("No RAR files found for streaming extraction")
        return None

    archive_path = ospath.join(download_path, rar_files[0]) if ospath.isdir(download_path) else download_path
    log.info(f"Starting streaming extract+upload for: {archive_path}")

    from ..utility.converters import extract_and_upload_streaming
    success = await extract_and_upload_streaming(
        rar_filepath=archive_path,
        password=_bot.Options.unzip_pswd if _bot.Options.unzip_pswd else None,
        file_filter=None,
        task_ctx=task_ctx
    )
    if not success:
        _task_error.set_error("Streaming extract-upload failed")
    return None  # Upload already done


async def _handle_archive_processing(download_path: str, action: str, task_ctx: TaskContext) -> str | None:
    """Handles standard zip, unzip, and dual-zip (undzip) batching/archive processing.

    This function completely encapsulates the chunking logic (950MB Telegram limits)
    and routes archive operations based on is_dir context.
    """
    _bot = task_ctx.bot
    _paths = task_ctx.paths
    _task_error = task_ctx.error

    current_mode = _bot.Mode.mode
    is_dir = (current_mode == "dir-leech")

    # Encapsulate the chunk size within the process stage
    chunk_size_bytes = get_max_split_size_mib() * 1024 * 1024

    log.info(f"[Process] Archive action '{action}' started. Source: {download_path}, is_dir: {is_dir}")

    if is_dir:
        # Directory Leech Processing Logic
        if not ospath.exists(download_path):
            _task_error.set_error(f"Dir-leech source missing: {download_path}")
            return None

        if action == "zip":
            await Zip_Handler(download_path, is_split=True, remove=False, task_ctx=task_ctx, max_split_size=chunk_size_bytes)
            return _paths.temp_zpath if not _task_error.state else None

        elif action == "unzip":
            await Unzip_Handler(download_path, remove=False, task_ctx=task_ctx)
            return _paths.temp_unzip_path if not _task_error.state else None

        elif action == "undzip":
            await Unzip_Handler(download_path, remove=False, task_ctx=task_ctx)
            if _task_error.state:
                return None
            await Zip_Handler(_paths.temp_unzip_path, is_split=True, remove=True, task_ctx=task_ctx, max_split_size=chunk_size_bytes)
            return _paths.temp_zpath if not _task_error.state else None
    else:
        # Link Leech Processing Logic
        if action == "zip":
            log.debug("[Process] Calling Zip_Handler...")
            await Zip_Handler(download_path, is_split=True, remove=True, task_ctx=task_ctx, max_split_size=chunk_size_bytes)
            return _paths.temp_zpath if not _task_error.state else None

        elif action == "unzip":
            log.debug("[Process] Calling Unzip_Handler...")
            await Unzip_Handler(download_path, remove=True, task_ctx=task_ctx)
            return _paths.temp_unzip_path if not _task_error.state else None

        elif action == "undzip":
            log.debug("[Process] Calling Unzip_Handler (dualzip)...")
            await Unzip_Handler(download_path, remove=True, task_ctx=task_ctx)
            if _task_error.state:
                return None
            log.debug("[Process] Calling Zip_Handler (dualzip)...")
            await Zip_Handler(_paths.temp_unzip_path, is_split=True, remove=True, task_ctx=task_ctx, max_split_size=chunk_size_bytes)
            return _paths.temp_zpath if not _task_error.state else None

        _task_error.set_error(f"Unknown archive action: {action}")
        return None


async def _handle_normal_processing(download_path: str, task_ctx: TaskContext) -> str | None:
    """Handles normal processing: returns path directly, or copies single file for dir-leech."""
    _bot = task_ctx.bot
    _paths = task_ctx.paths
    _task_error = task_ctx.error
    current_mode = _bot.Mode.mode
    is_dir = (current_mode == "dir-leech")

    final_path = None
    if is_dir:
        if not ospath.exists(download_path):
            _task_error.set_error(f"Dir-leech source missing: {download_path}")
            return None
        if ospath.isdir(download_path):
            final_path = download_path
        elif ospath.isfile(download_path):
            if not ospath.exists(_paths.temp_dirleech_path):
                makedirs(_paths.temp_dirleech_path, exist_ok=True)
            try:
                await async_copy(download_path, _paths.temp_dirleech_path, task_ctx)
                if task_ctx.cancel_event.is_set():
                    log.warning("File copy finished but task was actively cancelled.")
                    return None
                final_path = _paths.temp_dirleech_path
            except Exception as copy_err:
                log.error(f"Failed copy single file for dir-leech: {copy_err}")
                _task_error.set_error(f"Copy Error: {copy_err}")
                return None
        else:
            _task_error.set_error("Source path disappeared")
            return None
    else:
        log.debug("[Pipeline] Normal leech mode - no processing needed")
        final_path = download_path

    # Ensure every file is size-checked and split if it exceeds 1 GB
    if final_path:
        from .converters import sizeChecker
        import shutil
        if ospath.isdir(final_path):
            # List files inside final_path
            files = [ospath.join(final_path, f) for f in os.listdir(final_path) if ospath.isfile(ospath.join(final_path, f))]
            for fpath in files:
                did_split = await sizeChecker(fpath, remove=True, task_ctx=task_ctx)
                if did_split:
                    # Move all parts from temp_zpath back to final_path
                    temp_zpath = _paths.temp_zpath
                    if ospath.exists(temp_zpath):
                        for part in os.listdir(temp_zpath):
                            part_path = ospath.join(temp_zpath, part)
                            dest_path = ospath.join(final_path, part)
                            shutil.move(part_path, dest_path)
                        # Clean up temp_zpath
                        shutil.rmtree(temp_zpath, ignore_errors=True)
            return final_path
        else:
            # final_path is a single file
            did_split = await sizeChecker(final_path, remove=True, task_ctx=task_ctx)
            if did_split:
                return _paths.temp_zpath
            else:
                return final_path
    return None


async def _stage_process(download_path: str, task_ctx: TaskContext) -> str | None:
    """Process stage: handles zip, unzip, dualzip, stream_unzip or local copies.

    Args:
        download_path: The directory or file path to process.
        task_ctx: The execution TaskContext.

    Returns:
        The processed path to upload (str), or None if already uploaded (streaming) or failed.
    """
    if task_ctx.cancel_event.is_set():
        log.warning("[Pipeline] Process stage aborted: task actively cancelled.")
        task_ctx.error.set_error("Task actively cancelled.")
        return None

    _transfer = task_ctx.transfer
    _bot = task_ctx.bot

    # Set initial download size for status
    _transfer.total_down_size = getSize(download_path)
    log.info(f"[Pipeline] Processing. Size: {sizeUnit(_transfer.total_down_size)}, Type: {task_ctx.mode_type}")

    current_mode = _bot.Mode.mode
    mode_type = task_ctx.mode_type

    # Map normal mode under leech/dir-leech to zip if required by legacy logic
    # Upgrade: If 'normal' (Regular) is chosen, we ONLY compress to zip/7z if the total size is >= 1.8 GB.
    # Otherwise, it uploads the files directly as media (uncompressed).
    is_zip_leech = (
        mode_type == "normal" 
        and current_mode in ["leech", "dir-leech"] 
        and _transfer.total_down_size >= 1.8 * 1024 * 1024 * 1024
    )

    try:
        if mode_type == "zip" or is_zip_leech:
            return await _handle_archive_processing(download_path, "zip", task_ctx)
        elif mode_type == "unzip":
            return await _handle_archive_processing(download_path, "unzip", task_ctx)
        elif mode_type == "undzip":
            return await _handle_archive_processing(download_path, "undzip", task_ctx)
        elif mode_type == "stream_unzip":
            return await _handle_streaming_extraction(download_path, task_ctx)
        elif mode_type == "normal":
            return await _handle_normal_processing(download_path, task_ctx)
        else:
            log.warning(f"[Pipeline] Unknown mode_type: {mode_type}, falling back to normal processing")
            return await _handle_normal_processing(download_path, task_ctx)

    except Exception as processing_err:
        log.error(f"Error during processing stage: {processing_err}", exc_info=True)
        task_ctx.error.set_error(f"Processing error: {processing_err}")
        _transfer.total_down_size = 0
        return None


async def _stage_upload(processed_path: str | None, task_ctx: TaskContext) -> None:
    """Upload stage: uploads processed files to Telegram.

    Args:
        processed_path: The directory or file path to upload, or None (if already uploaded).
        task_ctx: The execution TaskContext.
    """
    _paths = task_ctx.paths
    _task_error = task_ctx.error

    if task_ctx.cancel_event.is_set():
        log.warning("[Pipeline] Upload stage aborted: task actively cancelled.")
        _task_error.set_error("Task actively cancelled.")
        return

    if processed_path is None:
        log.debug("[Pipeline] processed_path is None. Skipping upload stage (likely already processed/uploaded).")
        return

    if not ospath.exists(processed_path):
        log.error(f"[Pipeline] Upload path missing or invalid: {processed_path}")
        _task_error.set_error("Leech path invalid")
        return

    current_mode = task_ctx.bot.Mode.mode
    is_dir = (current_mode == "dir-leech")
    is_processed_temp = (processed_path in [_paths.temp_zpath, _paths.temp_unzip_path, _paths.temp_dirleech_path])
    cleanup_after_leech = not is_dir or is_processed_temp

    log.info(f"[Pipeline] Starting Leech handler for path: {processed_path}, cleanup_after_leech={cleanup_after_leech}")
    await Leech(processed_path, cleanup_after_leech, task_ctx)

    if task_ctx.cancel_event.is_set():
        log.warning("[Pipeline] Upload stage cancelled after Leech returned.")
        _task_error.set_error("Task actively cancelled.")
        return

    if _task_error.state:
        log.error("[Pipeline] Leech handler failed.")


# --- Refactored Do_Leech Orchestrator ---
async def Do_Leech(
        source,
        is_dir,
        is_ytdl,
        is_zip,
        is_unzip,
        is_dualzip,
        is_stream_unzip,
        task_ctx: TaskContext):
    """Execute leech operation (download + upload to Telegram).

    Args:
        source: List of URLs or directory path
        is_dir: Directory leech mode
        is_ytdl: YouTube-DL mode (legacy parameter)
        is_zip: Zip files before upload
        is_unzip: Unzip files before upload
        is_dualzip: Unzip then zip before upload
        is_stream_unzip: Streaming extract+upload for large archives
        task_ctx: Required. Strictly isolated TaskContext; no global fallback.
    """
    _paths = task_ctx.paths
    _task_error = task_ctx.error
    log.info(f"Do_Leech (Orchestrator) started. is_dir={is_dir}")
    original_down_path = _paths.down_path  # Store original base download path
    overall_success = True

    try:
        if is_dir:
            source_path_item = source[0]
            log.info(f"Do_Leech [Dir Mode]: Orchestrating processing for {source_path_item}")

            # 1. Processing Stage
            processed_path = await _stage_process(source_path_item, task_ctx)
            if _task_error.state:
                raise Exception(_task_error.text)

            # 2. Upload Stage
            await _stage_upload(processed_path, task_ctx)
            if _task_error.state:
                raise Exception(_task_error.text)
        else:
            source_links = list(source)
            if len(source_links) == 1 and is_torrent(source_links[0]):
                log.info("Single torrent/magnet link detected in Do_Leech. Using streaming torrent downloader.")
                from ..downlader.aria2 import download_and_upload_torrent_streaming
                success = await download_and_upload_torrent_streaming(source_links[0], task_ctx)
                if not success:
                    overall_success = False
                    if not _task_error.state:
                        _task_error.set_error("Streaming torrent download failed")
                return

            batch_size = getattr(task_ctx.bot.Options, 'batch_size', 1)
            total_links = len(source_links)

            # Validate filenames count if provided
            full_filenames_list = task_ctx.bot.Options.filenames if task_ctx.bot.Options.filenames else []
            manual_filenames_provided = bool(full_filenames_list)
            if manual_filenames_provided and len(full_filenames_list) != total_links:
                log.error(f"Do_Leech Error: Initial filename count ({len(full_filenames_list)}) doesn't match link count ({total_links}).")
                _task_error.set_error("Initial filename/link count mismatch.")
                raise Exception(_task_error.text)

            log.info(f"Do_Leech [Link Mode]: Orchestrating {total_links} links in batches of {batch_size}.")

            # --- Batch loop ---
            for i in range(0, total_links, batch_size):
                if task_ctx.cancel_event.is_set():
                    log.warning("Task actively cancelled. Breaking batch loop in Do_Leech.")
                    overall_success = False
                    break

                if _task_error.state:
                    log.warning(f"Skipping further batches due to earlier critical error: {_task_error.text}")
                    overall_success = False
                    break

                batch_start_index = i
                batch_end_index = min(i + batch_size, total_links)
                batch_links = source_links[batch_start_index:batch_end_index]

                log.info(f"--- Processing Batch {i // batch_size + 1} / {total_links} ---")

                # 1. Stage: Download
                download_path = await _stage_download(batch_links, task_ctx)
                if not download_path:
                    overall_success = False
                    continue

                # 2. Stage: Process
                processed_path = await _stage_process(download_path, task_ctx)
                if _task_error.state:
                    overall_success = False
                    break

                # 3. Stage: Upload
                await _stage_upload(processed_path, task_ctx)
                if _task_error.state:
                    overall_success = False
                    break

                log.info("--- Finished Batch ---")

    except Exception as leech_err:
        log.error(f"Error in Do_Leech main execution: {leech_err}", exc_info=True)
        if not _task_error.state:
            _task_error.set_error(f"Unexpected Leech Error: {leech_err}")
        overall_success = False

    finally:
        # Restore original download path
        if _paths.down_path != original_down_path:
            _paths.down_path = original_down_path

        # Final cleanup / reporting
        if overall_success and not _task_error.state:
            log.info("Do_Leech completed successfully. Calling SendLogs...")
            await SendLogs(True, task_ctx)
        elif not overall_success:
            log.warning("Do_Leech completed with errors.")
            if not _task_error.state:
                _task_error.set_error(_task_error.text or "Task completed with errors.")
        else:
            log.warning("Do_Leech finished in inconsistent state.")
            if not _task_error.state:
                _task_error.set_error("Inconsistent final state")


# --- Do_Mirror Function ---
async def Do_Mirror(
        source,
        is_ytdl,
        is_zip,
        is_unzip,
        is_dualzip,
        is_stream_unzip,
        task_ctx: TaskContext):
    """Execute mirror operation (download + copy to local directory).

    Args:
        source: List of URLs
        is_ytdl: YouTube-DL mode (legacy parameter)
        is_zip: Zip files before mirroring
        is_unzip: Unzip files before mirroring
        is_dualzip: Unzip then zip before mirroring
        is_stream_unzip: Streaming extract+upload for large archives
        task_ctx: Required. Strictly isolated TaskContext; no global fallback.
    """
    _bot = task_ctx.bot
    _paths = task_ctx.paths
    _transfer = task_ctx.transfer
    _messages = task_ctx.messages
    _task_error = task_ctx.error
    log.info(
        f"Do_Mirror using TaskContext for task_id: {task_ctx.task_id}"
    )

    log.info(
        f"Do_Mirror started. is_ytdl(legacy)={is_ytdl}, is_zip={is_zip}, is_unzip={is_unzip}, is_dualzip={is_dualzip}, is_stream_unzip={is_stream_unzip}")
    selected_service = _bot.Options.service_type

    # Ensure local mirror directory exists
    if not ospath.exists(_paths.mirror_dir):
        try:
            makedirs(_paths.mirror_dir)
            log.info(f"Created local mirror directory: {_paths.mirror_dir}")
        except Exception as mkdir_err:
            _task_error.state = True
            _task_error.text = f"Cannot create local mirror dir: {mkdir_err}"
            log.error(_task_error.text)
            return

    original_down_path = _paths.down_path

    if not is_ytdl and len(source) == 1 and is_torrent(source[0]):
        log.info("Single torrent/magnet link detected in Do_Mirror. Using streaming torrent downloader.")
        from ..downlader.aria2 import download_and_upload_torrent_streaming
        success = await download_and_upload_torrent_streaming(source[0], task_ctx)
        if not success:
            if not _task_error.state:
                _task_error.set_error("Streaming torrent download failed")
        return
    download_completed = False
    # --- Initialize cleanup variables ---
    cleanup_temp = False
    temp_path_to_clean = None
    dualzip_unzip_path = None
    mirror_dir_final = None
    # --- End Initializations ---

    try:
        # --- Download Phase ---
        log.info(
            f"Do_Mirror: Processing links via downloadManager (Service: {selected_service or 'auto'})..."
        )
        filenames_to_pass = _bot.Options.filenames if _bot.Options.filenames else None
        log.debug(
            f"Do_Mirror: Passing filenames list (Count: {len(filenames_to_pass) if filenames_to_pass else 0}) to downloadManager."
        )

        # Pass the retrieved filenames list to downloadManager
        await downloadManager(source, is_ytdl, filenames_to_pass, task_ctx)

        # Check _task_error state *after* downloadManager returns
        if _task_error.state:
            log.error(
                "Download failed before mirroring (downloadManager reported error).")
            return  # Stop Do_Mirror if download failed
        else:
            download_completed = True
            log.info("Do_Mirror: Download phase completed successfully.")

        # --- Mirroring Phase ---
        if download_completed:
            process_path = original_down_path  # Start with the original download path

            if not ospath.exists(process_path) or not os.listdir(process_path):
                log.warning(
                    f"Mirror download path empty/missing after successful download: {process_path}")
                if not _task_error.state:
                    _task_error.state = True
                    _task_error.text = "Mirror download inconsistency (Empty Dir)."
                return

            _transfer.total_down_size = getSize(process_path)
            applyCustomName(task_ctx)
            log.info(
                f"Download complete for mirror. Size: {sizeUnit(_transfer.total_down_size)}."
            )

            # Determine final mirror destination folder name
            mirror_base_name = _messages.download_name if _messages.download_name else ospath.basename(
                process_path if process_path != original_down_path else source[0] if isinstance(
                    source, list) and source else "Mirrored_Item")
            mirror_base_name, _ = ospath.splitext(
                mirror_base_name)  # Remove extension
            mirror_dir_final = ospath.join(_paths.mirror_dir, mirror_base_name)
            log.info(f"Target mirror directory set to: {mirror_dir_final}")
            if not ospath.exists(mirror_dir_final):
                makedirs(mirror_dir_final, exist_ok=True)

            source_path_for_copy = process_path  # Path containing files to be copied

            # Zip/Unzip processing before copy
            if is_zip:
                await Zip_Handler(process_path, True, True, task_ctx)
                source_path_for_copy = _paths.temp_zpath
                cleanup_temp = True
                temp_path_to_clean = _paths.temp_zpath
            elif is_stream_unzip:
                from ..utility.converters import extract_and_upload_streaming
                items = await asyncio.to_thread(os.listdir, process_path) if ospath.isdir(process_path) else [ospath.basename(process_path)]
                rars = [f for f in items if f.lower().endswith(
                    ('.rar', '.part01.rar', '.part001.rar', '.part1.rar'))]
                if not rars:
                    _task_error.state = True
                    _task_error.text = "No RAR for streaming"
                    return
                archive = ospath.join(process_path, rars[0]) if ospath.isdir(
                    process_path) else process_path
                success = await extract_and_upload_streaming(archive, _bot.Options.unzip_pswd if _bot.Options.unzip_pswd else None, None, task_ctx)
                if not success:
                    _task_error.state = True
                    return
                source_path_for_copy = None
                cleanup_temp = False  # Already uploaded
            elif is_unzip:
                await Unzip_Handler(process_path, True, task_ctx)
                source_path_for_copy = _paths.temp_unzip_path
                cleanup_temp = True
                temp_path_to_clean = _paths.temp_unzip_path
            elif is_dualzip:
                await Unzip_Handler(process_path, True, task_ctx)
                await Zip_Handler(_paths.temp_unzip_path, True, True, task_ctx)
                source_path_for_copy = _paths.temp_zpath
                cleanup_temp = True
                temp_path_to_clean = _paths.temp_zpath
                dualzip_unzip_path = _paths.temp_unzip_path

            if _task_error.state:
                log.error("Zip/Unzip failed before mirroring copy.")
                return
            if not ospath.exists(source_path_for_copy):
                log.error(
                    f"Mirror source path not found after processing: {source_path_for_copy}")
                if not _task_error.state:
                    _task_error.state = True
                    _task_error.text = "Mirror source path invalid."
                return

            # --- Mirror Copy Logic ---
            log.info(
                f"Mirroring content from {source_path_for_copy} to LOCAL Colab path: {mirror_dir_final}")
            try:
                mirror_items = await asyncio.to_thread(os.listdir, source_path_for_copy)
                for item in mirror_items:
                    if task_ctx.cancel_event.is_set():
                        log.warning("Active cancellation detected during mirror copy loop.")
                        _task_error.state = True
                        _task_error.text = "Mirror copy actively cancelled by user."
                        break
                    s_item = ospath.join(source_path_for_copy, item)
                    d_item = ospath.join(mirror_dir_final, item)
                    await async_copy(s_item, d_item, task_ctx)
                if not _task_error.state:
                    log.info(
                        f"Successfully mirrored content to {mirror_dir_final}")
            except Exception as copy_err:
                log.error(
                    f"Error mirroring content: {copy_err}",
                    exc_info=True)
                _task_error.state = True
                _task_error.text = f"Mirror copy error: {copy_err}"

        else:
            log.warning("Skipping mirror processing due to download failure.")

    except Exception as mirror_err:
        log.error(
            f"Error in Do_Mirror main execution: {mirror_err}",
            exc_info=True)
        if not _task_error.state:
            _task_error.state = True
            _task_error.text = f"Unexpected Mirror Error: {mirror_err}"
    finally:
        # Cleanup logic using initialized variables
        log.debug(
            f"Do_Mirror finally block reached. cleanup_temp={cleanup_temp}")
        if cleanup_temp and temp_path_to_clean and ospath.exists(
                temp_path_to_clean):
            log.info(
                f"Cleaning up mirror temp processing dir: {temp_path_to_clean}")
            shutil.rmtree(temp_path_to_clean, ignore_errors=True)
        if dualzip_unzip_path and ospath.exists(dualzip_unzip_path):
            log.info(
                f"Cleaning up mirror dualzip temp dir: {dualzip_unzip_path}")
            shutil.rmtree(dualzip_unzip_path, ignore_errors=True)
        if _paths.down_path != original_down_path:
            _paths.down_path = original_down_path
            log.debug("Restored original _paths.down_path for Mirror")

    # Final logging/reporting based on _task_error state
    if _task_error.state:
        log.warning(
            f"Do_Mirror finished with error: {_task_error.text}. Logs skipped/Cancel called."
        )
    else:
        log.info("Do_Mirror completed without error state. Sending logs...")
        await SendLogs(False, task_ctx)  # False indicates Mirror mode
        log.info("Do_Mirror finished successfully.")


# --- Do_GDrive_Upload Function ---
async def Do_GDrive_Upload(
        source,
        is_dir,
        is_ytdl,
        is_zip,
        is_unzip,
        is_dualzip,
        is_stream_unzip,
        task_ctx: TaskContext):
    """Execute Google Drive upload operation (download + upload to Google Drive).

    Args:
        source: List of URLs or directory path
        is_dir: Directory upload mode
        is_ytdl: YouTube-DL mode (legacy parameter)
        is_zip: Zip files before upload
        is_unzip: Unzip files before upload
        is_dualzip: Unzip then zip before upload
        is_stream_unzip: Streaming extract+upload for large archives
        task_ctx: Required. Strictly isolated TaskContext; no global fallback.
    """
    _bot = task_ctx.bot
    _paths = task_ctx.paths
    _transfer = task_ctx.transfer
    _messages = task_ctx.messages
    _task_error = task_ctx.error
    log.info(
        f"Do_GDrive_Upload using TaskContext for task_id: {task_ctx.task_id}"
    )

    log.info(
        f"Do_GDrive_Upload started. is_dir={is_dir}, is_ytdl(legacy)={is_ytdl}, is_zip={is_zip}, is_unzip={is_unzip}, is_dualzip={is_dualzip}, is_stream_unzip={is_stream_unzip}")

    overall_success = True
    full_filenames_list = _bot.Options.filenames if _bot.Options.filenames else []

    # Initialize Google Drive service
    from ..downlader.gdrive import build_service
    from ..utility.variables import Gdrive

    try:
        await build_service()

        if not Gdrive.service:
            log.error("Do_GDrive_Upload: Google Drive service not available")
            _task_error.state = True
            _task_error.text = "Google Drive authentication failed. Token.pickle not found or invalid."
            return

        if not is_dir and len(source) == 1 and is_torrent(source[0]):
            log.info("Single torrent/magnet link detected in Do_GDrive_Upload. Using streaming torrent downloader.")
            from ..downlader.aria2 import download_and_upload_torrent_streaming
            success = await download_and_upload_torrent_streaming(source[0], task_ctx)
            if not success:
                overall_success = False
                if not _task_error.state:
                    _task_error.set_error("Streaming torrent download failed")
            else:
                log.info("Do_GDrive_Upload completed successfully. Calling SendLogs...")
                await SendLogs(True, task_ctx)
            return

        log.info("Do_GDrive_Upload: Google Drive service initialized successfully")

        # --- Handle Directory Upload (No Batching) ---
        if is_dir:
            log.info("Do_GDrive_Upload: Directory mode selected.")
            source_path_item = source[0]
            log.info(
                f"Do_GDrive_Upload: Processing directory/file {source_path_item}")

            process_source_path = source_path_item
            gdrive_upload_path = None
            cleanup_after_upload = True

            if not ospath.exists(process_source_path):
                _task_error.state = True
                _task_error.text = f"Dir-upload source missing: {process_source_path}"
                raise Exception(_task_error.text)

            # Apply Zip/Unzip processing
            if is_zip:
                await Zip_Handler(process_source_path, False, False, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
                gdrive_upload_path = _paths.temp_zpath
            elif is_unzip:
                await Unzip_Handler(process_source_path, False, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
                gdrive_upload_path = _paths.temp_unzip_path
            elif is_dualzip:
                await Unzip_Handler(process_source_path, False, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
                await Zip_Handler(_paths.temp_unzip_path, True, True, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
                gdrive_upload_path = _paths.temp_zpath
            else:
                if ospath.isdir(process_source_path):
                    gdrive_upload_path = process_source_path
                    cleanup_after_upload = False
                elif ospath.isfile(process_source_path):
                    if not ospath.exists(_paths.temp_dirleech_path):
                        makedirs(_paths.temp_dirleech_path, exist_ok=True)
                    try:
                        await async_copy(
                            process_source_path,
                            _paths.temp_dirleech_path,
                            task_ctx)
                        gdrive_upload_path = _paths.temp_dirleech_path
                    except Exception as copy_err:
                        log.error(
                            f"Failed copy single file for dir-gdrive: {copy_err}")
                        _task_error.state = True
                        _task_error.text = f"Copy Error: {copy_err}"
                        raise Exception(_task_error.text)
                else:
                    _task_error.state = True
                    _task_error.text = "Source path disappeared"
                    raise Exception(_task_error.text)

            # Call Google Drive Upload handler
            if gdrive_upload_path and ospath.exists(gdrive_upload_path):
                log.info(
                    f"Do_GDrive_Upload: Starting GDrive upload for dir from path: {gdrive_upload_path}")
                from ..uploader.gdrive import GDrive_Upload
                await GDrive_Upload(gdrive_upload_path, cleanup_after_upload, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
            elif not _task_error.state:
                log.error(
                    f"Processing failed or gdrive path missing for dir-gdrive: {gdrive_upload_path}")
                _task_error.state = True
                _task_error.text = f"Dir processing error ({_bot.Mode.type})"
                raise Exception(_task_error.text)

        # --- Handle Link Modes with Batch Processing ---
        else:
            source_links = list(source)
            batch_size = getattr(task_ctx.bot.Options, 'batch_size', 1)
            total_links = len(source_links)
            manual_filenames_provided = bool(full_filenames_list)

            if manual_filenames_provided and len(
                    full_filenames_list) != total_links:
                log.error(
                    f"Do_GDrive_Upload Error: Initial filename count ({len(full_filenames_list)}) doesn't match link count ({total_links})."
                )
                _task_error.state = True
                _task_error.text = "Initial filename/link count mismatch."
                raise Exception(_task_error.text)

            log.info(
                f"Do_GDrive_Upload: Link mode selected. Processing {total_links} links in batches of {batch_size}.")

            # --- Batch Processing Loop ---
            for i in range(0, total_links, batch_size):
                if task_ctx.cancel_event.is_set():
                    log.warning("Task actively cancelled. Breaking GDrive upload batch loop.")
                    overall_success = False
                    break

                batch_links = source_links[i:i + batch_size]
                batch_filenames = full_filenames_list[i:i +
                                                      batch_size] if manual_filenames_provided else []

                batch_end = min(i + batch_size, total_links)
                total_batches = (total_links + batch_size - 1) // batch_size
                log.info(
                    f"--- Processing Batch {i // batch_size + 1} ({i + 1}-{batch_end}) / {total_batches} ---"
                )

                # Clean work directories
                batch_download_path = _paths.down_path
                log.info(
                    f"Cleaning work directories before batch {i // batch_size + 1}... Target: {batch_download_path}"
                )
                if ospath.exists(batch_download_path):
                    shutil.rmtree(batch_download_path, ignore_errors=True)
                makedirs(batch_download_path, exist_ok=True)

                # Download batch
                # Clear error state for this batch so downloadManager can
                # signal a failure without any cross-batch bleed.
                log.info("Downloading batch %d...", i // batch_size + 1)
                _task_error.clear()

                try:
                    await downloadManager(batch_links, is_ytdl, batch_filenames, task_ctx)

                    if _task_error.state:
                        log.warning(
                            "Batch %d download had failures: %s",
                            i // batch_size + 1, _task_error.text,
                        )
                except Exception as download_err:
                    log.error(
                        "Download error in batch %d: %s",
                        i // batch_size + 1, download_err, exc_info=True)
                    # Register the error so the empty-dir check below can skip
                    # the upload phase instead of proceeding with no files.
                    _task_error.set_error(
                        f"Download error (batch {i // batch_size + 1}): {download_err}")

                # Check if download directory has files
                if not ospath.exists(batch_download_path) or not os.listdir(
                        batch_download_path):
                    log.warning(
                        "Batch %d download directory empty or missing. "
                        "Skipping processing/upload.",
                        i // batch_size + 1,
                    )
                    overall_success = False
                    continue

                # --- Process and Upload ---
                log.info(
                    f"Processing/Uploading downloaded files for batch {i // batch_size + 1}...")
                batch_processing_error = False

                try:
                    _transfer.total_down_size = getSize(batch_download_path)
                    log.info(
                        f"Batch download size: {sizeUnit(_transfer.total_down_size)}. Processing type: {_bot.Mode.type}"
                    )

                    process_path = batch_download_path
                    gdrive_upload_path = None

                    # --- Zip/Unzip Logic ---
                    if is_zip:
                        log.debug(">>> Calling Zip_Handler...")
                        await Zip_Handler(process_path, True, True, task_ctx)
                        if _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Zip_Handler failed.")
                        else:
                            gdrive_upload_path = _paths.temp_zpath
                            log.debug(
                                ">>> Zip successful. gdrive_upload_path: %s",
                                gdrive_upload_path)
                    elif is_unzip:
                        log.debug(">>> Calling Unzip_Handler...")
                        await Unzip_Handler(process_path, True, task_ctx)
                        if _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Unzip_Handler failed.")
                        else:
                            gdrive_upload_path = _paths.temp_unzip_path
                            log.debug(
                                ">>> Unzip successful. gdrive_upload_path: %s",
                                gdrive_upload_path)
                    elif is_dualzip:
                        log.debug(">>> Calling Unzip_Handler (dualzip)...")
                        await Unzip_Handler(process_path, True, task_ctx)
                        if _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Unzip_Handler (dualzip) failed.")
                        else:
                            log.debug(">>> Calling Zip_Handler (dualzip)...")
                            await Zip_Handler(_paths.temp_unzip_path, True, True, task_ctx)
                            if _task_error.state:
                                batch_processing_error = True
                                log.error(">>> Zip_Handler (dualzip) failed.")
                            else:
                                gdrive_upload_path = _paths.temp_zpath
                                log.debug(
                                    ">>> Dualzip successful. gdrive_upload_path: %s",
                                    gdrive_upload_path)
                    else:
                        # Normal mode - no processing needed
                        log.debug(
                            ">>> Normal GDrive upload mode - no processing needed")
                        gdrive_upload_path = process_path
                        log.debug(
                            ">>> Normal mode. gdrive_upload_path: %s",
                            gdrive_upload_path)

                    # Check for processing errors before upload
                    if _task_error.state:
                        log.error("Zip/Unzip failed before GDrive upload.")
                        batch_processing_error = True
                    # Call GDrive Upload handler
                    elif gdrive_upload_path is not None and ospath.exists(gdrive_upload_path):
                        log.info(
                            "Do_GDrive_Upload batch: Starting GDrive upload for path: %s",
                            gdrive_upload_path)
                        from ..uploader.gdrive import GDrive_Upload
                        await GDrive_Upload(gdrive_upload_path, True, task_ctx)
                        if _task_error.state:
                            log.error(">>> GDrive upload failed.")
                            batch_processing_error = True
                        else:
                            log.debug(
                                ">>> GDrive upload successful for batch %d",
                                i // batch_size + 1)
                    else:
                        log.error(
                            "GDrive upload path missing or invalid: %s",
                            gdrive_upload_path)
                        batch_processing_error = True
                        _task_error.set_error("GDrive upload path invalid")

                except Exception as processing_err:
                    log.error(
                        "Error during batch processing: %s",
                        processing_err, exc_info=True)
                    batch_processing_error = True
                    _task_error.set_error(f"Processing error: {processing_err}")
                    # Clear stale size so it cannot bleed into the next batch
                    _transfer.total_down_size = 0

                # Handle critical processing errors -> Break the main loop
                if batch_processing_error:
                    overall_success = False
                    if not _task_error.state:
                        _task_error.set_error("Processing/Upload Error")
                    log.error(
                        "Critical processing/upload error detected. Stopping batch loop.")
                    break

                log.info("--- Finished Batch ---")

    except Exception as gdrive_err:
        log.error(
            "Error in Do_GDrive_Upload main execution: %s",
            gdrive_err, exc_info=True)
        if not _task_error.state:
            _task_error.set_error(f"Unexpected GDrive Error: {gdrive_err}")
        overall_success = False

    # --- Final cleanup logic ---
    if overall_success and not _task_error.state:
        log.info("Do_GDrive_Upload completed successfully. Calling SendLogs...")
        await SendLogs(True, task_ctx)  # True for non-mirror mode
    elif not overall_success:
        log.warning("Do_GDrive_Upload completed with errors.")
        if not _task_error.state:
            _task_error.set_error(_task_error.text or "Task completed with errors.")
        log.info("Do_GDrive_Upload finished with errors.")
