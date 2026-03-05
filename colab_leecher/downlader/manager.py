# /content/Telegram-Leecher/colab_leecher/downlader/manager.py

import logging
import os
import time
import asyncio
import requests
import aiohttp
import re
import urllib.parse
from natsort import natsorted
from datetime import datetime
from asyncio import sleep, get_running_loop
from .mega import megadl
from ..utility.handler import cancelTask
from .terabox_enhanced import TeraBoxDownloader  # Enhanced TeraBox with cookie support & fallback
from .instagram import instagram_download, instagram_profile_download, is_profile_url
from .ytdl import YTDL_Status, get_YT_Name 
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from .aria2 import aria2_Download, get_Aria2c_Name 
from .telegram import TelegramDownload, media_Identifier 
from ..utility.variables import BOT, Gdrive, MSG, Messages, Aria2c, BotTimes, Paths, TRANSFER, TaskError
from ..utility.task_context import TaskContext  # NEW: Import for multi-task support
from ..utility.helper import (
    isYtdlComplete, keyboard, sysINFO, is_google_drive, is_mega, is_terabox,
    is_instagram, is_nzbcloud, is_ytdl_link, is_telegram, status_bar, getTime, sizeUnit, speedETA,
    clean_filename, extract_filename_from_url, apply_dot_style, is_torrent
)
from .gdrive import ( 
    build_service, g_DownLoad, get_Gfolder_size, getFileMetadata, getIDFromURL,
)


log = logging.getLogger(__name__)

async def http_download_logic(url: str, file_path: str, display_name: str, headers: dict, cookies: dict, link_num: int, total_links: int) -> bool: # Added return type hint
    """Downloads a file via HTTP/S, tracks success/failure, and updates status."""
    global BotTimes, Messages, MSG, TRANSFER, TaskError, Paths, log 
    download_start_time = time.time()
    padding = len(str(total_links))
    status_header = f"<b>Downloading</b> <i>Link {str(link_num).zfill(padding)}/{str(total_links).zfill(padding)}</i>\n\n<b>Name:</b> <code>{display_name}</code>\n"
    Messages.status_head = status_header 

    try:

        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Use aiohttp for non-blocking async HTTP requests
        # Increased timeouts for slow servers like downloadly.ir
        timeout = aiohttp.ClientTimeout(total=None, connect=180, sock_read=600)
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url, headers=headers, cookies=cookies, allow_redirects=True) as response:
                response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
                total_size = int(response.headers.get('content-length', 0))

                downloaded_size = 0
                block_size = 1024 * 1024 # 1MB chunk
                last_update_call = 0

                with open(file_path, "wb") as file:
                    async for chunk in response.content.iter_chunked(block_size):
                        # Check if task was cancelled externally
                        if TaskError and TaskError.state:
                            log.warning(f"Download cancelled externally for {display_name}")
                            try:
                               file.close()
                               if os.path.exists(file_path): os.remove(file_path)
                            except Exception as cleanup_err: log.warning(f"Could not cleanup incomplete file {file_path} on cancel: {cleanup_err}")
                            # Add failure reason for cancellation
                            failed_info = {"link": url, "index": link_num, "reason": "Cancelled by User/Error"}
                            if TaskError: TaskError.failed_links.append(failed_info)
                            return False # Indicate failure

                        if chunk:
                            file.write(chunk)
                            downloaded_size += len(chunk)
                            now = time.time()
                            # Update status bar periodically
                            if now - last_update_call > 2:
                                last_update_call = now
                                current_total_downloaded = sum(TRANSFER.down_bytes) + downloaded_size
                                approx_total_project_size = TRANSFER.total_down_size if TRANSFER.total_down_size > 0 else sum(TRANSFER.down_bytes) + total_size if total_size > 0 else sum(TRANSFER.down_bytes)

                                if total_size > 0 :
                                    speed_string, eta, percentage = speedETA(download_start_time, downloaded_size, total_size)
                                    await status_bar(Messages.status_head, speed_string, percentage, getTime(eta), sizeUnit(current_total_downloaded), sizeUnit(approx_total_project_size), "aiohttp 🌐")
                                else: # Handle unknown size
                                    speed = downloaded_size / (now - download_start_time) if (now - download_start_time) > 0 else 0
                                    await status_bar(Messages.status_head, f"{sizeUnit(speed)}/s", 0, "N/A", sizeUnit(current_total_downloaded), "Unknown", "aiohttp 🌐")

                # --- Download successful ---
                log.info(f"Download complete: {display_name}")
                TRANSFER.down_bytes.append(downloaded_size)
                # <<< ADD TO SUCCESSFUL DOWNLOADS >>>
                TRANSFER.successful_downloads.append({'url': url, 'filename': display_name})
                return True # <<< RETURN TRUE >>>

    # --- Handle specific errors ---
    except asyncio.TimeoutError: error_reason = "Timeout"
    except aiohttp.ClientConnectionError: error_reason = "Connection Error"
    except aiohttp.ClientResponseError as http_err: error_reason = f"HTTP Error: {http_err.status} {http_err.message}"
    except aiohttp.ClientError as client_err: error_reason = f"Client Error: {str(client_err)[:100]}"
    except Exception as e: error_reason = f"Unexpected Error: {str(e)[:100]}"; log.error(f"Unexpected error downloading {display_name} (Link {link_num}): {e}", exc_info=True)

    # --- Common failure handling ---
    log.error(f"Download failed for {display_name} (Link {link_num}): {error_reason}")
    # <<< ADD TO FAILED LINKS >>>
    failed_info = {"link": url, "filename": display_name, "index": link_num, "reason": error_reason}
    if TaskError: TaskError.failed_links.append(failed_info)
    # Clean up potentially partially downloaded file
    try:
        # Check if file exists before removing
        if 'file' in locals() and not file.closed: file.close() # Ensure file is closed
        if os.path.exists(file_path): os.remove(file_path)
    except Exception as cleanup_err: log.warning(f"Could not cleanup failed download file {file_path}: {cleanup_err}")
    return False # <<< RETURN FALSE >>>


# --- Helper: Check if URL is from downloadly.ir ---
def is_downloadly(url: str) -> bool:
    """Check if URL is from downloadly.ir"""
    return 'downloadly.ir' in url.lower()


# --- Downloadly.ir Download with Proper Headers ---
async def downloadly_download(url: str, link_num: int, filename_hint: str = None, task_ctx: TaskContext = None) -> bool:
    """Downloads files from downloadly.ir with proper headers to bypass restrictions"""
    global Paths, Messages, TaskError, log

    # Multi-task support
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        log.info(f"downloadly_download() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        log.info("downloadly_download() using global state")

    # Extract filename from URL
    try:
        parsed_url = urllib.parse.urlparse(url)
        filename = filename_hint or parsed_url.path.split('/')[-1].split('?')[0]

        # Clean filename
        filename = clean_filename(filename)
        if not filename or filename == "":
            filename = "downloadly_file"

        filename = apply_dot_style(filename)

    except Exception as e:
        log.error(f"Failed to extract filename from downloadly.ir URL: {e}")
        filename = "downloadly_file.bin"

    # Set file path
    full_file_path = os.path.join(_paths.down_path, filename)

    # Downloadly.ir specific headers to bypass restrictions
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Referer': 'https://downloadly.ir/',
        'DNT': '1',
    }

    cookies = {}

    log.info(f"Starting downloadly.ir download: {filename}")

    # Use the existing http_download_logic with downloadly.ir headers
    success = await http_download_logic(
        url=url,
        file_path=full_file_path,
        display_name=filename,
        headers=headers,
        cookies=cookies,
        link_num=link_num,
        total_links=1
    )

    return success

# --- NZBCloud Downloader (Remains the same) ---
async def nzbcloud_download(urls: list, filenames: list, task_ctx: TaskContext = None):
    """Downloads files from NZBCloud using aria2c (faster and more reliable than aiohttp)."""

    # Check if the number of URLs matches the number of filenames
    if len(urls) != len(filenames):
        log.error(f"NZBCloud Error: Mismatch between URL count ({len(urls)}) and filename count ({len(filenames)}).")
        await cancelTask(f"NZBCloud Error: Mismatch URLs/FNs.", task_ctx)
        return False # Indicate failure

    total_links = len(urls)
    all_success = True # Assume success initially

    # Iterate through each URL and filename pair
    for i, (url, file_name) in enumerate(zip(urls, filenames)):
        url = url.strip()
        file_name = file_name.strip()

        # Skip if URL or filename is empty after stripping
        if not url or not file_name:
            log.warning(f"Skipping NZBCloud item {i+1}/{total_links}: Missing URL or Filename.")
            failed_info = {"link": url or "N/A", "filename": file_name or "N/A", "index": i + 1, "reason": "Missing URL/Filename"}
            if TaskError: TaskError.failed_links.append(failed_info)
            all_success = False # Mark as failed
            continue # Move to the next file

        log.info(f"Starting NZBCloud download {i+1}/{total_links}: '{file_name}' via aria2c")

        # Use aria2_Download instead of http_download_logic
        # aria2c has proper NZBCloud cookie handling, parallel connections, and retry logic
        success = await aria2_Download(
            link=url,
            num=i + 1,
            pre_determined_name=file_name,  # Pass the TITLE= filename
            task_ctx=task_ctx
        )

        # Log if the download function reported failure
        if not success:
            log.error(f"NZBCloud download failed for '{file_name}'. Check logs for details from aria2_Download.")
            all_success = False # Mark overall batch as having failures

    # Return the overall success status of the batch
    return all_success


# --- Debrid Downloader ---
# Replace the ENTIRE Debrid_download function in colab_leecher/downlader/manager.py

async def Debrid_download(urls: list, batch_filenames: list) -> bool: # Accepts batch_filenames
    global BOT, Paths, Messages, log, TaskError, TRANSFER # Ensure TRANSFER is global

    service_name = "Debrid" # For logs/errors
    log.info(f"{service_name}: Preparing download for batch.")
    # Define headers needed for Debrid (likely just User-Agent)
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = {} # No specific cookies known for Debrid

    expected_count = len(urls)
    filenames_provided_count = len(batch_filenames) if batch_filenames is not None else -1 # Use -1 to signify None

    log.info(f"{service_name}: Filenames list provided for batch (Count: {filenames_provided_count}). Expected links: {expected_count}")

    # --- REVISED CHECK ---
    if batch_filenames is None:
        log.error(f"{service_name} Error: Filename list for batch is missing (None). This indicates an upstream issue.")
        await cancelTask(f"{service_name} Error: Internal filename list missing for batch.")
        return False
    elif filenames_provided_count != expected_count:
        log.error(f"{service_name} Error: Batch filename count ({filenames_provided_count}) doesn't match batch link count ({expected_count}).")
        await cancelTask(f"{service_name} Error: Batch filename/link count mismatch ({filenames_provided_count} vs {expected_count}).")
        return False
    else:
        # List is provided and length matches, proceed
        filenames = batch_filenames # Use the passed list
        log.info(f"{service_name}: Proceeding with {len(filenames)} filenames for this batch.")
    # --- END REVISED CHECK ---

    # --- Download loop ---
    all_success = True
    for i, url in enumerate(urls):
        # Basic index check
        if i >= len(filenames):
            log.error(f"{service_name} Error: Index out of bounds accessing filename for batch link {i+1}.")
            all_success = False; break

        url = url.strip()
        file_name = filenames[i].strip() # Get corresponding filename from the batch list

        if not url or not file_name:
            log.warning(f"Skipping {service_name} item {i+1}. Missing URL or Filename in batch.")
            all_success = False
            failed_info = {"link": url or "N/A", "filename": file_name or "N/A", "index": "Batch-" + str(i + 1), "reason": "Missing URL/Filename"}
            if TaskError: TaskError.failed_links.append(failed_info)
            continue

        full_file_path = os.path.join(Paths.down_path, file_name)
        log.info(f"Starting {service_name} download {i+1}/{expected_count} (Batch): '{file_name}'")

        # Call http_download_logic, which now returns True/False and handles success/failure logging
        success = await http_download_logic(url, full_file_path, file_name, headers, cookies, i + 1, expected_count)

        if not success:
            log.error(f"{service_name} download failed for '{file_name}'. Details should be in TaskError.")
            all_success = False
            # No need to add to TaskError.failed_links here, http_download_logic does it

    return all_success

# --- Bitso Downloader ---
# Make sure necessary imports like BOT, Paths, log, cancelTask, http_download_logic are present
async def bitso_download(urls: list, batch_filenames: list) -> bool: # Accepts batch_filenames
    global BOT, Paths, Messages, log, TaskError, TRANSFER # Ensure TRANSFER is global

    service_name = "Bitso" # For logs/errors
    log.info(f"{service_name}: Preparing download for batch.")
    # Define headers and cookies needed for Bitso
    id_cookie = BOT.Setting.bitso_identity_cookie
    sess_cookie = BOT.Setting.bitso_phpsessid_cookie
    cookies = {}
    headers = {"Referer": "https://panel.bitso.ir/", "User-Agent": "Mozilla/5.0"}
    if id_cookie: cookies["_identity"] = id_cookie
    if sess_cookie: cookies["PHPSESSID"] = sess_cookie

    expected_count = len(urls)
    filenames_provided_count = len(batch_filenames) if batch_filenames is not None else -1 # Use -1 to signify None

    log.info(f"{service_name}: Filenames list provided for batch (Count: {filenames_provided_count}). Expected links: {expected_count}")

    # --- REVISED CHECK ---
    if batch_filenames is None:
        log.error(f"{service_name} Error: Filename list for batch is missing (None). This indicates an upstream issue.")
        await cancelTask(f"{service_name} Error: Internal filename list missing for batch.")
        return False
    elif filenames_provided_count != expected_count:
        log.error(f"{service_name} Error: Batch filename count ({filenames_provided_count}) doesn't match batch link count ({expected_count}).")
        await cancelTask(f"{service_name} Error: Batch filename/link count mismatch ({filenames_provided_count} vs {expected_count}).")
        return False
    else:
        # List is provided and length matches, proceed
        filenames = batch_filenames # Use the passed list
        log.info(f"{service_name}: Proceeding with {len(filenames)} filenames for this batch.")
    # --- END REVISED CHECK ---

    # --- Download loop ---
    all_success = True
    for i, url in enumerate(urls):
        # Basic index check
        if i >= len(filenames):
            log.error(f"{service_name} Error: Index out of bounds accessing filename for batch link {i+1}.")
            all_success = False; break

        url = url.strip()
        file_name = filenames[i].strip() # Get corresponding filename from the batch list

        if not url or not file_name:
            log.warning(f"Skipping {service_name} item {i+1}. Missing URL or Filename in batch.")
            all_success = False
            failed_info = {"link": url or "N/A", "filename": file_name or "N/A", "index": "Batch-" + str(i + 1), "reason": "Missing URL/Filename"}
            if TaskError: TaskError.failed_links.append(failed_info)
            continue

        full_file_path = os.path.join(Paths.down_path, file_name)
        log.info(f"Starting {service_name} download {i+1}/{expected_count} (Batch): '{file_name}'")

        # Call http_download_logic, which now returns True/False and handles success/failure logging
        success = await http_download_logic(url, full_file_path, file_name, headers, cookies, i + 1, expected_count)

        if not success:
            log.error(f"{service_name} download failed for '{file_name}'. Details should be in TaskError.")
            all_success = False
            # No need to add to TaskError.failed_links here, http_download_logic does it

    return all_success
# --- Download Manager: Refactored Routing ---
# Replace the ENTIRE downloadManager function in colab_leecher/downlader/manager.py

# Replace downloadManager in colab_leecher/downlader/manager.py

# Replace downloadManager in colab_leecher/downlader/manager.py
# Ensure necessary imports: log, BOT, TaskError, Paths, os, datetime, etc.
# Ensure specific download functions (Debrid_download, bitso_download, etc.) are imported

async def downloadManager(source: list, is_ytdl: bool, batch_filenames: list = None, task_ctx: TaskContext = None): # Accepts batch_filenames
    """Main download router that dispatches to service-specific downloaders.

    Args:
        source: List of download links
        is_ytdl: Whether this is a YouTube-DL download
        batch_filenames: Optional list of filenames for batch downloads
        task_ctx: Optional TaskContext for multi-task support
    """
    global TRANSFER, BOT, TaskError, MSG, log, BotTimes, Paths, Messages # Ensure BotTimes is accessible if needed

    # Multi-task support: Use task_ctx if provided, otherwise fallback to globals
    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        _transfer = task_ctx.transfer
        log.info(f"downloadManager() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        log.info("downloadManager() using global state (single-task mode)")

    selected_service = _bot.Options.service_type
    provided_filenames_count = len(batch_filenames) if isinstance(batch_filenames, list) else 0
    log.info(f"Download Manager received task. Service: '{selected_service}', Sources: {len(source)}, Filenames received for batch: {provided_filenames_count}")

    batch_had_failures = False
    os.makedirs(_paths.down_path, exist_ok=True)
    # BotTimes.task_start = datetime.now() # This should be set once when the overall task starts

    # --- Route based on explicit service_type first ---
    if selected_service in ["nzbcloud", "Debrid", "bitso"]:
        batch_success = False
        if selected_service == "nzbcloud":
             log.info("Routing task to nzbcloud_download function...")
             batch_success = await nzbcloud_download(source, batch_filenames, task_ctx)
        elif selected_service == "Debrid":
             batch_success = await Debrid_download(source, batch_filenames)
        elif selected_service == "bitso":
             batch_success = await bitso_download(source, batch_filenames)

        if not batch_success: batch_had_failures = True

    elif selected_service == "downloadly":
        # Downloadly.ir download with special headers
        log.info("Routing task to downloadly_download function...")
        for i, link in enumerate(source, 1):
            filename_hint = _messages.download_name if _messages.download_name else None
            link_success = await downloadly_download(link, i, filename_hint, task_ctx)
            if not link_success:
                batch_had_failures = True

    elif selected_service == "ytdl":
        # Assuming YTDL_Status handles errors internally by setting TaskError
        log.warning("YTDL download batch success/failure tracking might need review.")
        if not source: _task_error.state = True; _task_error.text = "No YTDL links provided."; return
        for i, link in enumerate(source):
            log.info(f"Starting YTDL status monitoring for link {i+1}/{len(source)}")
            await YTDL_Status(link, i + 1, task_ctx=task_ctx)
            if _task_error and _task_error.state:
                 log.error(f"YTDL processing failed for link {i+1}.")
                 failed_info = {"link": link, "filename": "YTDL Download", "index": i + 1, "reason": _task_error.text or "YTDL Failed"}
                 _task_error.failed_links.append(failed_info)
                 batch_had_failures = True
                 # Reset error for next link? Decide based on desired behavior
                 _task_error.state = False; _task_error.text = ""
        # No explicit success return needed, relies on TaskError state check by caller

    # --- Corrected Auto-Detect Logic ---
    elif selected_service == "direct" or selected_service is None:
         log.info("Service is 'direct' or unspecified, attempting auto-detection...")
         total_links = len(source)
         temp_failed_links_batch = [] # Track failures within this block

         for i, link in enumerate(source):
             # --- ADDED ACTUAL DOWNLOAD CALLS AND CHECKS ---
             link_success = False
             link_error_reason = "Unknown download error"
             # Use filename passed if available (unlikely in direct mode unless pre-extracted)
             # Fallback filename for error reporting
             intended_filename_for_error = f"Direct_Link_{i+1}"
             if isinstance(batch_filenames, list) and i < len(batch_filenames) and batch_filenames[i]:
                  intended_filename_for_error = batch_filenames[i]

             try:
                 log.info(f"Auto-detect: Processing link {i+1}/{total_links}: {link[:100]}...")
                 # Check link types and call appropriate downloader
                 # ASSUMPTION: All these downloaders return True on success, False on failure
                 # AND they append to TaskError.failed_links internally on failure.
                 if is_google_drive(link):
                     log.debug("Detected GDrive Link")
                     link_success = await g_DownLoad(link, i + 1, task_ctx) # Pass task_ctx (Phase 2.4)
                 elif is_telegram(link):
                     log.debug("Detected Telegram Link")
                     link_success = await TelegramDownload(link, i + 1, task_ctx) # Pass task_ctx (Phase 2.3)
                 elif is_mega(link):
                     log.debug("Detected Mega Link")
                     link_success = await megadl(link, i + 1, task_ctx) # Pass task_ctx (may not support yet)
                 elif is_terabox(link):
                      log.debug("Detected Terabox Link")
                      # Use enhanced TeraBox downloader with cookie support & fallback
                      terabox_downloader = TeraBoxDownloader(client=None, message=None, task_ctx=task_ctx)
                      link_success = await terabox_downloader.download(link, i + 1)
                 elif is_instagram(link):
                      log.debug("Detected Instagram Link")
                      # Check if it's a profile URL or individual post
                      if is_profile_url(link):
                          log.info("Detected Instagram Profile URL - downloading all posts")
                          link_success = await instagram_profile_download(link, i + 1, max_posts=9999)  # No practical limit
                      else:
                          log.info("Detected Instagram Post/Reel URL")
                          link_success = await instagram_download(link, i + 1)
                 elif is_ytdl_link(link):
                      log.debug("Detected YTDL-compatible link (YouTube, etc.)")
                      await YTDL_Status(link, i + 1, task_ctx=task_ctx)
                      # Check if YTDL set error state
                      link_success = not (_task_error and _task_error.state)
                      if not link_success and _task_error:
                          # YTDL_Status should handle error reporting via cancelTask or TaskError
                          log.warning(f"YTDL download failed for link {i+1}")
                 elif is_torrent(link): # Added torrent check
                      log.debug("Detected Torrent/Magnet link, using Aria2c")
                      link_success = await aria2_Download(link, i + 1, intended_filename_for_error, task_ctx)
                 else: # Default to Aria2c for other direct links
                      log.debug("Detected generic link, using Aria2c as default")
                      # <<< PASS THE GUESSED NAME FROM Messages >>>
                      filename_hint = _messages.download_name if _messages.download_name else None
                      link_success = await aria2_Download(link, i + 1, filename_hint, task_ctx) # Pass filename_hint and task_ctx
                      

                 # Check success status after call
                 if not link_success:
                      log.warning(f"Auto-detect: Download function reported failure for link {i+1}. Check TaskError details.")
                      # Failure details should have been added by the specific download function

             except Exception as Error:
                  # Catch unexpected errors during the call itself
                  link_error_reason = f"Unhandled DL Error: {str(Error)[:100]}"
                  log.error(f"Auto-detect Download Error (Link {i+1}/{total_links}): {Error}", exc_info=True);
                  link_success = False
                  # Add failure details for unhandled exceptions
                  failed_info = {"link": link, "filename": intended_filename_for_error, "index": i + 1, "reason": link_error_reason}
                  temp_failed_links_batch.append(failed_info)
                  # Set global error state here? Or rely on batch_had_failures? Let's rely on batch_had_failures.

             # Update overall batch failure status
             if not link_success:
                 batch_had_failures = True
             # --- END ACTUAL DOWNLOAD CALLS ---

         # Add any locally tracked failures (from generic exceptions) to the main list
         if _task_error and temp_failed_links_batch:
              _task_error.failed_links.extend(temp_failed_links_batch)
         # --- End Corrected Auto-Detect Logic ---

    else: # Unsupported service
         log.error(f"Unsupported service type selected: '{selected_service}'")
         if _task_error: _task_error.state = True; _task_error.text = f"Unsupported service type: {selected_service}"
         batch_had_failures = True

    # Set TaskError state if *any* download in this batch failed
    if batch_had_failures:
        log.warning("Download manager finished batch, and one or more downloads failed.")
        if _task_error and not _task_error.state: # Set general state if not set by specific error
            _task_error.state = True
            _task_error.text = "One or more downloads failed/skipped in batch."
    else:
        log.info("Download manager finished batch successfully.")

    # downloadManager doesn't return status, Do_Leech/Do_Mirror check TaskError state
# --- End of fnction ---
# --- Size Calculator (Uses TRANSFER instance - needs update) ---
async def calDownSize(sources, task_ctx: TaskContext = None):
    """Calculates total download size for GDrive and Telegram sources.

    Args:
        sources: List of download links
        task_ctx: Optional TaskContext for multi-task support
    """
    global TRANSFER, Gdrive # Use instance

    # Multi-task support: Use task_ctx if provided, otherwise fallback to globals
    if task_ctx:
        _transfer = task_ctx.transfer
        log.info(f"calDownSize() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _transfer = TRANSFER
        log.info("calDownSize() using global state (single-task mode)")

    log.info("Calculating download size (GDrive/TG only)..."); applicable_sources = [s for s in sources if is_google_drive(s) or is_telegram(s)]; total_calculated_size = 0
    if not applicable_sources: log.info("No GDrive/TG links for size pre-calc."); _transfer.total_down_size = 0; return # Use instance
    for link in natsorted(applicable_sources):
        try:
            if is_google_drive(link):
                await build_service();
                if not Gdrive.service: log.warning("GDrive service unavailable."); continue
                id = await getIDFromURL(link);
                if not id: continue # Skip if ID extraction failed
                meta = await getFileMetadata(id)
                if not meta: continue # Skip if metadata failed
                if meta.get("mimeType") == "application/vnd.google-apps.folder": size = await get_Gfolder_size(id); total_calculated_size += size if size != -1 else 0 # Await recursive call
                elif meta.get("size"): total_calculated_size += int(meta["size"])
            elif is_telegram(link):
                media, _ = await media_Identifier(link)
                if media and hasattr(media, 'file_size') and media.file_size: total_calculated_size += media.file_size
                else: log.warning(f"Could not get size for TG link: {link}")
        except Exception as e: log.error(f"Error calculating size for {link}: {e}", exc_info=False)
    _transfer.total_down_size = total_calculated_size; log.info(f"Total pre-calculated size: {sizeUnit(_transfer.total_down_size)}") # Use instance

# --- Initial Name Guesser (Remains the same) ---
# Make sure this function is defined as async
async def get_d_name(link: str, task_ctx: TaskContext = None):
    """Attempts to extract/guess initial download name from link.

    Args:
        link: Download link to extract name from
        task_ctx: Optional TaskContext for multi-task support
    """
    global Messages, Gdrive, log # Ensure globals needed are declared

    # Multi-task support: Use task_ctx if provided, otherwise fallback to globals
    if task_ctx:
        _messages = task_ctx.messages
        log.info(f"get_d_name() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _messages = Messages
        log.info("get_d_name() using global state (single-task mode)")

    name = None
    log.info(f"Attempting initial name guess for link: {link[:100]}...")
    try:
        # ===== PRIORITY 1: Check for TITLE= filename from bot.Options.filenames (NZBCloud format) =====
        if task_ctx and hasattr(task_ctx, 'bot') and hasattr(task_ctx.bot, 'Options'):
            if hasattr(task_ctx.bot.Options, 'filenames') and task_ctx.bot.Options.filenames:
                # Get the first filename (for single-link tasks)
                if len(task_ctx.bot.Options.filenames) > 0:
                    title_filename = task_ctx.bot.Options.filenames[0]
                    if title_filename:
                        name = title_filename
                        log.info(f"✅ Using TITLE= filename from bot.Options: {name}")

        # ===== FALLBACK: Extract from URL if no TITLE= filename found =====
        if not name:
            name = await extract_filename_from_url(link)

    except Exception as e:
        log.warning(f"Could not guess initial name for {link[:100]}: {e}")

    # Update Messages.download_name if a name was found
    if name:
        _messages.download_name = name
        log.info(f"Initial guessed name set to: {name}")
    else:
        _messages.download_name = None # Set to None if no name found
        log.info(f"Initial guessed name set to: None")

    # This function doesn't need to return anything if it just updates Messages.download_name
