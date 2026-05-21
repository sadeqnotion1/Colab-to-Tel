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
from .. import OWNER, colab_bot, DUMP_ID
from ..downlader.manager import calDownSize, get_d_name, downloadManager
from .helper import (
    getSize, applyCustomName, keyboard, sysINFO, is_google_drive,
    is_telegram, is_mega, is_terabox, is_torrent,
    clean_filename, sizeUnit
)
from .message_safety import user_error
from .ui_copy import build_task_in_progress_notice
from .handler import (
    Leech, Unzip_Handler, Zip_Handler, SendLogs, cancelTask,
)

from .variables import (
    BOT, MSG, BotTimes, Messages, Paths, Aria2c, TaskError,
    TRANSFER
)

# Import task context for multi-task support
from .task_context import TASK_QUEUE, TaskContext


log = logging.getLogger(__name__)

# Random thumbnail pool loaded from external file
def _load_thumbnail_urls():
    _file = ospath.join(ospath.dirname(__file__), "thumbnail_urls.txt")
    if ospath.exists(_file):
        with open(_file, "r", encoding="utf-8") as f:
            return [line.strip() for line in f if line.strip() and not line.strip().startswith("#")]
    return []

thumbnail_urls = _load_thumbnail_urls()


async def task_starter(message, text):
    """Handles the initial command, replies, and sets started state."""
    global BOT
    log.info(
        f"task_starter called by user {message.from_user.id} for mode '{BOT.Mode.mode}'"
    )
    try:
        await message.delete()
        log.debug("User command message deleted.")
    except Exception as e:
        log.error(f"Failed to delete user command message: {e}")

    if not BOT.State.task_going:
        BOT.State.started = True
        log.debug(
            f"BOT.State.started=True. BOT.State.task_going={BOT.State.task_going}"
        )
        log.info("Task not going. Replying to user to send links/path.")
        try:
            src_request_msg = await message.reply_text(
                text,
                parse_mode=enums.ParseMode.HTML,
            )
            log.info("Reply prompt sent.")
            return src_request_msg
        except Exception as e:
            log.error(f"Failed reply in task_starter: {e}", exc_info=True)
            BOT.State.started = False
            try:
                await message.reply_text(user_error("send the setup prompt"))
            except Exception as reply_err:
                log.debug(
                    f"Could not send task starter error reply: {reply_err}")
            return None
    else:

        log.warning("Task already going. Informing user.")
        try:
            msg = await message.reply_text(build_task_in_progress_notice())
            await sleep(15)
            await msg.delete()
        except Exception as e:
            log.error(f"Failed 'task ongoing' message: {e}")
        return None


async def taskScheduler(task_ctx: TaskContext):
    """Main function to orchestrate the download/upload task.

    Args:
        task_ctx: TaskContext for this task execution.
    """
    global BOT, MSG, BotTimes, Messages, Paths, TRANSFER, TaskError

    if task_ctx is None:
        raise ValueError("taskScheduler requires task_ctx")

    _bot = task_ctx.bot
    _msg = task_ctx  # TaskContext has status_msg and sent_msg directly!
    _messages = task_ctx.messages
    _paths = task_ctx.paths
    _transfer = task_ctx.transfer
    _task_error = task_ctx.error
    log.info(
        f"taskScheduler using TaskContext for task_id: {task_ctx.task_id}"
    )

    selected_service = _bot.Options.service_type
    log.info(
        f"taskScheduler entered. Mode: {_bot.Mode.mode}, Type: {_bot.Mode.type}, Service: {selected_service}"
    )
    src_text = []
    is_dualzip = (_bot.Mode.type == "undzip")
    is_unzip = (_bot.Mode.type == "unzip")
    # NEW: Streaming extract+upload for large archives
    is_stream_unzip = (_bot.Mode.type == "stream_unzip")
    is_zip = (_bot.Mode.type == "zip")
    current_mode = _bot.Mode.mode
    is_dir = (current_mode == "dir-leech")

    # Store original download path in case it's modified (e.g., for zip mode)
    original_Paths_down_path = _paths.down_path

    try:  # Main try block for the entire task
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

        # --- Conditional Random Thumbnail Download ---
        default_pic_url = Aria2c.pic_dwn_url  # Get default from Aria2c settings
        chosen_url = None
        hero_image_path = _paths.HERO_IMAGE  # Path where thumbnail will be saved

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

        # --- Download the chosen thumbnail (Your existing download logic) ---
        download_success = False  # Flag to track if download worked
        if chosen_url:
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

            # ===== PARALLEL MODE: Skip individual messages, use shared dashboa
            # Check if we're in parallel mode by seeing if we're part of
            # TASK_QUEUE
            is_parallel_mode = False
            if task_ctx:
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
                        _msg.status_msg = await colab_bot.send_message(chat_id=OWNER, text=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__ (Thumbnail Error)" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()) if task_ctx else keyboard())
                    else:
                        try:
                            _msg.status_msg = await colab_bot.send_photo(chat_id=OWNER, photo=img_to_send, caption=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()) if task_ctx else keyboard())
                        except Exception as photo_err:
                            log.warning(
                                f"Failed to send photo (MD5 or other error): {photo_err}. Sending text-only message.")
                            _msg.status_msg = await colab_bot.send_message(chat_id=OWNER, text=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()) if task_ctx else keyboard())
                else:
                    try:
                        _msg.status_msg = await colab_bot.send_photo(chat_id=OWNER, photo=img_to_send, caption=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()) if task_ctx else keyboard())
                    except Exception as photo_err:
                        log.warning(
                            f"Failed to send photo (MD5 or other error): {photo_err}. Sending text-only message.")
                        _msg.status_msg = await colab_bot.send_message(chat_id=OWNER, text=_messages.task_msg + _messages.status_head + "\n📝 __Initializing...__" + sysINFO(), reply_markup=keyboard(task_ctx.get_short_id()) if task_ctx else keyboard())
            elif is_parallel_mode and _msg.status_msg:
                # In parallel mode, we keep the individual status message (e.g., the "Processing..." prompt)
                # so it can be used for final logs/summary by SendLogs.
                log.info(
                    f"Parallel mode detected - keeping existing status message for task {task_ctx.get_short_id() if task_ctx else 'N/A'}"
                )
            else:
                # Status message already exists (shared message for parallel
                # tasks)
                log.info(
                    f"Skipping status message creation - using existing shared message for task {task_ctx.get_short_id() if task_ctx else 'N/A'}"
                )

        except Exception as msg_err:
            log.error(
                f"Error sending initial task messages: {msg_err}",
                exc_info=True)
            _task_error.state = True
            _task_error.text = f"Failed send status: {msg_err}"
            # Return early if status sending fails critically
            # No need to explicitly return, finally block handles cancellation
            # if TaskError is set
            pass  # Allow finally block to handle cancellation

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
                task_id_for_keyboard = task_ctx.get_short_id() if task_ctx else None
                if _msg.status_msg:
                    await _msg.status_msg.edit_caption(caption=_messages.task_msg + _messages.status_head + "\n📝 __Waiting for downloader...__" + sysINFO(), reply_markup=keyboard(task_id_for_keyboard))

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
            BotTimes.current_time = time()  # Update time before starting main work
            is_ytdl_task = (selected_service == 'ytdl') or _bot.Mode.ytdl
            log.info(
                f"Starting main task execution: Mode={current_mode}, Service={selected_service}, is_ytdl={is_ytdl_task}")
            if current_mode == "leech":
                await Do_Leech(_bot.SOURCE, is_dir, is_ytdl_task, is_zip, is_unzip, is_dualzip, is_stream_unzip, task_ctx)
            elif current_mode == "mirror":
                await Do_Mirror(_bot.SOURCE, is_ytdl_task, is_zip, is_unzip, is_dualzip, is_stream_unzip, task_ctx)
            elif current_mode == "gdrive":
                await Do_GDrive_Upload(_bot.SOURCE, is_dir, is_ytdl_task, is_zip, is_unzip, is_dualzip, is_stream_unzip, task_ctx)
            else:
                log.error(f"Unknown mode: {current_mode}")
                _task_error.state = True
                _task_error.text = f"Invalid mode: {current_mode}"

    except Exception as scheduler_err:
        log.error(
            f"Error within taskScheduler main try block: {scheduler_err}",
            exc_info=True)
        # Set error state if one hasn't been set already
        if not _task_error.state:
            _task_error.state = True
            _task_error.text = f"Scheduler Error: {scheduler_err}"
            # Don't call cancelTask here, finally block will handle it
    finally:
        # This block runs whether an exception occurred or not
        log.info(
            "taskScheduler finished or encountered error. Entering finally block.")
        # Restore original download path if it was changed
        if _paths.down_path != original_Paths_down_path:
            _paths.down_path = original_Paths_down_path
            log.debug("Restored original _paths.down_path")

        # Check if an error occurred during the task
        if _task_error.state:
            log.warning(
                f"Task failed. Reason: {_task_error.text}. Initiating cancellation/cleanup."
            )
            # Call cancelTask only if it wasn't the source of the error itself
            # This check might be complex depending on specific errors caught above
            # A simple approach is to always call it if TaskError.state is True
            await cancelTask(f"Task Failed: {_task_error.text}", task_ctx)
        else:
            log.info(
                "taskScheduler completed successfully (no TaskError set). Logs should be sent by Do_Leech/Do_Mirror.")
        # Note: SendLogs is called within Do_Leech/Do_Mirror on success.
        # cancelTask handles cleanup and status updates on failure.


# --- NEW Do_Leech Function with Batch Processing ---
# --- Replace the ENTIRE Do_Leech function with this ---
async def Do_Leech(
        source,
        is_dir,
        is_ytdl,
        is_zip,
        is_unzip,
        is_dualzip,
        is_stream_unzip,
        task_ctx=None):
    """Execute leech operation (download + upload to Telegram).

    Args:
        source: List of URLs or directory path
        is_dir: Directory leech mode
        is_ytdl: YouTube-DL mode (legacy parameter)
        is_zip: Zip files before upload
        is_unzip: Unzip files before upload
        is_dualzip: Unzip then zip before upload
        is_stream_unzip: Streaming extract+upload for large archives
        task_ctx: Optional TaskContext for multi-task support
    """
    global BOT, TRANSFER, Paths, Messages, TaskError, log  # Ensure log is accessible

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _transfer = task_ctx.transfer
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        log.info(f"Do_Leech using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _transfer = TRANSFER
        _messages = Messages
        _task_error = TaskError
        log.info("Do_Leech using global state (single-task mode)")

    log.info(
        f"Do_Leech started. is_dir={is_dir}, is_ytdl(legacy)={is_ytdl}, is_zip={is_zip}, is_unzip={is_unzip}, is_dualzip={is_dualzip}, is_stream_unzip={is_stream_unzip}")
    original_down_path = _paths.down_path  # Store original base download path
    overall_success = True  # Track if all batches succeeded
    # Get the full list of filenames if provided manually
    full_filenames_list = _bot.Options.filenames if _bot.Options.filenames else []

    # --- Main Try Block for Do_Leech ---
    try:
        # --- Handle Directory Leech (No Batching) ---
        if is_dir:
            # <<< Keep your existing, working dir-leech logic here >>>
            # <<< Ensure it correctly sets TaskError.state on failure >>>
            # Example Structure (replace with your actual logic):
            log.info("Do_Leech: Directory mode selected.")
            source_path_item = source[0]
            log.info(f"Do_Leech: Processing directory/file {source_path_item}")
            process_source_path = source_path_item
            leech_target_path = None
            cleanup_after_leech = True

            if not ospath.exists(process_source_path):
                _task_error.state = True
                _task_error.text = f"Dir-leech source missing: {process_source_path}"
                raise Exception(_task_error.text)  # Raise to exit via finally

            # Apply Zip/Unzip processing
            if is_zip:
                await Zip_Handler(process_source_path, True, False, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
                leech_target_path = _paths.temp_zpath
            elif is_stream_unzip:
                # NEW: Streaming extract+upload for large archives (65GB+)
                from ..utility.converters import extract_and_upload_streaming
                items_in_dir = await asyncio.to_thread(os.listdir, process_source_path) if ospath.isdir(process_source_path) else [ospath.basename(process_source_path)]
                rar_files = [f for f in items_in_dir if f.lower().endswith(
                    ('.rar', '.part01.rar', '.part001.rar', '.part1.rar'))]
                if not rar_files:
                    raise Exception(
                        "No RAR files found for streaming extraction")
                archive_path = ospath.join(process_source_path, rar_files[0]) if ospath.isdir(
                    process_source_path) else process_source_path
                success = await extract_and_upload_streaming(
                    rar_filepath=archive_path,
                    password=_bot.Options.unzip_pswd if _bot.Options.unzip_pswd else None,
                    file_filter=None,
                    task_ctx=task_ctx
                )
                if not success:
                    raise Exception("Streaming extract-upload failed")
                leech_target_path = None  # Files already uploaded - skip Leech
            elif is_unzip:
                await Unzip_Handler(process_source_path, False, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
                leech_target_path = _paths.temp_unzip_path
            elif is_dualzip:
                await Unzip_Handler(process_source_path, False, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
                await Zip_Handler(_paths.temp_unzip_path, True, True, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)
                leech_target_path = _paths.temp_zpath
            else:  # Normal leech for dir
                if ospath.isdir(process_source_path):
                    leech_target_path = process_source_path
                    cleanup_after_leech = False
                elif ospath.isfile(process_source_path):
                    # Copy single file logic... ensure it raises Exception on
                    # error
                    if not ospath.exists(_paths.temp_dirleech_path):
                        makedirs(_paths.temp_dirleech_path, exist_ok=True)
                    try:
                        shutil.copy2(
                            process_source_path,
                            _paths.temp_dirleech_path)
                        leech_target_path = _paths.temp_dirleech_path
                        # ... set name/size ...
                    except Exception as copy_err:
                        log.error(
                            f"Failed copy single file for dir-leech: {copy_err}")
                        _task_error.state = True
                        _task_error.text = f"Copy Error: {copy_err}"
                        raise Exception(_task_error.text)
                else:
                    _task_error.state = True
                    _task_error.text = "Source path disappeared"
                    raise Exception(_task_error.text)

            # Call Leech handler
            if leech_target_path and ospath.exists(leech_target_path):
                log.info(
                    f"Do_Leech: Starting Leech handler for dir from path: {leech_target_path}")
                await Leech(leech_target_path, cleanup_after_leech, task_ctx)
                if _task_error.state:
                    raise Exception(_task_error.text)  # Raise if Leech failed
            elif not _task_error.state:
                log.error(
                    f"Processing failed or leech path missing for dir-leech: {leech_target_path}")
                _task_error.state = True
                _task_error.text = f"Dir processing error ({_bot.Mode.type})"
                raise Exception(_task_error.text)
            # <<< End of example dir-leech logic >>>

        # --- Handle Link Modes with Batch Processing ---
        else:
            source_links = list(source)  # Ensure it's a list
            batch_size = 1  # Process one link per batch
            total_links = len(source_links)
            manual_filenames_provided = bool(full_filenames_list)

            # Validate filename count if manual filenames were provided
            if manual_filenames_provided and len(
                    full_filenames_list) != total_links:
                log.error(
                    f"Do_Leech Error: Initial filename count ({len(full_filenames_list)}) doesn't match link count ({total_links})."
                )
                # Set error state and raise exception to exit via finally block
                _task_error.state = True
                _task_error.text = "Initial filename/link count mismatch."
                raise Exception(_task_error.text)

            log.info(
                f"Do_Leech: Link mode selected. Processing {total_links} links in batches of {batch_size}.")

            # --- Start of Batch Loop ---
            for i in range(0, total_links, batch_size):
                # --- Start of Batch Processing Logic ---
                # Check 1: Check for critical errors *before* starting batch
                if _task_error and _task_error.state:
                    log.warning(
                        "Skipping further batches due to earlier critical _task_error.")
                    overall_success = False
                    break  # Exit the loop

                batch_start_index = i
                batch_end_index = min(i + batch_size, total_links)
                batch_links = source_links[batch_start_index:batch_end_index]
                batch_filenames = full_filenames_list[batch_start_index:batch_end_index] if manual_filenames_provided else [
                ]

                log.info(
                    f"--- Processing Batch {i // batch_size + 1} ({batch_start_index + 1}-{batch_end_index}) / {total_links} ---")

                # 1. Clean Up Dirs
                # Use original path for consistency if zip mode isn't creating
                # subdirs per batch
                batch_download_path = original_down_path
                _paths.down_path = batch_download_path  # Set current download path
                log.info(
                    f"Cleaning work directories before batch {i // batch_size + 1}... Target: {batch_download_path}"
                )
                # Ensure previous batch's potential leftovers are cleaned
                if ospath.exists(batch_download_path):
                    shutil.rmtree(batch_download_path, ignore_errors=True)
                # Clean specific temp dirs used by processing steps
                if ospath.exists(_paths.temp_zpath):
                    shutil.rmtree(_paths.temp_zpath, ignore_errors=True)
                if ospath.exists(_paths.temp_unzip_path):
                    shutil.rmtree(_paths.temp_unzip_path, ignore_errors=True)
                # Recreate the main download dir for this batch
                makedirs(batch_download_path, exist_ok=True)

                # 2. Download the current batch
                log.info(f"Downloading batch {i // batch_size + 1}...")
                # Reset temporary error state *before* calling download manager
                batch_task_error_state_before_dl = _task_error.state if _task_error else False
                if _task_error:
                    _task_error.state = False
                    _task_error.text = ""
                await downloadManager(batch_links, is_ytdl, batch_filenames, task_ctx)
                # Capture download success/failure *for this batch*
                batch_download_succeeded = not (
                    _task_error and _task_error.state)
                batch_download_error_text = _task_error.text if _task_error and _task_error.state else ""
                # Restore original error state if download succeeded but there
                # was a prior error
                if batch_download_succeeded and batch_task_error_state_before_dl:
                    _task_error.state = True
                    _task_error.text = "Earlier critical error occurred."

                # 3. Handle Download Errors (Non-Breaking)
                batch_had_download_failures = False
                if not batch_download_succeeded:
                    log.warning(
                        f"One or more downloads failed during batch {i // batch_size + 1}. Reason: {batch_download_error_text}. Continuing task."
                    )
                    overall_success = False  # Mark overall task as having failures
                    # Track this specific batch had download issues
                    batch_had_download_failures = True

                # 4. Check if Download Directory is Empty (Can skip
                # processing/upload)
                if not ospath.exists(batch_download_path) or not os.listdir(
                        batch_download_path):
                    log.warning(
                        f"Download path empty after batch {i // batch_size + 1}. Skipping processing/upload for this batch."
                    )
                    # If download failed, reset _task_error state so the main
                    # loop continues
                    if batch_had_download_failures and _task_error:
                        _task_error.state = False
                        _task_error.text = ""
                    continue  # Skip to the next iteration of the loop

                # 4.5. Smart Name Update - Update download_name based on what was actually downloaded
                # This ensures batch downloads get correct archive names (not
                # just the last file)
                from ..utility.helper import update_download_name_from_directory
                log.info(
                    f"Updating download_name based on files in: {batch_download_path}")
                smart_name = update_download_name_from_directory(
                    batch_download_path, task_ctx)
                log.info(f"Smart name determined: {smart_name}")

                # --- 5. Process and Upload Step (Inside its own try/except) ---
                # This block executes only if download succeeded (or failed but
                # left files) AND dir is not empty
                log.info(
                    f"Processing/Uploading downloaded files for batch {i // batch_size + 1}...")
                log.debug(
                    f">>> Starting processing/upload block for batch {i // batch_size + 1}.")
                batch_processing_error = False
                # --- Inner try for processing/upload ---
                try:
                    # Ensure getSize, sizeUnit, Zip/Unzip/Leech handlers are
                    # imported/available
                    _transfer.total_down_size = getSize(batch_download_path)
                    log.info(
                        f"Batch download size: {sizeUnit(_transfer.total_down_size)}. Processing type: {_bot.Mode.type}"
                    )

                    process_path = batch_download_path
                    leech_path = None

                    log.debug(
                        f">>> Initial process_path: {process_path}, Mode: {_bot.Mode.type}"
                    )

                    # --- Zip/Unzip Logic ---
                    if is_zip:
                        log.debug(">>> Calling Zip_Handler...")
                        # Assumes it removes original on success
                        await Zip_Handler(process_path, True, True, task_ctx)
                        if _task_error and _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Zip_Handler failed.")
                        else:
                            leech_path = _paths.temp_zpath
                            log.debug(
                                f">>> Zip successful. leech_path set to: {leech_path}")
                    elif is_stream_unzip:
                        # NEW: Streaming extract+upload for large archives
                        # (65GB+)
                        log.debug(
                            ">>> Calling Streaming Extract+Upload Handler...")
                        from ..utility.converters import extract_and_upload_streaming

                        # Find RAR archives in the process directory
                        items_in_dir = await asyncio.to_thread(os.listdir, process_path) if ospath.isdir(process_path) else [ospath.basename(process_path)]
                        rar_files = [f for f in items_in_dir if f.lower().endswith(
                            ('.rar', '.part01.rar', '.part001.rar', '.part1.rar'))]

                        if not rar_files:
                            log.error(
                                "No RAR archives found for streaming extraction")
                            batch_processing_error = True
                            if _task_error:
                                _task_error.state = True
                                _task_error.text = "No RAR files found"
                        else:
                            # Process first RAR archive
                            archive_path = ospath.join(
                                process_path, rar_files[0]) if ospath.isdir(process_path) else process_path

                            # Extract + Upload + Delete in streaming mode
                            log.info(
                                f"Starting streaming extract+upload for: {archive_path}")
                            success = await extract_and_upload_streaming(
                                rar_filepath=archive_path,
                                password=_bot.Options.unzip_pswd if _bot.Options.unzip_pswd else None,
                                file_filter=None,
                                task_ctx=task_ctx
                            )

                            if not success:
                                log.error(
                                    ">>> Streaming extract-upload failed.")
                                batch_processing_error = True
                                if _task_error:
                                    _task_error.state = True
                            else:
                                log.info(
                                    ">>> Streaming extract-upload completed successfully")
                                leech_path = None  # Skip normal Leech - files already uploaded
                    elif is_unzip:
                        log.debug(">>> Calling Unzip_Handler...")
                        await Unzip_Handler(process_path, True, task_ctx)
                        if _task_error and _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Unzip_Handler failed.")
                        else:
                            leech_path = _paths.temp_unzip_path
                            log.debug(
                                f">>> Unzip successful. leech_path set to: {leech_path}")
                    elif is_dualzip:
                        log.debug(">>> Calling Unzip_Handler (dualzip)...")
                        await Unzip_Handler(process_path, True, task_ctx)
                        if _task_error and _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Unzip_Handler (dualzip) failed.")
                        else:
                            log.debug(">>> Calling Zip_Handler (dualzip)...")
                            await Zip_Handler(_paths.temp_unzip_path, True, True, task_ctx)
                            if _task_error and _task_error.state:
                                batch_processing_error = True
                                log.error(">>> Zip_Handler (dualzip) failed.")
                            else:
                                leech_path = _paths.temp_zpath
                                log.debug(
                                    f">>> Dualzip successful. leech_path set to: {leech_path}")
                    else:
                        # Normal mode - no processing needed, upload downloaded
                        # files directly
                        log.debug(
                            ">>> Normal leech mode - no processing needed")
                        leech_path = process_path
                        log.debug(
                            f">>> Normal mode. leech_path set to: {leech_path}")

                    # Check for processing errors before leech
                    if _task_error.state:
                        log.error("Zip/Unzip failed before leech upload.")
                        batch_processing_error = True
                    # Call Leech handler to upload processed files to Telegram
                    elif leech_path is not None and ospath.exists(leech_path):
                        log.info(
                            f"Do_Leech batch: Starting Leech handler for path: {leech_path}")
                        await Leech(leech_path, True, task_ctx)
                        if _task_error.state:
                            log.error(">>> Leech handler failed.")
                            batch_processing_error = True
                        else:
                            log.debug(
                                f">>> Leech successful for batch {i // batch_size + 1}"
                            )
                    elif leech_path is None:
                        log.debug(
                            "leech_path is None - files already uploaded (streaming mode)")
                    else:
                        log.error(
                            f"Leech path missing or invalid: {leech_path}")
                        batch_processing_error = True
                        if _task_error:
                            _task_error.state = True
                            _task_error.text = "Leech path invalid"

                except Exception as processing_err:
                    log.error(
                        f"Error during batch processing: {processing_err}",
                        exc_info=True)
                    batch_processing_error = True
                    if _task_error:
                        _task_error.state = True
                        _task_error.text = f"Processing error: {processing_err}"

                # --- Logic AFTER processing/upload try-except block, still INSIDE the loop ---
                if batch_had_download_failures and not batch_processing_error:
                    log.debug(
                        "Resetting _task_error state after recoverable download failure.")
                    if _task_error:
                        _task_error.state = False
                        _task_error.text = ""

                # Handle critical processing errors -> Break the main loop
                if batch_processing_error:
                    overall_success = False
                    if _task_error and not _task_error.state:
                        _task_error.state = True
                        _task_error.text = "Processing/Upload Error"
                    log.error(
                        "Critical processing/upload error detected. Stopping.")
                    break  # Stop processing further batches

                log.info("--- Finished Batch ---")
            # --- End of Batch Loop ---

    # --- Main except for Do_Leech ---
    except Exception as leech_err:
        log.error(
            f"Error in Do_Leech main execution: {leech_err}",
            exc_info=True)
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = f"Unexpected Leech Error: {leech_err}"
        overall_success = False

    # --- Final cleanup logic for Do_Leech ---
    if overall_success and (not _task_error or not _task_error.state):
        log.info("Do_Leech completed successfully. Calling SendLogs...")
        await SendLogs(True, task_ctx)
    elif not overall_success:
        log.warning("Do_Leech completed with errors.")
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = _task_error.text or "Task completed with errors."
        log.info("Do_Leech finished with errors.")
    else:
        log.warning("Do_Leech finished in inconsistent state.")
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = "Inconsistent final state"


# --- Do_Mirror Function ---
async def Do_Mirror(
        source,
        is_ytdl,
        is_zip,
        is_unzip,
        is_dualzip,
        is_stream_unzip,
        task_ctx=None):
    """Execute mirror operation (download + copy to local directory).

    Args:
        source: List of URLs
        is_ytdl: YouTube-DL mode (legacy parameter)
        is_zip: Zip files before mirroring
        is_unzip: Unzip files before mirroring
        is_dualzip: Unzip then zip before mirroring
        is_stream_unzip: Streaming extract+upload for large archives
        task_ctx: Optional TaskContext for multi-task support
    """
    global BOT, TRANSFER, Paths, Messages, TaskError, log

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _transfer = task_ctx.transfer
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        log.info(
            f"Do_Mirror using TaskContext for task_id: {task_ctx.task_id}"
        )
    else:
        _bot = BOT
        _paths = Paths
        _transfer = TRANSFER
        _messages = Messages
        _task_error = TaskError
        log.info("Do_Mirror using global state (single-task mode)")

    log.info(
        f"Do_Mirror started. is_ytdl(legacy)={is_ytdl}, is_zip={is_zip}, is_unzip={is_unzip}, is_dualzip={is_dualzip}, is_stream_unzip={is_stream_unzip}")
    selected_service = _bot.Options.service_type

    # Ensure local mirror directory exists
    if not ospath.exists(_paths.mirror_dir):
        try:
            makedirs(_paths.mirror_dir)
            log.info(f"Created local mirror directory: {_paths.mirror_dir}")
        except Exception as mkdir_err:
            if _task_error:
                _task_error.state = True
                _task_error.text = f"Cannot create local mirror dir: {mkdir_err}"
            log.error(_task_error.text)
            return

    original_down_path = _paths.down_path
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
        if _task_error and _task_error.state:
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
                for item in os.listdir(source_path_for_copy):
                    s_item = ospath.join(source_path_for_copy, item)
                    d_item = ospath.join(mirror_dir_final, item)
                    if ospath.isdir(s_item):
                        shutil.copytree(s_item, d_item, dirs_exist_ok=True)
                    elif ospath.isfile(s_item):
                        shutil.copy2(s_item, d_item)
                log.info(
                    f"Successfully mirrored content to {mirror_dir_final}")
            except Exception as copy_err:
                log.error(
                    f"Error mirroring content: {copy_err}",
                    exc_info=True)
                if _task_error:
                    _task_error.state = True
                    _task_error.text = f"Mirror copy error: {copy_err}"

        else:
            log.warning("Skipping mirror processing due to download failure.")

    except Exception as mirror_err:
        log.error(
            f"Error in Do_Mirror main execution: {mirror_err}",
            exc_info=True)
        if _task_error and not _task_error.state:
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
    if _task_error and _task_error.state:
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
        task_ctx=None):
    """Execute Google Drive upload operation (download + upload to Google Drive).

    Args:
        source: List of URLs or directory path
        is_dir: Directory upload mode
        is_ytdl: YouTube-DL mode (legacy parameter)
        is_zip: Zip files before upload
        is_unzip: Unzip files before upload
        is_dualzip: Unzip then zip before upload
        is_stream_unzip: Streaming extract+upload for large archives
        task_ctx: Optional TaskContext for multi-task support
    """
    global BOT, TRANSFER, Paths, Messages, TaskError, log

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _transfer = task_ctx.transfer
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        log.info(
            f"Do_GDrive_Upload using TaskContext for task_id: {task_ctx.task_id}"
        )
    else:
        _bot = BOT
        _paths = Paths
        _transfer = TRANSFER
        _messages = Messages
        _task_error = TaskError
        log.info("Do_GDrive_Upload using global state (single-task mode)")

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
                        shutil.copy2(
                            process_source_path,
                            _paths.temp_dirleech_path)
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
            batch_size = 1
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
                log.info(f"Downloading batch {i // batch_size + 1}...")

                try:
                    await downloadManager(batch_links, batch_filenames, task_ctx)

                    if _task_error.state:
                        log.warning(
                            f"Batch {i // batch_size + 1} download had failures."
                        )
                except Exception as download_err:
                    log.error(
                        f"Download error in batch {i // batch_size + 1}: {download_err}",
                        exc_info=True)

                # Check if download directory has files
                if not ospath.exists(batch_download_path) or not os.listdir(
                        batch_download_path):
                    log.warning(
                        f"Batch {i // batch_size + 1} download directory empty or missing. Skipping processing/upload."
                    )
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
                        if _task_error and _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Zip_Handler failed.")
                        else:
                            gdrive_upload_path = _paths.temp_zpath
                            log.debug(
                                f">>> Zip successful. gdrive_upload_path set to: {gdrive_upload_path}")
                    elif is_unzip:
                        log.debug(">>> Calling Unzip_Handler...")
                        await Unzip_Handler(process_path, True, task_ctx)
                        if _task_error and _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Unzip_Handler failed.")
                        else:
                            gdrive_upload_path = _paths.temp_unzip_path
                            log.debug(
                                f">>> Unzip successful. gdrive_upload_path set to: {gdrive_upload_path}")
                    elif is_dualzip:
                        log.debug(">>> Calling Unzip_Handler (dualzip)...")
                        await Unzip_Handler(process_path, True, task_ctx)
                        if _task_error and _task_error.state:
                            batch_processing_error = True
                            log.error(">>> Unzip_Handler (dualzip) failed.")
                        else:
                            log.debug(">>> Calling Zip_Handler (dualzip)...")
                            await Zip_Handler(_paths.temp_unzip_path, True, True, task_ctx)
                            if _task_error and _task_error.state:
                                batch_processing_error = True
                                log.error(">>> Zip_Handler (dualzip) failed.")
                            else:
                                gdrive_upload_path = _paths.temp_zpath
                                log.debug(
                                    f">>> Dualzip successful. gdrive_upload_path set to: {gdrive_upload_path}")
                    else:
                        # Normal mode - no processing needed
                        log.debug(
                            ">>> Normal GDrive upload mode - no processing needed")
                        gdrive_upload_path = process_path
                        log.debug(
                            f">>> Normal mode. gdrive_upload_path set to: {gdrive_upload_path}")

                    # Check for processing errors before upload
                    if _task_error.state:
                        log.error("Zip/Unzip failed before GDrive upload.")
                        batch_processing_error = True
                    # Call GDrive Upload handler
                    elif gdrive_upload_path is not None and ospath.exists(gdrive_upload_path):
                        log.info(
                            f"Do_GDrive_Upload batch: Starting GDrive upload for path: {gdrive_upload_path}")
                        from ..uploader.gdrive import GDrive_Upload
                        await GDrive_Upload(gdrive_upload_path, True, task_ctx)
                        if _task_error.state:
                            log.error(">>> GDrive upload failed.")
                            batch_processing_error = True
                        else:
                            log.debug(
                                f">>> GDrive upload successful for batch {i // batch_size + 1}"
                            )
                    else:
                        log.error(
                            f"GDrive upload path missing or invalid: {gdrive_upload_path}")
                        batch_processing_error = True
                        if _task_error:
                            _task_error.state = True
                            _task_error.text = "GDrive upload path invalid"

                except Exception as processing_err:
                    log.error(
                        f"Error during batch processing: {processing_err}",
                        exc_info=True)
                    batch_processing_error = True
                    if _task_error:
                        _task_error.state = True
                        _task_error.text = f"Processing error: {processing_err}"

                # Handle critical processing errors -> Break the main loop
                if batch_processing_error:
                    overall_success = False
                    if _task_error and not _task_error.state:
                        _task_error.state = True
                        _task_error.text = "Processing/Upload Error"
                    log.error(
                        "Critical processing/upload error detected. Stopping.")
                    break

                log.info("--- Finished Batch ---")

    except Exception as gdrive_err:
        log.error(
            f"Error in Do_GDrive_Upload main execution: {gdrive_err}",
            exc_info=True)
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = f"Unexpected GDrive Error: {gdrive_err}"
        overall_success = False

    # --- Final cleanup logic ---
    if overall_success and (not _task_error or not _task_error.state):
        log.info("Do_GDrive_Upload completed successfully. Calling SendLogs...")
        await SendLogs(True, task_ctx)  # True for non-mirror mode
    elif not overall_success:
        log.warning("Do_GDrive_Upload completed with errors.")
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = _task_error.text or "Task completed with errors."
        log.info("Do_GDrive_Upload finished with errors.")
