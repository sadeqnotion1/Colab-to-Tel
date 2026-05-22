#/content/Telegram-Leecher/colab_leecher/uploader/telegram.py
import time 
import logging
import math
import os
import asyncio 
import socket 
import aiohttp 
from html import escape
from PIL import Image
from os import path as ospath
from datetime import datetime
from pyrogram import enums
from pyrogram.errors import FloodWait, SlowmodeWait
from ..utility.variables import BOT, BotTimes, Messages, MSG, Paths, TRANSFER, TaskError
from ..utility.task_context import TaskContext  # NEW: Import for multi-task support
from ..utility import helper
from .. import colab_bot, OWNER, DUMP_ID

log = logging.getLogger(__name__)


RETRYABLE_EXCEPTIONS = (
    FloodWait,
    SlowmodeWait,
    TimeoutError,            
    socket.timeout,          
    aiohttp.ClientError,     
)



async def upload_file(file_path: str, display_name: str, task_ctx: TaskContext = None) -> bool:
    """
    Uploads a single file or directory contents recursively to Telegram.

    Args:
        file_path: Path to file to upload
        display_name: Display name for the file
        task_ctx: Optional TaskContext for per-task state (NEW in Phase 3)
                  If provided, uses task_ctx.transfer and task_ctx.error
                  If None, falls back to global TRANSFER and TaskError (backward compat)

    Returns:
        True if upload successful, False otherwise
    """
    # NEW: Use task_ctx for transfer/error tracking if available
    transfer_obj = task_ctx.transfer if task_ctx else TRANSFER
    error_obj = task_ctx.error if task_ctx else TaskError
    task_id_str = f"[{task_ctx.get_short_id()}]" if task_ctx else "[legacy]"

    if not ospath.exists(file_path):
        log.error(f"Upload Error {task_id_str}: File/Dir does not exist: {file_path}")
        failed_info = {"link": "N/A", "filename": display_name, "index": "Upload", "reason": "Source file/dir missing"}
        if error_obj: error_obj.failed_links.append(failed_info)
        return False

    base_upload_name = display_name
    actual_upload_filename = ospath.basename(file_path)
    file_size = helper.getSize(file_path)

    # Check for zero-byte file
    if file_size == 0:
        log.error(f"Upload Error {task_id_str}: Skipping zero-byte file: {actual_upload_filename}")
        failed_info = {"link": "N/A", "filename": base_upload_name, "index": "Upload", "reason": "Zero-byte file"}
        if error_obj: error_obj.failed_links.append(failed_info)
        return False

    log.info(f"Preparing to upload {task_id_str}: {actual_upload_filename} (Display Name: {base_upload_name}) Size: {helper.sizeUnit(file_size)}")
    
    # NEW: Set total size for dashboard tracking
    if transfer_obj:
        transfer_obj.total_size = file_size
        if isinstance(transfer_obj.up_bytes, list) and len(transfer_obj.up_bytes) > 0:
            transfer_obj.up_bytes[0] = 0 # Reset current upload progress
        elif not isinstance(transfer_obj.up_bytes, list):
            transfer_obj.up_bytes = 0

    # --- Thumbnail, duration, dimension, caption logic ---
    thumb_path = None # Initialize to None, will be set later
    
    # PRIORITY #1: Custom Thumbnail set by user via /setthumb or by sending a photo
    if BOT.Setting.thumbnail and ospath.exists(Paths.THMB_PATH):
        thumb_path = Paths.THMB_PATH
        log.info(f"Using custom thumbnail for upload {task_id_str}: {thumb_path}")

    duration = 0
    width = 0
    height = 0
    f_type = helper.fileType(file_path)
    is_video = (f_type == "video")
    is_photo = (f_type == "photo")

    # --- Logic for Videos (Thumb & Duration) ---
    if is_video:
        # Check if it's a split file part
        if helper.is_split_file(actual_upload_filename):
            log.info(f"Split file detected: {actual_upload_filename}, using default thumbnail and duration 0.")
            if not thumb_path:
                thumb_path = Paths.DEFAULT_HERO # Use default thumb path initially if no custom
            duration = 0
        else:
            # Not a split file, try extracting duration and thumbnail separately
            log.debug(f"Attempting duration extraction for video: {actual_upload_filename}")
            # Call new metadata function
            metadata = await helper.get_video_metadata(file_path)
            duration = metadata["duration"]
            width = metadata["width"]
            height = metadata["height"]
            log.debug(f"Metadata extraction complete. Duration: {duration}, WxH: {width}x{height}")

            # Only generate video thumbnail if no custom thumbnail is set
            if not thumb_path:
                log.debug(f"Attempting thumbnail generation for video: {actual_upload_filename}")
                # Define a temporary directory for thumbs (portable across OS)
                import tempfile
                temp_thumb_dir = ospath.join(tempfile.gettempdir(), "colab_leecher_thumbs")
                thumb_path = await helper.get_video_thumbnail(file_path, output_dir=temp_thumb_dir) # Call new thumb function
                log.debug(f"Thumbnail generation attempt complete. Raw thumb path: {thumb_path}")

                # If thumb generation failed, fall back to default path
                if not thumb_path:
                    log.warning(f"Thumbnail generation failed for {actual_upload_filename}, using default path.")
                    thumb_path = Paths.DEFAULT_HERO
            else:
                log.info(f"Skipping video thumbnail generation as custom thumbnail is already set: {thumb_path}")
            
    # --- Logic for Photos (Thumb is the photo itself) ---
    elif is_photo:
         # For photos, we usually prefer the photo itself as thumb, 
         # unless a custom thumb is explicitly enabled and exists
         if not thumb_path:
            thumb_path = file_path # Use the photo itself as the thumbnail for send_document fallback

    # --- Common Thumbnail Processing & Final Validation (for Videos and Photos) ---
    # Applies conversion/validation if a thumb_path was determined above
    initial_thumb_path = thumb_path # Keep track of the path before conversion/validation
    log.debug(f"Initial thumb path before final checks: {initial_thumb_path}")

    if initial_thumb_path and isinstance(initial_thumb_path, str) and ospath.exists(initial_thumb_path):
        # Try to convert/verify the image (convertIMG returns None on failure)
        log.debug(f"Attempting conversion/verification for: {initial_thumb_path}")
        # Ensure helper.convertIMG exists and is imported/accessible
        try:
            converted_path = helper.convertIMG(initial_thumb_path)
        except Exception as img_err:
             log.error(f"Error calling helper.convertIMG: {img_err}")
             converted_path = None # Treat error as conversion failure

        if converted_path and ospath.exists(converted_path):
            # Use converted path if successful
            log.debug(f"Conversion successful/verified, using: {converted_path}")
            thumb_path = converted_path
        elif ospath.exists(initial_thumb_path):
            # If conversion failed but the original exists, use default as fallback
            log.warning(f"Thumbnail conversion failed for {initial_thumb_path}, using default.")
            thumb_path = Paths.DEFAULT_HERO
        else:
            # Conversion failed AND original is now missing
            log.warning(f"Thumbnail conversion failed and original missing ({initial_thumb_path}), using default.")
            thumb_path = Paths.DEFAULT_HERO
    else:
        # The initial path (e.g., DEFAULT_HERO from split file logic) wasn't valid or didn't exist
        if initial_thumb_path: # Log if there was an initial path specified but it didn't exist
             log.warning(f"Initial thumbnail path ({initial_thumb_path}) not found, using default.")
        # No need for else here, if initial_thumb_path was None, it remains None unless default is explicitly set
        # If it wasn't video/photo, or was split file, ensure default is considered
        if thumb_path is None or not ospath.exists(thumb_path):
             thumb_path = Paths.DEFAULT_HERO # Fallback to default path string if needed

    # --- Final Validation ---
    # Check if the chosen thumb_path (even if it's DEFAULT_HERO) actually exists.
    if not thumb_path or not isinstance(thumb_path, str) or not ospath.exists(thumb_path):
         if thumb_path: # Log if we had a path but it was invalid/missing
             log.warning(f"Final chosen thumbnail path ({thumb_path}) is invalid or file missing. Setting thumb to None for upload.")
         else: # Log if thumb_path was already None
             log.debug("Thumbnail path is None after processing. No thumb will be used for upload.")
         thumb_path = None # Set to None if no valid file found

    # --- Define Caption ---
    # Ensure caption is defined *after* all thumbnail logic
    try:
         # FIX: Escape prefix, suffix and filename to prevent HTML parsing errors
         safe_prefix = escape(BOT.Setting.prefix or '')
         safe_suffix = escape(BOT.Setting.suffix or '')
         safe_filename = escape(base_upload_name)
         caption = f"<code>{safe_prefix}{safe_filename}{safe_suffix}</code>"
    except Exception as cap_err:
         log.error(f"Error formatting caption: {cap_err}. Using default.")
         caption = f"<code>{escape(base_upload_name)}</code>" # Basic fallback caption

    # --- Initialize Upload State Variables ---
    # ** This block MUST be indented correctly **
    upload_success = False
    sent_message = None
    last_progress_time = 0
    retry_count = 0
    max_retries = 4 # Consider making this configurable
    error_reason = "Upload Failed"
    upload_start_time = 0 # Will be set before each attempt

    # --- Define Progress Callback ---
    # ** This 'async def' MUST be indented correctly **
    async def up_progress(current, total):
        # Indentation here is relative to the 'async def' line
        nonlocal last_progress_time, upload_start_time, base_upload_name # Ensure access to outer scope vars if needed
        now = time.time()
        # Throttle progress updates
        if now - last_progress_time > 2.5: # Update interval (e.g., 2.5 seconds)
            last_progress_time = now
            try:
                speed_string, eta_seconds, percentage = helper.speedETA(upload_start_time, current, total)
                
                # NEW: Update transfer object for real-time dashboard tracking
                if transfer_obj:
                    if isinstance(transfer_obj.up_bytes, list) and len(transfer_obj.up_bytes) > 0:
                        transfer_obj.up_bytes[0] = current
                    elif not isinstance(transfer_obj.up_bytes, list):
                        transfer_obj.up_bytes = current
                    transfer_obj.last_speed = speed_string
                    # Extract numeric speed if possible for dashboard sorting/agg
                    try:
                        transfer_obj.last_speed_bytes = current / (now - upload_start_time) if (now - upload_start_time) > 0 else 0
                    except: pass
                
                done_str = helper.sizeUnit(current)
                total_str = helper.sizeUnit(total)
                eta_str = helper.getTime(eta_seconds)

                status_head = f"<b>Uploading{' ' + task_id_str if task_ctx else ''}</b>\n\n<b>Name:</b> <code>{escape(base_upload_name)}</code>\n"
                log.debug(f"up_progress {task_id_str}: Calling status_bar. Speed='{speed_string}', Pct={percentage:.1f}, ETA='{eta_str}', Done='{done_str}', Total='{total_str}'")
                # NEW: Pass task_ctx to status_bar for per-task progress tracking
                await helper.status_bar(status_head, speed_string, percentage, eta_str, done_str, total_str, "TG Upload 🚀", task_ctx=task_ctx)
            except Exception as progress_err:
                log.warning(f"Error updating progress bar: {progress_err}")

    # --- Start Upload Attempt Loop ---
    # ** This 'while' loop MUST be indented correctly **
    while retry_count <= max_retries:
        # Indentation here is relative to the 'while' line
        try:
            upload_start_time = time.time() # Reset timer for each attempt
            last_progress_time = 0 # Reset progress throttle timer

            # Determine target chat ID (use DUMP_ID if set, otherwise OWNER)
            target_chat_id = DUMP_ID if DUMP_ID else OWNER
            if not target_chat_id:
                 log.error("Cannot upload: Neither DUMP_ID nor OWNER is set.")
                 error_reason = "Target chat ID not configured"
                 break # Exit loop if no target
            if target_chat_id == OWNER and not DUMP_ID:
                 log.warning("DUMP_ID not set, uploading to OWNER.")

            log.debug(f"Upload attempt {retry_count + 1}/{max_retries + 1} for {actual_upload_filename} to chat {target_chat_id}. Thumb: {thumb_path}")

            # --- Select Pyrogram Upload Method ---
            if BOT.Options.stream_upload and is_video:
                log.debug(f"Calling send_video for {actual_upload_filename}...")
                sent_message = await colab_bot.send_video(
                    chat_id=target_chat_id,
                    video=file_path,
                    file_name=base_upload_name,  # Override display name with proper content name
                    caption=caption,
                    progress=up_progress,
                    duration=duration,
                    width=width,
                    height=height,
                    thumb=thumb_path,
                    supports_streaming=True,
                    parse_mode=enums.ParseMode.HTML
                )
                log.debug(f"send_video call returned for {actual_upload_filename}. Message received: {bool(sent_message)}")
            elif not BOT.Options.stream_upload and is_photo:
                # Use send_photo only if explicitly NOT stream_upload AND it's a photo
                log.debug(f"Calling send_photo for {actual_upload_filename}...")
                sent_message = await colab_bot.send_photo(
                    chat_id=target_chat_id,
                    photo=file_path,
                    caption=caption,
                    progress=up_progress,
                    parse_mode=enums.ParseMode.HTML
                )
                log.debug(f"send_photo call returned for {actual_upload_filename}. Message received: {bool(sent_message)}")
            else:
                # Default to send_document for non-videos, non-photos, or if stream_upload is False for videos
                log.debug(f"Calling send_document for {actual_upload_filename}...")
                sent_message = await colab_bot.send_document(
                    chat_id=target_chat_id,
                    document=file_path,
                    file_name=base_upload_name,  # Override display name with proper content name
                    caption=caption,
                    progress=up_progress,
                    thumb=thumb_path, # send_document uses thumb too
                    force_document=True, # Ensure it sends as document, not potentially photo/video
                    parse_mode=enums.ParseMode.HTML
                )
                log.debug(f"send_document call returned for {actual_upload_filename}. Message received: {bool(sent_message)}")

            # --- Check Upload Result ---
            if sent_message:
                log.info(f"Successfully uploaded {task_id_str} '{base_upload_name}' (File: {actual_upload_filename}) to chat {target_chat_id} - Msg ID: {sent_message.id}")
                # NEW: Add to per-task transfer stats if available, otherwise global
                try:
                    transfer_obj.sent_file.append(sent_message)
                    transfer_obj.sent_file_names.append(base_upload_name)
                    # transfer_obj.up_bytes.append(file_size) # Moved after loop success
                except AttributeError:
                    log.warning(f"Could not record sent file details {task_id_str}, transfer object might be missing attributes.")
                upload_success = True
                break # Exit retry loop on success
            else:
                # This case should ideally not happen if Pyrogram raises exceptions on failure
                log.error(f"Upload API call returned None for {actual_upload_filename} without throwing an exception.")
                error_reason = "Upload API call returned None"
                # Go directly to retry logic below

        except RETRYABLE_EXCEPTIONS as wait_err:
            retry_count += 1
            wait_time = 15 # Default wait
            if isinstance(wait_err, (FloodWait, SlowmodeWait)):
                wait_time = wait_err.value + 5 # Use suggested wait time + buffer
                log.warning(f"Upload for {actual_upload_filename} hit {type(wait_err).__name__}: Waiting {wait_time}s... (Attempt {retry_count}/{max_retries + 1})")
            else:
                # Exponential backoff for other retryable errors
                wait_time = min(15 * (2 ** retry_count), 180) # e.g., 30, 60, 120, 180 max
                log.warning(f"Upload for {actual_upload_filename} hit {type(wait_err).__name__}. Waiting {wait_time}s... (Attempt {retry_count}/{max_retries + 1})")

            if retry_count > max_retries:
                error_reason = f"Exceeded max retries ({max_retries + 1}) due to {type(wait_err).__name__}"
                log.error(error_reason)
                break # Exit loop after max retries

            # Update status during wait
            status_head = f"<b>Uploading{' ' + task_id_str if task_ctx else ''}</b>\n\n<b>Name:</b> <code>{base_upload_name}</code>\n"
            try:
                # NEW: Pass task_ctx to status_bar
                await helper.status_bar(status_head, "N/A", 0, f"Waiting {wait_time}s", "N/A", helper.sizeUnit(file_size), f"TG {type(wait_err).__name__} ⏳", task_ctx=task_ctx)
            except Exception as status_err:
                log.warning(f"Could not update status during wait {task_id_str}: {status_err}")
            await asyncio.sleep(wait_time)
            continue # Continue to next retry attempt

        except Exception as e:
            # Non-retryable error
            error_reason = f"Non-retryable Upload Error: {str(e.__class__.__name__)} - {str(e)[:100]}"
            log.error(f"Failed to upload {actual_upload_filename} due to non-retryable error: {e}", exc_info=True)
            break # Exit loop immediately

    # --- After Retry Loop ---
    if not upload_success:
        log.error(f"Final upload status {task_id_str} for {actual_upload_filename}: FAILED. Reason: {error_reason}")
        # NEW: Record failure in per-task error object if available, otherwise global
        failed_info = {"link": "N/A", "filename": base_upload_name, "index": "Upload", "reason": error_reason}
        try:
            if error_obj: error_obj.failed_links.append(failed_info)
        except AttributeError:
             log.warning(f"Could not record failed link {task_id_str}, error object might be missing attributes.")
        return False
    else:
        # NEW: Record successful upload size in per-task transfer object if available, otherwise global
        try:
            if isinstance(transfer_obj.up_bytes, list):
                transfer_obj.up_bytes.append(file_size)
            else:
                transfer_obj.up_bytes += file_size
        except AttributeError:
            log.warning(f"Could not record uploaded bytes {task_id_str}, transfer object might be missing attributes.")
        except Exception as report_err:
            log.error(f"Error reporting uploaded bytes {task_id_str} for {actual_upload_filename}: {report_err}")
        return True
# --- End Replacement Function ---
