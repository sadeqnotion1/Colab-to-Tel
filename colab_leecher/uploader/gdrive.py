#/content/Telegram-Leecher/colab_leecher/uploader/gdrive.py

import time
import logging
import os
import asyncio
import shutil
import mimetypes
from os import path as ospath
from os import makedirs
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from natsort import natsorted
from ..utility.variables import BOT, Paths, Messages, MSG, TRANSFER, TaskError, Gdrive
from ..utility.task_context import TaskContext
from ..utility import helper
from ..utility.helper import status_bar, getSize, sizeUnit, getTime
from .. import colab_bot, OWNER

log = logging.getLogger(__name__)


def get_file_mime_type(file_path: str) -> str:
    """
    Detect MIME type for a file.

    Args:
        file_path: Path to the file

    Returns:
        MIME type string
    """
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'  # Default for unknown types
    return mime_type


def format_gdrive_link(file_id: str) -> str:
    """
    Generate shareable Google Drive link from file ID.

    Args:
        file_id: Google Drive file ID

    Returns:
        Shareable URL
    """
    return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"


async def create_folder_on_gdrive(folder_name: str, parent_id: str = None, task_ctx: TaskContext = None) -> str:
    """
    Create a folder on Google Drive.

    Args:
        folder_name: Name of the folder to create
        parent_id: Parent folder ID (None for root)
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        Created folder ID or None on failure
    """
    # Use task_ctx if provided
    _task_error = task_ctx.task_error if task_ctx else TaskError
    task_id_str = f"[{task_ctx.get_short_id()}]" if task_ctx else "[legacy]"

    if not Gdrive.service:
        log.error(f"{task_id_str} Google Drive service not initialized")
        if _task_error:
            _task_error.state = True
            _task_error.text = "GDrive service not available"
        return None

    try:
        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }

        if parent_id:
            file_metadata['parents'] = [parent_id]

        folder = Gdrive.service.files().create(
            body=file_metadata,
            fields='id, name, webViewLink'
        ).execute()

        folder_id = folder.get('id')
        log.info(f"{task_id_str} Created GDrive folder: {folder_name} (ID: {folder_id})")
        return folder_id

    except HttpError as e:
        log.error(f"{task_id_str} Failed to create GDrive folder '{folder_name}': {e}", exc_info=True)
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = f"GDrive folder creation failed: {e.reason}"
        return None
    except Exception as e:
        log.error(f"{task_id_str} Unexpected error creating GDrive folder: {e}", exc_info=True)
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = f"GDrive error: {str(e)}"
        return None


async def upload_to_gdrive(file_path: str, parent_folder_id: str = None, task_ctx: TaskContext = None) -> dict:
    """
    Upload a single file to Google Drive with progress tracking.

    Args:
        file_path: Path to the file to upload
        parent_folder_id: Parent folder ID on Google Drive (None for root)
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        Dict with file info {'id', 'name', 'webViewLink', 'size'} or None on failure
    """
    # Use task_ctx if provided
    _task_error = task_ctx.task_error if task_ctx else TaskError
    _transfer = task_ctx.transfer if task_ctx else TRANSFER
    task_id_str = f"[{task_ctx.get_short_id()}]" if task_ctx else "[legacy]"

    if not Gdrive.service:
        log.error(f"{task_id_str} Google Drive service not initialized")
        if _task_error:
            _task_error.state = True
            _task_error.text = "GDrive service not available"
        return None

    if not ospath.exists(file_path):
        log.error(f"{task_id_str} File does not exist: {file_path}")
        if _task_error:
            _task_error.state = True
            _task_error.text = f"File not found: {ospath.basename(file_path)}"
        return None

    filename = ospath.basename(file_path)
    file_size = getSize(file_path)

    # Check for zero-byte file
    if file_size == 0:
        log.error(f"{task_id_str} Skipping zero-byte file: {filename}")
        return None

    log.info(f"{task_id_str} Uploading to GDrive: {filename} ({sizeUnit(file_size)})")

    try:
        mime_type = get_file_mime_type(file_path)

        # Prepare file metadata
        file_metadata = {
            'name': filename
        }

        if parent_folder_id:
            file_metadata['parents'] = [parent_folder_id]

        # Create media upload with resumable support
        media = MediaFileUpload(
            file_path,
            mimetype=mime_type,
            resumable=True,
            chunksize=10 * 1024 * 1024  # 10MB chunks
        )

        # Create upload request
        request = Gdrive.service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, name, webViewLink, size'
        )

        # Execute with progress tracking
        response = None
        upload_start_time = time.time()
        last_update_time = upload_start_time

        while response is None:
            try:
                status, response = request.next_chunk()

                if status:
                    progress = status.progress() * 100
                    current_time = time.time()
                    elapsed = current_time - upload_start_time

                    # Update progress bar every second
                    if current_time - last_update_time >= 1.0 or progress >= 99:
                        last_update_time = current_time

                        # Calculate upload speed
                        uploaded_bytes = int((progress / 100) * file_size)
                        speed = uploaded_bytes / elapsed if elapsed > 0 else 0
                        speed_str = f"{sizeUnit(speed)}/s" if speed > 0 else "N/A"

                        # Calculate ETA
                        if progress > 0 and progress < 100:
                            eta_seconds = (elapsed / progress) * (100 - progress)
                            eta_str = getTime(eta_seconds)
                        else:
                            eta_str = "N/A"

                        # Update status bar
                        await status_bar(
                            down_msg=f"<b>☁️ Google Drive Upload »</b>\n\n<b>📂 File » </b><code>{filename}</code>\n",
                            speed=speed_str,
                            percentage=progress,
                            eta=eta_str,
                            done=f"Uploading... {progress:.1f}%",
                            total_size=sizeUnit(file_size),
                            engine="Google Drive API v3"
                        )

            except HttpError as chunk_error:
                log.error(f"{task_id_str} Upload chunk failed for {filename}: {chunk_error}", exc_info=True)
                if _task_error and not _task_error.state:
                    _task_error.state = True
                    _task_error.text = f"GDrive upload failed: {chunk_error.reason}"
                return None

        # Upload complete
        uploaded_file = response
        file_id = uploaded_file.get('id')
        web_link = uploaded_file.get('webViewLink', format_gdrive_link(file_id))

        log.info(f"{task_id_str} Successfully uploaded to GDrive: {filename} (ID: {file_id})")

        # Update final progress bar
        await status_bar(
            down_msg=f"<b>☁️ Google Drive Upload »</b>\n\n<b>📂 File » </b><code>{filename}</code>\n",
            speed="N/A",
            percentage=100.0,
            eta="N/A",
            done=f"Complete ✅ {sizeUnit(file_size)}",
            total_size=sizeUnit(file_size),
            engine="Google Drive API v3"
        )

        return {
            'id': file_id,
            'name': filename,
            'webViewLink': web_link,
            'size': file_size
        }

    except HttpError as e:
        log.error(f"{task_id_str} Failed to upload {filename} to GDrive: {e}", exc_info=True)
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = f"GDrive upload failed: {e.reason}"
        return None
    except Exception as e:
        log.error(f"{task_id_str} Unexpected error uploading {filename}: {e}", exc_info=True)
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = f"GDrive error: {str(e)}"
        return None


async def upload_folder_to_gdrive(folder_path: str, parent_folder_id: str = None, task_ctx: TaskContext = None) -> dict:
    """
    Recursively upload a folder and its contents to Google Drive.

    Args:
        folder_path: Path to the local folder
        parent_folder_id: Parent folder ID on Google Drive (None for root)
        task_ctx: Optional TaskContext for multi-task support

    Returns:
        Dict with folder info and uploaded files list, or None on failure
    """
    # Use task_ctx if provided
    _task_error = task_ctx.task_error if task_ctx else TaskError
    task_id_str = f"[{task_ctx.get_short_id()}]" if task_ctx else "[legacy]"

    if not ospath.exists(folder_path) or not ospath.isdir(folder_path):
        log.error(f"{task_id_str} Folder does not exist: {folder_path}")
        if _task_error:
            _task_error.state = True
            _task_error.text = f"Folder not found: {ospath.basename(folder_path)}"
        return None

    folder_name = ospath.basename(folder_path)
    log.info(f"{task_id_str} Uploading folder to GDrive: {folder_name}")

    # Create the folder on Google Drive
    gdrive_folder_id = await create_folder_on_gdrive(folder_name, parent_folder_id, task_ctx)
    if not gdrive_folder_id:
        log.error(f"{task_id_str} Failed to create folder on GDrive: {folder_name}")
        return None

    uploaded_files = []
    failed_files = []

    # Get all items in the folder
    try:
        items = natsorted(os.listdir(folder_path))
    except Exception as e:
        log.error(f"{task_id_str} Failed to list folder contents: {e}", exc_info=True)
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = f"Failed to read folder: {str(e)}"
        return None

    # Upload each item
    for item in items:
        item_path = ospath.join(folder_path, item)

        if _task_error.state:
            log.warning(f"{task_id_str} Skipping {item} due to prior error")
            break

        if ospath.isfile(item_path):
            # Upload file
            file_info = await upload_to_gdrive(item_path, gdrive_folder_id, task_ctx)
            if file_info:
                uploaded_files.append(file_info)
            else:
                failed_files.append(item)
                log.warning(f"{task_id_str} Failed to upload file: {item}")

        elif ospath.isdir(item_path):
            # Recursively upload subfolder
            subfolder_info = await upload_folder_to_gdrive(item_path, gdrive_folder_id, task_ctx)
            if subfolder_info:
                uploaded_files.extend(subfolder_info.get('files', []))
            else:
                failed_files.append(item)
                log.warning(f"{task_id_str} Failed to upload subfolder: {item}")

    log.info(f"{task_id_str} Folder upload complete: {folder_name} - {len(uploaded_files)} files uploaded, {len(failed_files)} failed")

    return {
        'folder_id': gdrive_folder_id,
        'folder_name': folder_name,
        'files': uploaded_files,
        'failed': failed_files
    }


async def GDrive_Upload(path: str, cleanup: bool = False, task_ctx: TaskContext = None):
    """
    Main Google Drive upload handler (similar to Leech for Telegram).

    Args:
        path: Directory or file path to upload
        cleanup: Whether to remove source after upload
        task_ctx: Optional TaskContext for multi-task support
    """
    global log, BOT, Paths, Messages, TaskError, TRANSFER, MSG, Gdrive

    # Multi-task support: Use task_ctx if provided, otherwise fallback to globals
    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        _transfer = task_ctx.transfer
        _msg = task_ctx.msg
        log.info(f"GDrive_Upload using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _msg = MSG
        log.info("GDrive_Upload using global state (single-task mode)")

    # Check if Google Drive service is available
    if not Gdrive.service:
        log.error("GDrive_Upload Error: Google Drive service not initialized")
        _task_error.state = True
        _task_error.text = "Google Drive authentication failed. Token.pickle not found or invalid."
        return

    if not ospath.exists(path):
        log.error(f"GDrive_Upload Error: Source path does not exist: {path}")
        _task_error.state = True
        _task_error.text = "GDrive upload source path missing."
        return

    log.info(f"GDrive_Upload: Handler started for path: {path}")
    files_processed_count = 0
    files_failed_count = 0
    uploaded_links = []

    try:
        if ospath.isfile(path):
            # Upload single file
            log.info(f"GDrive_Upload: Uploading single file: {ospath.basename(path)}")
            file_info = await upload_to_gdrive(path, None, task_ctx)

            if file_info:
                files_processed_count += 1
                uploaded_links.append({
                    'name': file_info['name'],
                    'link': file_info['webViewLink'],
                    'size': file_info['size']
                })
                log.info(f"GDrive_Upload: Successfully uploaded file: {file_info['name']}")
            else:
                files_failed_count += 1
                log.error(f"GDrive_Upload: Failed to upload file: {ospath.basename(path)}")
                if not _task_error.state:
                    _task_error.state = True
                    _task_error.text = f"Failed to upload {ospath.basename(path)}"

        elif ospath.isdir(path):
            # Upload folder
            log.info(f"GDrive_Upload: Uploading folder: {ospath.basename(path)}")
            folder_info = await upload_folder_to_gdrive(path, None, task_ctx)

            if folder_info:
                files_processed_count = len(folder_info.get('files', []))
                files_failed_count = len(folder_info.get('failed', []))

                # Store uploaded file links
                for file_data in folder_info.get('files', []):
                    uploaded_links.append({
                        'name': file_data['name'],
                        'link': file_data['webViewLink'],
                        'size': file_data['size']
                    })

                log.info(f"GDrive_Upload: Folder upload complete - {files_processed_count} files uploaded, {files_failed_count} failed")

                if files_failed_count > 0:
                    log.warning(f"GDrive_Upload: Some files failed to upload in folder: {ospath.basename(path)}")
                    if not _task_error.state:
                        _task_error.state = True
                        _task_error.text = f"{files_failed_count} file(s) failed to upload"
            else:
                files_failed_count += 1
                log.error(f"GDrive_Upload: Failed to upload folder: {ospath.basename(path)}")
                if not _task_error.state:
                    _task_error.state = True
                    _task_error.text = f"Failed to upload folder {ospath.basename(path)}"
        else:
            log.error(f"GDrive_Upload: Path is neither file nor directory: {path}")
            _task_error.state = True
            _task_error.text = "Invalid upload source type"
            return

        # Store uploaded links in messages for SendLogs
        if uploaded_links:
            _messages.uploaded_links = uploaded_links

        log.info(f"GDrive_Upload: Handler finished - {files_processed_count} file(s) uploaded, {files_failed_count} failed")

    except Exception as e:
        log.error(f"GDrive_Upload: Unexpected error: {e}", exc_info=True)
        if _task_error and not _task_error.state:
            _task_error.state = True
            _task_error.text = f"GDrive upload error: {str(e)}"
        files_failed_count += 1

    finally:
        # Cleanup if requested
        if cleanup and ospath.exists(path):
            try:
                log.info(f"GDrive_Upload: Cleaning up source: {path}")
                if ospath.isfile(path):
                    os.remove(path)
                elif ospath.isdir(path):
                    shutil.rmtree(path, ignore_errors=True)
                log.info(f"GDrive_Upload: Cleanup complete")
            except Exception as cleanup_err:
                log.warning(f"GDrive_Upload: Cleanup failed: {cleanup_err}")
