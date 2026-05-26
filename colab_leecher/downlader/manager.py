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
from ..utility.handler import cancelTask, TaskContext
from .terabox_enhanced import TeraBoxDownloader  # Enhanced TeraBox with cookie support & fallback
from .instagram import instagram_download, instagram_profile_download, is_profile_url
from .ytdl import YTDL_Status, get_YT_Name 
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from .aria2 import aria2_Download, get_Aria2c_Name 
from .telegram import TelegramDownload, media_Identifier 
from ..utility.variables import BOT, Gdrive, MSG, Messages, Aria2c, BotTimes, Paths, TRANSFER, TaskError
from ..utility.helper import (
    isYtdlComplete, keyboard, sysINFO, is_google_drive, is_mega, is_terabox,
    is_instagram, is_nzbcloud, is_ytdl_link, is_telegram, status_bar, getTime, sizeUnit, speedETA,
    clean_filename, extract_filename_from_url, apply_dot_style, is_torrent
)
from .gdrive import ( 
    build_service, g_DownLoad, get_Gfolder_size, getFileMetadata, getIDFromURL,
)


log = logging.getLogger(__name__)

async def http_download_logic(url: str, file_path: str, display_name: str, headers: dict, cookies: dict, link_num: int, total_links: int, task_ctx: TaskContext = None) -> bool:
    """Downloads a file via HTTP/S, tracks success/failure, and updates status."""
    global BotTimes, Messages, MSG, TRANSFER, TaskError, Paths, log 

    if task_ctx:
        _bot_times = task_ctx.bot_times
        _messages = task_ctx.messages
        _transfer = task_ctx.transfer
        _task_error = task_ctx.error
        _paths = task_ctx.paths
    else:
        _bot_times = BotTimes
        _messages = Messages
        _transfer = TRANSFER
        _task_error = TaskError
        _paths = Paths

    download_start_time = time.time()
    padding = len(str(total_links))
    status_header = f"<b>Downloading</b> <i>Link {str(link_num).zfill(padding)}/{str(total_links).zfill(padding)}</i>\n\n<b>Name:</b> <code>{display_name}</code>\n"
    _messages.status_head = status_header 

    try:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        # Use aiohttp for non-blocking async HTTP requests
        timeout = aiohttp.ClientTimeout(total=None, connect=180, sock_read=600)
        connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300)
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.get(url, headers=headers, cookies=cookies, allow_redirects=True) as response:
                response.raise_for_status() 
                total_size = int(response.headers.get('content-length', 0))

                downloaded_size = 0
                block_size = 1024 * 1024 
                last_update_call = 0

                with open(file_path, "wb") as file:
                    async for chunk in response.content.iter_chunked(block_size):
                        if (_task_error and _task_error.state) or (task_ctx and task_ctx.cancel_event.is_set()):
                            log.warning(f"Download cancelled externally/actively for {display_name}")
                            try:
                               file.close()
                               if os.path.exists(file_path): os.remove(file_path)
                            except Exception as cleanup_err: log.warning(f"Could not cleanup incomplete file {file_path} on cancel: {cleanup_err}")
                            failed_info = {"link": url, "index": link_num, "reason": "Cancelled by User/Error"}
                            _task_error.failed_links.append(failed_info)
                            return False 

                        if chunk:
                            file.write(chunk)
                            downloaded_size += len(chunk)
                            now = time.time()
                            if now - last_update_call > 2:
                                last_update_call = now
                                current_total_downloaded = sum(_transfer.down_bytes) + downloaded_size
                                approx_total_project_size = _transfer.total_down_size if _transfer.total_down_size > 0 else sum(_transfer.down_bytes) + total_size if total_size > 0 else sum(_transfer.down_bytes)

                                if total_size > 0 :
                                    speed_string, eta, percentage = speedETA(download_start_time, downloaded_size, total_size)
                                    await status_bar(_messages.status_head, speed_string, percentage, getTime(eta), sizeUnit(current_total_downloaded), sizeUnit(approx_total_project_size), engine="aiohttp 🌐", task_ctx=task_ctx)
                                else: 
                                    speed = downloaded_size / (now - download_start_time) if (now - download_start_time) > 0 else 0
                                    await status_bar(_messages.status_head, f"{sizeUnit(speed)}/s", 0, "N/A", sizeUnit(current_total_downloaded), "Unknown", engine="aiohttp 🌐", task_ctx=task_ctx)

                log.info(f"Download complete: {display_name}")
                _transfer.down_bytes.append(downloaded_size)
                _transfer.successful_downloads.append({'url': url, 'filename': display_name})
                return True 

    except asyncio.TimeoutError: error_reason = "Timeout"
    except aiohttp.ClientConnectionError: error_reason = "Connection Error"
    except aiohttp.ClientResponseError as http_err: error_reason = f"HTTP Error: {http_err.status} {http_err.message}"
    except aiohttp.ClientError as client_err: error_reason = f"Client Error: {str(client_err)[:100]}"
    except Exception as e: error_reason = f"Unexpected Error: {str(e)[:100]}"; log.error(f"Unexpected error downloading {display_name} (Link {link_num}): {e}", exc_info=True)

    log.error(f"Download failed for {display_name} (Link {link_num}): {error_reason}")
    failed_info = {"link": url, "filename": display_name, "index": link_num, "reason": error_reason}
    if _task_error: _task_error.failed_links.append(failed_info)
    try:
        if 'file' in locals() and not file.closed: file.close()
        if os.path.exists(file_path): os.remove(file_path)
    except Exception as cleanup_err: log.warning(f"Could not cleanup failed download file {file_path}: {cleanup_err}")
    return False 


def is_downloadly(url: str) -> bool:
    """Check if URL is from downloadly.ir"""
    return 'downloadly.ir' in url.lower()


async def downloadly_download(url: str, link_num: int, filename_hint: str = None, task_ctx: TaskContext = None) -> bool:
    """Downloads files from downloadly.ir with proper headers to bypass restrictions"""
    global Paths, Messages, TaskError, log

    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error
        log.info(f"downloadly_download() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        log.info("downloadly_download() using global state")

    try:
        parsed_url = urllib.parse.urlparse(url)
        filename = filename_hint or parsed_url.path.split('/')[-1].split('?')[0]
        filename = clean_filename(filename)
        if not filename or filename == "":
            filename = "downloadly_file"
        filename = apply_dot_style(filename)
    except Exception as e:
        log.error(f"Failed to extract filename from downloadly.ir URL: {e}")
        filename = "downloadly_file.bin"

    full_file_path = os.path.join(_paths.down_path, filename)
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
    return await http_download_logic(url, full_file_path, filename, headers, cookies, link_num, 1, task_ctx)


async def nzbcloud_download(urls: list, filenames: list, task_ctx: TaskContext = None):
    """Downloads files from NZBCloud using aria2c."""
    if len(urls) != len(filenames):
        log.error(f"NZBCloud Error: Mismatch between URL count ({len(urls)}) and filename count ({len(filenames)}).")
        await cancelTask(f"NZBCloud Error: Mismatch URLs/FNs.", task_ctx)
        return False

    total_links = len(urls)
    all_success = True 
    for i, (url, file_name) in enumerate(zip(urls, filenames)):
        url = url.strip()
        file_name = file_name.strip()
        if not url or not file_name:
            log.warning(f"Skipping NZBCloud item {i+1}/{total_links}: Missing URL or Filename.")
            failed_info = {"link": url or "N/A", "filename": file_name or "N/A", "index": i + 1, "reason": "Missing URL/Filename"}
            if task_ctx: task_ctx.error.failed_links.append(failed_info)
            elif TaskError: TaskError.failed_links.append(failed_info)
            all_success = False 
            continue 

        log.info(f"Starting NZBCloud download {i+1}/{total_links}: '{file_name}' via aria2c")
        success = await aria2_Download(url, i + 1, file_name, task_ctx)
        if not success:
            log.error(f"NZBCloud download failed for '{file_name}'.")
            all_success = False 

    return all_success


async def Debrid_download(urls: list, batch_filenames: list, task_ctx: TaskContext = None) -> bool:
    global BOT, Paths, log, TaskError, TRANSFER

    if task_ctx:
        _paths = task_ctx.paths
        _task_error = task_ctx.error
    else:
        _paths = Paths
        _task_error = TaskError

    service_name = "Debrid"
    headers = {"User-Agent": "Mozilla/5.0"}
    cookies = {}

    expected_count = len(urls)
    filenames_provided_count = len(batch_filenames) if batch_filenames is not None else -1

    if batch_filenames is None:
        log.error(f"{service_name} Error: Filename list for batch is missing.")
        await cancelTask(f"{service_name} Error: Internal filename list missing for batch.", task_ctx)
        return False
    elif filenames_provided_count != expected_count:
        log.error(f"{service_name} Error: Batch filename count ({filenames_provided_count}) mismatch.")
        await cancelTask(f"{service_name} Error: Batch filename/link count mismatch.", task_ctx)
        return False

    all_success = True
    for i, url in enumerate(urls):
        url = url.strip()
        file_name = batch_filenames[i].strip()
        if not url or not file_name:
            all_success = False
            failed_info = {"link": url or "N/A", "filename": file_name or "N/A", "index": "Batch-" + str(i + 1), "reason": "Missing URL/Filename"}
            _task_error.failed_links.append(failed_info)
            continue

        full_file_path = os.path.join(_paths.down_path, file_name)
        success = await http_download_logic(url, full_file_path, file_name, headers, cookies, i + 1, expected_count, task_ctx)
        if not success: all_success = False

    return all_success


async def bitso_download(urls: list, batch_filenames: list, task_ctx: TaskContext = None) -> bool:
    global BOT, Paths, log, TaskError

    if task_ctx:
        _paths = task_ctx.paths
        _task_error = task_ctx.error
        _bot = task_ctx.bot
    else:
        _paths = Paths
        _task_error = TaskError
        _bot = BOT

    service_name = "Bitso"
    id_cookie = _bot.Setting.bitso_identity_cookie
    sess_cookie = _bot.Setting.bitso_phpsessid_cookie
    cookies = {}
    headers = {"Referer": "https://panel.bitso.ir/", "User-Agent": "Mozilla/5.0"}
    if id_cookie: cookies["_identity"] = id_cookie
    if sess_cookie: cookies["PHPSESSID"] = sess_cookie

    expected_count = len(urls)
    if batch_filenames is None:
        await cancelTask(f"{service_name} Error: Internal filename list missing for batch.", task_ctx)
        return False
    elif len(batch_filenames) != expected_count:
        await cancelTask(f"{service_name} Error: Batch filename/link count mismatch.", task_ctx)
        return False

    all_success = True
    for i, url in enumerate(urls):
        url = url.strip()
        file_name = batch_filenames[i].strip()
        if not url or not file_name:
            all_success = False
            failed_info = {"link": url or "N/A", "filename": file_name or "N/A", "index": "Batch-" + str(i + 1), "reason": "Missing URL/Filename"}
            _task_error.failed_links.append(failed_info)
            continue

        full_file_path = os.path.join(_paths.down_path, file_name)
        success = await http_download_logic(url, full_file_path, file_name, headers, cookies, i + 1, expected_count, task_ctx)
        if not success: all_success = False

    return all_success


async def downloadManager(source: list, is_ytdl: bool, batch_filenames: list = None, task_ctx: TaskContext = None):
    global TRANSFER, BOT, TaskError, MSG, log, BotTimes, Paths, Messages

    if task_ctx:
        _bot = task_ctx.bot
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error
        _transfer = task_ctx.transfer
        log.info(f"downloadManager() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _bot = BOT
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        log.info("downloadManager() using global state")

    selected_service = _bot.Options.service_type
    log.info(f"Download Manager routing. Service: '{selected_service}', Sources: {len(source)}")

    if task_ctx and task_ctx.cancel_event.is_set():
        log.warning("downloadManager called but task is actively cancelled.")
        _task_error.state = True
        _task_error.text = "Task actively cancelled."
        return

    batch_had_failures = False
    os.makedirs(_paths.down_path, exist_ok=True)

    if selected_service in ["nzbcloud", "Debrid", "bitso"]:
        batch_success = False
        if selected_service == "nzbcloud":
             batch_success = await nzbcloud_download(source, batch_filenames, task_ctx)
        elif selected_service == "Debrid":
             batch_success = await Debrid_download(source, batch_filenames, task_ctx)
        elif selected_service == "bitso":
             batch_success = await bitso_download(source, batch_filenames, task_ctx)
        if not batch_success: batch_had_failures = True

    elif selected_service == "downloadly":
        for i, link in enumerate(source, 1):
            if task_ctx and task_ctx.cancel_event.is_set():
                log.warning("Active cancellation detected in downloadly loop.")
                batch_had_failures = True
                break
            filename_hint = _messages.download_name if _messages.download_name else None
            link_success = await downloadly_download(link, i, filename_hint, task_ctx)
            if not link_success: batch_had_failures = True

    elif selected_service == "ytdl":
        if not source: _task_error.state = True; _task_error.text = "No YTDL links provided."; return
        for i, link in enumerate(source):
            if task_ctx and task_ctx.cancel_event.is_set():
                log.warning("Active cancellation detected in ytdl loop.")
                batch_had_failures = True
                break
            await YTDL_Status(link, i + 1, task_ctx=task_ctx)
            if _task_error and _task_error.state:
                 failed_info = {"link": link, "filename": "YTDL Download", "index": i + 1, "reason": _task_error.text or "YTDL Failed"}
                 _task_error.failed_links.append(failed_info)
                 batch_had_failures = True
                 _task_error.state = False; _task_error.text = ""

    elif selected_service == "direct" or selected_service is None:
         total_links = len(source)
         for i, link in enumerate(source):
             if task_ctx and task_ctx.cancel_event.is_set():
                 log.warning("Active cancellation detected in direct download loop.")
                 batch_had_failures = True
                 break
             link_success = False
             intended_filename = batch_filenames[i] if (batch_filenames and i < len(batch_filenames)) else f"Link_{i+1}"
             try:
                 if is_google_drive(link):
                     link_success = await g_DownLoad(link, i + 1, task_ctx)
                 elif is_telegram(link):
                     link_success = await TelegramDownload(link, i + 1, task_ctx)
                 elif is_mega(link):
                     link_success = await megadl(link, i + 1, task_ctx)
                 elif is_terabox(link):
                      terabox_downloader = TeraBoxDownloader(client=None, message=None, task_ctx=task_ctx)
                      link_success = await terabox_downloader.download(link, i + 1)
                 elif is_instagram(link):
                      if is_profile_url(link):
                          link_success = await instagram_profile_download(link, i + 1, max_posts=9999)
                      else:
                          link_success = await instagram_download(link, i + 1)
                 elif is_ytdl_link(link):
                      await YTDL_Status(link, i + 1, task_ctx=task_ctx)
                      link_success = not (_task_error and _task_error.state)
                 elif is_torrent(link):
                      link_success = await aria2_Download(link, i + 1, intended_filename, task_ctx)
                 else:
                      filename_hint = _messages.download_name if _messages.download_name else None
                      link_success = await aria2_Download(link, i + 1, filename_hint, task_ctx)
             except Exception as Error:
                  log.error(f"Auto-detect Error (Link {i+1}): {Error}", exc_info=True)
                  link_success = False
                  failed_info = {"link": link, "filename": intended_filename, "index": i + 1, "reason": str(Error)[:100]}
                  _task_error.failed_links.append(failed_info)

             if not link_success: batch_had_failures = True
    else:
         log.error(f"Unsupported service: '{selected_service}'")
         _task_error.state = True; _task_error.text = f"Unsupported service: {selected_service}"
         batch_had_failures = True

    if batch_had_failures and not _task_error.state:
        _task_error.state = True
        _task_error.text = "One or more downloads failed in batch."


async def calDownSize(sources, task_ctx: TaskContext = None):
    global TRANSFER, Gdrive
    if task_ctx:
        _transfer = task_ctx.transfer
    else:
        _transfer = TRANSFER

    log.info("Calculating download size..."); applicable_sources = [s for s in sources if is_google_drive(s) or is_telegram(s)]; total_calculated_size = 0
    if not applicable_sources: _transfer.total_down_size = 0; return 
    for link in natsorted(applicable_sources):
        try:
            if is_google_drive(link):
                await build_service(task_ctx)
                if not Gdrive.service: continue
                id = await getIDFromURL(link, task_ctx)
                if not id: continue
                meta = await getFileMetadata(id, task_ctx)
                if not meta: continue
                if meta.get("mimeType") == "application/vnd.google-apps.folder": 
                    size = await get_Gfolder_size(id)
                    total_calculated_size += size if size != -1 else 0
                elif meta.get("size"): total_calculated_size += int(meta["size"])
            elif is_telegram(link):
                media, _ = await media_Identifier(link)
                if media and hasattr(media, 'file_size') and media.file_size: total_calculated_size += media.file_size
        except Exception as e: log.error(f"Error calculating size: {e}")
    _transfer.total_down_size = total_calculated_size; log.info(f"Total size: {sizeUnit(_transfer.total_down_size)}")


async def get_d_name(link: str, task_ctx: TaskContext = None):
    global Messages, log 
    if task_ctx:
        _messages = task_ctx.messages
    else:
        _messages = Messages

    name = None
    try:
        if task_ctx and hasattr(task_ctx, 'bot') and hasattr(task_ctx.bot, 'Options'):
            if hasattr(task_ctx.bot.Options, 'filenames') and task_ctx.bot.Options.filenames:
                if len(task_ctx.bot.Options.filenames) > 0:
                    name = task_ctx.bot.Options.filenames[0]
        if not name: name = await extract_filename_from_url(link)
    except Exception as e: log.warning(f"Could not guess name: {e}")

    if name:
        _messages.download_name = name
        log.info(f"Guessed name: {name}")
    else:
        _messages.download_name = None
