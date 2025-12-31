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

    executable = os.getenv("MEGATOOLS_EXECUTABLE") or os.getenv("MEGATOOLS_BIN")
    if executable:
        if not (os.path.isfile(executable) and os.access(executable, os.X_OK)):
            log.warning(f"MEGATOOLS_EXECUTABLE set but not usable: {executable}")
            executable = None
    if not executable:
        executable = shutil.which("megatools")
        if executable:
            log.info(f"Using system megatools: {executable}")

    mega = Megatools(executable=executable) if executable else Megatools()
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
            # Assume failure if we don't know the filename? Or success? Let's assume failure.
            failed_info = {"link": link, "filename": "Unknown", "index": num, "reason": "Could not determine filename"}
            if _task_error: _task_error.failed_links.append(failed_info)
            success = False

    except MegaError as e:
        error_reason = f"MegaError: {e}"
        log.error(f"An Error occurred during Mega download for link {num}: {error_reason}")

        failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason}
        if _task_error: _task_error.failed_links.append(failed_info)
        success = False
    except OSError as e:
        if getattr(e, "errno", None) == 8:
            error_reason = "Megatools binary invalid (Exec format). Install system megatools or set MEGATOOLS_EXECUTABLE."
        else:
            error_reason = f"OS error: {str(e)[:100]}"
        log.error(f"Unexpected error during Mega download {link}: {error_reason}", exc_info=True)

        failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason}
        if _task_error: _task_error.failed_links.append(failed_info)
        success = False
    except Exception as e:
        error_reason = f"Unexpected Mega Error: {str(e)[:100]}"
        log.error(f"Unexpected error during Mega download {link}: {e}", exc_info=True)
  
        failed_info = {"link": link, "filename": intended_filename, "index": num, "reason": error_reason}
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
