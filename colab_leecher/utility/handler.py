# /content/Telegram-Leecher/colab_leecher/utility/handler.py
import os
import re
import shutil
import logging
import pathlib
import asyncio
from time import time
from .. import OWNER, colab_bot, DUMP_ID
from natsort import natsorted
from datetime import datetime
from os import makedirs, path as ospath
from ..uploader.telegram import upload_file
from .variables import BOT, MSG, BotTimes, Messages, Paths, TRANSFER, TaskError
from .converters import archive, extract, videoConverter, sizeChecker
from .helper import fileType, getSize, getTime, keyboard, shortFileName, sizeUnit, sysINFO
from .message_safety import escape_html, safe_href
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from .task_context import TaskContext  # NEW: Import for multi-task support

log = logging.getLogger(__name__)


async def Leech(path: str, remove_source: bool, task_ctx: TaskContext = None):
    """Upload files to Telegram.

    Args:
        path: Directory or file path to upload
        remove_source: Whether to remove source after upload
        task_ctx: Optional TaskContext for multi-task support
    """
    global log, BOT, Paths, Messages, TaskError, TRANSFER, MSG

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        from .. import colab_bot
        _bot = BOT  # TaskContext doesn't have bot attribute, use global
        _paths = task_ctx.paths  # Use task-specific paths (temp_zip, etc.)
        _messages = task_ctx.messages
        _task_error = task_ctx.error  # Use task_ctx.error, not task_ctx.task_error
        _transfer = task_ctx.transfer
        _msg = MSG  # TaskContext doesn't have msg attribute, use global
        log.info(f"Leech using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _msg = MSG
        log.info("Leech using global state (single-task mode)")

    if not ospath.exists(path):
        log.error(f"Leech Error: Source path does not exist: {path}")
        _task_error.state = True
        _task_error.text = "Leech source path missing."
        return

    log.info(f"Leech: Handler started for path: {path}")
    files_processed_count = 0
    files_failed_count = 0

    items_to_process = []
    if ospath.isdir(path):
        items_to_process = [
            ospath.join(
                path,
                item) for item in natsorted(
                os.listdir(path))]
    elif ospath.isfile(path):
        # Check if it's the first part of a split archive (.001)
        if path.lower().endswith(".001"):
            dirname = ospath.dirname(path)
            filename = ospath.basename(path)
            # "Archive.7z.001" -> "Archive.7z"
            base_archive_name = filename[:-4] 
            log.info(f"Split archive detected starting with {filename}. Collecting all parts...")
            
            # Find all parts with the same base name (e.g., .001, .002, etc.)
            parts = []
            for f in natsorted(os.listdir(dirname)):
                if f.startswith(base_archive_name) and re.search(r'\.[0-9]{3}$', f):
                    parts.append(ospath.join(dirname, f))
            
            if parts:
                items_to_process = parts
                log.info(f"Found {len(parts)} parts for split archive.")
            else:
                items_to_process = [path]
        else:
            items_to_process = [path]
    else:
        log.error(
            f"Leech Error: Source path is neither file nor directory: {path}")
        _task_error.state = True
        _task_error.text = "Leech source path invalid type."
        return

    total_items_to_process = len(items_to_process)
    log.info(
        f"Leech: Found {total_items_to_process} potential item(s) to process/upload from initial path: {path}")

    for index, item_path in enumerate(items_to_process):
        current_item_name = ospath.basename(item_path)
        log.info(
            f"Leech: Processing item {index + 1}/{total_items_to_process}: {current_item_name}")

        if _task_error.state:
            log.warning(
                f"Leech: Skipping item '{current_item_name}' due to prior error state.")
            files_failed_count += 1
            continue

        upload_path_for_item = item_path
        processing_required_and_done = False

        try:
            processing_required_and_done = await sizeChecker(upload_path_for_item, remove_source, task_ctx)

            if _task_error.state:
                log.error(
                    f"Leech: Error during sizeChecker/processing for '{current_item_name}'. Reason: {_task_error.text}")
                raise Exception(_task_error.text)

            upload_source_location = upload_path_for_item
            if processing_required_and_done:
                potential_processed_path = _paths.temp_zpath
                log.info(
                    f"Leech: Processing was required for '{current_item_name}'. Checking for output in {potential_processed_path}")
                if ospath.exists(potential_processed_path) and os.listdir(
                        potential_processed_path):
                    upload_source_location = potential_processed_path
                    log.info(
                        f"Leech: Found processed content. Uploading content from: {upload_source_location}")
                else:
                    log.warning(
                        f"Leech: Processing done but processed path '{potential_processed_path}' missing or empty. Uploading original item from: {upload_source_location}")
            else:
                log.info(
                    f"Leech: No processing needed for '{current_item_name}'. Uploading from: {upload_source_location}")

            # --- Uploading ---
            if not ospath.exists(upload_source_location):
                log.error(
                    f"Leech: Final upload source location '{upload_source_location}' does not exist. Skipping upload for '{current_item_name}'.")
                if not _task_error.state:
                    _task_error.state = True
                    _task_error.text = f"Upload source missing: {ospath.basename(upload_source_location)}"
                raise Exception(_task_error.text)

            upload_success = False
            if ospath.isdir(upload_source_location):
                log.info(
                    f"Leech: Uploading contents of directory: {upload_source_location} for original item '{current_item_name}'")
                files_in_dir = [
                    f for f in natsorted(
                        os.listdir(upload_source_location)) if ospath.isfile(
                        ospath.join(
                            upload_source_location, f))]

                if not files_in_dir:
                    log.warning(
                        f"Leech: Upload directory '{upload_source_location}' contains no files to upload for item '{current_item_name}'.")
                    upload_success = True  # Treat empty processed dir as success for this item
                else:
                    total_files_in_dir = len(files_in_dir)
                    log.info(
                        f"Leech: Found {total_files_in_dir} file(s) in '{upload_source_location}' to upload for item '{current_item_name}'.")
                    all_parts_uploaded = True
                    for file_index, sub_item_name in enumerate(files_in_dir):
                        sub_item_path = ospath.join(
                            upload_source_location, sub_item_name)
                        part_display_name = sub_item_name
                        log.info(
                            f"Leech: Uploading file from directory: {sub_item_name} (Display: {part_display_name})")
                        # Ensure upload_file is imported
                        uploaded = await upload_file(sub_item_path, part_display_name, task_ctx)

                        if uploaded is not True:
                            log.error(
                                f"Leech: upload_file returned failure for sub-item: {sub_item_name} (Display: {part_display_name})")
                            all_parts_uploaded = False
                            if _task_error and not _task_error.state:
                                _task_error.state = True
                                _task_error.text = _task_error.text or f"Upload failed for {part_display_name}"
                            break

                    upload_success = all_parts_uploaded
                    if not all_parts_uploaded:
                        log.error(
                            f"Leech: Not all files in directory '{upload_source_location}' were uploaded successfully for item '{current_item_name}'.")

            elif ospath.isfile(upload_source_location):
                log.info(
                    f"Leech: Uploading single file: {upload_source_location} (Display: {current_item_name})")
                # Ensure upload_file is imported
                uploaded = await upload_file(upload_source_location, current_item_name, task_ctx)
                if uploaded is True:
                    upload_success = True
                else:
                    log.error(
                        f"Leech: upload_file returned failure for single file: {current_item_name}")
                    upload_success = False
                    if _task_error and not _task_error.state:
                        _task_error.state = True
                        _task_error.text = _task_error.text or f"Upload failed for {current_item_name}"
            else:
                log.error(
                    f"Leech: Path '{upload_source_location}' is not a file or directory. Skipping.")
                if not _task_error.state:
                    _task_error.state = True
                    _task_error.text = f"Invalid upload source type: {upload_source_location}"
                raise Exception(_task_error.text)

            # --- Update Counts ---
            if upload_success:
                files_processed_count += 1
                log.info(
                    f"Leech: Successfully processed/uploaded item corresponding to: {current_item_name}")
            else:
                # Failure reason should already be logged and _task_error
                # potentially set
                log.error(
                    f"Leech: Failed to process/upload item corresponding to: {current_item_name}")
                # We will increment files_failed_count in the except block
                # Ensure an exception is raised if upload failed
                raise Exception(
                    _task_error.text or f"Upload failed for {current_item_name}")

            # --- Cleanup Temporary Directory AFTER Upload (if processing occurred) ---
            if processing_required_and_done and upload_source_location == _paths.temp_zpath and ospath.exists(
                    _paths.temp_zpath):
                log.info(
                    f"Cleaning up temporary processing directory: {_paths.temp_zpath}")
                shutil.rmtree(_paths.temp_zpath, ignore_errors=True)
                try:
                    makedirs(_paths.temp_zpath, exist_ok=True)
                except Exception as mkdir_err:
                    log.warning(
                        f"Could not recreate temp dir {_paths.temp_zpath}: {mkdir_err}")

        # --- !!! THIS IS THE RESTORED except BLOCK !!! ---
        # It catches errors specific to the processing of the current item_path
        except Exception as item_err:
            files_failed_count += 1  # Increment failure count here
            log.error(
                f"Leech: Error processing item '{current_item_name}': {item_err}",
                exc_info=True)
            # Ensure _task_error state is set if not already
            if not _task_error.state:
                _task_error.state = True
                # Use the specific error message if _task_error.text wasn't set
                # by the failing function
                _task_error.text = _task_error.text or f"Error processing {current_item_name}: {str(item_err)[:100]}"
            # The loop will continue to the next item unless _task_error.state
            # causes skipping at the top

        # --- End of Try block for individual item processing ---

    # --- End of for loop ---

    log.info(
        f"Leech: Function finished. Processed: {files_processed_count}, Failed: {files_failed_count}")
    # No return needed, Do_Leech checks _task_error state

    # Let Do_Leech check the final _task_error state

# NOTE: The actual Zip_Handler and Unzip_Handler implementations are below (lines 550+)
# This section was a stub/placeholder


async def Unzip_Handler(
        source_path: str,
        remove_source: bool = True,
        task_ctx: TaskContext = None):
    """
    Handles extraction of archives found within the source_path.
    Improved to correctly handle multi-part RAR archives.

    Args:
        source_path: Directory containing archives to extract
        remove_source: Whether to remove source after extraction
        task_ctx: Optional TaskContext for multi-task support
    """
    global log, BOT, Paths, Messages, BotTimes, MSG, TaskError, TRANSFER, cleanup_paths  # Ensure all needed globals
    from .converters import extract  # Ensure 'extract' is imported

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _bot = BOT  # TaskContext doesn't have bot attribute, use global
        _paths = task_ctx.paths  # Use task-specific paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error  # Use task_ctx.error, not task_ctx.task_error
        _transfer = task_ctx.transfer
        _msg = MSG  # TaskContext doesn't have msg attribute, use global
        log.info(
            f"Unzip_Handler using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _msg = MSG
        log.info("Unzip_Handler using global state (single-task mode)")

    log.info(f"Unzip Handler started for: {source_path}")
    if not ospath.isdir(source_path):
        log.error(
            f"Unzip Handler Error: Source path is not a directory: {source_path}")
        _task_error.state = True
        _task_error.text = f"Unzip source path invalid: {ospath.basename(source_path)}"
        return False  # Cannot proceed

    target_unzip_path = _paths.temp_unzip_path  # Get target path from variables
    os.makedirs(target_unzip_path, exist_ok=True)  # Ensure target dir exists

    archive_files_found = []
    try:
        # List all files, ignore directories directly inside source_path
        items = [
            f for f in os.listdir(source_path) if ospath.isfile(
                ospath.join(
                    source_path,
                    f))]
        log.info(
            f"Scanning directory for archives: {source_path}. Found {len(items)} files.")

        # Identify potential archive files (common extensions)
        archive_extensions = {
            ".rar",
            ".zip",
            ".7z",
            ".tar",
            ".gz",
            ".tgz",
            ".001",
            ".z01"}
        archive_files_found = [f for f in items if any(
            f.lower().endswith(ext) for ext in archive_extensions)]

        if not archive_files_found:
            log.warning(
                f"No archive files found in {source_path}. Skipping extraction.")
            return True  # No archives to extract is not an error in itself

    except Exception as list_err:
        log.error(
            f"Error listing files in {source_path}: {list_err}",
            exc_info=True)
        _task_error.state = True
        _task_error.text = f"Error scanning unzip source: {str(list_err)[:50]}"
        return False

    extraction_errors = []
    processed_bases = set()  # Keep track of processed multi-part archives

    for item_name in archive_files_found:
        item_path = ospath.join(source_path, item_name)
        base_name, ext_lower = ospath.splitext(item_name.lower())
        first_part_identifier = None

        # --- Logic to identify the *first* part of multi-part RAR ---
        rar_part_match = re.match(r"(.+)\.part(\d+)\.rar$", item_name.lower())
        if rar_part_match:
            base_name = rar_part_match.group(1)
            part_num = int(rar_part_match.group(2))
            if part_num == 1:
                first_part_identifier = item_path  # This is the .part1.rar file
            else:
                # This is part 2 or later, skip extraction attempt
                log.debug(
                    f"Skipping extraction attempt for subsequent RAR part: {item_name}")
                # Mark base as handled by part 1 later
                processed_bases.add(base_name)
                continue
        elif ext_lower == ".rar":
            # Could be a single RAR or the first part without .partX naming
            # Check if other parts like .r00, .r01 exist? (More complex, skip for now)
            # Assume this is the first/only part if no .partX match was found
            # earlier
            first_part_identifier = item_path
            # Get base name without .rar
            base_name, _ = ospath.splitext(item_name)
            # Avoid processing if a .part1.rar for this base was already
            # processed
            if base_name in processed_bases:
                log.debug(
                    f"Skipping extraction for {item_name}, base '{base_name}' likely handled by .part1.rar")
                continue
        # --- End Multi-part RAR Logic ---

        # For non-RAR or identified first RAR parts
        elif ext_lower in archive_extensions:  # Handle zip, 7z, tar etc.
            first_part_identifier = item_path
            base_name, _ = ospath.splitext(item_name)
            # Add logic here if needed to detect first parts of zip/7z
            # multipart, e.g. .001 / .z01
            if ext_lower == ".001" or ext_lower == ".z01":
                log.debug(
                    f"Identified potential first part of split archive: {item_name}")
            elif ext_lower in [".002", ".z02"]:  # Example for subsequent parts
                log.debug(f"Skipping subsequent split part: {item_name}")
                continue  # Skip explicit extraction of later parts

        # --- Extraction Attempt ---
        if first_part_identifier:
            log.info(
                f"Attempting extraction for: {ospath.basename(first_part_identifier)}")
            success = False
            try:
                # --- CORRECTED FUNCTION CALL: Use 'extract' ---
                # Pass only the path to the (first) archive file and remove=False
                # Password is handled inside 'extract' using
                # BOT.Options.unzip_pswd
                success = await extract(first_part_identifier, remove=False)
                # --- End Corrected Call ---

                if success:
                    log.info(f"Extraction successful for base: {base_name}")
                    processed_bases.add(base_name)  # Mark as done
                else:
                    # Extract function logs errors internally, but we add
                    # context here
                    log.error(
                        f"Extraction failed for '{item_name}'. Reason logged by 'extract' function.")
                    # Use _task_error.text set by extract function if
                    # available? Or set generic one?
                    fail_reason = _task_error.text if _task_error.state else "Unknown (from extract)"
                    extraction_errors.append(
                        f"Failed: {item_name} - {fail_reason}")
                    _task_error.state = False  # Reset _task_error state after logging it for this file

            except Exception as extract_call_err:
                # Catch errors calling the extract function itself
                log.error(
                    f"Unexpected error calling extract for {item_name}: {extract_call_err}",
                    exc_info=True)
                extraction_errors.append(
                    f"Failed: {item_name} - Call Error: {str(extract_call_err)[:50]}")

    # --- Final Status Check ---
    if extraction_errors:
        log.error(
            f"Unzip_Handler finished, but {len(extraction_errors)} extraction error(s) occurred.")
        # Combine errors for _task_error
        _task_error.state = True
        _task_error.text = "; ".join(extraction_errors)
        # Decide if the whole task fails or continues with successfully extracted files
        # For now, let's return False indicating the handler had issues
        return False
    else:
        log.info("Unzip_Handler finished successfully. All archives processed.")
        return True  # Indicate overall success

# ----- END OF REPLACEMENT BLOCK -----


async def cancelTask(Reason: str, task_ctx: TaskContext = None):
    """
    Cancel a task and clean up resources.

    Args:
        Reason: Reason for cancellation.
        task_ctx: TaskContext for per-task cancellation.
    """
    global OWNER, colab_bot, log

    if task_ctx is None:
        log.error(
            "cancelTask called without task_ctx; legacy global cancellation path has been removed.")
        return

    transfer_obj = task_ctx.transfer
    error_obj = task_ctx.error
    messages_obj = task_ctx.messages
    start_time = task_ctx.started_at or task_ctx.created_at or datetime.now()

    task_failed = error_obj.state
    final_reason = error_obj.text if task_failed and error_obj.text else Reason

    log.warning(
        f"Task {task_ctx.get_short_id()} cancellation/completion triggered. "
        f"Reason: {final_reason}"
    )
    task_ctx.mark_cancelled()

    # Avoid cancelling/awaiting the currently executing task to prevent
    # self-deadlock.
    current_asyncio_task = asyncio.current_task()
    if (
        task_ctx.async_task
        and task_ctx.async_task is not current_asyncio_task
        and not task_ctx.async_task.done()
    ):
        log.info(f"Cancelling asyncio task for {task_ctx.get_short_id()}")
        task_ctx.async_task.cancel()
        try:
            await task_ctx.async_task
        except asyncio.CancelledError:
            log.info(f"Task {task_ctx.get_short_id()} successfully cancelled")
        except Exception as e:
            log.error(
                f"Task {task_ctx.get_short_id()} raised exception during cancellation: {e}")

    try:
        time_spent = getTime((datetime.now() - start_time).seconds)
    except Exception:
        time_spent = "Unknown"

    service_type = task_ctx.service_type or "N/A"
    mode = task_ctx.mode or "N/A"
    mode_type = task_ctx.mode_type or "N/A"

    report_content = f"===== Task Report - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} =====\n"
    report_content += f"Task ID: {task_ctx.get_short_id()}\n"
    report_content += f"Reason for Stop/Completion: {final_reason}\n"
    report_content += f"Mode: {mode}, Type: {mode_type}, Service: {service_type}\n"
    report_content += f"Total Time Elapsed: {time_spent}\n"
    report_content += f"Source Link: {messages_obj.src_link or 'N/A'}\n\n"

    processed_urls = set()

    report_content += f"--- Successful Downloads ({len(transfer_obj.successful_downloads)}) ---\n"
    if transfer_obj.successful_downloads:
        for idx, item in enumerate(transfer_obj.successful_downloads):
            url = item.get("url", "N/A")
            processed_urls.add(url)
            report_content += f"{idx + 1}. Filename: {item.get('filename', 'N/A')}\n"
            report_content += f"   URL: {url}\n\n"
    else:
        report_content += "   None\n\n"

    report_content += f"--- Failed Downloads ({len(error_obj.failed_links)}) ---\n"
    if error_obj.failed_links:
        for idx, item in enumerate(error_obj.failed_links):
            url = item.get("link", "N/A")
            processed_urls.add(url)
            report_content += f"{idx + 1}. Index/Link Num: {item.get('index', 'N/A')}\n"
            report_content += f"   Filename: {item.get('filename', 'N/A')}\n"
            report_content += f"   URL: {url}\n"
            report_content += f"   Reason: {item.get('reason', 'Unknown')}\n\n"
    else:
        report_content += "   None\n\n"

    skipped_links = []
    original_links = task_ctx.source_urls or []
    original_filenames = task_ctx.filenames or []
    if len(original_links) > (
            len(transfer_obj.successful_downloads) + len(error_obj.failed_links)):
        for i, url in enumerate(original_links):
            if url not in processed_urls:
                filename = (
                    original_filenames[i]
                    if i < len(original_filenames)
                    else "N/A (Filename List Mismatch?)"
                )
                skipped_links.append({"url": url, "filename": filename})

    report_content += f"--- Skipped / Not Attempted ({len(skipped_links)}) ---\n"
    if skipped_links:
        for idx, item in enumerate(skipped_links):
            report_content += f"{idx + 1}. Filename: {item.get('filename', 'N/A')}\n"
            report_content += f"   URL: {item.get('url', 'N/A')}\n\n"
    else:
        report_content += "   None\n\n"

    if mode != "mirror":
        report_content += f"--- Successful Uploads ({len(transfer_obj.sent_file)}) ---\n"
        if not transfer_obj.sent_file:
            report_content += "   None\n\n"

    report_content += "===== End of Report =====\n"

    work_path = task_ctx.work_path
    report_file_path = os.path.join(work_path, "download_report.txt")
    report_saved = False
    try:
        os.makedirs(work_path, exist_ok=True)
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        log.info(f"Download report saved to {report_file_path}")
        report_saved = True
    except Exception as e:
        log.error(f"Failed to save download report file: {e}")
        report_file_path = None

    skip_cleanup = bool(error_obj.failed_links)
    if not skip_cleanup:
        try:
            if os.path.exists(work_path):
                shutil.rmtree(work_path, ignore_errors=True)
                log.info(f"Cleaning up workspace: {work_path}")
        except Exception as e:
            log.error(f"Error during workspace cleanup: {e}", exc_info=True)
    else:
        log.warning(
            f"Workspace cleanup skipped due to download failures. "
            f"Check {work_path} for partial downloads and report."
        )

    # FIX #2: was markdown-styled failure/cancel text rendered incorrectly in HTML mode.
    # Markdown ** renders as literal asterisks in HTML-mode messages.
    final_summary_header = "<b>\u274c Task Failed!</b>" if task_failed else "<b>\U0001f6d1 Task Cancelled by User</b>"
    # FIX: Escape final_reason to prevent HTML parsing errors
    safe_reason = escape_html(final_reason)
    final_summary_text = (
        f"{final_summary_header}\n"
        f"Task ID: {task_ctx.get_short_id()}\n"
        f"Reason: {safe_reason}\n"
        f"Elapsed: {time_spent}\n"
    )
    if report_saved:
        final_summary_text += "\n\U0001f4dc Report file generated & sent."
    else:
        final_summary_text += "\n\u26a0\ufe0f Report file generation failed."

    if error_obj.failed_links:
        final_summary_text += f"\nFailed Downloads: {len(error_obj.failed_links)}"
    if skipped_links:
        final_summary_text += f"\nSkipped/Not Attempted: {len(skipped_links)}"
    if error_obj.failed_links or skipped_links:
        final_summary_text += "\n(See report file for details)"

    report_message_id_to_reply = None
    if OWNER and colab_bot:
        try:
            if report_saved and report_file_path and os.path.exists(
                    report_file_path):
                log.info(
                    f"Sending report file {report_file_path} to owner {OWNER}")
                report_msg = await colab_bot.send_document(
                    OWNER,
                    document=report_file_path,
                    caption=f"Download Report: {mode} - {final_reason}"[:200],
                )
                report_message_id_to_reply = report_msg.id
                try:
                    os.remove(report_file_path)
                except OSError as e:
                    log.warning(
                        f"Could not remove report file {report_file_path}: {e}")
            else:
                log.warning(
                    "Report file not saved or found, cannot send document.")

            # FIX #5: unified emoji style with cancelTask keyboard
            final_markup = InlineKeyboardMarkup(
                [[
                    InlineKeyboardButton("\U0001f4e3 Channel", url="https://t.me/Colab_Leecher"),
                    InlineKeyboardButton("\U0001f4ac Group", url="https://t.me/Colab_Leecher_Discuss"),
                ]]
            )
            status_msg = task_ctx.status_msg

            if report_message_id_to_reply:
                await colab_bot.send_message(
                    OWNER,
                    final_summary_text,
                    reply_to_message_id=report_message_id_to_reply,
                    reply_markup=final_markup,
                    disable_web_page_preview=True,
                )
            elif status_msg:
                try:
                    await status_msg.reply_text(
                        final_summary_text,
                        quote=True,
                        reply_markup=final_markup,
                        disable_web_page_preview=True,
                    )
                except Exception:
                    await colab_bot.send_message(
                        OWNER,
                        final_summary_text,
                        reply_markup=final_markup,
                        disable_web_page_preview=True,
                    )
            else:
                await colab_bot.send_message(
                    OWNER,
                    final_summary_text,
                    reply_markup=final_markup,
                    disable_web_page_preview=True,
                )
            log.info("Sent final cancellation/failure message to owner.")
        except Exception as send_err:
            log.error(
                f"Failed send cancellation report/summary message: {send_err}")

    status_msg = task_ctx.status_msg
    if status_msg:
        try:
            await status_msg.delete()
        except Exception as del_err:
            log.warning(f"Could not delete original status message: {del_err}")
        finally:
            task_ctx.status_msg = None

    from .task_context import TASK_QUEUE

    removed = await TASK_QUEUE.remove_task(task_ctx.task_id)
    if removed:
        log.info(
            f"Task {task_ctx.get_short_id()} removed from TASK_QUEUE. "
            f"Active tasks: {TASK_QUEUE.get_task_count()}"
        )

    try:
        from .task_dashboard import force_update_summary
        await force_update_summary(colab_bot)
    except Exception as e:
        log.warning(f"Failed to update summary after task removal: {e}")

# --- End of cancelTask function ---

# --- Zip_Handler (ensure logging and error handling if needed) ---


async def Zip_Handler(
        down_path: str,
        is_split: bool,
        remove: bool,
        task_ctx: TaskContext = None):
    """Create archive from files.

    Args:
        down_path: Path to files to archive
        is_split: Whether to split the archive
        remove: Whether to remove source after archiving
        task_ctx: Optional TaskContext for multi-task support
    """
    global BOT, Messages, MSG, TRANSFER, BotTimes, Paths, TaskError

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _bot = BOT  # TaskContext doesn't have bot attribute, use global
        _paths = task_ctx.paths  # ✅ Use task-specific paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error  # Use task_ctx.error, not task_ctx.task_error
        _transfer = task_ctx.transfer
        _msg = MSG  # TaskContext doesn't have msg attribute, use global
        log.info(
            f"Zip_Handler using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _msg = MSG
        log.info("Zip_Handler using global state (single-task mode)")

    log.info(f"Zip Handler started for: {down_path}")
    try:
        # Convert is_split boolean to max_split_size_bytes
        # Default split size: 1000MB (1GB) if splitting enabled, 0 if not
        max_split_size = (1000 * 1024 * 1024) if is_split else 0
        # Fixed parameter order
        await archive(down_path, remove, max_split_size, task_ctx)
        # Check if archive function set _task_error
        if _task_error and _task_error.state:
            log.error(
                f"Zip Handler failed because archive function reported an error.")
            return  # Propagate failure
        # Check if output exists as basic validation
        if not ospath.exists(
                _paths.temp_zpath) or not os.listdir(
                _paths.temp_zpath):
            log.error("Zipping failed, output directory empty/missing.")
            if _task_error:
                _task_error.state = True
                _task_error.text = "Zipping failed (no output)"
            return
        _transfer.total_down_size = getSize(_paths.temp_zpath)
        log.info(
            f"Zipping complete. Output size: {sizeUnit(_transfer.total_down_size)}")
    except Exception as zip_err:
        log.error(f"Error in Zip_Handler: {zip_err}", exc_info=True)
        if _task_error:
            _task_error.state = True
            _task_error.text = f"Zip Handler Error: {zip_err}"

    # IMPORTANT: Return here to prevent falling through into Unzip_Handler
    # code below
    return

    # Messages.status_head = f"\n<b>📂 EXTRACTING » </b>\n\n<code>{os.path.basename(down_path)}</code>\n"
    # if MSG.status_msg: await MSG.status_msg.edit_text(...) # Status handled
    # inside extract now

    temp_unzip_path = Paths.temp_unzip_path  # Defined in variables
    supported_exts = [
        ".7z",
        ".gz",
        ".zip",
        ".rar",
        ".tar",
        ".tgz",
        ".001",
        ".z01"]  # Example list

    try:
        if ospath.isfile(down_path):
            # If it's a single file, check if it's an archive
            filename = ospath.basename(down_path).lower()
            _, ext = ospath.splitext(filename)
            if ext in supported_exts:
                log.info(f"Attempting extract single file: {filename}")
                # Assume extract returns success/fail status or sets TaskError
                # Pass remove flag
                extract_success = await extract(down_path, remove)
                if extract_success:
                    pass
                else:
                    TaskError.state = True  # Ensure state is set if extract fails silently
            else:
                log.warning(
                    f"Single file '{filename}' is not a supported archive type for extraction.")
                # Copy the single non-archive file to the unzip path for
                # consistency
                makedirs(temp_unzip_path, exist_ok=True)
                shutil.copy2(down_path, temp_unzip_path)
                Messages.download_name = ospath.basename(
                    down_path)  # Set name context
                if remove:
                    os.remove(down_path)  # Remove original if requested
        elif ospath.isdir(down_path):
            # If it's a directory, try extracting supported archives within it
            log.info(f"Scanning directory for archives: {down_path}")
            any_extracted_in_dir = False
            files_in_dir = [str(p) for p in pathlib.Path(
                down_path).rglob("*") if p.is_file()]
            for f_path in natsorted(files_in_dir):
                filename = ospath.basename(f_path).lower()
                _, ext = ospath.splitext(filename)
                if ext in supported_exts:
                    log.info(
                        f"Attempting extract archive within dir: {filename}")
                    # Pass remove flag
                    extract_success = await extract(f_path, remove)
                    if extract_success:
                        any_extracted_in_dir = True
                    else:
                        TaskError.state = True
                        # Stop if any extraction fails? Or continue? Let's
                        # stop.
                        break
            if TaskError.state:
                return  # Exit if extraction failed mid-directory

            # If no archives were found/extracted in directory, copy original
            # content
            if not any_extracted_in_dir:
                log.warning(
                    f"No supported archives found/extracted in directory: {down_path}. Copying original content.")
                try:
                    # Copy contents into the temp_unzip_path
                    makedirs(temp_unzip_path, exist_ok=True)
                    shutil.copytree(
                        down_path, temp_unzip_path, dirs_exist_ok=True)
                    if remove:
                        # Remove original dir if requested
                        shutil.rmtree(down_path)
                    Messages.download_name = ospath.basename(
                        down_path)  # Set name context
                except Exception as copy_err:
                    log.error(f"Failed copy original dir content: {copy_err}")
                    if TaskError:
                        TaskError.state = True
                        TaskError.text = f"Copy error: {copy_err}"
                    return
        else:
            # Should not happen if path check at start works
            log.error(
                f"Unzip source path is neither file nor directory: {down_path}")
            if TaskError:
                TaskError.state = True
                TaskError.text = "Invalid unzip source"
            return

        # Final check and size calculation
        if ospath.exists(temp_unzip_path):
            TRANSFER.total_down_size = getSize(temp_unzip_path)
            log.info(
                f"Extraction/Copy complete. Final size in '{temp_unzip_path}': {sizeUnit(TRANSFER.total_down_size)}")
        elif not TaskError.state:
            # If no error state was set, but output path is missing, set error
            log.error(
                f"Extraction failed, output path missing: {temp_unzip_path}")
            TaskError.state = True
            TaskError.text = "Extraction failed (no output)"

    except Exception as unzip_err:
        log.error(f"Error in Unzip_Handler: {unzip_err}", exc_info=True)
        if TaskError:
            TaskError.state = True
            TaskError.text = f"Unzip Handler Error: {unzip_err}"


# --- SendLogs Function (Ensure it exists and is correct) ---
async def SendLogs(is_leech: bool, task_ctx: TaskContext):
    """
    Send completion logs and final summary after task completes.

    Args:
        is_leech: True for leech mode, False for mirror mode
        task_ctx: TaskContext for this task
    """
    global OWNER, colab_bot

    if task_ctx is None:
        raise ValueError("SendLogs requires task_ctx")

    transfer_obj = task_ctx.transfer
    messages_obj = task_ctx.messages
    status_msg = task_ctx.status_msg
    start_time = task_ctx.started_at or task_ctx.created_at or datetime.now()
    task_id_str = f"[{task_ctx.get_short_id()}]"

    log.info(f"SendLogs {task_id_str}: Preparing final summary...")
    try:
        total_uploaded_size = (
            sum(transfer_obj.up_bytes)
            if isinstance(transfer_obj.up_bytes, list)
            else transfer_obj.up_bytes
        )
        file_count = len(transfer_obj.sent_file)
        usage_link = (
            "\n\n<a href='https://colab.research.google.com/drive/12hdEqaidRZ8krqj7rpnyDzg1dkKmvdvp'>"
            "Colab usage guide</a>"
        )

        if is_leech:
            file_count_display = f"<b>Files:</b> <code>{file_count}</code>\n"
            size_label = "Uploaded"
            size_value = sizeUnit(total_uploaded_size)
            completion_title = "Leech Complete"
        else:
            file_count_display = ""
            size_label = "Total Size"
            size_value = sizeUnit(transfer_obj.total_down_size)
            completion_title = "Mirror Complete"

        custom_name = getattr(task_ctx.bot.Options, "custom_name", "")
        display_name = escape_html(custom_name or messages_obj.download_name or "N/A")
        try:
            elapsed_seconds = (datetime.now() - start_time).seconds
            elapsed_time_str = getTime(elapsed_seconds)
        except Exception:
            elapsed_time_str = "N/A"

        task_summary = messages_obj.task_msg if messages_obj and messages_obj.task_msg else ""
        short_id = task_ctx.get_short_id()
        last_text = (
            f"\n\n<b>{completion_title}</b> <code>{short_id}</code>\n\n"
            f"<b>Name:</b> <code>{display_name}</code>\n"
            f"<b>{size_label}:</b> <code>{size_value}</code>\n"
            f"{file_count_display}"
            f"<b>Time Taken:</b> <code>{elapsed_time_str}</code>"
        )

        if status_msg:
            final_status_text = task_summary + usage_link + last_text
            final_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("GitHub", url="https://github.com/XronTrix10/Telegram-Leecher")],
                [
                    InlineKeyboardButton("Channel", url="https://t.me/Colab_Leecher"),
                    InlineKeyboardButton("Group", url="https://t.me/Colab_Leecher_Discuss"),
                ],
            ])
            try:
                sent_msg = task_ctx.sent_msg
                if sent_msg:
                    source_href = safe_href(messages_obj.src_link if messages_obj else None)
                    source_markup = (
                        f"<a href='{escape_html(source_href)}'>Open</a>"
                        if source_href
                        else "Unavailable"
                    )
                    await sent_msg.reply_text(
                        text=f"<b>Source:</b> {source_markup}" + last_text,
                        disable_web_page_preview=False,
                    )
                    log.info(f"Sent final summary to dump chat {task_id_str}.")
                else:
                    log.warning(
                        f"Cannot send final summary to dump chat {task_id_str}, sent_msg invalid.")

                if hasattr(status_msg, "photo") and status_msg.photo:
                    await status_msg.edit_caption(caption=final_status_text, reply_markup=final_markup)
                    log.info(
                        f"Edited final status caption (thumbnail preserved) for owner {task_id_str}.")
                else:
                    await status_msg.edit_text(
                        text=final_status_text,
                        reply_markup=final_markup,
                        disable_web_page_preview=True,
                    )
                    log.info(
                        f"Edited final status text for owner {task_id_str}.")

                if is_leech and file_count > 0:
                    log_texts = []
                    current_log_text = f"<b>Uploaded Files Log ({file_count}):</b>\n"
                    for i in range(file_count):
                        try:
                            file_obj = transfer_obj.sent_file[i]
                            file_name = (
                                transfer_obj.sent_file_names[i]
                                if i < len(transfer_obj.sent_file_names)
                                else "Unknown Name"
                            )
                            link_chat_id = (
                                str(file_obj.chat.id).replace("-100", "")
                                if hasattr(file_obj, "chat") and hasattr(file_obj.chat, "id")
                                else None
                            )
                            msg_id = file_obj.id if hasattr(
                                file_obj, "id") else None
                            file_link = f"https://t.me/c/{link_chat_id}/{msg_id}" if link_chat_id and msg_id else "N/A"
                            safe_file_name = escape_html(file_name)
                            safe_file_link = safe_href(file_link)
                            file_text = (
                                f"\n({str(i + 1).zfill(2)}) <a href='{escape_html(safe_file_link)}'>{safe_file_name}</a>"
                                if safe_file_link
                                else f"\n({str(i + 1).zfill(2)}) {safe_file_name} (Link Unavailable)"
                            )
                            if len(current_log_text + file_text) >= 4096:
                                log_texts.append(current_log_text)
                                current_log_text = file_text
                            else:
                                current_log_text += file_text
                        except Exception as log_build_err:
                            log.error(
                                f"Error building log entry {i + 1}: {log_build_err}")
                            current_log_text += f"\n({str(i + 1).zfill(2)}) Error."
                    log_texts.append(current_log_text)

                    last_log_msg = status_msg
                    for fn_txt in log_texts:
                        try:
                            last_log_msg = await last_log_msg.reply_text(
                                text=fn_txt,
                                disable_web_page_preview=True,
                                quote=True,
                            )
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            log.error(
                                f"Error Sending log part {task_id_str}: {e}",
                                exc_info=False)
                            if OWNER and colab_bot:
                                await colab_bot.send_message(OWNER, fn_txt)
                            break

                if hasattr(
                        messages_obj,
                        "uploaded_links") and messages_obj.uploaded_links:
                    gdrive_links = messages_obj.uploaded_links
                    gdrive_count = len(gdrive_links)
                    log.info(
                        f"Formatting {gdrive_count} Google Drive upload links {task_id_str}...")

                    gdrive_log_texts = []
                    current_gdrive_log = f"<b>Uploaded to Google Drive ({gdrive_count}):</b>\n"
                    for i, item in enumerate(gdrive_links):
                        try:
                            file_name = item.get("name", "Unknown")
                            file_link = item.get("link", "N/A")
                            file_size = sizeUnit(item.get("size", 0))
                            safe_file_name = escape_html(file_name)
                            safe_file_link = safe_href(file_link)
                            gdrive_entry = (
                                f"\n({str(i + 1).zfill(2)}) <a href='{escape_html(safe_file_link)}'>{safe_file_name}</a> ({file_size})"
                                if safe_file_link
                                else f"\n({str(i + 1).zfill(2)}) {safe_file_name} ({file_size}) (Link Unavailable)"
                            )
                            if len(current_gdrive_log + gdrive_entry) >= 4096:
                                gdrive_log_texts.append(current_gdrive_log)
                                current_gdrive_log = gdrive_entry
                            else:
                                current_gdrive_log += gdrive_entry
                        except Exception as gdrive_log_err:
                            log.error(
                                f"Error building GDrive log entry {i + 1}: {gdrive_log_err}")
                            current_gdrive_log += f"\n({str(i + 1).zfill(2)}) Error."
                    gdrive_log_texts.append(current_gdrive_log)

                    last_gdrive_msg = status_msg
                    for gdrive_txt in gdrive_log_texts:
                        try:
                            last_gdrive_msg = await last_gdrive_msg.reply_text(
                                text=gdrive_txt,
                                disable_web_page_preview=False,
                                quote=True,
                            )
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            log.error(
                                f"Error sending GDrive log part {task_id_str}: {e}",
                                exc_info=False)
                            if OWNER and colab_bot:
                                await colab_bot.send_message(OWNER, gdrive_txt, disable_web_page_preview=False)
                            break

            except Exception as e:
                log.error(
                    f"Error sending/editing final logs {task_id_str}: {e}",
                    exc_info=True)
                if OWNER and colab_bot:
                    await colab_bot.send_message(OWNER, f"Error updating final status {task_id_str}.")
        else:
            log.error(
                f"Cannot send final logs {task_id_str}: Status message object missing.")
            if OWNER and colab_bot:
                await colab_bot.send_message(OWNER, last_text)

    except Exception as send_log_err:
        log.error(
            f"Error in SendLogs function {task_id_str}: {send_log_err}",
            exc_info=True)
    finally:
        log.info(f"SendLogs complete {task_id_str}.")
