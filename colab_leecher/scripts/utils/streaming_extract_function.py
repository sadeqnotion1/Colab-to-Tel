

# ==================================================================
# STREAMING EXTRACT + UPLOAD (Track 2 - For Large Archives 65GB+)
# ==================================================================

async def extract_and_upload_streaming(
    rar_filepath: str,
    password: str = None,
    file_filter: list = None,
    task_ctx = None
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
    import shutil
    import logging
    from datetime import datetime
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

    from ...utility.converters import prompt_for_password

    async def _request_password(error_type: str) -> None:
        retry_context = {
            'rar_filepath': rar_filepath,
            'password': password,
            'file_filter': file_filter,
            'task_ctx': task_ctx,
            'function': 'extract_and_upload_streaming'
        }
        await prompt_for_password(
            os.path.basename(rar_filepath),
            retry_context=retry_context,
            error_type=error_type,
            task_ctx=task_ctx,
        )

    # Create an isolated temp directory for single-file extraction.
    temp_extract_dir = tempfile.mkdtemp(prefix="streaming_extract_")

    # Open RAR archive
    try:
        rar_ref = rarfile.RarFile(rar_filepath)
        if password:
            rar_ref.setpassword(password)
            log.info(f"Opened password-protected RAR archive: {os.path.basename(rar_filepath)}")
        else:
            log.info(f"Opened RAR archive: {os.path.basename(rar_filepath)}")
    except rarfile.BadRarFile as e:
        log.error(f"Invalid RAR archive: {e}")
        if _task_error:
            _task_error.state = True
            _task_error.text = "Invalid RAR archive"
        return False
    except rarfile.PasswordRequired:
        log.warning(f"RAR requires password but none provided. Prompting user...")
        await _request_password("required")

        # Return False but don't set task error yet - we're waiting for password
        log.info("Waiting for user to provide password via Telegram...")
        return False
    except rarfile.RarWrongPassword:
        log.warning(f"Incorrect password for RAR. Prompting user for correct password...")
        await _request_password("incorrect")

        # Return False but don't set task error yet - we're waiting for password
        log.info("Waiting for user to provide correct password via Telegram...")
        return False

    # Get list of members to extract
    try:
        members = rar_ref.infolist()
    except rarfile.PasswordRequired:
        log.warning(f"RAR requires password (deferred check during infolist). Prompting user...")
        await _request_password("required")

        # Return False but don't set task error yet - we're waiting for password
        log.info("Waiting for user to provide password via Telegram...")
        return False
    except rarfile.RarWrongPassword:
        log.warning(f"Incorrect password for RAR (deferred check during infolist). Prompting user...")
        await _request_password("incorrect")

        # Return False but don't set task error yet - we're waiting for password
        log.info("Waiting for user to provide correct password via Telegram...")
        return False

    # Apply file filter if provided
    if file_filter:
        members_to_extract = [
            m for m in members
            if not m.is_dir() and any(m.filename.lower().endswith(ext.lower()) for ext in file_filter)
        ]
        log.info(f"File filter applied: {file_filter} - {len(members_to_extract)} files match")
    else:
        members_to_extract = [m for m in members if not m.is_dir()]
        log.info(f"No filter - extracting all {len(members_to_extract)} files")

    total_files = len(members_to_extract)
    if total_files == 0:
        log.warning("No files to extract")
        rar_ref.close()
        return False

    log.info(f"Starting streaming extraction of {total_files} files from {os.path.basename(rar_filepath)}")

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
            log.error("Cannot import upload_file - upload functionality unavailable")
            rar_ref.close()
            return False

    # Process each file
    for idx, member in enumerate(members_to_extract, 1):
        try:
            # Calculate progress
            percentage = ((idx - 1) / total_files) * 100  # Progress before current file
            elapsed = time.time() - start_time
            eta_seconds = (elapsed / idx) * (total_files - idx) if idx > 0 else 0
            eta_str = getTime(eta_seconds) if eta_seconds > 0 else "N/A"

            # Extract single file to temp location
            temp_file_path = os.path.join(temp_extract_dir, os.path.basename(member.filename))

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

            # Extract with streaming (1MB chunks)
            log.info(f"[{idx}/{total_files}] Extracting {member.filename} ({sizeUnit(member.file_size)})")
            try:
                with rar_ref.open(member, 'r') as source:
                    with open(temp_file_path, 'wb') as dest:
                        while True:
                            chunk = source.read(1024 * 1024)  # 1 MB chunks
                            if not chunk:
                                break
                            dest.write(chunk)
                log.info(f"Extracted to temp: {temp_file_path}")
            except rarfile.PasswordRequired:
                log.warning(f"RAR requires password (deferred check during extraction). Prompting user...")
                rar_ref.close()
                await _request_password("required")
                log.info("Waiting for user to provide password via Telegram...")
                return False
            except rarfile.RarWrongPassword:
                log.warning(f"Incorrect password for RAR (deferred check during extraction). Prompting user...")
                rar_ref.close()
                await _request_password("incorrect")
                log.info("Waiting for user to provide correct password via Telegram...")
                return False

            # Update status: Uploading
            percentage_upload = ((idx - 0.5) / total_files) * 100  # Midpoint progress
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
            log.info(f"[{idx}/{total_files}] Uploading {member.filename} to Telegram")
            upload_success = await upload_file(
                file_path=temp_file_path,
                filename=member.filename,
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
                log.info(f"✅ [{idx}/{total_files}] Uploaded {member.filename} successfully")

            # Delete temp file immediately to free disk space
            try:
                os.remove(temp_file_path)
                log.debug(f"Deleted temp file: {temp_file_path}")
            except OSError as e:
                log.warning(f"Could not delete temp file {temp_file_path}: {e}")

        except Exception as e:
            log.error(f"Error processing {member.filename}: {e}", exc_info=True)
            if _task_error:
                _task_error.state = True
            # Continue with next file
            continue

    # Cleanup temp directory
    try:
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

    log.info(f"Streaming extract-upload completed: {files_processed}/{total_files} files in {getTime(elapsed_total)}")

    rar_ref.close()
    return files_processed == total_files
