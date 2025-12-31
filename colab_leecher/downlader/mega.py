#================================================
#FILE: colab_leecher/downlader/mega.py
#================================================
#Telegra-Leecher/colab_leecher/downlader/mega.py
import subprocess
import logging 
import shutil
from datetime import datetime
from colab_leecher.utility.helper import status_bar, getTime
from colab_leecher.utility.variables import BotTimes, Messages, Paths, TaskError, TRANSFER 
from pymegatools import Megatools, MegaError
import os 

log = logging.getLogger(__name__) 



def _is_folder_url(url: str) -> bool:
    """Detect if a Mega URL is a folder URL that may not work with megadl.

    Returns True only for actual folder URLs, not for file URLs within folders.
    Examples:
        - https://mega.nz/folder/ABC#key -> True (folder)
        - https://mega.nz/folder/ABC#key/file/XYZ -> False (file within folder)
        - https://mega.nz/file/XYZ#key -> False (direct file)
    """
    url_lower = url.lower()

    # If URL has /file/ anywhere, it's a file URL (even if in a folder path)
    if '/file/' in url_lower:
        return False

    # Only return True if it has /folder/ and no /file/
    return '/folder/' in url_lower


def _is_file_in_folder_url(url: str) -> bool:
    """Detect if a Mega URL is a file within a folder path.

    These URLs have both /folder/ and /file/ components and typically look like:
    https://mega.nz/folder/ABC#key/file/XYZ

    These URLs cannot be handled by megadl CLI tool and require pymegatools library.
    """
    url_lower = url.lower()
    return '/folder/' in url_lower and '/file/' in url_lower


async def megadl(link: str, num: int, task_ctx=None) -> bool:
    global BotTimes, Messages, Paths, TaskError, log, TRANSFER

    intended_filename = "Unknown Mega File"

    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.task_error
        _transfer = task_ctx.transfer
        _bot_times = task_ctx.bot_times
        log.info(f"megadl() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _bot_times = BotTimes
        log.info("megadl() using global state (single-task mode)")

    log.info(f"Starting Mega download for link index {num}")
    _bot_times.task_start = datetime.now()

    is_folder_url = _is_folder_url(link)
    is_file_in_folder = _is_file_in_folder_url(link)

    if is_folder_url:
        log.info(f"Detected folder-type Mega URL: {link}")
    if is_file_in_folder:
        log.info(f"Detected file-within-folder Mega URL: {link}")

    # For folder URLs or file-within-folder URLs, skip ALL CLI tools and use pymegatools library directly
    # CLI tools like megadl cannot handle these URL formats properly
    if is_folder_url or is_file_in_folder:
        if is_folder_url:
            log.info("Folder URL detected. Skipping CLI tools and using pymegatools library (may handle folder URLs better)...")
        else:
            log.info("File-within-folder URL detected. Skipping CLI tools (megadl doesn't support this format) and using pymegatools library...")
        executable = None
        use_megadl = False
        use_megatools_dl = False
    else:
        # For direct file URLs, try to find CLI tools
        executable = os.getenv("MEGATOOLS_EXECUTABLE") or os.getenv("MEGATOOLS_BIN")
        use_megadl = False
        use_megatools_dl = False

        if executable:
            if not (os.path.isfile(executable) and os.access(executable, os.X_OK)):
                log.warning(f"MEGATOOLS_EXECUTABLE set but not usable: {executable}")
                executable = None
            else:
                basename = os.path.basename(executable).lower()
                if basename.startswith("megadl"):
                    use_megadl = True
                    log.info(f"Using megadl executable: {executable}")
                elif basename == "megatools":
                    use_megatools_dl = True
                    log.info(f"Using megatools executable: {executable}")

        if not executable:
            # For direct file URLs, prefer megadl for simplicity
            system_megadl = shutil.which("megadl")
            if system_megadl:
                executable = system_megadl
                use_megadl = True
                log.info(f"Using system megadl: {executable}")
            else:
                # Try other megatools commands
                system_megatools = shutil.which("megatools")
                if system_megatools:
                    executable = system_megatools
                    use_megatools_dl = True
                    log.info(f"Using system megatools: {executable}")

    def _pick_downloaded_file(before_files):
        try:
            after_files = [
                f for f in os.listdir(_paths.down_path)
                if os.path.isfile(os.path.join(_paths.down_path, f))
            ]
        except OSError:
            return None

        new_files = [f for f in after_files if f not in before_files]
        candidates = new_files if new_files else after_files
        if not candidates:
            return None
        return max(candidates, key=lambda f: os.path.getmtime(os.path.join(_paths.down_path, f)))

    if use_megadl or use_megatools_dl:
        tool_name = "megadl" if use_megadl else "megatools"
        _messages.status_head = f"<b>DOWNLOADING FROM MEGA</b>\n\n<code>Link {str(num).zfill(2)}</code>\n"
        before_files = set()
        try:
            before_files = {
                f for f in os.listdir(_paths.down_path)
                if os.path.isfile(os.path.join(_paths.down_path, f))
            }
        except OSError:
            pass

        # Build command variants based on the tool
        if use_megatools_dl:
            # megatools uses: megatools dl --path <dir> <url>
            variants = [
                {"cmd": [executable, "dl", "--path", _paths.down_path, link], "cwd": None},
                {"cmd": [executable, "dl", f"--path={_paths.down_path}", link], "cwd": None},
            ]
        else:
            # megadl uses: megadl --path <dir> <url> or megadl <url> (in target dir)
            variants = [
                {"cmd": [executable, "--path", _paths.down_path, link], "cwd": None},
                {"cmd": [executable, f"--path={_paths.down_path}", link], "cwd": None},
                {"cmd": [executable, link], "cwd": _paths.down_path},
            ]

        last_stdout = ""
        last_stderr = ""
        last_returncode = None

        for i, variant in enumerate(variants):
            log.debug(f"Trying {tool_name} variant {i+1}/{len(variants)}: {' '.join(variant['cmd'])}")
            proc = subprocess.run(variant["cmd"], capture_output=True, text=True, cwd=variant["cwd"])
            last_stdout = proc.stdout or ""
            last_stderr = proc.stderr or ""
            last_returncode = proc.returncode

            downloaded_name = _pick_downloaded_file(before_files)
            if downloaded_name:
                _transfer.successful_downloads.append({'url': link, 'filename': downloaded_name})
                log.info(f"{tool_name} download complete: {downloaded_name}")
                return True

            if proc.returncode == 0 and "unrecognized" not in (proc.stderr or "").lower():
                break

        # Build error message
        error_reason = (last_stderr or last_stdout or f"{tool_name} failed").strip()
        if not error_reason:
            error_reason = f"{tool_name} finished but no output file detected (exit {last_returncode})"

        # Add context for folder URLs
        if is_folder_url:
            error_reason = f"{error_reason} (Note: This is a folder URL which may not be supported by {tool_name})"

        failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason[:200]}
        if _task_error: _task_error.failed_links.append(failed_info)
        log.error(f"{tool_name} failed for link {num}: {error_reason}")
        return False

    if not executable:
        if is_folder_url:
            log.info("Attempting pymegatools library for folder URL (may handle folder links better than CLI tools)")
        else:
            log.warning("No megatools/megadl CLI binary found; falling back to pymegatools library (may have issues)")

        # Try to use pymegatools library as last resort (or primary for folder URLs)
        mega = Megatools()
        success = False
        try:
            _messages.download_name = ""

            async def progress_cb(stream, process):
                await pro_for_mega(stream, process, task_ctx)

            await mega.async_download(link, progress=progress_cb, path=_paths.down_path)

            intended_filename = _messages.download_name or intended_filename

            final_filename = _messages.download_name or "Unknown Mega Download"
            if not final_filename.startswith("Unknown"):
                if os.path.exists(os.path.join(_paths.down_path, final_filename)):
                    _transfer.successful_downloads.append({'url': link, 'filename': final_filename})
                    success = True
                else:
                    log.error(f"Mega download finished for {link} but output file '{final_filename}' not found.")
                    failed_info = {"link": link, "filename": final_filename, "index": num, "reason": "Output file not found post-download"}
                    if _task_error: _task_error.failed_links.append(failed_info)
                    success = False
            else:
                log.warning(f"Mega download finished for link {num}, but filename is unknown. Cannot confirm success.")
                failed_info = {"link": link, "filename": "Unknown", "index": num, "reason": "Could not determine filename"}
                if _task_error: _task_error.failed_links.append(failed_info)
                success = False

        except MegaError as e:
            error_reason = f"MegaError: {e}"
            log.error(f"An Error occurred during Mega download for link {num}: {error_reason}")

            if is_folder_url:
                error_reason += ". Folder URLs may not be supported. Try using the direct file link instead."

            failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason[:250]}
            if _task_error: _task_error.failed_links.append(failed_info)
            success = False
        except OSError as e:
            # errno 8 = Exec format error (binary download is broken/HTML)
            if getattr(e, "errno", None) == 8 or "Exec format error" in str(e):
                log.error(f"pymegatools binary download failed. Attempting to install system megatools package...")

                # Try to install system megatools as fallback
                try:
                    log.info("Running: apt-get update && apt-get install -y megatools")
                    install_result = subprocess.run(
                        "apt-get update && apt-get install -y megatools",
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=120
                    )

                    if install_result.returncode == 0:
                        log.info("Successfully installed system megatools package.")

                        # Check if megatools is now available
                        megatools_path = shutil.which("megatools")
                        if megatools_path:
                            log.info(f"System megatools found at {megatools_path}. Retrying download with CLI tool...")

                            # Retry with megatools CLI - use recursive call with environment variable set
                            os.environ["MEGATOOLS_EXECUTABLE"] = megatools_path
                            return await megadl(link, num, task_ctx)
                        else:
                            log.warning("megatools installed but not found in PATH")
                    else:
                        log.error(f"Failed to install megatools: {install_result.stderr}")

                except Exception as install_err:
                    log.error(f"Error installing megatools: {install_err}")

                error_reason = "pymegatools binary download failed (404/HTML). Tried to install system megatools but failed"
                if is_folder_url or is_file_in_folder:
                    error_reason += ". For folder/file-in-folder URLs, try converting to direct file link format."
            else:
                error_reason = f"OS error: {str(e)[:100]}"
                log.error(f"Unexpected OS error during Mega download {link}: {error_reason}", exc_info=True)
                if is_folder_url or is_file_in_folder:
                    error_reason += ". Folder URLs may require special handling."

            failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason[:250]}
            if _task_error: _task_error.failed_links.append(failed_info)
            success = False
        except Exception as e:
            error_reason = f"Unexpected Mega Error: {str(e)[:100]}"
            log.error(f"Unexpected error during Mega download {link}: {e}", exc_info=True)

            if is_folder_url:
                error_reason += ". Folder URLs may not be supported. Try converting to direct file link."

            failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason[:250]}
            if _task_error: _task_error.failed_links.append(failed_info)
            success = False

        return success

    # Use pymegatools with the found executable
    mega = Megatools(executable=executable)
    success = False
    try:
        _messages.download_name = ""

        async def progress_cb(stream, process):
            await pro_for_mega(stream, process, task_ctx)

        await mega.async_download(link, progress=progress_cb, path=_paths.down_path)

        intended_filename = _messages.download_name or intended_filename

        final_filename = _messages.download_name or "Unknown Mega Download"
        if not final_filename.startswith("Unknown"):
            if os.path.exists(os.path.join(_paths.down_path, final_filename)):
                _transfer.successful_downloads.append({'url': link, 'filename': final_filename})
                success = True
            else:
                log.error(f"Mega download finished for {link} but output file '{final_filename}' not found.")
                failed_info = {"link": link, "filename": final_filename, "index": num, "reason": "Output file not found post-download"}
                if _task_error: _task_error.failed_links.append(failed_info)
                success = False
        else:
            log.warning(f"Mega download finished for link {num}, but filename is unknown. Cannot confirm success.")
            failed_info = {"link": link, "filename": "Unknown", "index": num, "reason": "Could not determine filename"}
            if _task_error: _task_error.failed_links.append(failed_info)
            success = False

    except MegaError as e:
        error_reason = f"MegaError: {e}"
        log.error(f"An Error occurred during Mega download for link {num}: {error_reason}")

        if is_folder_url:
            error_reason += ". Folder URLs may not be supported. Try using the direct file link instead."

        failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason[:250]}
        if _task_error: _task_error.failed_links.append(failed_info)
        success = False
    except OSError as e:
        # errno 8 = Exec format error (binary download is broken/HTML)
        if getattr(e, "errno", None) == 8 or "Exec format error" in str(e):
            error_reason = "pymegatools binary download failed (404/HTML). Install system megatools: apt-get install megatools"
            log.error(f"pymegatools binary download is broken. Install system megatools: {error_reason}")
            if is_folder_url:
                error_reason += ". For folder URLs, try converting to direct file link format."
        else:
            error_reason = f"OS error: {str(e)[:100]}"
            log.error(f"Unexpected OS error during Mega download {link}: {error_reason}", exc_info=True)
            if is_folder_url:
                error_reason += ". Folder URLs may require special handling."

        failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason[:250]}
        if _task_error: _task_error.failed_links.append(failed_info)
        success = False
    except Exception as e:
        error_reason = f"Unexpected Mega Error: {str(e)[:100]}"
        log.error(f"Unexpected error during Mega download {link}: {e}", exc_info=True)

        if is_folder_url:
            error_reason += ". Folder URLs may not be supported. Try converting to direct file link."

        failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason[:250]}
        if _task_error: _task_error.failed_links.append(failed_info)
        success = False

    return success

async def pro_for_mega(stream, process, task_ctx=None):
    global Messages, BotTimes
    if task_ctx:
        _messages = task_ctx.messages
        log.info(f"pro_for_mega() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _messages = Messages

    line = stream[-1]
    file_name = "N/A"
    percentage = 0
    downloaded_size = "N/A"
    total_size = "N/A"
    speed = "N/A"
    eta = "Unknown"  
    try:
        ok = line.split(":")
        file_name = ok[0]
        ok = ok[1].split()
        percentage = float(ok[0][:-1])
        downloaded_size = ok[2] + " " + ok[3]
        total_size = ok[7] + " " + ok[8]
        speed = ok[9][1:] + " " + ok[10][:-1]

        remaining_bytes = float(ok[7]) - float(ok[2])
        bytes_per_second = float(ok[9][1:]) * (1024 if ok[10][-1] == 'K' else 1)  # Convert KB/s to bytes/s if necessary
        if bytes_per_second != 0:
            remaining_seconds = remaining_bytes / bytes_per_second
            eta = getTime(remaining_seconds)

    except Exception:
        pass

    _messages.download_name = file_name
    _messages.status_head = (
        f"<b>DOWNLOADING FROM MEGA</b>\n\n"
        f"<b>Name</b> <code>{file_name}</code>\n"
    )

    await status_bar(
        _messages.status_head,
        speed,
        percentage,
        eta,
        downloaded_size,
        total_size,
        "Mega",
        task_ctx=task_ctx,
    )
