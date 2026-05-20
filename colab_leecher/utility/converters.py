# /content/Telegram-Leecher/colab_leecher/utility/converters.py
import os
import re
import json
import math
import GPUtil
import shutil
import logging
import subprocess
import asyncio
from datetime import datetime
from os import makedirs, path as ospath
from html import escape
from pyrogram import enums
try:
    from moviepy.editor import VideoFileClip as VideoClip
except ImportError:
    VideoClip = None

from .variables import BOT, MSG, BotTimes, Paths, Messages, TaskError
from .helper import (
    getSize,
    keyboard,
    multipartArchive,
    sizeUnit,
    speedETA,
    status_bar,
    sysINFO,
    getTime,
    clean_filename)
from .task_context import TaskContext
from .reply_state import set_password_reply_waiting
from .ui_copy import (
    build_archiver_progress_text,
    build_archiver_verification_text,
    build_converter_progress_text,
)
# Import bot client and owner ID for password prompts
from .. import colab_bot, OWNER

log = logging.getLogger(__name__)


async def prompt_for_password(
    archive_filename: str,
    retry_context: dict | None,
    error_type: str = "required",
    task_ctx: TaskContext | None = None,
) -> bool:
    """Send a password prompt and store per-user retry context."""
    try:
        target_user_id = OWNER
        target_chat_id = OWNER
        if task_ctx:
            target_user_id = getattr(task_ctx, "user_id", OWNER) or OWNER
            target_chat_id = getattr(task_ctx, "chat_id", OWNER) or OWNER

        if error_type == "incorrect":
            message_text = (
                "<b>Password Required</b>\n\n"
                "The password you provided is incorrect for:\n"
                f"<code>{escape(archive_filename)}</code>\n\n"
                "Reply to this message with the correct password."
            )
        else:
            message_text = (
                "<b>Password Required</b>\n\n"
                "The archive requires a password:\n"
                f"<code>{escape(archive_filename)}</code>\n\n"
                "Reply to this message with the password."
            )

        prompt_msg = await colab_bot.send_message(
            chat_id=target_chat_id,
            text=message_text,
            parse_mode=enums.ParseMode.HTML,
        )

        await set_password_reply_waiting(
            user_id=target_user_id,
            chat_id=target_chat_id,
            prompt_message_id=prompt_msg.id,
            retry_context=retry_context,
        )

        log.info(
            f"Password prompt sent for {archive_filename}. Waiting for user reply "
            f"(user={target_user_id}, chat={target_chat_id})."
        )
        return True

    except Exception as e:
        log.error(f"Failed to send password prompt: {e}")
        return False


async def archive(path: str, remove: bool, max_split_size_bytes: int,
                  task_ctx: TaskContext = None) -> tuple[str | None, int]:
    """Creates a single archive using 7z (.zip format) from the source path.

    Args:
        path: Source path to archive
        remove: Whether to remove source after archiving
        max_split_size_bytes: Maximum split size in bytes
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        tuple: (archive_path, archive_size) on success, (None, 0) on failure
    """

    global BOT, Messages, Paths, BotTimes, MSG, TaskError, log, getSize, sizeUnit, getTime, status_bar, multipartArchive, urlparse, urllib, os, ospath, re, asyncio, shutil, collections

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        _msg = task_ctx.msg
        log.info(
            f"archive() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _msg = MSG
        log.info("archive() using global state (single-task mode)")

    archive_success = False
    archive_out_path = None
    final_archive_size = 0
    error_reason = "Archive process failed."
    last_reported_pct = -1
    last_update_time = datetime.now()

    if not ospath.exists(path):
        log.error(f"Archive Error: Source path does not exist: {path}")
        _task_error.state = True
        _task_error.text = "Archive source path missing."
        return None, 0

    # Determine archive name with priority: custom_name > TITLE= filenames > download_name > file basename > dir basename > "archive"
    # NOTE: TITLE= filenames (from NZBCloud/Debrid) are checked BEFORE
    # download_name to use real content names instead of temporary disk names
    # like "play"
    if _bot.Options.custom_name:
        name = _bot.Options.custom_name
        log.info(f"Using custom_name for archive: {name}")
    elif _bot.Options.filenames and len(_bot.Options.filenames) > 0:
        # PRIORITY #2: Use TITLE= filename from NZBcloud/Debrid/bitso (checked BEFORE download_name!)
        # This ensures files show real content names instead of temporary names
        # like "play.zip"
        first_filename = _bot.Options.filenames[0]
        # Remove extension like .mkv, .mp4 etc.
        name, _ = ospath.splitext(first_filename)
        log.info(
            f"Using filename from TITLE= for archive: {name} (from {first_filename})")
    elif _messages.download_name:
        # Use download_name - set by smart naming or initial guess
        # (aria2/ytdl/gdrive etc.)
        # Strip extension in case it has one
        name, _ = ospath.splitext(_messages.download_name)
        log.info(
            f"Using download_name for archive: {name} (from {_messages.download_name})")
    elif ospath.isfile(path):
        # Single file: use its filename without extension
        name, _ = ospath.splitext(ospath.basename(path))
        log.info(f"Using file basename for archive: {name}")
    elif ospath.isdir(path):
        # Fallback to directory basename (might be "Download")
        name = ospath.basename(path)
        log.warning(
            f"Using directory basename for archive name: {name} - consider setting custom_name if unexpected")
    else:
        # Ultimate fallback
        name = "archive"
        log.warning("Using fallback archive name: archive")

    # Sanitize the determined name to remove invalid filesystem characters
    clean_name = clean_filename(name)
    if not clean_name:
        # If cleaning resulted in empty/None, use fallback
        log.warning(
            f"Archive name '{name}' became invalid after cleaning. Using fallback 'archive'")
        clean_name = "archive"

    makedirs(_paths.temp_zpath, exist_ok=True)

    # Determine archive format (ZIP, RAR, or 7Z)
    # Note: RAR creation requires WinRAR (proprietary), 7z on Linux can only
    # extract RAR
    archive_format = _bot.Options.archive_format if hasattr(
        _bot.Options, 'archive_format') else "7z"
    archive_format = archive_format.lower()  # Ensure lowercase

    if archive_format == "rar":
        archive_out_final_name = f"{clean_name}.rar"
        archive_format_param = "-trar"
        compression_level = "-mx=5"  # Normal compression for RAR
        format_display = "RAR"
    elif archive_format == "7z":
        # 7Z format: Best compression, CRC checks, works on all platforms, less
        # corruption
        archive_out_final_name = f"{clean_name}.7z"
        archive_format_param = "-t7z"
        # FASTEST compression (TikTok videos are already compressed)
        compression_level = "-mx=1"
        format_display = "7Z"
    else:  # ZIP (fallback)
        archive_out_final_name = f"{clean_name}.zip"
        archive_format_param = "-tzip"
        # FASTEST compression
        compression_level = "-mx=1"
        format_display = "ZIP"

    pswd_arg = None
    if _bot.Options.zip_pswd:
        pswd_arg = f"-p{_bot.Options.zip_pswd}"
        log.info(
            f"Using 7z to create password-protected {format_display} archive: {archive_out_final_name}")
    else:
        log.info(
            f"Using 7z to create non-password {format_display} archive: {archive_out_final_name}")

    archive_out_path = ospath.join(_paths.temp_zpath, archive_out_final_name)
    _messages.download_name = archive_out_final_name
    _messages.status_head = f"<b>🔐 ARCHIVING ({format_display} via 7z) » </b>\n\n<code>{archive_out_final_name}</code>\n"

    # Get task_start from task context
    if task_ctx:
        task_ctx.bot_times.task_start = datetime.now()
        _task_start = task_ctx.bot_times.task_start
    else:
        BotTimes.task_start = datetime.now()
        _task_start = BotTimes.task_start

    # Pre-flight checks before running 7z
    log.info("Archive pre-flight checks:")
    log.info(f"  Source path: {path}")
    log.info(f"  Source exists: {ospath.exists(path)}")
    log.info(f"  Source is file: {ospath.isfile(path)}")
    log.info(f"  Source is dir: {ospath.isdir(path)}")

    if ospath.isdir(path):
        try:
            items_in_dir = os.listdir(path)
            log.info(f"  Items in source dir: {len(items_in_dir)}")
            if len(items_in_dir) == 0:
                log.error("Archive Error: Source directory is empty!")
                _task_error.state = True
                _task_error.text = "Cannot archive empty directory."
                return None, 0
        except Exception as list_err:
            log.error(f"  Could not list source directory: {list_err}")

    log.info(f"  Output path: {archive_out_path}")
    log.info(f"  Output dir: {_paths.temp_zpath}")
    log.info(f"  Output dir exists: {ospath.exists(_paths.temp_zpath)}")

    # Check for problematic characters in paths
    if '"' in path or '"' in archive_out_path:
        log.error(
            "Archive Error: Paths contain double-quotes which will break 7z command!")
        _task_error.state = True
        _task_error.text = "Invalid characters in archive paths."
        return None, 0

    cmd_args = ["7z", "a", compression_level, archive_format_param]
    if pswd_arg:
        cmd_args.append(pswd_arg)
    
    # NEW: Add splitting support if max_split_size_bytes is provided
    if max_split_size_bytes and max_split_size_bytes > 0:
        # Convert to string with 'b' suffix for bytes
        cmd_args.append(f"-v{max_split_size_bytes}b")
        log.info(f"Splitting enabled: {sizeUnit(max_split_size_bytes)} per part.")

    cmd_args.extend(["-bsp1", archive_out_path, path])
    masked_cmd = ["***" if arg.startswith("-p") else arg for arg in cmd_args]
    log.info(f"Running 7z command: {' '.join(masked_cmd)}")
    proc = None
    stderr_output = []  # Store stderr for error reporting

    try:
        # --- Calculate total size before starting process ---
        total_size = getSize(path)
        total_in_unit = sizeUnit(total_size) if total_size > 0 else "N/A"
        last_reported_pct = -1  # Reset percentage tracking
        last_update_time = datetime.now()  # Reset last update time

        proc = await asyncio.create_subprocess_exec(
            *cmd_args,
            stdout=asyncio.subprocess.PIPE,  # Capture stdout for progress
            stderr=asyncio.subprocess.PIPE,
            limit=10 * 1024 * 1024  # 10MB buffer: prevents LimitOverrunError on long 7z output lines
        )
        log.debug(f"Archiver (7z) process started (PID: {proc.pid})")

        # Modified log_stream to handle both \n and \r for real-time progress
        async def log_stream_wrapper(stream, stream_name, is_stdout):
            nonlocal last_reported_pct, last_update_time  # CRITICAL: Fix missing updates
            lines = []
            buffer = ""
            while True:
                # Read in chunks to catch \r progress updates from 7z
                chunk_bytes = await stream.read(1024)
                if not chunk_bytes:
                    break
                
                buffer += chunk_bytes.decode('utf-8', errors='ignore')
                
                while True:
                    # Find first occurrence of \r or \n
                    pos_n = buffer.find('\n')
                    pos_r = buffer.find('\r')
                    
                    if pos_n == -1 and pos_r == -1:
                        break
                    
                    # Get the earliest delimiter
                    if pos_n != -1 and (pos_r == -1 or pos_n < pos_r):
                        pos = pos_n
                    else:
                        pos = pos_r
                    
                    line = buffer[:pos].strip()
                    buffer = buffer[pos + 1:]

                    if line:
                        if not is_stdout:
                            log.warning(f"7z {stream_name}: {line}")
                            lines.append(line)
                        else:
                            log.debug(f"7z {stream_name}: {line}")
                        
                        # Progress tracking
                        if is_stdout:
                            match = re.search(r"(\d+)\s*%", line)
                            if match:
                                try:
                                    percentage = int(match.group(1))
                                    current_time = datetime.now()
                                    # Increased update frequency (1.5s instead of 2.5s) for a more "fluid" feel
                                    if (percentage > last_reported_pct or (
                                            current_time - last_update_time).total_seconds() >= 1.5):

                                        # Update throttle variables
                                        last_reported_pct = percentage
                                        last_update_time = current_time

                                        # Calculate Speed and ETA based on percentage and time
                                        elapsed_seconds = (current_time - _task_start).total_seconds()
                                        if elapsed_seconds > 0.5 and percentage > 0:
                                            # Estimate bytes processed: total * percentage
                                            bytes_done = total_size * (percentage / 100)
                                            speed_bps = bytes_done / elapsed_seconds
                                            remaining_bytes = total_size - bytes_done
                                            
                                            speed_text = f"{sizeUnit(speed_bps)}/s"
                                            if speed_bps > 0:
                                                eta_seconds = remaining_bytes / speed_bps
                                                eta_text = getTime(eta_seconds)
                                            else:
                                                eta_text = "Calculating..."
                                        else:
                                            speed_text = "N/A"
                                            eta_text = "Calculating..."

                                        # Update TaskMessages archiving progress
                                        _messages.total_files = 1
                                        _messages.files_processed = 1 if percentage >= 100 else 0
                                        _messages.current_file = archive_out_final_name

                                        # Use the beautiful gradient style progress bar
                                        bar = ProgressBar.generate(percentage, length=20, style='gradient')
                                        
                                        elapsed_time_str = getTime(elapsed_seconds)
                                        status_text = build_archiver_progress_text(
                                            _messages.status_head,
                                            bar=bar,
                                            percentage=percentage,
                                            speed_text=speed_text,
                                            eta_text=eta_text,
                                            elapsed_time_text=elapsed_time_str,
                                            source_size_text=total_in_unit,
                                        )
                                        await status_bar(status_text, "N/A", 0, "N/A", "N/A", "N/A", "Archiver (7z) 🗜️", use_custom_text=True, task_ctx=task_ctx, force_update=True)
                                except ValueError:
                                    log.warning(
                                        f"Could not convert 7z percentage '{match.group(1)}' to int.")
                                except Exception as status_err:
                                    log.warning(
                                        f"Status update error in log_stream: {status_err}")
                
                await asyncio.sleep(0.01)
            return lines

        # Run stream loggers concurrently
        stdout_task = asyncio.create_task(
            log_stream_wrapper(
                proc.stdout, 'stdout', True))
        stderr_task = asyncio.create_task(
            log_stream_wrapper(
                proc.stderr, 'stderr', False))

        # CRITICAL FIX: Wait for BOTH process AND streams to complete simultaneously
        # This prevents race condition where process exits but streams still reading
        # and archive file not fully flushed to disk
        exit_code, stdout_lines, stderr_output = await asyncio.gather(
            proc.wait(),
            stdout_task,
            stderr_task
        )
        log.debug(
            f"Archiver (7z) process finished with exit code: {exit_code}")

        # CRITICAL FIX: Ensure archive file is fully written to disk before proceeding
        # Small delay to allow OS buffers to flush
        await asyncio.sleep(0.5)

        # Detect if splitting occurred (.001, .002, etc.)
        first_volume = archive_out_path + ".001"
        is_split = (max_split_size_bytes and max_split_size_bytes > 0 and ospath.exists(first_volume))
        
        # Determine the primary path to check/return
        actual_archive_path = first_volume if is_split else archive_out_path

        # Explicitly sync the archive file(s) to disk if they exist
        if ospath.exists(actual_archive_path):
            try:
                # Open and sync file to ensure all writes are committed to disk
                with open(actual_archive_path, 'rb') as f:
                    os.fsync(f.fileno())
                log.debug(f"Archive file synced to disk: {actual_archive_path}")
            except Exception as sync_err:
                log.warning(
                    f"Could not fsync archive file (may be fine): {sync_err}")

        # Check success and GET SIZE
        if exit_code == 0 and ospath.exists(actual_archive_path):
            try:
                if is_split:
                    # Calculate total size of all volumes
                    final_archive_size = 0
                    vol_num = 1
                    while True:
                        vol_path = f"{archive_out_path}.{vol_num:03d}"
                        if ospath.exists(vol_path):
                            final_archive_size += getSize(vol_path)
                            vol_num += 1
                        else:
                            break
                    log.info(f"Split archiving completed: {vol_num-1} parts, Total Size: {sizeUnit(final_archive_size)}")
                else:
                    final_archive_size = getSize(archive_out_path)
                
                if final_archive_size > 0:
                    log.info(
                        f"Archiving completed successfully: {actual_archive_path}, Size: {sizeUnit(final_archive_size)}")

                    # INTEGRITY CHECK: Verify archive is valid before uploading
                    log.info(
                        f"🔍 Verifying archive integrity before upload: {archive_out_final_name}")

                    # Update status message to show verification is in progress
                    try:
                        verify_msg = build_archiver_verification_text(
                            _messages.status_head,
                            title="Verifying Archive",
                            file_name=archive_out_final_name if not is_split else f"{archive_out_final_name}.001",
                            file_size_text=sizeUnit(final_archive_size),
                            status_text="Testing archive integrity...",
                        )
                        await status_bar(verify_msg, "N/A", 0, "N/A", "N/A", "N/A", "Archiver (7z) 🗜️", use_custom_text=True, task_ctx=task_ctx, force_update=True)
                    except Exception as status_err:
                        log.debug(
                            f"Could not update status during verification: {status_err}")

                    try:
                        # Use 7z test command to verify archive integrity
                        # For split archives, 7z test command should be run on the FIRST volume
                        test_cmd_args = ["7z", "t", actual_archive_path]
                        log.debug(
                            f"Running integrity test: {' '.join(test_cmd_args)}")

                        test_proc = await asyncio.create_subprocess_exec(
                            *test_cmd_args,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )

                        test_stdout, test_stderr = await test_proc.communicate()
                        test_exit_code = test_proc.returncode

                        if test_exit_code == 0:
                            log.info(
                                f"✅ Archive integrity verified successfully: {archive_out_final_name}")
                            archive_success = True

                            # Update status to show verification passed
                            try:
                                verify_success_msg = build_archiver_verification_text(
                                    _messages.status_head,
                                    title="Archive Verified",
                                    file_name=archive_out_final_name,
                                    file_size_text=sizeUnit(final_archive_size),
                                    status_text="Integrity check passed. Ready to upload.",
                                )
                                await status_bar(verify_success_msg, "N/A", 0, "N/A", "N/A", "N/A", "Archiver (7z) 🗜️", use_custom_text=True, task_ctx=task_ctx, force_update=True)
                            except Exception as status_err:
                                log.debug(
                                    f"Could not update status after verification: {status_err}")
                        else:
                            # Archive is corrupted!
                            log.error(
                                f"❌ Archive integrity check FAILED for {archive_out_final_name} (exit code: {test_exit_code})")
                            log.error(
                                f"7z test stderr: {test_stderr.decode( 'utf-8', errors='ignore')[ :500]}")
                            error_reason = f"Archive integrity check failed (corrupted archive, code {test_exit_code})"
                            archive_success = False

                            # Update status to show verification failed
                            try:
                                verify_fail_msg = build_archiver_verification_text(
                                    _messages.status_head,
                                    title="Verification Failed",
                                    file_name=archive_out_final_name,
                                    file_size_text=sizeUnit(final_archive_size),
                                    status_text="Archive is corrupted. Removing file...",
                                )
                                await status_bar(verify_fail_msg, "N/A", 0, "N/A", "N/A", "N/A", "Archiver (7z) 🗜️", use_custom_text=True, task_ctx=task_ctx)
                            except Exception as status_err:
                                log.debug(
                                    f"Could not update status for verification failure: {status_err}")

                            # Remove corrupted archive
                            if ospath.exists(archive_out_path):
                                try:
                                    os.remove(archive_out_path)
                                    log.info(
                                        f"Removed corrupted archive: {archive_out_path}")
                                except OSError as e:
                                    log.warning(
                                        f"Could not remove corrupted archive {archive_out_path}: {e}")

                    except Exception as verify_err:
                        log.error(
                            f"❌ Exception during archive verification: {verify_err}")
                        error_reason = f"Archive verification exception: {str(verify_err)[ :100]}"
                        archive_success = False

                        # Remove potentially corrupted archive
                        if ospath.exists(archive_out_path):
                            try:
                                os.remove(archive_out_path)
                                log.info(
                                    f"Removed unverified archive: {archive_out_path}")
                            except OSError as e:
                                log.warning(
                                    f"Could not remove unverified archive {archive_out_path}: {e}")

                else:  # Success code 0 but size is 0
                    log.error(
                        "Archiver (7z) finished (code 0) but output file size is 0.")
                    error_reason = "Archive success code 0 but output file size is 0."
                    archive_success = False
                    if ospath.exists(archive_out_path):
                        os.remove(archive_out_path)
            except Exception as size_err:
                log.error(
                    f"Archiver (7z) finished (code 0) but failed to get size of output {archive_out_path}: {size_err}")
                error_reason = "Archive success code 0 but failed to get output size."
                archive_success = False
                if ospath.exists(archive_out_path):
                    try:
                        os.remove(archive_out_path)
                    except OSError as e:
                        log.warning(
                            f"Could not remove zero-size archive {archive_out_path}: {e}")

        else:  # Non-zero exit code or file missing
            log.error(
                f"Archiving failed for '{archive_out_final_name}' with code {exit_code}.")

            # Build detailed error message with stderr output
            error_reason = f"Archive failed code {exit_code}."
            if not ospath.exists(archive_out_path):
                error_reason += " Output file missing."

            # Add stderr details if available
            if stderr_output:
                # Last 3 stderr lines
                stderr_msg = " | ".join(stderr_output[-3:])
                error_reason += f" 7z error: {stderr_msg}"
                log.error(f"7z stderr output: {stderr_msg}")

            archive_success = False
            if ospath.exists(
                    archive_out_path):  # Cleanup failed attempt if file exists
                try:
                    os.remove(archive_out_path)
                except OSError as e:
                    log.warning(
                        f"Could not remove failed archive {archive_out_path}: {e}")

    except Exception as archive_err:  # This except block now correctly follows the try
        log.error(
            f"Error during archive execution: {archive_err}",
            exc_info=True)
        if proc and proc.returncode is None:  # Check if process exists and is running
            try:
                proc.kill()
                await proc.wait()  # Try to kill hanging process
            except Exception as kill_err:
                log.warning(f"Error killing archiver process: {kill_err}")
        error_reason = f"Archive Exception: {str(archive_err)[:100]}"
        archive_success = False
        # Ensure cleanup even on exception
        if ospath.exists(archive_out_path):
            try:
                os.remove(archive_out_path)
            except OSError as e:
                log.warning(
                    f"Could not remove archive {archive_out_path} after exception: {e}")

    # Set TaskError if archiving failed
    if not archive_success:
        _task_error.state = True
        _task_error.text = error_reason
        # Log final failure reason
        log.error(f"Archive Task failed: {error_reason}")
        return None, 0

    # Remove original if successful and requested
    if archive_success and remove:
        log.info(f"Removing original source after archiving: {path}")
        try:
            if ospath.isfile(path):
                os.remove(path)
            elif ospath.isdir(path):
                shutil.rmtree(path)
        except Exception as rm_err:
            log.warning(f"Failed to remove original source '{path}': {rm_err}")

    return archive_out_path, final_archive_size
# ----- END OF archive function definition -----


async def videoConverter(file: str):
    # Make sure Messages is global if used in msg_updater
    global BOT, MSG, BotTimes, Messages

    # Nested function for moviepy conversion
    def convert_to_mp4(input_file, out_file):
        if VideoClip is None:
            log.error(
                "Moviepy (VideoFileClip) not found, cannot convert using this method.")
            return  # Cannot proceed without moviepy
        try:
            clip = VideoClip(input_file)
            # Define ffmpeg parameters if needed, check moviepy documentation
            clip.write_videofile(
                out_file,
                codec="libx264",       # Example codec
                audio_codec="aac",    # Example audio codec
                threads=4,            # Example: Use multiple threads
                logger='bar',         # Example: Show progress bar
                # ffmpeg_params=["-strict", "-2"] # Optional: Add specific
                # ffmpeg params if necessary
            )
            clip.close()  # Close the clip explicitly
        except Exception as moviepy_err:
            log.error(
                f"Moviepy conversion failed for {input_file}: {moviepy_err}",
                exc_info=True)
            # Optionally try to remove potentially corrupt output file
            if ospath.exists(out_file) and getSize(out_file) == 0:
                try:
                    os.remove(out_file)
                except OSError:
                    pass

    # Nested function to update status message

    async def msg_updater(c: int, tr, engine: str, core: str):
        # Ensure Messages is accessible (global or passed as argument)
        bar = "░" * c + "█" + "░" * (11 - c)
        messg = build_converter_progress_text(
            bar=bar,
            attempt=str(tr),
            engine=engine,
            handler_name=core,
            elapsed_time_text=getTime((datetime.now() - BotTimes.start_time).seconds),
        )
        full_message = Messages.task_msg + mtext + messg + \
            sysINFO()  # Ensure mtext is defined in outer scope
        try:
            if MSG.status_msg:
                await MSG.status_msg.edit_text(
                    text=full_message,
                    reply_markup=keyboard(),
                    parse_mode=enums.ParseMode.HTML,
                )
        except Exception as e:
            if "Message is not modified" not in str(e):
                log.warning(f"Status update failed during conversion: {e}")

    # --- videoConverter main logic ---
    name, ext = ospath.splitext(file)
    log.info(f"Starting video conversion check for: {ospath.basename(file)}")

    # Return if It's already the target format (mp4 or mkv?)
    # This check might be too simplistic depending on desired output
    # if ext.lower() in [".mkv", ".mp4"]:
    #    log.info("File is already MKV/MP4, skipping conversion.")
    #    return file

    # Use BOT.Options for target extension
    c, out_file, Err = 0, f"{name}.{BOT.Options.video_out}", False
    gpu_available = len(GPUtil.getAvailable()) > 0  # Check if GPU exists

    # Example quality setting - adjust as needed
    quality_args = [
        "-preset",
        "slow",
        "-crf",
        "18"] if BOT.Options.convert_quality else [
        "-preset",
        "medium",
        "-crf",
        "23"]  # Use CRF for quality

    # Determine ffmpeg command based on GPU availability
    if gpu_available:
        # Example NVENC command (adjust based on GPU and desired quality/speed)
        cmd_args = [
            "ffmpeg",
            "-y",
            "-i",
            file,
            "-c:v",
            "h264_nvenc",
            *quality_args,
            "-c:a",
            "copy",
            out_file]
        core = "GPU (NVENC)"
    else:
        # Example libx264 (CPU) command
        cmd_args = [
            "ffmpeg",
            "-y",
            "-i",
            file,
            "-c:v",
            "libx264",
            *quality_args,
            "-c:a",
            "copy",
            out_file]
        core = "CPU (libx264)"

    mtext = f"<b>🎥 Converting Video »</b>\n\n<code>{ospath.basename(file)}</code>\n\n"
    log.info(f"Running ffmpeg (Attempt 1): {' '.join(cmd_args)}")
    proc = None
    try:
        proc = subprocess.Popen(
            cmd_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE)
        while proc.poll() is None:
            await msg_updater(c, "1st", "FFmpeg 🏍", core)
            c = (c + 1) % 12
            await asyncio.sleep(3)  # Use asyncio.sleep

        stdout, stderr = proc.communicate()
        if proc.returncode != 0:
            log.error(
                f"FFmpeg (Attempt 1) failed with code {proc.returncode}.")
            if stderr:
                log.error(
                    f"FFmpeg stderr:\n{stderr.decode( 'utf-8', errors='ignore')}")
            Err = True
        else:
            # Check output file validity even on success code 0
            if not ospath.exists(out_file) or getSize(out_file) == 0:
                log.warning(
                    "FFmpeg reported success but output file invalid/empty.")
                if ospath.exists(out_file):
                    os.remove(out_file)  # Remove empty file
                Err = True
            else:
                log.info("FFmpeg (Attempt 1) conversion successful.")
                Err = False  # Conversion succeeded

    except Exception as ffmpeg_err:
        log.error(
            f"Error during FFmpeg (Attempt 1) execution: {ffmpeg_err}",
            exc_info=True)
        if proc and proc.poll() is None:
            proc.kill()
        Err = True

    # --- Attempt 2 (Moviepy) only if FFmpeg failed AND moviepy is available ---
    if Err and VideoClip is not None:
        log.warning(
            "FFmpeg failed, attempting conversion with Moviepy (CPU)...")
        moviepy_success = False
        try:
            # Run moviepy conversion in a separate thread to avoid blocking asyncio loop
            # Use ThreadPoolExecutor for better management if doing many
            # conversions
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, convert_to_mp4, file, out_file)

            # Check result after thread finishes
            if ospath.exists(out_file) and getSize(out_file) > 0:
                log.info("Moviepy conversion successful.")
                moviepy_success = True
            else:
                log.error("Moviepy conversion failed or produced empty file.")
                if ospath.exists(out_file):
                    os.remove(out_file)
                moviepy_success = False

        except Exception as thread_err:
            log.error(
                f"Error running Moviepy conversion in executor: {thread_err}",
                exc_info=True)
            moviepy_success = False

        # Update Err based on moviepy result
        Err = not moviepy_success

    # Final decision based on Err status
    if Err:
        log.error(
            f"Video conversion failed for {ospath.basename(file)} after all attempts.")
        return file  # Return original file path if conversion failed
    else:
        log.info(
            f"Video conversion successful. Output: {ospath.basename(out_file)}")
        # Remove original file after successful conversion
        try:
            if ospath.exists(file):
                os.remove(file)
        except OSError as e:
            log.warning(
                f"Could not remove original file {file} after conversion: {e}")
        return out_file  # Return new converted file path

# Replace sizeChecker in colab_leecher/utility/converters.py
# Ensure necessary imports: log, ospath, os, BOT, Paths, archive,
# splitVideo, splitArchive, getSize, sizeUnit, fileType, TaskError,
# asyncio


async def sizeChecker(
        file_path,
        remove: bool,
        task_ctx: TaskContext = None) -> bool:
    """Checks if file exceeds size limit and processes it accordingly.

    Args:
        file_path: Path to file to check
        remove: Whether to remove original after processing
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        bool: True if processing was done, False if file is within limits
    """
    global Paths, BOT, TaskError, log

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _paths = task_ctx.paths
        _bot = task_ctx.bot
        _task_error = task_ctx.task_error
        log.info(
            f"sizeChecker() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _bot = BOT
        _task_error = TaskError
        log.info("sizeChecker() using global state (single-task mode)")

    log.info(f"sizeChecker started for: {ospath.basename(file_path)}")
    max_size_bytes = 1000 * 1024 * 1024
    target_video_split_mb = 1000

    file_size = 0
    try:
        if ospath.exists(file_path):
            file_size = os.stat(file_path).st_size
        else:
            log.warning(f"sizeChecker: Input file does not exist: {file_path}")
            return False
    except OSError as e:
        log.error(f"sizeChecker: Cannot stat input file {file_path}: {e}")
        return False

    if file_size > max_size_bytes:
        log.info(
            f"File size {sizeUnit(file_size)} exceeds {sizeUnit(max_size_bytes)} limit. Processing required.")
        _, filename = ospath.split(file_path)
        _, extension = ospath.splitext(filename)
        ext_lower = extension.lower()
        processing_done = False

        archive_exts = {
            ".zip",
            ".rar",
            ".7z",
            ".tar",
            ".gz",
            ".bz2",
            ".xz",
            ".tgz",
            ".tbz",
            ".tbz2",
            ".txz"}

        if ext_lower in archive_exts:
            log.info(
                f"File '{filename}' is already an archive > limit. Splitting archive directly.")
            # Pass task_ctx
            await splitArchive(file_path, max_size_bytes, task_ctx)
            if _task_error.state:
                log.error(f"splitArchive failed. Reason: {_task_error.text}")
            return True

        # Check if MP4 or MKV
        if ext_lower in ['.mp4', '.mkv']:
            if _bot.Options.is_split:
                log.info(
                    f"File '{filename}' is MP4/MKV > limit. Splitting video.")
                # Pass task_ctx
                await splitVideo(file_path, target_video_split_mb, remove, task_ctx)
                processing_done = True
            else:
                # Archive MP4/MKV if splitting is off
                log.info(
                    f"File '{filename}' is MP4/MKV > limit, but video splitting is OFF. Archiving instead.")
                # <<< --- Get path AND size from archive --- >>>
                archive_output_path, archive_size = await archive(file_path, remove, max_size_bytes, task_ctx)
                # <<< --- Check TaskError and path --- >>>
                if _task_error.state or not archive_output_path:
                    log.error(
                        f"Archiving failed for MP4/MKV '{filename}'. Skipping further processing.")
                    processing_done = True  # Mark as attempted
                else:
                    log.info(
                        f"Archiving MP4/MKV succeeded. Output: {archive_output_path}, Size: {sizeUnit(archive_size)}")
                    processing_done = True
                    # <<< --- Check returned archive_size for splitting --- >>>
                    if archive_size > max_size_bytes:
                        log.info(
                            f"MP4/MKV archive size {sizeUnit(archive_size)} exceeds limit. Splitting archive...")
                        # Pass task_ctx
                        await splitArchive(archive_output_path, max_size_bytes, task_ctx)
                        if _task_error.state:
                            log.error(
                                f"splitArchive failed. Reason: {_task_error.text}")
                    else:
                        log.info(
                            "Created archive size is within limit. No splitting needed.")
        else:
            # Not MP4/MKV: Archive it first
            log.info(
                f"File '{filename}' is > limit and not MP4/MKV. Archiving first...")
            # <<< --- Get path AND size from archive --- >>>
            archive_output_path, archive_size = await archive(file_path, remove, max_size_bytes, task_ctx)

            # <<< --- Check TaskError and path --- >>>
            if _task_error.state or not archive_output_path:
                log.error(
                    f"Archiving failed for '{filename}'. Skipping further processing. Reason: {_task_error.text if _task_error.text else 'Archive function failed.'}")
                processing_done = True
            else:
                log.info(
                    f"Archiving succeeded. Output: {archive_output_path}, Size: {sizeUnit(archive_size)}")
                # <<< --- Check returned archive_size for splitting --- >>>
                if archive_size > max_size_bytes:
                    log.info(
                        f"Archive size {sizeUnit(archive_size)} exceeds limit. Splitting archive...")
                    # Pass task_ctx
                    await splitArchive(archive_output_path, max_size_bytes, task_ctx)
                    if _task_error.state:
                        log.error(
                            f"splitArchive failed. Reason: {_task_error.text}")
                elif archive_size <= 0:  # Check if size is invalid
                    log.error(
                        "Archive size reported as 0 B by archive function. Cannot proceed.")
                    if not _task_error.state:
                        _task_error.state = True
                        _task_error.text = "Created archive size is 0 B."
                else:
                    log.info(
                        "Created archive size is within limit. No splitting needed.")
                processing_done = True

        # await asyncio.sleep(0.5) # Delay likely not needed now
        return processing_done
    else:
        # File size is within limit
        return False

# Replace archive in colab_leecher/utility/converters.py
# Ensure necessary imports: log, os, ospath, subprocess, shutil, BOT,
# Messages, Paths, BotTimes, MSG, TaskError, getSize, sizeUnit, speedETA,
# status_bar, getTime, makedirs, asyncio

# ----- extract FUNCTION -----


async def extract(zip_filepath, remove: bool, task_ctx: TaskContext = None):
    """Extracts archive files.

    Args:
        zip_filepath: Path to archive file to extract
        remove: Whether to remove archive after extraction
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        bool: True on success, False on failure
    """
    # Ensure necessary globals and imports are accessible
    global BOT, Paths, Messages, BotTimes, MSG, log, TaskError, getSize, sizeUnit, multipartArchive, speedETA, status_bar, getTime, makedirs, os, ospath, subprocess, shutil, re

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        _msg = task_ctx.msg
        log.info(
            f"extract() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _msg = MSG
        log.info("extract() using global state (single-task mode)")

    extract_success = False
    error_reason = "Extraction failed"

    if not ospath.exists(zip_filepath):
        log.error(f"Extract Error: Input file does not exist: {zip_filepath}")
        _task_error.state = True
        _task_error.text = f"Extract source missing: {ospath.basename(zip_filepath)}"
        return False

    dir_path, filename = ospath.split(zip_filepath)
    _messages.status_head = f"<b>📂 EXTRACTING »</b>\n\n<code>{filename}</code>\n"

    password = _bot.Options.unzip_pswd  # Get potential password

    name, ext = ospath.splitext(filename)
    ext_lower = ext.lower()
    file_pattern = ""
    real_name = name
    temp_unzip_path = _paths.temp_unzip_path
    total_size_bytes = 0
    command_list = None  # Use a list for command and args

    os.makedirs(temp_unzip_path, exist_ok=True)

    # --- For .zip files, use streaming extraction (memory-safe) ---
    if ext_lower == ".zip" and ".part" not in name.lower() and ".z01" not in name.lower():
        log.info(f"Using streaming extraction for {filename}")
        # Use new streaming extractor for plain .zip files
        streaming_success = await extract_zip_streaming(
            zip_filepath=zip_filepath,
            extract_to=temp_unzip_path,
            remove=remove,
            file_filter=None,  # Extract all files (can be customized later)
            task_ctx=task_ctx
        )
        return streaming_success

    # --- For .rar files, use streaming extraction (memory-safe) ---
    if ext_lower == ".rar":
        log.info(f"Using streaming extraction for RAR: {filename}")

        # Generate resume state file path
        resume_file = ospath.join(_paths.down_path, f".resume_{name}.json")

        streaming_success = await extract_rar_streaming(
            rar_filepath=zip_filepath,
            # Note: variable is named zip_filepath but holds any archive path
            extract_to=temp_unzip_path,
            remove=remove,
            password=password,  # Password already retrieved on line 516
            file_filter=None,
            # Default: extract all (can be set via bot command)
            resume_state_file=resume_file,
            memory_limit_mb=800,
            task_ctx=task_ctx
        )
        if streaming_success:
            return True
        log.warning(
            "Streaming RAR extraction failed; attempting command-line fallback.")
        if _task_error and _task_error.state:
            _task_error.state = False
            _task_error.text = ""

    # --- Determine command list based on extension ---
    if ext_lower == ".rar":
        unrar_path = shutil.which("unrar")
        if unrar_path:
            command_list = [unrar_path, 'x', '-o+', '-y']
            if password:
                command_list.append(f'-p{password}')
            command_list.extend([zip_filepath, temp_unzip_path + os.sep])
        else:
            command_list = ['7z', 'x', f'-o{temp_unzip_path}', '-y']
            if password:
                command_list.append(f'-p{password}')
            command_list.append(zip_filepath)
        if ".part" in name.lower():
            file_pattern = "rar"
    elif ext_lower in [".tar", ".tar.gz", ".tgz"]:
        if ext_lower == ".tar":
            command_list = ['tar', '-xf', zip_filepath, '-C', temp_unzip_path]
        else:
            command_list = ['tar', '-xzf', zip_filepath, '-C', temp_unzip_path]
    elif ext_lower in [".zip", ".7z", ".001", ".z01"]:
        # Note: 7z syntax for password is -pPassword (no space)
        command_list = [
            '7z',
            'x',
            f'-o{temp_unzip_path}',
            '-y']  # Base command for 7z
        if password:
            command_list.append(f'-p{password}')  # Add password arg IF set
        command_list.append(zip_filepath)  # Add input file path
        if ext_lower == ".001":
            file_pattern = "7z"
        elif ext_lower == ".z01":
            file_pattern = "zip"
    else:
        log.error(
            f"Unsupported archive extension for extraction: '{ext_lower}'")
        _task_error.state = True
        _task_error.text = f"Unsupported archive type: {ext_lower}"
        return False

    # Calculate total size (handle multipart)
    try:
        # ... (size calculation logic remains same) ...
        if not file_pattern:
            total_size_bytes = getSize(zip_filepath)
            real_name, _ = ospath.splitext(filename)
        else:
            real_name, total_size_bytes = multipartArchive(
                zip_filepath, file_pattern, False)
        sizeUnit(total_size_bytes) if total_size_bytes > 0 else "N/A"
        _messages.download_name = real_name
        _messages.status_head = f"<b>📂 EXTRACTING »</b>\n\n<code>{real_name}{ext}</code>\n"
    except Exception as size_err:
        log.error(f"Error calculating archive size for {filename}: {size_err}")

    if not command_list:
        log.error(
            f"Extraction command list could not be determined for {filename}.")
        _task_error.state = True
        _task_error.text = f"Cannot determine extract command for {filename}"
        return False

    # Log the list itself for clarity
    log.info(f"Running Extractor Command List: {command_list}")

    # Get task_start from task context
    if task_ctx:
        task_ctx.bot_times.task_start = datetime.now()
        _task_start = task_ctx.bot_times.task_start
    else:
        BotTimes.task_start = datetime.now()
        _task_start = BotTimes.task_start
    proc = None
    try:
        # --- Execute command using list, shell=False (default) ---
        # Ensure shell=False is implicitly used by passing a list
        proc = subprocess.run(
            command_list,
            capture_output=True,
            text=True,
            check=False)

        exit_code = proc.returncode
        stdout = proc.stdout
        stderr = proc.stderr

        if stdout:
            log.info(f"Extractor stdout:\n{stdout}")
        # Log stderr even if exit code is 0, as some tools print warnings there
        if stderr:
            log.error(f"Extractor stderr:\n{stderr}")

        if exit_code == 0:
            log.info(
                f"Extraction completed successfully (code 0) for '{filename}'.")
            extract_success = True
            # ... (determine final_extracted_path logic remains same) ...
            extracted_items = os.listdir(temp_unzip_path)
            if len(extracted_items) == 1:
                ospath.join(temp_unzip_path, extracted_items[0])
            else:
                pass
        else:
            error_reason = f"Extractor failed code {exit_code}."
            # Prioritize getting last line of stderr for concise error
            # reporting
            if stderr:
                last_stderr_line = stderr.strip().splitlines(
                )[-1] if stderr.strip() else 'None'
                error_reason += f" Stderr: {last_stderr_line}"

            # Check if error is password-related
            stderr_lower = stderr.lower() if stderr else ""
            is_password_error = any(keyword in stderr_lower for keyword in [
                "password", "encrypted", "incorrect password", "wrong password"
            ])

            if is_password_error:
                log.warning(
                    "Command-line extraction failed due to password error. Prompting user...")

                retry_context = {
                    'zip_filepath': zip_filepath,
                    'remove': remove,
                    'task_ctx': task_ctx
                }

                # Determine error type based on whether password was provided
                error_type = "incorrect" if password else "required"

                # Prompt user for password
                await prompt_for_password(
                    filename,
                    retry_context=retry_context,
                    error_type=error_type,
                    task_ctx=task_ctx,
                )

                log.info("Waiting for user to provide password via Telegram...")
                return False  # Don't set task error yet

            log.error(
                f"Extraction failed for '{filename}'. Reason: {error_reason}")
            extract_success = False
            _task_error.state = True
            _task_error.text = error_reason

    except FileNotFoundError as fnf_error:
        log.error(
            f"Extraction command not found: {command_list[0]}. Ensure it's installed. Error: {fnf_error}",
            exc_info=True)
        _task_error.state = True
        _task_error.text = f"Extractor command '{command_list[0]}' not found."
        extract_success = False
    except Exception as extract_run_err:
        log.error(
            f"Error running extraction process for {filename}: {extract_run_err}",
            exc_info=True)
        _task_error.state = True
        _task_error.text = f"Extractor runtime error: {str(extract_run_err)[ :50]}"
        extract_success = False

    # Remove original archive(s) if extraction was successful *and* requested
    if extract_success and remove:
        # ... (removal logic remains same) ...
        log.info(
            f"Removing original archive(s) after successful extraction: {filename}")
        multipartArchive(zip_filepath, file_pattern, True)
        if ospath.exists(zip_filepath):
            try:
                os.remove(zip_filepath)
            except OSError as rm_err:
                log.warning(
                    f"Could not remove archive trigger file {zip_filepath}: {rm_err}")

    # Return success status
    return extract_success
# ----- END OF THE FUNCTION -----


# --- Streaming ZIP Extraction (Memory-Safe for Large Archives) ---
async def extract_zip_streaming(
    zip_filepath: str,
    extract_to: str = None,
    remove: bool = True,
    file_filter: list = None,
    chunk_size: int = 1024 * 1024,  # 1 MB chunks
    task_ctx: TaskContext = None
) -> bool:
    """Streams ZIP extraction for memory-safe handling of large archives.

    This function extracts ZIP files one file at a time, reading/writing in small chunks
    to avoid memory exhaustion. Perfect for large archives (65+ GB) in Colab.

    Args:
        zip_filepath: Path to ZIP file to extract
        extract_to: Target extraction directory (default: same dir as zip)
        remove: Whether to remove ZIP after successful extraction
        file_filter: List of extensions to extract (e.g., ['.csv', '.json']). None = extract all
        chunk_size: Size of chunks to read/write (default: 1 MB)
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        bool: True on success, False on failure

    Example:
        # Extract only CSV files from large archive
        await extract_zip_streaming(
            "/path/to/huge.zip",
            file_filter=['.csv'],
            task_ctx=task_ctx
        )
    """
    from zipfile import ZipFile
    from pathlib import Path
    import time

    global BOT, Paths, Messages, MSG, TaskError, log, status_bar, getTime, getSize, sizeUnit

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        _msg = task_ctx.msg
        log.info(
            f"extract_zip_streaming() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _msg = MSG
        log.info("extract_zip_streaming() using global state (single-task mode)")

    # Validate input
    if not ospath.exists(zip_filepath):
        log.error(
            f"Streaming Extract Error: ZIP file does not exist: {zip_filepath}")
        _task_error.state = True
        _task_error.text = f"ZIP file missing: {ospath.basename(zip_filepath)}"
        return False

    # Determine extraction target
    if extract_to is None:
        extract_to = _paths.temp_unzip_path

    Path(extract_to).mkdir(parents=True, exist_ok=True)

    zip_filename = ospath.basename(zip_filepath)
    zip_size = getSize(zip_filepath)
    zip_size_str = sizeUnit(zip_size)

    log.info(
        f"Starting streaming extraction of {zip_filename} ({zip_size_str}) to {extract_to}")
    _messages.status_head = f"<b>📂 EXTRACTING (Streaming) »</b>\n\n<code>{zip_filename}</code>\n"

    extraction_start_time = time.time()
    files_extracted = 0
    files_skipped = 0
    bytes_extracted = 0

    try:
        with ZipFile(zip_filepath, 'r') as zip_ref:
            # Get list of files in ZIP
            all_members = zip_ref.infolist()
            total_files = len([m for m in all_members if not m.is_dir()])

            # Apply file filter if specified
            if file_filter:
                members_to_extract = [
                    m for m in all_members if not m.is_dir() and any(
                        m.filename.lower().endswith(
                            ext.lower()) for ext in file_filter)]
                log.info(
                    f"Filter applied: {len(members_to_extract)}/{total_files} files match {file_filter}")
            else:
                members_to_extract = [m for m in all_members if not m.is_dir()]

            # Zip Bomb Protection: Check total uncompressed size
            total_uncompressed_size = sum(
                m.file_size for m in members_to_extract)
            MAX_UNZIP_SIZE = 50 * 1024 * 1024 * 1024  # 50 GB limit

            if total_uncompressed_size > MAX_UNZIP_SIZE:
                log.error(
                    f"Zip Bomb detected? Total uncompressed size {sizeUnit(total_uncompressed_size)} exceeds limit {sizeUnit(MAX_UNZIP_SIZE)}")
                _task_error.state = True
                _task_error.text = f"Archive too large: {sizeUnit(total_uncompressed_size)}"
                return False

            total_to_extract = len(members_to_extract)

            if total_to_extract == 0:
                log.warning(f"No files to extract from {zip_filename}")
                _task_error.state = True
                _task_error.text = "No matching files found in ZIP"
                return False

            log.info(
                f"Extracting {total_to_extract} files from ZIP archive...")

            # Extract each file with chunked streaming
            for idx, member in enumerate(members_to_extract, 1):
                try:
                    # Calculate progress
                    percentage = (idx / total_to_extract) * 100
                    elapsed = time.time() - extraction_start_time

                    # Estimate ETA based on files processed
                    if idx > 1:
                        eta_seconds = (elapsed / (idx - 1)) * \
                            (total_to_extract - idx + 1)
                        eta_str = getTime(eta_seconds)
                    else:
                        eta_str = "Calculating..."

                    # Update TaskMessages extraction progress fields for
                    # dashboard
                    _messages.total_files = total_to_extract
                    _messages.files_processed = idx - 1  # Files completed so far
                    _messages.current_file = member.filename
                    _messages.archive_size = bytes_extracted

                    # Update progress bar
                    status_text = f"Extracting file {idx}/{total_to_extract}: {member.filename}"
                    log.info(f"[{percentage:.1f}%] {status_text}")

                    await status_bar(
                        down_msg=_messages.status_head,
                        speed="N/A",
                        percentage=percentage,
                        eta=eta_str,
                        done=status_text,
                        total_size=zip_size_str,
                        engine="Streaming Extractor (zipfile)",
                        task_ctx=task_ctx,
                        force_update=True
                    )

                    # Create target path
                    target_path = Path(extract_to) / member.filename

                    # Zip Slip Protection
                    if not os.path.abspath(target_path).startswith(
                            os.path.abspath(extract_to)):
                        log.warning(
                            f"Zip Slip attempt detected! Skipping: {member.filename}")
                        continue

                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    # Stream extract file in chunks
                    with zip_ref.open(member, 'r') as source, open(target_path, 'wb') as target:
                        while True:
                            chunk = source.read(chunk_size)
                            if not chunk:
                                break
                            target.write(chunk)
                            bytes_extracted += len(chunk)

                    files_extracted += 1
                    log.debug(
                        f"Extracted: {member.filename} ({sizeUnit( member.file_size)})")

                except Exception as file_err:
                    log.error(
                        f"Failed to extract {member.filename}: {file_err}")
                    files_skipped += 1
                    # Continue with next file instead of failing completely
                    continue

            # Final progress update
            await status_bar(
                down_msg=_messages.status_head,
                speed="N/A",
                percentage=100.0,
                eta="Complete",
                done=f"✅ Extracted {files_extracted} files ({sizeUnit(bytes_extracted)})",
                total_size=zip_size_str,
                engine="Streaming Extractor (zipfile)"
            )

            log.info(
                f"Streaming extraction complete: {files_extracted} files extracted, {files_skipped} skipped")

            # Remove source ZIP if requested
            if remove:
                try:
                    os.remove(zip_filepath)
                    log.info(f"Removed source ZIP: {zip_filename}")
                except Exception as rm_err:
                    log.warning(
                        f"Could not remove ZIP file {zip_filename}: {rm_err}")

            return True

    except Exception as zip_err:
        log.error(
            f"Streaming extraction failed for {zip_filename}: {zip_err}",
            exc_info=True)
        _task_error.state = True
        _task_error.text = f"ZIP extraction error: {str(zip_err)[:50]}"
        return False


# --- Streaming RAR Extraction (Memory-Safe for Large Archives) ---
async def extract_rar_streaming(
    rar_filepath: str,
    extract_to: str = None,
    remove: bool = True,
    password: str = None,
    file_filter: list = None,
    chunk_size: int = 1024 * 1024,  # 1 MB chunks
    resume_state_file: str = None,  # For resume capability
    memory_limit_mb: int = 800,     # Abort if exceeded
    task_ctx: TaskContext = None
) -> bool:
    """Streams RAR extraction for memory-safe handling of large archives.

    This function extracts RAR files one file at a time, reading/writing in small chunks
    to avoid memory exhaustion. Handles multi-part RAR archives (.part01.rar) and
    password-protected archives. Includes memory monitoring and resume capability.

    Args:
        rar_filepath: Path to RAR file to extract (or first part for multi-part)
        extract_to: Target extraction directory (default: temp_unzip_path)
        remove: Whether to remove RAR after successful extraction
        password: Optional password for encrypted archives
        file_filter: List of extensions to extract (e.g., ['.csv', '.json']). None = all
        chunk_size: Size of chunks to read/write (default: 1 MB)
        resume_state_file: Path to resume state file for interrupted extractions
        memory_limit_mb: Abort extraction if memory exceeds this limit (default: 800 MB)
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        bool: True on success, False on failure

    Example:
        # Extract password-protected multi-part RAR with memory monitoring
        await extract_rar_streaming(
            "/path/to/archive.part01.rar",
            password="secret123",
            file_filter=['.mkv', '.mp4'],
            resume_state_file="/path/.resume_archive.json",
            task_ctx=task_ctx
        )
    """
    from pathlib import Path
    import time
    import json
    from datetime import datetime

    global BOT, Paths, Messages, MSG, TaskError, log, status_bar, getTime, getSize, sizeUnit, multipartArchive

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        _msg = task_ctx.msg
        _bot = task_ctx.bot
        log.info(
            f"extract_rar_streaming() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _msg = MSG
        _bot = BOT
        log.info("extract_rar_streaming() using global state (single-task mode)")

    # Validate input
    if not ospath.exists(rar_filepath):
        log.error(
            f"Streaming Extract Error: RAR file does not exist: {rar_filepath}")
        _task_error.state = True
        _task_error.text = f"RAR file missing: {ospath.basename(rar_filepath)}"
        return False

    # Determine extraction target
    if extract_to is None:
        extract_to = _paths.temp_unzip_path

    Path(extract_to).mkdir(parents=True, exist_ok=True)

    rar_filename = ospath.basename(rar_filepath)
    is_multipart = ".part" in rar_filename.lower()

    # Calculate archive size (handle multi-part)
    if is_multipart:
        real_name, total_size_bytes = multipartArchive(
            rar_filepath, "rar", False)
        rar_size = total_size_bytes
    else:
        rar_size = getSize(rar_filepath)
        real_name, _ = ospath.splitext(rar_filename)

    rar_size_str = sizeUnit(rar_size)

    log.info(
        f"Starting streaming extraction of {rar_filename} ({rar_size_str}) to {extract_to}")
    _messages.status_head = f"<b>📂 EXTRACTING (Streaming) »</b>\n\n<code>{real_name}.rar</code>\n"

    extraction_start_time = time.time()
    files_extracted = 0
    files_skipped = 0
    bytes_extracted = 0
    extracted_files_list = []

    # Import rarfile
    try:
        import rarfile
    except ImportError:
        log.error(
            "rarfile library not installed. Install with: pip install rarfile")
        _task_error.state = True
        _task_error.text = "rarfile library missing"
        return False

    # Set unrar tool path
    rarfile.UNRAR_TOOL = "unrar"

    # Open RAR file
    try:
        rar_ref = rarfile.RarFile(rar_filepath)
        if password:
            rar_ref.setpassword(password)
            log.info(f"Opening password-protected RAR: {rar_filename}")
        else:
            log.info(f"Opening RAR: {rar_filename}")

    except rarfile.BadRarFile as e:
        log.error(f"Invalid RAR file: {e}")
        _task_error.state = True
        _task_error.text = f"Invalid RAR file: {str(e)[:50]}"
        return False
    except rarfile.PasswordRequired:
        log.warning(
            "RAR requires password but none provided. Prompting user...")

        retry_context = {
            'rar_filepath': rar_filepath,
            'extract_to': extract_to,
            'remove': remove,
            'file_filter': file_filter,
            'chunk_size': chunk_size,
            'resume_state_file': resume_state_file,
            'memory_limit_mb': memory_limit_mb,
            'task_ctx': task_ctx
        }

        # Prompt user for password
        await prompt_for_password(
            rar_filename,
            retry_context=retry_context,
            error_type="required",
            task_ctx=task_ctx,
        )

        # Return False but don't set task error yet - we're waiting for
        # password
        log.info("Waiting for user to provide password via Telegram...")
        return False

    except rarfile.RarWrongPassword:
        log.warning(
            "Incorrect password for RAR. Prompting user for correct password...")

        retry_context = {
            'rar_filepath': rar_filepath,
            'extract_to': extract_to,
            'remove': remove,
            'file_filter': file_filter,
            'chunk_size': chunk_size,
            'resume_state_file': resume_state_file,
            'memory_limit_mb': memory_limit_mb,
            'task_ctx': task_ctx
        }

        # Prompt user for correct password
        await prompt_for_password(
            rar_filename,
            retry_context=retry_context,
            error_type="incorrect",
            task_ctx=task_ctx,
        )

        # Return False but don't set task error yet - we're waiting for
        # password
        log.info("Waiting for user to provide correct password via Telegram...")
        return False

    except Exception as e:
        log.error(f"Failed to open RAR: {e}")
        _task_error.state = True
        _task_error.text = f"RAR open error: {str(e)[:50]}"
        return False

    try:
        # Get list of members in RAR
        all_members = rar_ref.infolist()
        total_files = len([m for m in all_members if not m.isdir()])

        # Apply file filter if specified
        if file_filter:
            members_to_extract = [
                m for m in all_members if not m.isdir() and any(
                    m.filename.lower().endswith(
                        ext.lower()) for ext in file_filter)]
            log.info(
                f"Filter applied: {len(members_to_extract)}/{total_files} files match {file_filter}")
        else:
            members_to_extract = [m for m in all_members if not m.isdir()]

        # Load resume state if available
        resume_state = None
        if resume_state_file and ospath.exists(resume_state_file):
            try:
                with open(resume_state_file, 'r') as f:
                    resume_state = json.load(f)
                    already_extracted = set(
                        resume_state.get(
                            'extracted_files', []))
                    log.info(
                        f"Resuming extraction: {len(already_extracted)} files already extracted")

                    # Filter out already-extracted files
                    members_to_extract = [
                        m for m in members_to_extract
                        if m.filename not in already_extracted
                    ]
                    extracted_files_list = list(already_extracted)
                    files_extracted = len(already_extracted)
            except Exception as resume_err:
                log.warning(
                    f"Could not load resume state: {resume_err}. Starting fresh.")
                resume_state = None

        # Zip Bomb Protection: Check total uncompressed size
        total_uncompressed_size = sum(m.file_size for m in members_to_extract)
        MAX_UNZIP_SIZE = 50 * 1024 * 1024 * 1024  # 50 GB limit

        if total_uncompressed_size > MAX_UNZIP_SIZE:
            log.error(
                f"Zip Bomb detected? Total uncompressed size {sizeUnit(total_uncompressed_size)} exceeds limit {sizeUnit(MAX_UNZIP_SIZE)}")
            _task_error.state = True
            _task_error.text = f"Archive too large: {sizeUnit(total_uncompressed_size)}"
            rar_ref.close()
            return False

        total_to_extract = len(members_to_extract)

        # Validate we have files to extract
        if total_to_extract == 0 and files_extracted == 0:
            log.warning(f"No files to extract from {rar_filename}")
            _task_error.state = True
            _task_error.text = "No matching files in RAR"
            rar_ref.close()
            return False

        if total_to_extract == 0:
            log.info(f"All files already extracted from {rar_filename}")
            rar_ref.close()
            return True

        log.info(f"Extracting {total_to_extract} files from RAR archive...")

        # Initialize memory monitoring (optional - fallback if psutil not
        # available)
        try:
            import psutil
            process = psutil.Process(os.getpid())
            initial_mem_mb = process.memory_info().rss / 1024 / 1024
            memory_monitoring_available = True
            log.info(
                f"Memory monitoring enabled (current: {initial_mem_mb:.0f}MB, limit: {memory_limit_mb}MB)")
        except ImportError:
            process = None
            initial_mem_mb = 0
            memory_monitoring_available = False
            log.warning("psutil not available - memory monitoring disabled")

        # Helper function to save resume state
        def save_resume_state():
            if not resume_state_file:
                return
            try:
                state = {
                    "rar_filepath": rar_filepath,
                    "extract_to": extract_to,
                    "extracted_files": extracted_files_list,
                    "last_updated": datetime.now().isoformat(),
                    "total_files": total_files,
                    "files_extracted": files_extracted
                }
                with open(resume_state_file, 'w') as f:
                    json.dump(state, f, indent=2)
            except Exception as save_err:
                log.warning(f"Could not save resume state: {save_err}")

        # Extract each file with chunked streaming
        for idx, member in enumerate(members_to_extract, 1):
            try:
                # Calculate progress
                percentage = ((files_extracted + idx) /
                              (total_files if not file_filter else len(all_members))) * 100
                elapsed = time.time() - extraction_start_time

                # Estimate ETA
                if idx > 1:
                    eta_seconds = (elapsed / (idx - 1)) * \
                        (total_to_extract - idx + 1)
                    eta_str = getTime(eta_seconds)
                else:
                    eta_str = "Calculating..."

                # Update TaskMessages extraction progress fields for dashboard
                _messages.total_files = total_files
                _messages.files_processed = files_extracted + idx - 1  # Files completed so far
                _messages.current_file = member.filename
                _messages.archive_size = bytes_extracted

                # Update progress bar
                status_text = f"Extracting file {files_extracted + idx}/{total_files}: {member.filename}"
                log.info(f"[{percentage:.1f}%] {status_text}")

                await status_bar(
                    down_msg=_messages.status_head,
                    speed="N/A",
                    percentage=percentage,
                    eta=eta_str,
                    done=status_text,
                    total_size=rar_size_str,
                    engine="Streaming Extractor (rarfile)",
                    task_ctx=task_ctx,
                    force_update=True
                )

                # Check memory usage every 10 files (if monitoring available)
                if idx % 10 == 0 and memory_monitoring_available:
                    current_mem_mb = process.memory_info().rss / 1024 / 1024

                    if current_mem_mb > memory_limit_mb:
                        log.error(
                            f"Memory limit exceeded: {current_mem_mb:.0f}MB > {memory_limit_mb}MB")
                        _task_error.state = True
                        _task_error.text = f"Memory limit exceeded ({current_mem_mb:.0f}MB)"

                        # Save resume state before aborting
                        save_resume_state()

                        await status_bar(
                            down_msg=_messages.status_head,
                            speed="N/A",
                            percentage=percentage,
                            eta="Paused",
                            done="⚠️ Paused: Memory limit reached. Resume to continue.",
                            total_size=rar_size_str,
                            engine="Streaming Extractor (rarfile)"
                        )

                        rar_ref.close()
                        return False  # User can resume later

                # Create target path (preserve directory structure)
                target_path = Path(extract_to) / member.filename

                # Zip Slip Protection
                if not os.path.abspath(target_path).startswith(
                        os.path.abspath(extract_to)):
                    log.warning(
                        f"Zip Slip attempt detected! Skipping: {member.filename}")
                    continue

                target_path.parent.mkdir(parents=True, exist_ok=True)

                # Stream extract file in chunks
                with rar_ref.open(member, 'r') as source, open(target_path, 'wb') as target:
                    while True:
                        chunk = source.read(chunk_size)
                        if not chunk:
                            break
                        target.write(chunk)
                        bytes_extracted += len(chunk)

                files_extracted += 1
                extracted_files_list.append(member.filename)
                log.debug(
                    f"Extracted: {member.filename} ({sizeUnit( member.file_size)})")

                # Save resume state every 5 files
                if idx % 5 == 0:
                    save_resume_state()

            except rarfile.BadRarFile as e:
                log.error(f"Corrupt RAR member {member.filename}: {e}")
                files_skipped += 1
                save_resume_state()
                continue  # Skip corrupt files, continue extraction
            except Exception as file_err:
                log.error(f"Failed to extract {member.filename}: {file_err}")
                files_skipped += 1
                save_resume_state()
                continue  # Continue with next file instead of failing completely

        # Close RAR file
        rar_ref.close()

        # Final progress update
        await status_bar(
            down_msg=_messages.status_head,
            speed="N/A",
            percentage=100.0,
            eta="Complete",
            done=f"✅ Extracted {files_extracted} files ({sizeUnit(bytes_extracted)})"
            + (f" | {files_skipped} skipped" if files_skipped > 0 else ""),
            total_size=rar_size_str,
            engine="Streaming Extractor (rarfile)"
        )

        log.info(
            f"Streaming extraction complete: {files_extracted} files extracted, {files_skipped} skipped")

        # Remove resume state file on success
        if resume_state_file and ospath.exists(resume_state_file):
            try:
                os.remove(resume_state_file)
                log.debug(f"Removed resume state file: {resume_state_file}")
            except OSError as remove_state_err:
                log.debug(
                    f"Failed to remove resume state file {resume_state_file}: {remove_state_err}")

        # Remove source RAR if requested
        if remove:
            try:
                if is_multipart:
                    # Remove all parts via multipartArchive helper
                    multipartArchive(rar_filepath, "rar", True)
                    log.info(f"Removed multi-part RAR: {real_name}")
                else:
                    # Remove single RAR
                    os.remove(rar_filepath)
                    log.info(f"Removed source RAR: {rar_filename}")
            except Exception as rm_err:
                log.warning(
                    f"Could not remove RAR file {rar_filename}: {rm_err}")

        return True

    except Exception as rar_err:
        log.error(
            f"Streaming extraction failed for {rar_filename}: {rar_err}",
            exc_info=True)
        _task_error.state = True
        _task_error.text = f"RAR extraction error: {str(rar_err)[:50]}"
        try:
            rar_ref.close()
        except Exception as close_err:
            log.debug(f"Failed to close rar reference cleanly: {close_err}")
        return False
# ----- END OF FUNCTION -----


# --- splitArchive (Needs status return ideally) ---
async def splitArchive(
        file_path,
        max_size_bytes,
        task_ctx: TaskContext = None) -> bool:
    """Splits large archive files into smaller parts.

    Args:
        file_path: Path to archive file to split
        max_size_bytes: Maximum size per part in bytes
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        bool: True on success, False on failure
    """
    global Paths, BOT, MSG, Messages, BotTimes, TaskError, log

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        log.info(
            f"splitArchive() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        log.info("splitArchive() using global state (single-task mode)")

    split_success = False
    if not ospath.exists(file_path) or not ospath.isfile(file_path):
        log.error(
            f"splitArchive Error: Input file missing or invalid: {file_path}")
        _task_error.state = True
        _task_error.text = f"Archive splitting source missing: {ospath.basename(file_path)}"
        return False

    _, filename = ospath.split(file_path)
    # Output parts TO the temp_zpath directory
    makedirs(_paths.temp_zpath, exist_ok=True)

    name_root, ext = ospath.splitext(filename)
    compound_exts = [".tar.gz", ".tar.bz2", ".tar.xz", ".tar.zst"]
    lower_filename = filename.lower()
    for compound_ext in compound_exts:
        if lower_filename.endswith(compound_ext):
            name_root = filename[:-len(compound_ext)]
            ext = filename[-len(compound_ext):]
            break

    _messages.status_head = f"<b>✂️ SPLITTING ARCHIVE » </b>\n\n<code>{filename}</code>\n"
    total_size = getSize(file_path)
    total_size_str = sizeUnit(total_size) if total_size > 0 else "N/A"
    log.info(
        f"Splitting archive '{filename}' ({total_size_str}) into parts of max {sizeUnit(max_size_bytes)}")

    # Get task_start from task context
    if task_ctx:
        task_ctx.bot_times.task_start = datetime.now()
        _task_start = task_ctx.bot_times.task_start
    else:
        BotTimes.task_start = datetime.now()
        _task_start = BotTimes.task_start

    bytes_written = 0
    part_num = 1
    error_reason = "Archive splitting failed."

    try:
        with open(file_path, "rb") as f_in:
            while True:
                chunk = f_in.read(max_size_bytes)
                if not chunk:
                    break

                output_filename = ospath.join(
                    _paths.temp_zpath,
                    f"{name_root}.part{str(part_num).zfill(3)}{ext}"
                )
                log.debug(f"Writing part {part_num}: {output_filename}")
                with open(output_filename, "wb") as f_out:
                    f_out.write(chunk)

                bytes_written += len(chunk)
                # --- Status Update Logic ---
                speed_string, eta, percentage = speedETA(
                    _task_start, bytes_written, total_size)
                await status_bar(_messages.status_head, speed_string, percentage, getTime(eta), sizeUnit(bytes_written), total_size_str, "Splitter ✂️",)
                # --- End Status Update ---
                part_num += 1
                await asyncio.sleep(0.1)

        # Verify success
        if bytes_written >= total_size:
            log.info(
                f"Archive splitting completed successfully for {filename}. Parts: {part_num - 1}")
            split_success = True
            # <<< --- ADDED LOGGING AROUND REMOVAL --- >>>
            try:
                log.info(
                    f"Attempting to remove original large archive after split: {file_path}")
                os.remove(file_path)
                log.info(
                    f"Successfully removed original archive: {file_path}")  # Log success
            except OSError as rm_err:
                log.warning(
                    f"Could not remove original archive {file_path} after splitting: {rm_err}")
                # Consider if this should be treated as a failure? For now, just warn.
                # split_success = False # Uncomment to make removal failure a task failure
            # <<< --- END ADDED LOGGING --- >>>
        else:
            log.warning(
                f"Archive splitting finished for {filename}, but bytes written ({bytes_written}) != total size ({total_size}).")
            error_reason = f"Split size mismatch ({bytes_written} vs {total_size})"
            split_success = False

    except IOError as io_err:
        log.error(
            f"I/O error during archive splitting for {filename}: {io_err}",
            exc_info=True)
        error_reason = f"I/O Error during split: {str(io_err)[:100]}"
        split_success = False
    except Exception as split_err:
        log.error(
            f"Unexpected error during archive splitting for {filename}: {split_err}",
            exc_info=True)
        error_reason = f"Unexpected split error: {str(split_err)[:100]}"
        split_success = False

    # Set TaskError and clean up parts if splitting failed
    if not split_success:
        _task_error.state = True
        _task_error.text = error_reason
        log.info(f"Cleaning up parts due to split failure for: {filename}")
        for i in range(1, part_num):
            part_file = ospath.join(
                _paths.temp_zpath, f"{name_root}.part{str(i).zfill(3)}{ext}")
            if ospath.exists(part_file):
                try:
                    os.remove(part_file)
                except OSError:
                    pass

    return split_success


# --- splitVideo (with fixes from previous steps) ---
async def splitVideo(
        file_path,
        target_segment_size_mb: int,
        remove: bool,
        task_ctx: TaskContext = None):
    """Splits large video files into smaller segments.

    Args:
        file_path: Path to video file to split
        target_segment_size_mb: Target size per segment in MB
        remove: Whether to remove original after splitting
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        bool: True on success, False on failure
    """
    # Returns True on success, False on failure
    # Ensure globals accessible, add log
    global Paths, BOT, MSG, Messages, BotTimes, TaskError, log

    # Multi-task support: Use task_ctx if provided, otherwise fallback to
    # globals
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        log.info(
            f"splitVideo() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        log.info("splitVideo() using global state (single-task mode)")

    log.info(
        f"Attempting to split video: {os.path.basename(file_path)} into segments of ~{target_segment_size_mb}MB, ensuring max ~2GB per part.")
    _, filename = ospath.split(file_path)
    just_name, extension = ospath.splitext(filename)

    # --- Get File Info ---
    bitrate = None
    duration_total_seconds = 0.0
    total_file_size = 0
    try:
        if not ospath.exists(file_path):
            log.error(f"splitVideo: Input file not found: {file_path}")
            _task_error.state = True
            _task_error.text = f"Split source missing: {filename}"
            return False

        total_file_size = getSize(file_path)
        if total_file_size <= 0:
            log.error(
                f"splitVideo: Could not get valid size for {filename}. Cannot split.")
            _task_error.state = True
            _task_error.text = f"Split source size invalid: {filename}"
            return False

        cmd_probe = [
            "ffprobe",
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            "-select_streams",
            "v:0",
            file_path]
        output = subprocess.check_output(cmd_probe, timeout=30)
        video_info = json.loads(output)

        if 'format' in video_info and 'duration' in video_info['format']:
            duration_total_seconds = float(video_info['format']['duration'])

        if 'streams' in video_info and len(
                video_info['streams']) > 0 and 'bit_rate' in video_info['streams'][0]:
            bitrate = float(video_info['streams'][0]['bit_rate'])
        elif 'format' in video_info and 'bit_rate' in video_info['format']:
            bitrate = float(video_info['format']['bit_rate'])

        if duration_total_seconds <= 0:
            log.warning(
                f"Could not determine duration for {filename}. Cannot reliably split by time.")
            _task_error.state = True
            _task_error.text = f"Could not get video duration for {filename}"
            return False

        if not bitrate or bitrate <= 0:
            log.warning(
                f"Could not determine bitrate for {filename}. Will estimate based on size/duration.")
            bitrate = (total_file_size * 8) / duration_total_seconds

    except subprocess.TimeoutExpired:
        log.error(
            f"Error: ffprobe timed out getting video metadata for {filename}")
        _task_error.state = True
        _task_error.text = f"ffprobe timeout for {filename}"
        return False
    except subprocess.CalledProcessError as cpe:
        log.error(
            f"Error: ffprobe failed getting video metadata for {filename}. Return code: {cpe.returncode}")
        if cpe.stderr:
            log.error(
                f"ffprobe stderr: {cpe.stderr.decode( 'utf-8', errors='ignore')}")
        _task_error.state = True
        _task_error.text = f"ffprobe failed for {filename}"
        return False
    except json.JSONDecodeError:
        log.error(f"Error: Could not parse ffprobe JSON output for {filename}")
        _task_error.state = True
        _task_error.text = f"ffprobe JSON error for {filename}"
        return False
    except Exception as probe_err:
        log.error(
            f"Error: Could not get video metadata for {filename}: {probe_err}",
            exc_info=True)
        _task_error.state = True
        _task_error.text = f"Metadata error for {filename}"
        return False

    # --- Calculate Segment Duration ---
    MAX_SPLIT_SIZE_BYTES = 1000 * 1024 * 1024  # 1000 MiB (Strict < 1GB)

    # Priority 1: If file size requires splitting, use that calculation
    if total_file_size > MAX_SPLIT_SIZE_BYTES:
        min_parts_required = math.ceil(total_file_size / MAX_SPLIT_SIZE_BYTES)
        final_segment_duration = math.floor(
            duration_total_seconds / min_parts_required)
        log.info(
            f"File size ({sizeUnit(total_file_size)}) requires minimum {min_parts_required} parts.")
        log.info(
            f"Segment duration set to {final_segment_duration}s to stay within {sizeUnit(MAX_SPLIT_SIZE_BYTES)} per part.")
    # Priority 2: File is small enough for one part, but we're splitting
    # anyway for other reasons
    else:
        if bitrate > 0:
            target_size_bits = target_segment_size_mb * 1024 * 1024 * 8
            final_segment_duration = int(target_size_bits / bitrate)
            log.info(
                f"File size OK, using target {target_segment_size_mb}MB segments → {final_segment_duration}s duration")
        else:
            # No bitrate info, just split into reasonable chunks
            final_segment_duration = 1200  # 20 minutes default
            log.warning("No bitrate info, using default 20min segments")

    # Ensure minimum duration
    final_segment_duration = max(10, final_segment_duration)

    if final_segment_duration >= duration_total_seconds:
        log.info(
            f"Final calculated segment duration ({final_segment_duration}s) >= total duration ({duration_total_seconds:.2f}s). No splitting required.")
        return True

    # Adjust segment duration to avoid tiny final segment
    # Calculate how many segments we'll create and check if the last one would
    # be too small
    estimated_segments = math.ceil(
        duration_total_seconds /
        final_segment_duration)
    remainder_duration = duration_total_seconds % final_segment_duration

    # If the last segment would be less than 30% of target duration, adjust to
    # make segments more equal
    if remainder_duration > 0 and remainder_duration < (
            final_segment_duration * 0.3):
        log.info(
            f"Last segment would be only {remainder_duration:.1f}s (too small). Adjusting segment duration.")
        # Redistribute duration evenly across all segments
        final_segment_duration = int(
            duration_total_seconds / estimated_segments)
        log.info(
            f"Adjusted segment duration to {final_segment_duration}s to create {estimated_segments} more equal segments.")

    log.info(
        f"Final segment duration chosen: {final_segment_duration} seconds.")

    # --- Execute FFmpeg Split ---
    makedirs(_paths.temp_zpath, exist_ok=True)
    split_output_pattern = ospath.join(
        _paths.temp_zpath,
        f"{just_name}.part%03d{extension}")
    cmd_split_args = [
        "ffmpeg",
        "-i",
        file_path,
        "-c",
        "copy",
        "-map",
        "0:v",
        "-map",
        "0:a?",
        "-copyts",
        "-segment_time",
        str(final_segment_duration),
        "-f",
        "segment",
        "-reset_timestamps",
        "1",
        "-segment_start_number",
        "1",
        "-movflags",
        "+faststart",
        split_output_pattern,
    ]

    log.info(f"Executing ffmpeg split: {' '.join(cmd_split_args)}")
    _messages.status_head = f"<b>✂️ SPLITTING » </b>\n\n<code>{filename}</code>\n"

    # Get task_start from task context
    if task_ctx:
        task_ctx.bot_times.task_start = datetime.now()
        _task_start = task_ctx.bot_times.task_start
    else:
        BotTimes.task_start = datetime.now()
        _task_start = BotTimes.task_start

    proc = None
    ffmpeg_success = False
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd_split_args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        total_in_unit = sizeUnit(total_file_size)
        log.info(f"Monitoring split process (PID: {proc.pid})...")

        # --- Monitor Progress with Restored Progress Bar ---
        while proc.returncode is None:
            current_split_size = getSize(
                _paths.temp_zpath)  # Size of output dir

            # Calculate rough percentage based on output size (may not be
            # accurate)
            percentage = 0
            if total_file_size > 0:
                percentage = min(
                    100, (current_split_size / total_file_size) * 100)

            # Calculate speed and ETA based on output size change (also rough)
            # speed_string, eta_seconds, _ = speedETA(_task_start, current_split_size, total_file_size)
            # eta_str = getTime(eta_seconds)
            # Note: Speed/ETA based on output dir size is very inaccurate for splitting.
            # Let's omit them for now and just show the bar and elapsed time.
            getTime((datetime.now() - _task_start).seconds)

            # Call status_bar WITHOUT use_custom_text=True to show the bar
            # Provide necessary parameters, using "N/A" for less reliable ones
            # like speed/ETA
            await status_bar(
                down_msg=_messages.status_head,
                speed="N/A",  # Speed is unreliable here
                percentage=percentage,  # Use rough percentage for bar
                eta="N/A",  # ETA is unreliable here
                done=sizeUnit(current_split_size),  # Show current output size
                total_size=total_in_unit,  # Show original total size
                engine="Splitter ✂️"
                # removed use_custom_text=True
            )

            # Check process status without blocking excessively
            try:
                await asyncio.wait_for(proc.wait(), timeout=2.0)  # Wait for 2s
            except asyncio.TimeoutError:
                pass  # Process still running, continue loop
        # --- End Monitoring Loop ---

        # Process finished, get final results
        stdout, stderr = await proc.communicate()  # Get remaining output
        log.info(f"Split process finished with return code: {proc.returncode}")

        # --- Check success based on return code and output files ---
        if proc.returncode == 0:
            segment_files = sorted([f for f in os.listdir(_paths.temp_zpath) if f.startswith(
                f"{just_name}.part") and f.endswith(extension)])
            if segment_files:
                log.info(
                    f"FFmpeg split completed successfully for {filename}. Segments found: {len(segment_files)}")

                # --- Post-process: Detect and merge tiny final segments ---
                if len(segment_files) >= 2:
                    last_file_path = ospath.join(
                        _paths.temp_zpath, segment_files[-1])
                    second_last_file_path = ospath.join(
                        _paths.temp_zpath, segment_files[-2])

                    last_file_size = getSize(last_file_path) if ospath.exists(
                        last_file_path) else 0
                    getSize(second_last_file_path) if ospath.exists(
                        second_last_file_path) else 0

                    # If last segment is < 10MB (very small), merge it with the
                    # previous one
                    MIN_SEGMENT_SIZE = 10 * 1024 * 1024  # 10 MB
                    if last_file_size > 0 and last_file_size < MIN_SEGMENT_SIZE:
                        log.warning(
                            f"Last segment {segment_files[-1]} is only {sizeUnit(last_file_size)}, merging with previous segment.")

                        # Create merged file
                        merged_path = ospath.join(
                            _paths.temp_zpath, f"{just_name}.merged{extension}")

                        # Use FFmpeg concat demuxer to merge
                        concat_file = ospath.join(
                            _paths.temp_zpath, "concat_list.txt")
                        with open(concat_file, 'w') as f:
                            f.write(f"file '{segment_files[-2]}'\n")
                            f.write(f"file '{segment_files[-1]}'\n")

                        merged_filename = f"{just_name}.merged{extension}"
                        merge_cmd_args = [
                            "ffmpeg",
                            "-f",
                            "concat",
                            "-safe",
                            "0",
                            "-i",
                            "concat_list.txt",
                            "-c",
                            "copy",
                            merged_filename,
                        ]
                        log.info(
                            f"Merging last two segments: {' '.join(merge_cmd_args)}")

                        try:
                            merge_proc = await asyncio.create_subprocess_exec(
                                *merge_cmd_args,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                                cwd=_paths.temp_zpath
                            )
                            await merge_proc.wait()

                            if merge_proc.returncode == 0 and ospath.exists(
                                    merged_path):
                                # Remove old files and rename merged
                                os.remove(second_last_file_path)
                                os.remove(last_file_path)
                                os.rename(merged_path, second_last_file_path)
                                os.remove(concat_file)

                                segment_files = sorted([f for f in os.listdir(_paths.temp_zpath) if f.startswith(
                                    f"{just_name}.part") and f.endswith(extension)])
                                log.info(
                                    f"✅ Successfully merged tiny segment. New segment count: {len(segment_files)}")
                            else:
                                log.warning(
                                    "Merge failed, keeping original segments")
                                if ospath.exists(concat_file):
                                    os.remove(concat_file)
                        except Exception as merge_err:
                            log.warning(
                                f"Error during merge: {merge_err}. Keeping original segments.")
                            if ospath.exists(concat_file):
                                os.remove(concat_file)

                ffmpeg_success = True
                total_parts_size = getSize(_paths.temp_zpath)
                if abs(total_parts_size -
                        total_file_size) > total_file_size * 0.1:
                    log.warning(
                        f"Total size of split parts ({sizeUnit(total_parts_size)}) differs significantly from original ({total_in_unit}). Check results.")
            else:
                log.error(
                    f"FFmpeg split finished with code 0 but no segment files found for {filename} in {_paths.temp_zpath}.")
                if stderr:
                    log.error(
                        f"FFmpeg stderr:\n{stderr.decode( 'utf-8', errors='ignore')}")
                _task_error.state = True
                _task_error.text = f"Split failed (no output files): {filename}"
                ffmpeg_success = False
        else:
            log.error(
                f"FFmpeg split failed for {filename} with return code {proc.returncode}.")
            if stderr:
                log.error(
                    f"FFmpeg stderr:\n{stderr.decode( 'utf-8', errors='ignore')}")
            _task_error.state = True
            _task_error.text = f"Split failed (ffmpeg code {proc.returncode}): {filename}"
            ffmpeg_success = False

    except asyncio.TimeoutError:  # Should not happen with wait_for loop logic, but keep as fallback
        log.error(
            f"Error: ffmpeg process communication timed out during split for {filename}")
        if proc and proc.returncode is None:
            await kill_proc(proc)  # Use helper to kill
        _task_error.state = True
        _task_error.text = f"Split communication timeout for {filename}"
        ffmpeg_success = False
    except Exception as split_err:
        log.error(
            f"Error during ffmpeg execution for {filename}: {split_err}",
            exc_info=True)
        if proc and proc.returncode is None:
            await kill_proc(proc)  # Use helper to kill
        _task_error.state = True
        _task_error.text = f"Split execution error for {filename}"
        ffmpeg_success = False

    # Clean up original file if successful AND remove=True
    if ffmpeg_success and remove:
        try:
            if ospath.exists(file_path):
                os.remove(file_path)
                log.info(
                    f"Removed original file after successful split: {filename}")
        except OSError as rm_err:
            log.warning(
                f"Could not remove original file {filename} after split: {rm_err}")

    if not ffmpeg_success and not _task_error.state:
        _task_error.state = True
        _task_error.text = _task_error.text or f"Video splitting failed for {filename}"

    return ffmpeg_success


async def kill_proc(proc):
    """Helper to terminate/kill asyncio subprocess"""
    if proc is None or proc.returncode is not None:
        return
    log.warning(f"Attempting to terminate/kill process PID: {proc.pid}")
    try:
        proc.terminate()
        # Wait briefly for termination
        await asyncio.wait_for(proc.wait(), timeout=5)
        log.info(f"Process {proc.pid} terminated.")
    except asyncio.TimeoutError:
        log.warning(
            f"Process {proc.pid} did not terminate gracefully, killing...")
        try:
            proc.kill()
            await proc.wait()  # Wait for kill
            log.info(f"Process {proc.pid} killed.")
        except ProcessLookupError:
            log.info(f"Process {proc.pid} already gone.")
        except Exception as kill_err:
            log.error(f"Error killing process {proc.pid}: {kill_err}")
    except ProcessLookupError:
        log.info(f"Process {proc.pid} already gone.")
    except Exception as term_err:
        log.error(f"Error terminating process {proc.pid}: {term_err}")


# ==================================================================
# STREAMING EXTRACT + UPLOAD (Track 2 - For Large Archives 65GB+)
# ==================================================================

async def extract_and_upload_streaming(
    rar_filepath: str,
    password: str = None,
    file_filter: list = None,
    task_ctx=None
) -> bool:
    """
    Extract RAR members one-by-one and upload immediately.
    Memory and disk efficient for large archives (65GB+).

    Process:
    1. Extract single file to temp location
    2. Upload file to Telegram
    3. Delete temp file
    4. Repeat for next file

    Disk usage: archive_size + largest_single_file (vs. archive_size * 2 for batch mode)

    Args:
        rar_filepath: Path to RAR archive (can be .part01.rar)
        password: Optional password for protected archives
        file_filter: List of extensions to extract (e.g., ['.mkv', '.mp4'])
        task_ctx: Task context for isolated state (optional)

    Returns:
        True if all files extracted and uploaded successfully
    """
    import rarfile
    import os
    import time
    import tempfile
    import logging
    from .helper import status_bar, getTime, sizeUnit

    log = logging.getLogger(__name__)

    # Get context objects (task_ctx or global)
    if task_ctx:
        _paths = task_ctx.paths if hasattr(task_ctx, 'paths') else None
        _messages = task_ctx.messages
        _task_error = task_ctx.error
        _status_msg = task_ctx.status_msg
    else:
        from .variables import Paths, Messages, TaskError, MSG
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _status_msg = MSG.status_msg

    # Validate inputs
    if not os.path.exists(rar_filepath):
        log.error(f"RAR file not found: {rar_filepath}")
        if _task_error:
            _task_error.state = True
            _task_error.text = f"Archive not found: {rar_filepath}"
        return False

    # Create isolated temp directory for single-file extraction
    base_temp_dir = None
    if _paths and hasattr(_paths, "work_path") and _paths.work_path:
        base_temp_dir = _paths.work_path
        os.makedirs(base_temp_dir, exist_ok=True)
    temp_extract_dir = tempfile.mkdtemp(
        prefix="streaming_extract_", dir=base_temp_dir)

    # Open RAR archive
    try:
        rar_ref = rarfile.RarFile(rar_filepath)
        if password:
            rar_ref.setpassword(password)
            log.info(
                f"Opened password-protected RAR archive: {os.path.basename(rar_filepath)}")
        else:
            log.info(f"Opened RAR archive: {os.path.basename(rar_filepath)}")
    except rarfile.BadRarFile as e:
        log.error(f"Invalid RAR archive: {e}")
        if _task_error:
            _task_error.state = True
            _task_error.text = "Invalid RAR archive"
        return False
    except rarfile.PasswordRequired:
        log.warning(
            "RAR requires password but none provided. Prompting user...")

        retry_context = {
            'rar_filepath': rar_filepath,
            'password': password,
            'file_filter': file_filter,
            'task_ctx': task_ctx,
            'function': 'extract_and_upload_streaming'
        }

        # Prompt user for password
        await prompt_for_password(
            os.path.basename(rar_filepath),
            retry_context=retry_context,
            error_type="required",
            task_ctx=task_ctx,
        )

        # Return False but don't set task error yet - we're waiting for
        # password
        log.info("Waiting for user to provide password via Telegram...")
        return False

    except rarfile.RarWrongPassword:
        log.warning(
            "Incorrect password for RAR. Prompting user for correct password...")

        retry_context = {
            'rar_filepath': rar_filepath,
            'password': password,
            'file_filter': file_filter,
            'task_ctx': task_ctx,
            'function': 'extract_and_upload_streaming'
        }

        # Prompt user for correct password
        await prompt_for_password(
            os.path.basename(rar_filepath),
            retry_context=retry_context,
            error_type="incorrect",
            task_ctx=task_ctx,
        )

        # Return False but don't set task error yet - we're waiting for
        # password
        log.info("Waiting for user to provide correct password via Telegram...")
        return False

    # Get list of members to extract
    try:
        members = rar_ref.infolist()
    except rarfile.PasswordRequired:
        log.warning(
            "RAR requires password (deferred check during infolist). Prompting user...")

        retry_context = {
            'rar_filepath': rar_filepath,
            'password': password,
            'file_filter': file_filter,
            'task_ctx': task_ctx,
            'function': 'extract_and_upload_streaming'
        }

        # Prompt user for password
        await prompt_for_password(
            os.path.basename(rar_filepath),
            retry_context=retry_context,
            error_type="required",
            task_ctx=task_ctx,
        )

        # Return False but don't set task error yet - we're waiting for
        # password
        log.info("Waiting for user to provide password via Telegram...")
        return False
    except rarfile.RarWrongPassword:
        log.warning(
            "Incorrect password for RAR (deferred check during infolist). Prompting user...")

        retry_context = {
            'rar_filepath': rar_filepath,
            'password': password,
            'file_filter': file_filter,
            'task_ctx': task_ctx,
            'function': 'extract_and_upload_streaming'
        }

        # Prompt user for correct password
        await prompt_for_password(
            os.path.basename(rar_filepath),
            retry_context=retry_context,
            error_type="incorrect",
            task_ctx=task_ctx,
        )

        # Return False but don't set task error yet - we're waiting for
        # password
        log.info("Waiting for user to provide correct password via Telegram...")
        return False

    # Apply file filter if provided
    if file_filter:
        members_to_extract = [
            m for m in members if not m.is_dir() and any(
                m.filename.lower().endswith(
                    ext.lower()) for ext in file_filter)]
        log.info(
            f"File filter applied: {file_filter} - {len(members_to_extract)} files match")
    else:
        members_to_extract = [m for m in members if not m.is_dir()]
        log.info(f"No filter - extracting all {len(members_to_extract)} files")

    total_files = len(members_to_extract)
    if total_files == 0:
        log.warning("No files to extract")
        rar_ref.close()
        return False

    log.info(
        f"Starting streaming extraction of {total_files} files from {os.path.basename(rar_filepath)}")

    # Statistics
    start_time = time.time()
    files_processed = 0
    bytes_uploaded = 0

    # Status header
    status_head = (
        f"<b>🔄 Streaming Extract + Upload »</b>\n\n"
        f"<b>📦 Archive:</b> <code>{os.path.basename(rar_filepath)}</code>\n"
    )

    # Import upload function
    try:
        from ..uploader.telegram import upload_file
    except ImportError:
        try:
            from uploader.telegram import upload_file
        except ImportError:
            log.error(
                "Cannot import upload_file - upload functionality unavailable")
            rar_ref.close()
            return False

    # Process each file
    for idx, member in enumerate(members_to_extract, 1):
        try:
            # Calculate progress
            percentage = ((idx - 1) / total_files) * \
                100  # Progress before current file
            elapsed = time.time() - start_time
            eta_seconds = (elapsed / idx) * \
                (total_files - idx) if idx > 0 else 0
            eta_str = getTime(eta_seconds) if eta_seconds > 0 else "N/A"

            # Extract single file to temp location
            temp_file_path = os.path.join(
                temp_extract_dir, os.path.basename(
                    member.filename))

            # Update status: Extracting
            status_text = (
                f"📂 Extracting {idx}/{total_files}\n"
                f"<code>{member.filename}</code> ({sizeUnit(member.file_size)})"
            )

            if _status_msg:
                await status_bar(
                    down_msg=status_head,
                    speed="N/A",
                    percentage=percentage,
                    eta=eta_str,
                    done=status_text,
                    total_size=f"{files_processed}/{total_files} files",
                    engine="Streaming Extractor+Uploader",
                    task_ctx=task_ctx
                )

            # Extract with streaming (1MB chunks) - handle short reads
            # gracefully
            log.info(
                f"[{idx}/{total_files}] Extracting {member.filename} ({sizeUnit(member.file_size)})")
            try:
                with rar_ref.open(member, 'r') as source:
                    with open(temp_file_path, 'wb') as dest:
                        # Use shutil.copyfileobj for robust streaming (handles
                        # short reads)
                        import shutil
                        shutil.copyfileobj(
                            source, dest, length=1024 * 1024)  # 1 MB chunks
                log.info(f"Extracted to temp: {temp_file_path}")
            except rarfile.PasswordRequired:
                log.warning(
                    "RAR requires password (deferred check during extraction). Prompting user...")
                rar_ref.close()

                retry_context = {
                    'rar_filepath': rar_filepath,
                    'password': password,
                    'file_filter': file_filter,
                    'task_ctx': task_ctx,
                    'function': 'extract_and_upload_streaming'
                }

                # Prompt user for password
                await prompt_for_password(
                    os.path.basename(rar_filepath),
                    retry_context=retry_context,
                    error_type="required",
                    task_ctx=task_ctx,
                )
                log.info("Waiting for user to provide password via Telegram...")
                return False
            except rarfile.RarWrongPassword:
                log.warning(
                    "Incorrect password for RAR (deferred check during extraction). Prompting user...")
                rar_ref.close()

                retry_context = {
                    'rar_filepath': rar_filepath,
                    'password': password,
                    'file_filter': file_filter,
                    'task_ctx': task_ctx,
                    'function': 'extract_and_upload_streaming'
                }

                # Prompt user for correct password
                await prompt_for_password(
                    os.path.basename(rar_filepath),
                    retry_context=retry_context,
                    error_type="incorrect",
                    task_ctx=task_ctx,
                )
                log.info(
                    "Waiting for user to provide correct password via Telegram...")
                return False
            except rarfile.BadRarFile as e:
                # Handle corrupt/incomplete RAR members
                log.error(f"RAR extraction error for {member.filename}: {e}")
                # Skip this file and continue
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
                continue

            # Update status: Uploading
            percentage_upload = (
                (idx - 0.5) / total_files) * 100  # Midpoint progress
            status_text = (
                f"⬆️ Uploading {idx}/{total_files}\n"
                f"<code>{member.filename}</code> ({sizeUnit(member.file_size)})"
            )

            if _status_msg:
                await status_bar(
                    down_msg=status_head,
                    speed="N/A",
                    percentage=percentage_upload,
                    eta=eta_str,
                    done=status_text,
                    total_size=f"{files_processed}/{total_files} files",
                    engine="Streaming Extractor+Uploader",
                    task_ctx=task_ctx
                )

            # Upload file to Telegram
            log.info(
                f"[{idx}/{total_files}] Uploading {member.filename} to Telegram")
            upload_success = await upload_file(
                file_path=temp_file_path,
                display_name=member.filename,
                task_ctx=task_ctx
            )

            if not upload_success:
                log.error(f"Upload failed for {member.filename}")
                if _task_error:
                    _task_error.state = True
                    _task_error.text = f"Upload failed: {member.filename}"
                # Continue with other files (don't abort entire batch)
            else:
                bytes_uploaded += member.file_size
                files_processed += 1
                log.info(
                    f"✅ [{idx}/{total_files}] Uploaded {member.filename} successfully")

            # Delete temp file immediately to free disk space
            try:
                os.remove(temp_file_path)
                log.debug(f"Deleted temp file: {temp_file_path}")
            except OSError as e:
                log.warning(
                    f"Could not delete temp file {temp_file_path}: {e}")

        except Exception as e:
            log.error(
                f"Error processing {member.filename}: {e}",
                exc_info=True)
            if _task_error:
                _task_error.state = True
            # Continue with next file
            continue

    # Cleanup temp directory
    try:
        import shutil
        shutil.rmtree(temp_extract_dir)
        log.info(f"Cleaned up temp directory: {temp_extract_dir}")
    except Exception as e:
        log.warning(f"Could not clean up temp directory: {e}")

    # Final status
    elapsed_total = time.time() - start_time

    if _status_msg:
        await status_bar(
            down_msg=status_head,
            speed="N/A",
            percentage=100.0,
            eta="Complete",
            done=f"✅ Processed {files_processed}/{total_files} files ({sizeUnit(bytes_uploaded)})",
            total_size=f"{files_processed} files",
            engine="Streaming Extractor+Uploader",
            task_ctx=task_ctx
        )

    log.info(
        f"Streaming extract-upload completed: {files_processed}/{total_files} files in {getTime(elapsed_total)}")

    rar_ref.close()
    return files_processed == total_files
