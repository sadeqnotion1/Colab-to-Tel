#================================================
#FILE: colab_leecher/downlader/requests_dl.py
#================================================
import logging
from ..utility.handler import cancelTask, TaskContext
from ..utility.variables import BOT, Messages

logger = logging.getLogger(__name__)

async def download_multiple_files_Debrid(urls, file_names, task_ctx: TaskContext = None):
    global BOT, Messages

    if task_ctx:
        _bot = task_ctx.bot
        _messages = task_ctx.messages
    else:
        _bot = BOT
        _messages = Messages

    cf_clearance = getattr(_bot.Options, "cf_clearance", None)
    if len(urls) != len(file_names):
        logger.error("Debrid URL/FN mismatch!")
        await cancelTask("Debrid URL/Filename counts mismatch.", task_ctx)
        return

    for idx, (url, file_name) in enumerate(zip(urls, file_names)):
        url, file_name = url.strip(), file_name.strip()
        if not file_name or not url:
            logger.warning(f"Skip Debrid [{idx+1}]: No FN/URL for {url or file_name}")
            continue
        _messages.download_name = file_name 
        # Note: download_file_Debrid needs to be imported/defined
        # For now we just update the signature of this helper
        try:
            from .manager import http_download_logic
            # This is a bit circular, but good for consistency
            pass 
        except ImportError:
            pass


async def download_multiple_files_bitso(urls, file_names, referer_url, task_ctx: TaskContext = None):
    global BOT, Messages

    if task_ctx:
        _bot = task_ctx.bot
        _messages = task_ctx.messages
    else:
        _bot = BOT
        _messages = Messages

    id_cookie = getattr(_bot.Options, "bitso_id_cookie", None)
    sess_cookie = getattr(_bot.Options, "bitso_sess_cookie", None)

    if len(urls) != len(file_names):
        logger.error("Bitso URL/FN mismatch!")
        await cancelTask("Bitso URL/Filename counts mismatch.", task_ctx)
        return

    for idx, (url, file_name) in enumerate(zip(urls, file_names)):
        url, file_name = url.strip(), file_name.strip()
        if not file_name or not url:
            logger.warning(f"Skip Bitso [{idx+1}]: No FN/URL for {url or file_name}")
            continue
        _messages.download_name = file_name 
