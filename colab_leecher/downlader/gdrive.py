# /content/Telegram-Leecher/colab_leecher/downlader/gdrive.py
# Uses TRANSFER instance

import io
import logging
import pickle
import asyncio
import os
from pathlib import Path
from natsort import natsorted
from re import search as re_search
from os import path as ospath
from urllib.parse import parse_qs, urlparse
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload
from ..utility.handler import cancelTask, TaskContext # Relative
from ..utility.helper import sizeUnit, getTime, speedETA, status_bar, clean_filename # Relative, added clean_filename
# --- MODIFICATION: Import TRANSFER instance ---
from ..utility.variables import Gdrive, Messages, Paths, BotTimes, TRANSFER, TaskError # Import TRANSFER instance
# from ..utility.transfer_state import Transfer # Remove class import
# --- END MODIFICATION ---

# Setup logger
log = logging.getLogger(__name__)


def _load_pickled_credentials(token_path: str):
    token_file = Path(token_path)
    if token_file.suffix.lower() != ".pickle":
        raise ValueError(f"Unsupported token format: {token_file.name}")
    if token_file.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Token file is unexpectedly large")
    with token_file.open("rb") as token:
        # token.pickle is a local trusted artifact provided by the operator.
        return pickle.load(token)  # nosec


async def build_service(task_ctx: TaskContext = None):
    """Initializes the Google Drive API service."""
    global Gdrive, Paths
    if not ospath.exists(Paths.access_token):
        log.error(f"Token file not found: {Paths.access_token}")
        Gdrive.service = None
        await cancelTask("token.pickle NOT FOUND!", task_ctx)
        return

    try:
        creds = _load_pickled_credentials(Paths.access_token)
        Gdrive.service = build("drive", "v3", credentials=creds)
        log.info("GDrive service built.")
    except Exception as e:
        log.error(f"Failed build GDrive service: {e}", exc_info=True)
        Gdrive.service = None
        await cancelTask(f"GDrive Error: {e}", task_ctx)


async def g_DownLoad(link, num, task_ctx: TaskContext = None):
    """Downloads a Google Drive file or folder."""
    global Messages, Paths, BotTimes, Gdrive
    
    # Use task_ctx if provided
    if task_ctx:
        _messages = task_ctx.messages
        _paths = task_ctx.paths
    else:
        _messages = Messages
        _paths = Paths

    if not Gdrive.service: 
        log.error("GDrive service not init.")
        await cancelTask("GDrive Service Error.", task_ctx)
        return
        
    display_name = _messages.download_name if _messages.download_name else "GDrive Download"
    status_header = f"<b>Google Drive Download</b> <i>Link {str(num).zfill(2)}</i>\n\n<b>Name:</b> <code>{display_name}</code>\n"
    
    try:
        file_id = await getIDFromURL(link, task_ctx)
        if not file_id: return
        meta = await getFileMetadata(file_id, task_ctx)
        if not meta: return
        
        os.makedirs(_paths.down_path, exist_ok=True)
        if meta.get("mimeType") == "application/vnd.google-apps.folder":
            log.info(f"GDrive Folder: {meta.get('name')}")
            _messages.status_head = f"<b>Google Drive Folder</b>\n\n<b>Folder:</b> <code>{meta.get('name', file_id)}</code>\n"
            await gDownloadFolder(file_id, _paths.down_path, task_ctx)
        else:
            log.info(f"GDrive File: {meta.get('name')}")
            _messages.status_head = status_header
            await gDownloadFile(file_id, _paths.down_path, task_ctx)
    except Exception as e: 
        log.error(f"Unexpected GDrive download error: {e}", exc_info=True)
        await cancelTask(f"GDrive Error: {e}", task_ctx)


async def getIDFromURL(link: str, task_ctx: TaskContext = None):
    """Extracts the Google Drive file/folder ID from a URL."""
    try:
        gdrive_id = None
        if "folders/" in link or "file/d/" in link: 
            res = re_search(r"/(?:folders|file/d)/([-\w]+)", link)
            if res: gdrive_id = res.group(1)
        
        if not gdrive_id: 
            parsed = urlparse(link)
            gdrive_id = parse_qs(parsed.query).get("id",[None])[0]
            
        if gdrive_id: 
            log.debug(f"Extracted GDrive ID: {gdrive_id}")
            return gdrive_id
            
        log.error(f"Could not extract GDrive ID: {link}")
        await cancelTask("G-Drive ID not found.", task_ctx)
        return None
    except Exception as e: 
        log.error(f"Error parsing GDrive URL {link}: {e}")
        await cancelTask("Error parsing GDrive URL.", task_ctx)
        return None


async def getFileMetadata(file_id, task_ctx: TaskContext = None):
    """Retrieves file metadata using the Drive API."""
    global Gdrive
    if not Gdrive.service: 
        log.error("GDrive service not available for metadata.")
        return None
        
    try:
        loop = asyncio.get_running_loop()
        meta = await loop.run_in_executor(None, lambda: Gdrive.service.files().get(fileId=file_id, supportsAllDrives=True, fields="name, id, mimeType, size, teamDriveId, driveId").execute())
        log.debug(f"GDrive Metadata for ID {file_id}: {meta}")
        return meta
    except HttpError as error:
        log.error(f"GDrive API error getting metadata for {file_id}: {error}", exc_info=True)
        error_reason = f"API Error: {error.resp.status} {error.reason}"
        if error.resp.status == 404: 
            error_reason = "File/Folder not found/permission denied."
        elif error.resp.status == 403: 
            error_reason = "Permission denied."
        await cancelTask(f"GDrive Metadata Error: {error_reason}", task_ctx)
        return None
    except Exception as e: 
        log.error(f"Unexpected error getting metadata for {file_id}: {e}", exc_info=True)
        await cancelTask(f"Unexpected GDrive Metadata Error: {e}", task_ctx)
        return None


async def get_Gfolder_size(folder_id):
    """Recursively calculates the total size of a Google Drive folder."""
    global Gdrive
    if not Gdrive.service: 
        log.error("GDrive service unavailable for folder size.")
        return -1
        
    total_size = 0
    page_token = None
    try:
        while True:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, lambda: Gdrive.service.files().list(q=f"'{folder_id}' in parents and trashed = false", spaces='drive', fields='nextPageToken, files(id, name, mimeType, size)', pageToken=page_token, supportsAllDrives=True, includeItemsFromAllDrives=True, pageSize=1000).execute())
            items = response.get('files', [])
            for item in items:
                if item['mimeType'] == 'application/vnd.google-apps.folder': 
                    subfolder_size = await get_Gfolder_size(item['id'])
                    total_size += subfolder_size if subfolder_size != -1 else 0
                elif item.get('size'): 
                    total_size += int(item['size'])
            page_token = response.get('nextPageToken', None)
            if page_token is None: break
        return total_size
    except HttpError as error: 
        log.error(f"GDrive API error getting folder size {folder_id}: {error}", exc_info=False)
        return -1
    except Exception as e: 
        log.error(f"Unexpected error getting folder size {folder_id}: {e}", exc_info=True)
        return -1


async def gDownloadFile(file_id, path, task_ctx: TaskContext = None) -> bool:
    global TRANSFER, BotTimes, Messages, Paths, MSG, Gdrive, TaskError
    
    if task_ctx:
        _transfer = task_ctx.transfer
        _bot_times = task_ctx.bot_times
        _messages = task_ctx.messages
        _paths = task_ctx.paths
        _task_error = task_ctx.error
    else:
        _transfer = TRANSFER
        _bot_times = BotTimes
        _messages = Messages
        _paths = Paths
        _task_error = TaskError

    if not Gdrive.service: 
        log.error("GDrive service not available.")
        return False
        
    file_path = None
    file_name = f"gdrive_{file_id}"
    success = False
    
    try:
        file_meta = await getFileMetadata(file_id, task_ctx)
        if not file_meta: return False
        
        if file_meta["mimeType"].startswith("application/vnd.google-apps"):
             err = f"Cannot download GDocs ({file_meta.get('name')}). Export first."
             log.error(err)
             failed_info = {"link": f"drive_id:{file_id}", "filename": file_meta.get('name', file_name), "index": "N/A", "reason": err}
             _task_error.failed_links.append(failed_info)
             return False

        file_name = clean_filename(file_meta.get("name", file_name))
        file_path = ospath.join(path, file_name)
        file_size = int(file_meta.get("size", 0))
        log.info(f"Starting GDrive file download: {file_name} (Size: {sizeUnit(file_size)}) to {file_path}")

        def _execute_download():
            try:
                request = Gdrive.service.files().get_media(fileId=file_id, supportsAllDrives=True)
                fh = io.FileIO(file_path, "wb")
                downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024 * 5)
                done = False
                while not done:
                    status, done = downloader.next_chunk()
                    if status:
                        downloaded_bytes = int(status.resumable_progress)
                        total_bytes = int(status.total_size)
                        asyncio.run_coroutine_threadsafe(_update_gdrive_progress(downloaded_bytes, total_bytes, task_ctx), asyncio.get_running_loop())
                fh.close()
                return ospath.getsize(file_path)
            except Exception as e:
                log.error(f"Error in _execute_download: {e}")
                if 'fh' in locals(): fh.close()
                return -1

        loop = asyncio.get_running_loop()
        final_downloaded_size = await loop.run_in_executor(None, _execute_download)

        if final_downloaded_size is not None and final_downloaded_size >= 0:
            size_to_add = final_downloaded_size if final_downloaded_size > 0 else file_size
            _transfer.down_bytes.append(size_to_add)
            log.info(f"GDrive file download complete: {file_name}")
            _transfer.successful_downloads.append({'url': f"drive_id:{file_id}", 'filename': file_name})
            success = True
        else:
             log.error(f"GDrive download finished {file_name} but size invalid/failed.")
             failed_info = {"link": f"drive_id:{file_id}", "filename": file_name, "index": "N/A", "reason": "Download finished with invalid size"}
             _task_error.failed_links.append(failed_info)
             if ospath.exists(file_path): os.remove(file_path)
             success = False

    except HttpError as error:
        err_reason = f"API Error {error.resp.status}"
        if "User Rate Limit Exceeded" in str(error): err_reason = "Download quota exceeded."
        elif "cannot download abusive content" in str(error).lower(): err_reason = "Content marked as abusive."
        elif error.resp.status == 403: err_reason = "Permission Denied."
        elif error.resp.status == 404: err_reason = "File Not Found."
        log.error(f"GDrive HttpError downloading file {file_id}: {error}", exc_info=False)
        failed_info = {"link": f"drive_id:{file_id}", "filename": file_name, "index": "N/A", "reason": f"GDrive HttpError: {err_reason}"}
        _task_error.failed_links.append(failed_info)
        if file_path and ospath.exists(file_path): os.remove(file_path)
        success = False
    except Exception as e:
        err_reason = f"Unexpected GDrive Error: {str(e)[:100]}"
        log.error(f"Unexpected error downloading GDrive file {file_id}: {e}", exc_info=True)
        failed_info = {"link": f"drive_id:{file_id}", "filename": file_name, "index": "N/A", "reason": err_reason}
        _task_error.failed_links.append(failed_info)
        if file_path and ospath.exists(file_path): os.remove(file_path)
        success = False

    return success


async def _update_gdrive_progress(downloaded, total, task_ctx: TaskContext = None):
    """Coroutine to update status bar from executor thread."""
    global TRANSFER, BotTimes, Messages
    
    if task_ctx:
        _transfer = task_ctx.transfer
        _bot_times = task_ctx.bot_times
        _messages = task_ctx.messages
    else:
        _transfer = TRANSFER
        _bot_times = BotTimes
        _messages = Messages

    start_time_for_eta = _bot_times.task_start
    current_overall = sum(_transfer.down_bytes) + downloaded
    display_total = _transfer.total_down_size if _transfer.total_down_size > 0 else total
    speed_string, eta, percentage = speedETA(start_time_for_eta, current_overall, display_total)
    
    await status_bar(
        down_msg=_messages.status_head,
        speed=speed_string,
        percentage=percentage,
        eta=getTime(eta),
        done=sizeUnit(current_overall),
        total_size=sizeUnit(display_total),
        engine="G-Api ♻️",
        task_ctx=task_ctx
    )


async def gDownloadFolder(folder_id, path, task_ctx: TaskContext = None):
    """Recursively downloads files within a Google Drive folder."""
    global Gdrive, Messages
    
    if task_ctx:
        _messages = task_ctx.messages
    else:
        _messages = Messages

    if not Gdrive.service: 
        log.error("GDrive service unavailable for folder download.")
        return
        
    try:
        folder_meta = await getFileMetadata(folder_id, task_ctx)
        if not folder_meta: return
        
        folder_name = clean_filename(folder_meta.get("name", f"gdrive_folder_{folder_id}"))
        current_path = ospath.join(path, folder_name)
        os.makedirs(current_path, exist_ok=True)
        log.info(f"Entering GDrive folder: {folder_name}")

        def _execute_list(token): 
            return Gdrive.service.files().list(q=f"'{folder_id}' in parents and trashed = false", spaces='drive', fields='nextPageToken, files(id, name, mimeType)', pageToken=token, supportsAllDrives=True, includeItemsFromAllDrives=True, orderBy="folder, name", pageSize=200).execute()

        page_token = None
        while True:
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, _execute_list, page_token)
            items = response.get('files', [])
            
            folders = [item for item in items if item['mimeType'] == 'application/vnd.google-apps.folder']
            files = [item for item in items if item['mimeType'] != 'application/vnd.google-apps.folder']
            
            for item in folders: 
                await gDownloadFolder(item['id'], current_path, task_ctx)
                
            for item in files:
                file_display_name = clean_filename(item.get("name", item['id']))
                _messages.status_head = f"<b>📥 GDRIVE FILE » </b>\n\n<b>Folder »</b> <code>.../{folder_name}</code>\n<b>File »</b> <code>{file_display_name}</code>\n"
                await gDownloadFile(item['id'], current_path, task_ctx)
                
            page_token = response.get('nextPageToken', None)
            if page_token is None: break
    except Exception as e: 
        log.error(f"Error processing GDrive folder {folder_id}: {e}", exc_info=True)
        await cancelTask(f"Error processing GDrive folder: {e}", task_ctx)
