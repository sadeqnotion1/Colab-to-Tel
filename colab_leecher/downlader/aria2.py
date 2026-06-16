#colab_leecher/downlader/aria2.py
import os
import re
import logging
import urllib.parse
import subprocess
import asyncio 
from datetime import datetime
from ..utility.helper import sizeUnit, status_bar, clean_filename, apply_dot_style, getTime, is_google_drive, is_mega, getSize, is_torrent # Import getTime if used by status_bar
from ..utility.message_safety import escape_html
from ..utility.variables import BOT, Aria2c, Paths, Messages, BotTimes, TaskError, TRANSFER # Import TaskError & TRANSFER

log = logging.getLogger(__name__)

# Public trackers help low-seed magnets find peers
_EXTRA_TRACKERS = ",".join([
    "udp://tracker.opentrackr.org:1337/announce",
    "udp://open.tracker.cl:1337/announce",
    "udp://exodus.desync.com:6969/announce",
    "udp://tracker.torrent.eu.org:451/announce",
    "udp://open.stealth.si:80/announce",
])

def _parse_size_to_bytes(size_str: str) -> int:
    """Convert aria2c -S size strings like '5.0GiB' / '700MiB' to bytes."""
    import re
    if not size_str or size_str.lower() == "unknown":
        return 0
    m = re.match(r"([\d.]+)\s*([KMGTP]?i?B)", size_str.strip(), re.IGNORECASE)
    if not m:
        return 0
    val = float(m.group(1))
    unit = m.group(2).upper()
    mult = {
        "B": 1,
        "KB": 1000, "KIB": 1024,
        "MB": 1000 ** 2, "MIB": 1024 ** 2,
        "GB": 1000 ** 3, "GIB": 1024 ** 3,
        "TB": 1000 ** 4, "TIB": 1024 ** 4,
        "PB": 1000 ** 5, "PIB": 1024 ** 5,
    }.get(unit, 1)
    return int(val * mult)

async def _download_one_file(file_idx, rel_file_path, down_path, torrent_file_path,
                             task_ctx, *, max_retries=3, stall_timeout=300):
    """Download a single file from the torrent with retries + stall detection.

    aria2c's --bt-stop-timeout aborts the transfer if speed stays at 0 B/s for
    `stall_timeout` seconds, so a dead file can no longer hang the whole job.
    Returns True on success.
    """
    for attempt in range(1, max_retries + 1):
        cmd = [
            "aria2c",
            f"--select-file={file_idx}",
            "--file-allocation=none",
            "--seed-time=0",
            "--summary-interval=1",
            "--max-tries=5",
            "--retry-wait=5",
            f"--bt-stop-timeout={stall_timeout}",
            "--enable-dht=true",
            "--bt-enable-lpd=true",
            "--bt-max-peers=200",
            f"--bt-tracker={_EXTRA_TRACKERS}",
            "-d", down_path,
            torrent_file_path,
        ]
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )

        async def _log_stream(stream, name):
            while True:
                line_bytes = await stream.readline()
                if not line_bytes:
                    break
                line = line_bytes.decode("utf-8", errors="ignore").strip()
                if line and name == "stdout":
                    await on_output(line, os.path.basename(rel_file_path), task_ctx)
                await asyncio.sleep(0.05)

        stdout_task = asyncio.create_task(_log_stream(proc.stdout, "stdout"))
        stderr_task = asyncio.create_task(_log_stream(proc.stderr, "stderr"))
        try:
            exit_code = await proc.wait()
        except asyncio.CancelledError:
            proc.kill()
            await proc.wait()
            raise
        finally:
            stdout_task.cancel()
            stderr_task.cancel()

        if exit_code == 0:
            return True

        log.warning(
            f"Download attempt {attempt}/{max_retries} for '{rel_file_path}' "
            f"failed (exit {exit_code})."
        )
        if task_ctx and task_ctx.cancel_event.is_set():
            return False
        await asyncio.sleep(5 * attempt)

    return False

# get_Aria2c_Name
def get_Aria2c_Name(link):
    # Make sure BOT is accessible
    global BOT, log
    # Return custom name if set
    if BOT.Options.custom_name: # Check directly if custom_name has value
        log.debug(f"Using custom name for Aria2c: {BOT.Options.custom_name}")
        return BOT.Options.custom_name

    # Try getting name via dry run (can be slow)
    log.debug(f"Attempting Aria2c dry run for name: {link[:100]}...")
    name = "UNKNOWN DOWNLOAD NAME" # Default
    try:
        cmd_args = ["aria2c", "-x10", "--dry-run", "--file-allocation=none", link]
        # Use subprocess.run with timeout
        result = subprocess.run(cmd_args, capture_output=True, text=True, timeout=15, check=False)

        if result.returncode == 0 and result.stdout:
            # Look for 'complete:' or 'out=' lines
            match_out = re.search(r"out=([^/\n]+)\n", result.stdout) # Prefer 'out=' parameter if present
            match_comp = re.search(r"complete: (.+)\n", result.stdout) # Fallback to 'complete:'

            if match_out:
                 filename = match_out.group(1).strip()
                 log.debug(f"Got filename from 'out=': {filename}")
                 name = filename
            elif match_comp:
                 filename = match_comp.group(1).strip().split("/")[-1] # Get last part of path
                 log.debug(f"Got filename from 'complete:': {filename}")
                 name = filename
            else:
                 log.warning(f"Aria2c dry run stdout did not contain expected 'out=' or 'complete:' for {link[:100]}")
        else:
            log.warning(f"Aria2c dry run failed (Code: {result.returncode}) or no output for {link[:100]}. Stderr: {result.stderr.strip() if result.stderr else 'N/A'}")

    except subprocess.TimeoutExpired:
         log.warning(f"Aria2c dry run timed out for {link[:100]}.")
    except Exception as dry_run_err:
         log.error(f"Error during Aria2c dry run for name: {dry_run_err}")

    return name
# --- end get_Aria2c_Name ---    
# --- on_output ---
# ----- MODIFIED version of the user-provided on_output function -----
# ----- Replace the existing on_output in aria2.py with this: -----
async def on_output(output: str, current_filename: str, task_ctx=None):
    # Ensure necessary globals are accessible if needed
    global Messages, BotTimes, Aria2c, log, status_bar, sizeUnit, TaskError

    # Multi-task support: Use task_ctx if provided, otherwise fallback to globals
    if task_ctx:
        _messages = task_ctx.messages
        _bot_times = task_ctx.bot_times
    else:
        _messages = Messages
        _bot_times = BotTimes

    total_size = None
    downloaded_bytes = None
    percentage = None
    eta = None
    speed_string = "0B/s" # Initialize speed

    try:
        # --- FIXED Primary Regex Pattern ---
        pattern = re.compile(
            r"\[#[a-f0-9]+\s+" # Start with [# followed by hex ID and spaces
            r"(?P<downloaded>[\d\.]+\s*[KMGTP]?i?B)/(?P<total>[\d\.]+\s*[KMGTP]?i?B)" # Downloaded/Total
            r"\((?P<percent>[\d\.]+)%\).*?" # Percentage
            r"DL:(?P<speed>[\d\.]+\s*[KMGTP]?i?B(?:/s)?)" # Speed with optional /s
            r"(?:\s+ETA:(?P<eta>[^\]]+))?" # Optional ETA
            r"\]", # Closing bracket
            re.IGNORECASE
        )
        match = pattern.search(output)
        # --- END FIXED Regex ---

        if match:
            # Use .strip() on captured groups just in case of extra whitespace
            downloaded_bytes = match.group("downloaded").strip()
            total_size = match.group("total").strip()
            percentage = float(match.group("percent").strip())
            speed_raw = match.group("speed").strip() if match.group("speed") else None # Get raw speed value

            # Add '/s' if missing from captured speed for consistency in display
            if speed_raw and not speed_raw.endswith('/s'):
                speed_string = speed_raw + "/s"
            elif speed_raw:
                speed_string = speed_raw
            else:
                speed_string = "N/A" # Fallback if speed group somehow didn't match

            eta = match.group("eta").strip() if match.group("eta") else "N/A" # Excludes ']'
            log.debug(f"Regex matched: Speed='{speed_string}', ETA='{eta}'") # Log captured values
            Aria2c.link_info = True # Mark that we got info
        else:
            # Fallback attempt (should be very rare now)
            if "ETA:" in output and "%" in output and "/" in output:
                log.warning(f"Primary regex failed on line: '{output.strip()}' - Attempting fallback split.")
                # Fallback logic (remains the same)
                parts = output.split()
                try:
                    stats = next((p for p in parts if "/" in p and "%" in p), None)
                    if stats:
                         downloaded_bytes, rest = stats.split("/", 1)
                         if "(" in rest and ")" in rest:
                             total_size = rest.split("(")[0]
                             percent_str = rest.split("(")[1].split(")")[0]
                             percent_num_match = re.search(r"[\d\.]+", percent_str)
                             if percent_num_match:
                                  percentage = float(percent_num_match.group(0))
                             else: raise ValueError(f"Fallback: Could not extract number from percent_str '{percent_str}'")

                    eta_part = next((p for p in parts if p.startswith("ETA:")), None)
                    if eta_part:
                         eta_val = eta_part.split(":", 1)[1].strip()
                         eta = eta_val.removesuffix(']')
                    else: eta = "N/A"

                    speed_string = None # Mark for manual calculation
                    Aria2c.link_info = True

                except Exception as split_err:
                     log.warning(f"Fallback split parsing failed: {split_err} on line: '{output.strip()}'")
                     total_size = None; percentage = None; downloaded_bytes = None; eta = None
            else:
                 if output and "[#" in output:
                      log.debug(f"Line did not match regex or fallback criteria: {output.strip()}")


    except Exception as e:
        log.error(f"Could not parse output line: '{output.strip()}' - Error: {e}")
        total_size = None; percentage = None; downloaded_bytes = None; eta = None; speed_string = None


    # --- Status Update Section ---
    if percentage is not None and downloaded_bytes and total_size and eta:
        _messages.status_head = f"<b>Downloading</b>\n\n<b>Name:</b> <code>{escape_html(current_filename)}</code>\n"

        done_bytes = _parse_size_to_bytes(str(downloaded_bytes))
        total_bytes = _parse_size_to_bytes(str(total_size))

        # Manual speed calculation only if regex somehow failed to capture speed
        if speed_string is None or speed_string == "N/A":
            log.debug("Calculating speed manually (fallback or regex failed speed group).")
            try:
                elapsed_time_seconds = (datetime.now() - _bot_times.task_start).total_seconds()
                elapsed_time_seconds = max(1, elapsed_time_seconds)
                current_speed = done_bytes / elapsed_time_seconds
                speed_string = f"{sizeUnit(current_speed)}/s"
            except Exception as speed_calc_err:
                log.error(f"Error calculating speed manually: {speed_calc_err}")
                speed_string = "N/A"

        if speed_string is None: speed_string = "N/A" # Final safety check

        try:
            clean_eta = eta.removesuffix(']') # Ensure trailing ']' is removed
            await status_bar(
                _messages.status_head, speed_string, int(percentage), clean_eta,
                done_bytes, total_bytes, engine="Aria2c 🧨",
                task_ctx=task_ctx  # Pass task_ctx for per-task progress tracking
            )
            # Update parallel dashboard if task is in queue
            if task_ctx:
                from ..utility.task_dashboard import try_update_summary
                await try_update_summary()
        except Exception as status_err:
             log.error(f"Error calling status_bar: {status_err}")

    elif not Aria2c.link_info: # Timeout check
         elapsed_time_seconds = (datetime.now() - _bot_times.task_start).total_seconds()
         if elapsed_time_seconds >= 270:
             log.error(f"No valid progress info received for ~270s. Assuming dead link for: {current_filename}")

# ----- END OF FUNCTION -----

async def curl_cffi_Download(
    link: str,
    num: int,
    pre_determined_name: str = None,
    task_ctx = None,
    headers: dict = None,
    cookies: dict = None
) -> bool:
    global BotTimes, Messages, TaskError, TRANSFER, Aria2c, Paths, log
    from curl_cffi.requests import AsyncSession
    import time
    from ..utility.helper import speedETA, sizeUnit, getTime, status_bar, clean_filename

    # Multi-task support: Use task_ctx if provided, otherwise fallback to globals
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error
        _transfer = task_ctx.transfer
        _bot_times = task_ctx.bot_times
        log.info(f"curl_cffi_Download() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _bot_times = BotTimes
        log.info("curl_cffi_Download() using global state")

    # URL sanitization
    link = link.strip().replace('\n', '').replace('\r', '').replace('\t', '')

    url_derived_name = None
    try:
        parsed_url = urllib.parse.urlparse(link)
        url_path_name = os.path.basename(urllib.parse.unquote(parsed_url.path))
        if url_path_name:
            url_derived_name = url_path_name
    except Exception as url_parse_err:
        log.warning(f"curl_cffi: Could not derive filename: {url_parse_err}")

    raw_name = url_derived_name or pre_determined_name or f"curl_cffi_download_{num}"
    expected_filename = clean_filename(raw_name) or f"curl_cffi_download_{num}_cleaned"
    file_path = os.path.join(_paths.down_path, expected_filename)
    display_name_for_status = expected_filename

    log.info(f"Starting curl_cffi download for link index {num} (Expecting: '{expected_filename}')")
    download_start_time = time.time()
    _messages.status_head = f"<b>Downloading</b> <i>Link {str(num).zfill(2)}</i>\n\n<b>Name:</b> <code>{escape_html(display_name_for_status)}</code>\n"

    try:
        os.makedirs(_paths.down_path, exist_ok=True)
    except OSError as mkdir_err:
        log.error(f"curl_cffi: Cannot create download dir: {mkdir_err}")
        return False

    # Headers and cookies preparation
    custom_headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
    }
    
    if headers:
        for k, v in headers.items():
            if k.lower() == 'cookie':
                continue
            custom_headers[k] = v

    if "Referer" not in custom_headers:
        try:
            parsed_ref = urllib.parse.urlparse(link)
            custom_headers["Referer"] = f"{parsed_ref.scheme}://{parsed_ref.netloc}/"
        except Exception:
            custom_headers["Referer"] = link

    # NZBcloud integration
    if 'nzbcloud.com' in link.lower():
        from .. import BOT
        cf_clearance = BOT.Setting.nzb_cf_clearance
        custom_headers['Referer'] = 'https://app.nzbcloud.com/'
        custom_headers['Sec-Fetch-Dest'] = 'video'
        custom_headers['Sec-Fetch-Mode'] = 'no-cors'
        custom_headers['Sec-Fetch-Site'] = 'same-site'
        user_agent = getattr(BOT.Setting, 'nzb_user_agent', '') or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
        custom_headers['User-Agent'] = user_agent
        if cf_clearance:
            custom_headers['Cookie'] = f'cf_clearance={cf_clearance}'
            log.info("🍪 curl_cffi: Using Cloudflare cf_clearance cookie")

    success = False
    error_reason = "curl_cffi Unknown Failure"
    file_size = 0

    try:
        async with AsyncSession(impersonate="chrome") as session:
            async with session.get(link, headers=custom_headers, stream=True, follow_redirects=True) as response:
                if response.status_code >= 400:
                    error_reason = f"HTTP Error {response.status_code}"
                    log.error(f"curl_cffi download response status: {response.status_code}")
                    return False
                
                total_size = 0
                content_length = response.headers.get('content-length') or response.headers.get('Content-Length')
                if content_length:
                    try:
                        total_size = int(content_length)
                    except ValueError:
                        pass

                log.info(f"🚀 curl_cffi download started: {expected_filename} | Total size: {sizeUnit(total_size)}")

                downloaded_size = 0
                last_update_call = 0

                with open(file_path, "wb") as f:
                    async for chunk in response.aiter_content(chunk_size=1024*1024):
                        if (_task_error and _task_error.state) or (task_ctx and task_ctx.cancel_event.is_set()):
                            log.warning(f"curl_cffi download cancelled for {expected_filename}")
                            f.close()
                            if os.path.exists(file_path):
                                try: os.remove(file_path)
                                except OSError: pass
                            error_reason = "Cancelled by User/Error"
                            return False

                        if chunk:
                            f.write(chunk)
                            downloaded_size += len(chunk)
                            now = time.time()

                            if now - last_update_call > 2:
                                last_update_call = now
                                if total_size > 0:
                                    speed_string, eta, percentage = speedETA(download_start_time, downloaded_size, total_size)
                                    log.info(f"📥 curl_cffi progress: {sizeUnit(downloaded_size)}/{sizeUnit(total_size)} ({percentage:.1f}%) | {speed_string} | ETA: {getTime(eta)}")
                                    await status_bar(_messages.status_head, speed_string, int(percentage), getTime(eta),
                                                   downloaded_size, total_size, "curl_cffi 🌐", task_ctx=task_ctx)
                                else:
                                    speed = downloaded_size / (now - download_start_time) if (now - download_start_time) > 0 else 0
                                    speed_string = f"{sizeUnit(speed)}/s"
                                    log.info(f"📥 curl_cffi progress: {sizeUnit(downloaded_size)} / Unknown | {speed_string}")
                                    await status_bar(_messages.status_head, speed_string, 0, "N/A",
                                                   downloaded_size, 0, "curl_cffi 🌐", task_ctx=task_ctx)
                                
                                if task_ctx:
                                    from ..utility.task_dashboard import try_update_summary
                                    await try_update_summary()
                
                # Sniff stub HTML page
                _STUB_THRESHOLD = 10 * 1024
                if downloaded_size < _STUB_THRESHOLD and downloaded_size > 0:
                    try:
                        with open(file_path, 'rb') as _sf:
                            _head = _sf.read(512)
                        _ht = _head.decode('utf-8', errors='replace').strip().lower()
                        _is_html = (
                            _ht.startswith('<!doctype') or _ht.startswith('<html') or
                            '<html' in _ht[:200] or '<head' in _ht[:200] or
                            _ht.startswith('<?xml')
                        )
                        if _is_html:
                            log.error(f"curl_cffi: Server returned HTML error page ({downloaded_size} B) instead of file.")
                            try: os.remove(file_path)
                            except OSError: pass
                            return False
                    except Exception as sniff_err:
                        log.warning(f"curl_cffi: Could not sniff downloaded content: {sniff_err}")

                log.info(f"curl_cffi download complete: {expected_filename} ({sizeUnit(downloaded_size)})")
                success = True
                file_size = downloaded_size

    except Exception as err:
        log.error(f"curl_cffi download failed for link index {num}: {err}", exc_info=True)
        success = False
        if os.path.exists(file_path):
            try: os.remove(file_path)
            except OSError: pass

    return success


async def aria2_Download(link: str, num: int, pre_determined_name: str = None, task_ctx = None, headers: dict = None, cookies: dict = None) -> bool:
    # Ensure necessary globals are accessible
    global BotTimes, Messages, TaskError, TRANSFER, Aria2c, Paths, log, clean_filename, apply_dot_style, on_output, is_google_drive, is_mega # Removed unnecessary urlparse, urllib, os here as they are imported

    # ===== URL SANITIZATION: Remove newlines/carriage returns =====
    # This prevents "Newline or carriage return detected in headers" errors from aiohttp
    # Strips whitespace and removes \n, \r, \t characters that can appear from copy-paste
    original_link = link
    link = link.strip().replace('\n', '').replace('\r', '').replace('\t', '')
    if link != original_link:
        log.warning(f"URL contained whitespace/newlines for link {num}. Sanitized: {link[:100]}...")
    # ===== END SANITIZATION =====

    # Multi-task support: Use task_ctx if provided, otherwise fallback to globals
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error
        _transfer = task_ctx.transfer
        _bot_times = task_ctx.bot_times
        log.info(f"aria2_Download() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _bot_times = BotTimes
        log.info("aria2_Download() using global state")

    success = False
    error_reason = "Aria2 Unknown Failure"
    exit_code = -1
    expected_filename = None
    raw_name = None

    # --- Determine Expected Filename (PRIORITIZE URL Path Robustly) ---
    url_derived_name = None
    try:
        # Attempt to get filename directly from the last part of the URL path
        # Use the imported module name explicitly
        parsed_url = urllib.parse.urlparse(link)
        url_path_name = os.path.basename(urllib.parse.unquote(parsed_url.path))
        if url_path_name:
            url_derived_name = url_path_name
            log.info(f"Derived raw name from URL path for link index {num}: '{url_derived_name}'")
        else:
            log.warning(f"URL path parsing resulted in empty filename for link index {num}.")
            # Fall through to check pre_determined_name
    except NameError as ne:
        # Catch NameError specifically related to missing imports
        log.error(f"IMPORT ERROR: Required module missing? {ne}. Cannot derive filename from URL.", exc_info=True)
        # Fall through to try pre_determined_name
    except Exception as url_parse_err:
        log.warning(f"Could not derive filename from URL path for link index {num}: {url_parse_err}. Checking pre_determined_name.")
        # Fall through to try pre_determined_name

    # Set raw_name based on priority: URL derived > pre_determined > fallback
    if url_derived_name:
        raw_name = url_derived_name
    elif pre_determined_name:
        raw_name = pre_determined_name
        log.info(f"Using pre-determined name for link index {num} as URL derivation failed/skipped: '{raw_name}'")
    else:
        log.warning(f"No filename derived from URL or pre-determined name for link {num}. Using fallback.")
        raw_name = f"aria2_download_{num}"

    # Clean the determined raw_name
    cleaned_name = clean_filename(raw_name)
    if not cleaned_name:
        log.warning(f"Raw name '{raw_name}' became invalid after cleaning for link index {num}. Using fallback.")
        cleaned_name = f"aria2_download_{num}_cleaned"

    expected_filename = cleaned_name
    display_name_for_status = cleaned_name
    # --- End Filename Determination ---

    log.info(f"Starting Aria2c download for link index {num} (Expecting: '{expected_filename}')")
    _bot_times.task_start = datetime.now()
    _messages.status_head = f"<b>Downloading</b> <i>Link {str(num).zfill(2)}</i>\n\n<b>Name:</b> <code>{escape_html(display_name_for_status)}</code>\n"

    try:
        os.makedirs(_paths.down_path, exist_ok=True)
    except OSError as mkdir_err:
        error_reason = f"Cannot create download dir: {mkdir_err}"
        log.error(error_reason)
        failed_info = {"link": link, "filename": expected_filename, "index": num, "reason": error_reason}
        if _task_error: _task_error.failed_links.append(failed_info)
        return False

    # --- Build command WITH --content-disposition=false ---
    # Always send browser-mimicking headers so servers that block bot User-Agents
    # (like aria2/1.x.x) behave the same as they do with IDM or a real browser.
    try:
        parsed_for_referer = urllib.parse.urlparse(link)
        referer = f"{parsed_for_referer.scheme}://{parsed_for_referer.netloc}/"
    except Exception:
        referer = link

    # Dynamic headers & cookies setup
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    referer_val = referer
    custom_headers = []

    if headers:
        for k, v in headers.items():
            k_lower = k.lower()
            if k_lower == 'user-agent':
                user_agent = v
            elif k_lower == 'referer':
                referer_val = v
            elif k_lower == 'cookie':
                # Handled via cookies dict/header separately
                custom_headers.append((k, v))
            else:
                custom_headers.append((k, v))

    if cookies:
        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])
        custom_headers.append(("Cookie", cookie_str))

    command = [
        "aria2c", "-x16", "--seed-time=0", "--summary-interval=1", "--max-tries=3",
        "--console-log-level=warn", "--file-allocation=none",
        "--content-disposition=false",
        "--user-agent", user_agent,
        "--header", "Accept: */*",
        "--header", "Accept-Language: en-US,en;q=0.9",
        "--header", "Accept-Encoding: gzip, deflate, br",
        "--header", f"Referer: {referer_val}",
        "-d", _paths.down_path
    ]

    for hk, hv in custom_headers:
        command.extend(["--header", f"{hk}: {hv}"])

    # Add Cloudflare cookie and headers for NZBCloud downloads (Aria2c)
    if 'nzbcloud.com' in link.lower():
        from .. import BOT
        cf_clearance = BOT.Setting.nzb_cf_clearance
        log.info(f"🔍 NZBCloud link detected. Cookie configured: {bool(cf_clearance)}")
        if cf_clearance:
            log.info(f"🍪 Adding Cloudflare cookie to Aria2c for NZBCloud download (length: {len(cf_clearance)})")
            user_agent = getattr(BOT.Setting, 'nzb_user_agent', '') or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"
            command.extend([
                "--header", f"Cookie: cf_clearance={cf_clearance}",
                "--header", "Referer: https://app.nzbcloud.com/",
                "--header", "Sec-Fetch-Dest: video",
                "--header", "Sec-Fetch-Mode: no-cors",
                "--header", "Sec-Fetch-Site: same-site",
                "--user-agent", user_agent
            ])
            log.debug(f"📋 Aria2c command has {len(command)} arguments including {sum(1 for x in command if x == '--header')} headers")
        else:
            log.warning(f"⚠️ NZBCloud download detected but cf_clearance cookie not configured. Download may fail with 403 error.")

    # Force aria2c to write the file using exactly our determined filename.
    # Without --out, aria2c derives its own name from the raw URL path which may
    # differ from our cleaned expected_filename (e.g. leading underscore kept by
    # aria2c but stripped by clean_filename). This eliminates the mismatch entirely.
    command.extend(["-o", expected_filename])

    # Add the link as the final argument
    command.append(link)
    # --- End Command ---

    # Exit codes that are safe to retry (transient network/connection failures).
    # Permanent codes (3=404, 9=disk full, 24=auth, etc.) are not retried.
    _RETRYABLE_CODES = {1, 29}
    _MAX_RETRIES = 3

    proc = None

    for _attempt in range(1, _MAX_RETRIES + 1):
        success = False
        exit_code = -1
        proc = None

        try:
            proc = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            # Mask URL in logs for security
            log_command = command.copy()
            if len(log_command) > 0:
                log_command[-1] = "REDACTED_URL"
            log.debug(f"Aria2c process started (PID: {proc.pid}) with command: {' '.join(log_command)}")

            # --- Async stream reader ---
            async def log_stream(stream, stream_name):
                 while True:
                     line_bytes = await stream.readline()
                     if not line_bytes: break
                     line = line_bytes.decode('utf-8', errors='ignore').strip()
                     if line:
                         log.debug(f"Aria2c {stream_name}: {line}")
                         if stream_name == 'stdout':
                              await on_output(line, display_name_for_status, task_ctx)
                     await asyncio.sleep(0.05)

            stdout_task = asyncio.create_task(log_stream(proc.stdout, 'stdout'))
            stderr_task = asyncio.create_task(log_stream(proc.stderr, 'stderr'))

            exit_code = await proc.wait()
            await asyncio.gather(stdout_task, stderr_task)
            log.debug(f"Aria2c process finished with exit code: {exit_code} (attempt {_attempt}/{_MAX_RETRIES})")

            # --- Success Check (with Added Diagnostics) ---
            await asyncio.sleep(0.2) # Small delay

            final_filepath_on_disk = os.path.join(_paths.down_path, expected_filename)
            file_exists = os.path.exists(final_filepath_on_disk)
            file_size = 0
            if file_exists:
                 try: file_size = os.path.getsize(final_filepath_on_disk)
                 except OSError as size_err: log.error(f"Could not get size for existing file {final_filepath_on_disk}: {size_err}")

            if exit_code == 0:
                if file_exists and file_size > 0:
                     # --- Content-sniff: detect stub/error-page responses ---
                     # Servers sometimes return HTTP 200 with a tiny HTML error body
                     # instead of the real file (auth wall, CDN token expiry, etc.).
                     # aria2c considers that a success; we must catch it here.
                     _STUB_THRESHOLD = 10 * 1024  # 10 KB
                     if file_size < _STUB_THRESHOLD:
                         try:
                             with open(final_filepath_on_disk, 'rb') as _f:
                                 _head = _f.read(512)
                             _head_text = _head.decode('utf-8', errors='replace').strip().lower()
                             _is_html = (
                                 _head_text.startswith('<!doctype') or
                                 _head_text.startswith('<html') or
                                 '<html' in _head_text[:200] or
                                 '<head' in _head_text[:200] or
                                 _head_text.startswith('<?xml')
                             )
                             if _is_html:
                                 log.error(
                                     f"Aria2c downloaded a stub/error page ({file_size} bytes) "
                                     f"instead of the real file for link {num}. "
                                     f"Server response preview: {_head.decode('utf-8', errors='replace')[:300]!r}"
                                 )
                                 try: os.remove(final_filepath_on_disk)
                                 except OSError: pass
                                 error_reason = (
                                     f"Server returned an error/auth page ({file_size} B) instead of "
                                     f"the real file. The URL likely requires browser cookies or a session token. "
                                     f"Try the Debrid or Bitso service if you have credentials for this host."
                                 )
                                 success = False
                             else:
                                 log.warning(
                                     f"Aria2c download looks very small ({file_size} B) for link {num} "
                                     f"but content does not appear to be HTML. Treating as success. "
                                     f"Preview: {_head.decode('utf-8', errors='replace')[:100]!r}"
                                 )
                                 log.info(f"Aria2c download complete. Found expected file: {final_filepath_on_disk} (Size: {file_size})")
                                 success = True
                         except Exception as sniff_err:
                             log.warning(f"Could not sniff downloaded file content: {sniff_err}. Treating as success.")
                             log.info(f"Aria2c download complete. Found expected file: {final_filepath_on_disk} (Size: {file_size})")
                             success = True
                     else:
                         log.info(f"Aria2c download complete. Found expected file: {final_filepath_on_disk} (Size: {file_size})")
                         success = True
                     # --- End content-sniff ---

                else:
                     log.error(f"Aria2 success code 0 but check failed for: {final_filepath_on_disk}")
                     log.warning(f"Details: File Exists? {file_exists}, File Size: {file_size}")
                     if file_exists and file_size == 0:
                          log.warning(f"Removing empty file: {final_filepath_on_disk}")
                          try: os.remove(final_filepath_on_disk)
                          except OSError as cl_err: log.warning(f"Failed cleanup empty aria2 file: {cl_err}")

                     try:
                          dir_contents = [name for name in os.listdir(_paths.down_path) if not name.endswith(".aria2")]
                          log.warning(f"Contents of download directory ({_paths.down_path}): {dir_contents}") # DIAGNOSTIC LOG
                     except Exception as list_err:
                          log.warning(f"Could not list download directory contents: {list_err}")
                          dir_contents = []

                     if dir_contents:
                          if len(dir_contents) == 1:
                               resolved_name = dir_contents[0]
                               resolved_path = os.path.join(_paths.down_path, resolved_name)
                          else:
                               resolved_name = expected_filename
                               resolved_path = _paths.down_path

                          resolved_size = getSize(resolved_path)
                          if resolved_size > 0:
                               log.warning(f"Expected file missing; using actual output '{resolved_name}' for link {num}.")
                               expected_filename = resolved_name
                               final_filepath_on_disk = resolved_path
                               file_size = resolved_size
                               success = True
                          else:
                               error_reason = f"Aria2 success code 0 but output invalid/empty: {expected_filename}"
                               success = False
                     else:
                          error_reason = f"Aria2 success code 0 but expected output file invalid/missing/empty: {expected_filename}"
                          success = False
            else:
                # Determine error reason for this exit code
                if exit_code == 3:   error_reason = "Aria2 Error: Resource Not Found (404?)"
                elif exit_code == 9: error_reason = "Aria2 Error: Not enough disk space"
                elif exit_code == 24: error_reason = "Aria2 Error: HTTP authorization failed (401/403?)"
                elif exit_code == 29: error_reason = "Aria2 Error: Network/Connection Issue (Code 29)"
                else:                error_reason = f"Aria2 failed code {exit_code}"

                # Retry transient codes if attempts remain
                if exit_code in _RETRYABLE_CODES and _attempt < _MAX_RETRIES:
                    _wait = 3 ** _attempt  # 3 s, 9 s
                    log.warning(
                        f"Aria2c transient failure (code {exit_code}) on attempt {_attempt}/{_MAX_RETRIES} "
                        f"for link index {num}. Retrying in {_wait}s…"
                    )
                    # Cleanup any partial output before retry
                    if os.path.exists(final_filepath_on_disk):
                        try: os.remove(final_filepath_on_disk)
                        except OSError as cl_err: log.warning(f"Failed cleanup aria2 file before retry: {cl_err}")
                    await asyncio.sleep(_wait)
                    continue  # next attempt
                else:
                    # Fallback to curl_cffi for NZBCloud downloads if aria2c fails
                    if 'nzbcloud.com' in link.lower():
                        log.warning(f"Aria2c failed with code {exit_code} for NZBCloud URL. Falling back to curl_cffi_Download...")
                        if os.path.exists(final_filepath_on_disk):
                            try: os.remove(final_filepath_on_disk)
                            except OSError: pass
                        
                        success = await curl_cffi_Download(
                            link=link,
                            num=num,
                            pre_determined_name=pre_determined_name,
                            task_ctx=task_ctx,
                            headers=headers,
                            cookies=cookies
                        )
                        if success:
                            if os.path.exists(final_filepath_on_disk):
                                file_size = os.path.getsize(final_filepath_on_disk)
                        else:
                            error_reason = "curl_cffi fallback download failed"
                        break

                    log.error(f"Aria2c download failed for link index {num}. Reason: {error_reason}")
                    success = False
                    # Cleanup
                    if os.path.exists(final_filepath_on_disk):
                         try: os.remove(final_filepath_on_disk)
                         except OSError as cl_err: log.warning(f"Failed cleanup aria2 file: {cl_err}")

        except asyncio.CancelledError:
            log.warning(f"Aria2 download cancelled for link index {num}. Terminating subprocess...")
            if proc and proc.returncode is None:
                try:
                    proc.terminate() # Try terminate first
                    try:
                        await asyncio.wait_for(proc.wait(), timeout=5.0)
                    except asyncio.TimeoutError:
                        log.warning("Aria2 process ignored terminate, killing...")
                        proc.kill()
                        await proc.wait()
                except Exception as kill_err:
                     log.warning(f"Error terminating aria2c process: {kill_err}")

            # Cleanup partial file
            if expected_filename:
                 cleanup_path = os.path.join(_paths.down_path, expected_filename)
                 if os.path.exists(cleanup_path):
                     try: os.remove(cleanup_path)
                     except OSError as cl_err: log.warning(f"Failed cleanup aria2 file after cancellation: {cl_err}")

            # Re-raise to ensure cancellation propagates
            raise

        except FileNotFoundError as fnf:
            # aria2c executable not found - fall back to aiohttp
            log.warning(f"aria2c executable not found. Falling back to aiohttp for link index {num}")
            log.info(f"Installing aria2 is recommended for better download performance. Continuing with aiohttp...")

            # Fall back to aiohttp download
            import aiohttp
            import time
            from ..utility.helper import speedETA, sizeUnit, getTime, status_bar

            try:
                file_path = os.path.join(_paths.down_path, expected_filename)
                download_start_time = time.time()
                _messages.status_head = f"<b>Downloading</b> <i>Link {str(num).zfill(2)}</i>\n\n<b>Name:</b> <code>{escape_html(display_name_for_status)}</code>\n"

                timeout = aiohttp.ClientTimeout(total=None, connect=180, sock_read=600)
                connector = aiohttp.TCPConnector(limit=10, limit_per_host=5, ttl_dns_cache=300)
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                    "Accept": "*/*",
                    "Accept-Language": "en-US,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Connection": "keep-alive",
                    "Referer": link.split('?')[0] if '?' in link else link
                }

                # Add Cloudflare cookie and headers for NZBCloud downloads
                if 'nzbcloud.com' in link.lower():
                    from .. import BOT
                    cf_clearance = BOT.Setting.nzb_cf_clearance
                    if cf_clearance:
                        # Add cookie directly to request headers (most reliable method)
                        headers['Cookie'] = f'cf_clearance={cf_clearance}'
                        # Match browser headers exactly for Cloudflare
                        headers['Referer'] = 'https://app.nzbcloud.com/'
                        headers['Sec-Fetch-Dest'] = 'video'
                        headers['Sec-Fetch-Mode'] = 'no-cors'
                        headers['Sec-Fetch-Site'] = 'same-site'
                        user_agent = getattr(BOT.Setting, 'nzb_user_agent', '') or 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36'
                        headers['User-Agent'] = user_agent
                        log.info(f"🍪 Using Cloudflare cookie for NZBCloud download")

                async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
                    async with session.get(link, headers=headers, allow_redirects=True) as response:
                        response.raise_for_status()
                        total_size = int(response.headers.get('content-length', 0))
                        log.info(f"🚀 aiohttp download started: {expected_filename} | Total size: {sizeUnit(total_size)}")

                        downloaded_size = 0
                        block_size = 1024 * 1024  # 1MB chunks
                        last_update_call = 0

                        with open(file_path, "wb") as file:
                            async for chunk in response.content.iter_chunked(block_size):
                                if _task_error and _task_error.state:
                                    log.warning(f"Download cancelled for {expected_filename}")
                                    file.close()
                                    if os.path.exists(file_path): os.remove(file_path)
                                    error_reason = "Cancelled by User/Error"
                                    success = False
                                    break

                                if chunk:
                                    file.write(chunk)
                                    downloaded_size += len(chunk)
                                    now = time.time()

                                    # Update status periodically
                                    if now - last_update_call > 2:
                                        last_update_call = now
                                        if total_size > 0:
                                            speed_string, eta, percentage = speedETA(download_start_time, downloaded_size, total_size)
                                            log.info(f"📥 aiohttp progress: {sizeUnit(downloaded_size)}/{sizeUnit(total_size)} ({percentage:.1f}%) | {speed_string} | ETA: {getTime(eta)}")
                                            await status_bar(_messages.status_head, speed_string, percentage, getTime(eta),
                                                           sizeUnit(downloaded_size), sizeUnit(total_size), "aiohttp 🌐", task_ctx=task_ctx)
                                            # Update parallel dashboard if task is in queue
                                            if task_ctx:
                                                from ..utility.task_dashboard import try_update_summary
                                                await try_update_summary()
                            else:
                                # Download completed successfully
                                log.info(f"aiohttp download complete: {expected_filename} ({sizeUnit(downloaded_size)})")
                                success = True
                                file_size = downloaded_size

            except Exception as aiohttp_err:
                error_reason = f"aiohttp fallback error: {str(aiohttp_err)[:100]}"
                log.error(f"aiohttp fallback failed for link index {num}: {aiohttp_err}")
                success = False
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                    except OSError as remove_err:
                        log.warning(f"Failed to remove fallback file {file_path}: {remove_err}")

        except Exception as e:
            # Handle other general exceptions
            error_reason = f"Aria2 Process Error: {str(e)[:100]}"
            log.error(f"Error running Aria2c process for link index {num}: {e}", exc_info=True)
            if proc and proc.returncode is None:
                try: proc.kill(); await proc.wait()
                except Exception as kill_err: log.warning(f"Error killing aria2c process: {kill_err}")
            success = False
            # Cleanup
            if expected_filename:
                 cleanup_path = os.path.join(_paths.down_path, expected_filename)
                 if os.path.exists(cleanup_path):
                     try: os.remove(cleanup_path)
                     except OSError as cl_err: log.warning(f"Failed cleanup aria2 file after exception: {cl_err}")

        # Reached here: either success or permanent failure — exit retry loop
        break

    # Report status using the filename derived from URL
    if success and expected_filename:
        try:
            dl_size = file_size if file_size > 0 else os.path.getsize(final_filepath_on_disk)
            _transfer.down_bytes.append(dl_size)  # Add to total bytes downloaded
            _transfer.successful_downloads.append({'url': link, 'filename': expected_filename})
            log.debug(f"✅ Recorded download: {expected_filename} ({dl_size} bytes)")
        except Exception as report_err: log.error(f"Error getting size/reporting success for {expected_filename}: {report_err}")
    elif not success:
        failed_info = {"link": link, "filename": expected_filename or raw_name, "index": num, "reason": error_reason}
        if _task_error: _task_error.failed_links.append(failed_info)

    return success
# ----- END OF FINAL FINAL REVISED FUNCTION -----


async def download_and_upload_torrent_streaming(link: str, task_ctx=None) -> bool:
    """
    Downloads torrent/magnet files one by one, uploads them, and deletes them.
    Saves disk space on Google Colab.
    """
    import os
    import shutil
    import asyncio
    import logging
    import tempfile
    from ..utility.helper import status_bar, sizeUnit, getTime, clean_filename
    from ..utility.variables import Paths

    log = logging.getLogger(__name__)

    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error
        _transfer = task_ctx.transfer
        _status_msg = task_ctx.status_msg
    else:
        from ..utility.variables import Paths, Messages, TaskError, TRANSFER, MSG
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _status_msg = MSG.status_msg

    # Create temporary directory for torrent metadata
    temp_dir = tempfile.mkdtemp(prefix="torrent_metadata_", dir=_paths.WORK_PATH)
    torrent_file_path = None

    try:
        # Step 1: Get torrent file
        if os.path.exists(link) and os.path.isfile(link) and link.lower().endswith(".torrent"):
            # It's already a local torrent file
            torrent_file_path = link
            log.info(f"Using local torrent file: {torrent_file_path}")
        elif link.startswith("magnet:"):
            # Update status: Fetching metadata
            log.info("Fetching torrent metadata for magnet link...")
            if _status_msg:
                await status_bar(
                    down_msg="<b>🧲 Streaming Torrent »</b>\n\n<b>Link:</b> <code>Magnet</code>\n",
                    speed="N/A",
                    percentage=0,
                    eta="N/A",
                    done="Fetching torrent metadata...",
                    total_size="N/A",
                    engine="Aria2c 🧨",
                    task_ctx=task_ctx
                )

            # Command to download metadata only
            cmd = [
                "aria2c",
                "--bt-metadata-only=true",
                "--bt-save-metadata=true",
                "--file-allocation=none",
                "--seed-time=0",
                "-d", temp_dir,
                link
            ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Monitor progress of metadata fetching
            async def log_metadata_stream(stream, name):
                while True:
                    line_bytes = await stream.readline()
                    if not line_bytes:
                        break
                    line = line_bytes.decode('utf-8', errors='ignore').strip()
                    if line:
                        log.info(f"[Metadata {name}] {line}")
                    await asyncio.sleep(0.1)

            stdout_task = asyncio.create_task(log_metadata_stream(proc.stdout, "stdout"))
            stderr_task = asyncio.create_task(log_metadata_stream(proc.stderr, "stderr"))

            try:
                exit_code = await asyncio.wait_for(proc.wait(), timeout=300) # 5 minutes max
            except asyncio.TimeoutError:
                log.error("Fetching torrent metadata timed out.")
                try:
                    proc.kill()
                    await proc.wait()
                except Exception:
                    pass
                if _task_error:
                    _task_error.set_error("Metadata fetch timed out")
                return False
            finally:
                stdout_task.cancel()
                stderr_task.cancel()

            if proc.returncode != 0:
                log.error(f"Aria2 failed to fetch metadata, exit code {proc.returncode}")
                if _task_error:
                    _task_error.set_error(f"Failed to fetch metadata (code {proc.returncode})")
                return False

            # Find .torrent file
            torrent_files = [f for f in os.listdir(temp_dir) if f.endswith(".torrent")]
            if not torrent_files:
                log.error("No .torrent file found after metadata download.")
                if _task_error:
                    _task_error.set_error("Metadata downloaded but .torrent file not found")
                return False

            torrent_file_path = os.path.join(temp_dir, torrent_files[0])
            log.info(f"Successfully fetched torrent metadata: {torrent_file_path}")

        else:
            # It's a torrent file URL. Download it.
            log.info(f"Downloading torrent file from URL: {link[:100]}...")
            if _status_msg:
                await status_bar(
                    down_msg="<b>🧲 Streaming Torrent »</b>\n\n<b>Link:</b> <code>URL</code>\n",
                    speed="N/A",
                    percentage=0,
                    eta="N/A",
                    done="Downloading torrent file...",
                    total_size="N/A",
                    engine="Aria2c 🧨",
                    task_ctx=task_ctx
                )

            # Download using aiohttp or simple request to temp_dir
            import aiohttp
            torrent_file_path = os.path.join(temp_dir, "temp.torrent")
            async with aiohttp.ClientSession() as session:
                async with session.get(link, timeout=60) as resp:
                    if resp.status != 200:
                        log.error(f"Failed to download torrent file, status {resp.status}")
                        if _task_error:
                            _task_error.set_error(f"Failed to download torrent file (HTTP {resp.status})")
                        return False
                    with open(torrent_file_path, "wb") as f:
                        f.write(await resp.read())
            log.info("Successfully downloaded torrent file.")

        # Step 2: Parse torrent content using aria2c -S
        try:
            sz = os.path.getsize(torrent_file_path)
            log.info(f"Local torrent file size: {sz} bytes")
        except Exception as sz_err:
            log.warning(f"Could not get torrent file size: {sz_err}")

        cmd = ["aria2c", "-S", torrent_file_path]
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        stdout_str = stdout.decode('utf-8', errors='ignore')

        files = []
        torrent_name = "Torrent_Download"
        current_file = None
        for line in stdout_str.splitlines():
            line = line.strip()
            if line.startswith("Name:"):
                torrent_name = line.split("Name:", 1)[1].strip()
                continue
            parts = line.split('|')
            if len(parts) >= 2:
                left = parts[0].strip()
                is_idx = False
                idx = -1
                try:
                    idx = int(left)
                    is_idx = True
                except ValueError:
                    pass

                if is_idx:
                    if len(parts) >= 3:
                        size_str = parts[-1].strip()
                        file_path = "|".join(parts[1:-1]).strip()
                        files.append({
                            'idx': idx,
                            'path': file_path,
                            'size_str': size_str
                        })
                        current_file = None
                    else:
                        file_path = parts[1].strip()
                        current_file = {
                            'idx': idx,
                            'path': file_path,
                            'size_str': 'Unknown'
                        }
                elif left == "" and current_file is not None:
                    size_str = parts[1].strip()
                    if " " in size_str:
                        size_str = size_str.split(" ")[0].strip()
                    current_file['size_str'] = size_str
                    files.append(current_file)
                    current_file = None

        if not files:
            stderr_str = stderr.decode('utf-8', errors='ignore')
            log.error(f"No files found in torrent. Exit code: {proc.returncode}")
            log.error(f"aria2c -S stdout:\n{stdout_str}")
            log.error(f"aria2c -S stderr:\n{stderr_str}")
            if _task_error:
                _task_error.set_error("No files found in torrent")
            return False

        log.info(f"Torrent '{torrent_name}' contains {len(files)} files.")
        if _messages:
            _messages.download_name = torrent_name

        # Step 3: Loop and download/upload file-by-file
        total_files = len(files)
        files_processed = 0
        bytes_uploaded = 0

        # Initialize GDrive folder if in gdrive mode
        gdrive_folder_id = None
        gdrive_dir_cache = {}
        current_mode = task_ctx.bot.Mode.mode if (task_ctx and hasattr(task_ctx, 'bot')) else "leech"

        if current_mode == "gdrive":
            # Create a base folder for this torrent on Google Drive
            custom_folder_name = task_ctx.bot.Options.custom_name if (task_ctx and getattr(task_ctx.bot.Options, 'custom_name', None)) else torrent_name
            from ..uploader.gdrive import create_folder_on_gdrive, upload_to_gdrive
            gdrive_folder_id = await create_folder_on_gdrive(custom_folder_name, parent_id=None, task_ctx=task_ctx)
            if not gdrive_folder_id:
                log.error("Failed to create root Google Drive folder.")
                if _task_error:
                    _task_error.set_error("GDrive folder creation failed")
                return False

        async def get_or_create_gdrive_folder(relative_dir_path, root_folder_id):
            if not relative_dir_path:
                return root_folder_id
            parts = [p for p in relative_dir_path.split('/') if p and p != '.']
            # Reconstruct path and create folders hierarchically
            curr_parent = root_folder_id
            curr_path = ""
            for part in parts:
                curr_path = f"{curr_path}/{part}" if curr_path else part
                if curr_path in gdrive_dir_cache:
                    curr_parent = gdrive_dir_cache[curr_path]
                else:
                    new_folder_id = await create_folder_on_gdrive(part, curr_parent, task_ctx)
                    gdrive_dir_cache[curr_path] = new_folder_id
                    curr_parent = new_folder_id
            return curr_parent

        selected_indices = None
        if task_ctx and hasattr(task_ctx, 'metadata'):
            sel = task_ctx.metadata.get('selected_torrent_files')
            if sel and isinstance(sel, set) and len(sel) < len(files):
                selected_indices = sel
                log.info(f"User selected {len(selected_indices)}/{len(files)} files for download")

        filtered_files = [f for f in files if not selected_indices or f['idx'] in selected_indices]
        if not filtered_files:
            log.error("No files selected for download")
            if _task_error:
                _task_error.set_error("No files selected")
            return False

        total_files_to_download = len(filtered_files)
        log.info(f"Will download {total_files_to_download} of {len(files)} files")

        status_head = (
            f"<b>🔄 Streaming Torrent »</b>\n\n"
            f"<b>📦 Torrent:</b> <code>{torrent_name}</code>\n"
        )

        failed_files = []                 # (path, reason) collected for the final report
        DISK_HEADROOM = 1 * 1024 ** 3     # keep 1 GB free as a safety margin
        down_path = _paths.down_path

        for idx, f_info in enumerate(filtered_files, 1):
            if task_ctx and task_ctx.cancel_event.is_set():
                log.warning("Torrent streaming task cancelled by user.")
                break

            file_idx = f_info["idx"]
            rel_file_path = f_info["path"]
            file_size_str = f_info["size_str"]
            expected_bytes = _parse_size_to_bytes(file_size_str)

            # --- Disk-space pre-check (room for the file + its split parts) ---
            try:
                free = shutil.disk_usage(down_path).free
            except Exception:
                free = None
            needed = expected_bytes * 2 + DISK_HEADROOM if expected_bytes else 0
            if free is not None and needed and free < needed:
                reason = f"not enough disk: need ~{sizeUnit(needed)}, free {sizeUnit(free)}"
                log.error(f"Skipping '{rel_file_path}': {reason}")
                failed_files.append((rel_file_path, reason))
                continue

            log.info(f"[{idx}/{total_files_to_download}] Downloading {rel_file_path} ({file_size_str})")

            if _status_msg:
                await status_bar(
                    down_msg=status_head,
                    speed="N/A", percentage=((idx - 1) / total_files_to_download) * 100,
                    eta="N/A",
                    done=f"📂 Downloading {idx}/{total_files_to_download}\n<code>{os.path.basename(rel_file_path)}</code> ({file_size_str})",
                    total_size=f"{files_processed}/{total_files_to_download} files",
                    engine="Streaming Torrent Downloader", task_ctx=task_ctx,
                )

            # --- Download with retries + stall timeout ---
            ok = await _download_one_file(file_idx, rel_file_path, down_path,
                                          torrent_file_path, task_ctx)
            if not ok:
                failed_files.append((rel_file_path, "download failed/stalled"))
                continue

            file_abs_path = os.path.normpath(os.path.join(down_path, rel_file_path.lstrip("./")))
            if not os.path.exists(file_abs_path):
                failed_files.append((rel_file_path, "file missing after download"))
                continue

            file_size_bytes = os.path.getsize(file_abs_path)

            if _status_msg:
                await status_bar(
                    down_msg=status_head,
                    speed="N/A", percentage=((idx - 0.5) / total_files_to_download) * 100,
                    eta="N/A",
                    done=f"⬆️ Uploading {idx}/{total_files_to_download}\n<code>{os.path.basename(rel_file_path)}</code> ({sizeUnit(file_size_bytes)})",
                    total_size=f"{files_processed}/{total_files_to_download} files",
                    engine="Streaming Torrent Downloader", task_ctx=task_ctx,
                )

            # --- Upload (wrapped so one failure can't crash the run) ---
            upload_success = False
            try:
                if current_mode == "gdrive":
                    relative_dir = os.path.dirname(rel_file_path.lstrip("./"))
                    target_folder_id = await get_or_create_gdrive_folder(relative_dir, gdrive_folder_id)
                    res = await upload_to_gdrive(file_abs_path, target_folder_id, task_ctx)
                    if res:
                        upload_success = True
                        if _messages:
                            if not getattr(_messages, "uploaded_links", None):
                                _messages.uploaded_links = []
                            _messages.uploaded_links.append(
                                {"name": res["name"], "link": res["webViewLink"], "size": res["size"]})
                elif current_mode == "mirror":
                    target_abs_path = os.path.normpath(os.path.join(_paths.mirror_dir, rel_file_path.lstrip("./")))
                    os.makedirs(os.path.dirname(target_abs_path), exist_ok=True)
                    await asyncio.to_thread(shutil.move, file_abs_path, target_abs_path)
                    upload_success = True
                else:  # Telegram leech
                    from ..uploader.telegram import upload_file
                    upload_success = await upload_file(
                        file_path=file_abs_path,
                        display_name=os.path.basename(file_abs_path),
                        task_ctx=task_ctx,
                    )
            except Exception as up_err:
                log.error(f"Upload raised for {rel_file_path}: {up_err}", exc_info=True)
                upload_success = False

            if upload_success:
                files_processed += 1
                bytes_uploaded += file_size_bytes
                log.info(f"Uploaded {idx}/{total_files_to_download}: {rel_file_path}")
            else:
                failed_files.append((rel_file_path, "upload failed"))

            # --- Always free disk (mirror already moved the file) ---
            if current_mode != "mirror" and os.path.exists(file_abs_path):
                try:
                    os.remove(file_abs_path)
                except OSError as e:
                    log.warning(f"Could not delete temp file {file_abs_path}: {e}")

            # Prune empty dirs
            for root, dirs, _f in os.walk(down_path, topdown=False):
                for d in dirs:
                    d_path = os.path.join(root, d)
                    try:
                        if not os.listdir(d_path):
                            os.rmdir(d_path)
                    except Exception:
                        pass

        # Final update
        if _status_msg:
            await status_bar(
                down_msg=status_head,
                speed="N/A",
                percentage=100.0,
                eta="Complete",
                done=f"✅ Processed {files_processed}/{total_files_to_download} files ({sizeUnit(bytes_uploaded)})",
                total_size=f"{files_processed} files",
                engine="Streaming Torrent Downloader",
                task_ctx=task_ctx
            )

        # --- End-of-run report ---
        if failed_files:
            report = "\n".join(f"• {p} — {why}" for p, why in failed_files)
            log.error(f"{len(failed_files)} file(s) did not complete:\n{report}")
            if _messages:
                _messages.failed_torrent_files = failed_files

        return len(failed_files) == 0

    except Exception as e:
        log.error(f"Error in streaming torrent download: {e}", exc_info=True)
        if _task_error:
            _task_error.set_error(f"Streaming torrent error: {str(e)[:100]}")
        return False

    finally:
        # Clean up temp torrent directory
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
        # Clean up local torrent file if it was from torrent_uploads
        if torrent_file_path and "torrent_uploads" in torrent_file_path and os.path.exists(torrent_file_path):
            try:
                os.remove(torrent_file_path)
                log.info(f"Cleaned up uploaded torrent file: {torrent_file_path}")
            except Exception as clean_err:
                log.warning(f"Could not clean up uploaded torrent file: {clean_err}")

