#================================================
#FILE: colab_leecher/downlader/telegram.py
#================================================
import logging
import os 
from datetime import datetime
from .. import colab_bot 
from ..utility.handler import cancelTask, TaskContext
from ..utility.variables import Paths, Messages, BotTimes, TRANSFER, MSG, TaskError
from ..utility.helper import speedETA, getTime, sizeUnit, status_bar, getSize, clean_filename 
import time

# Setup logger
log = logging.getLogger(__name__)

async def media_Identifier(link, task_ctx: TaskContext = None):
    """Identifies the media message and object from a Telegram link."""
    parts = link.split("/")
    message_id = None; msg_chat_id = None
    try:
        if '/c/' in link: # Channel/supergroup links
             channel_id = parts[-2]
             if not channel_id.startswith("1"): msg_chat_id = parts[-2] # Public?
             else: msg_chat_id = int("-100" + channel_id)
             message_id = int(parts[-1])
        elif len(parts) >= 5: msg_chat_id = parts[-2]; message_id = int(parts[-1]) # Public?
        else: 
            log.error(f"Could not parse TG link: {link}")
            await cancelTask(f"Invalid TG link format: {link}", task_ctx)
            return None, None
    except (ValueError, IndexError) as e: 
        log.error(f"Error parsing TG link {link}: {e}")
        await cancelTask(f"Invalid TG link format: {link}", task_ctx)
        return None, None

    message = None
    try:
        message = await colab_bot.get_messages(msg_chat_id, message_id)
        log.info(f"Retrieved message {message_id} from chat {msg_chat_id}")
    except Exception as e:
        log.error(f"Error getting message {message_id} from {msg_chat_id}: {e}", exc_info=True); reason = str(e)
        if "CHAT_ID_INVALID" in reason or "PEER_ID_INVALID" in reason: reason = f"Chat ID '{msg_chat_id}' invalid/inaccessible."
        elif "MESSAGE_ID_INVALID" in reason: reason = f"Message ID '{message_id}' invalid in chat '{msg_chat_id}'."
        await cancelTask(f"Could not get TG message: {reason}", task_ctx)
        return None, None

    if message:
        media = message.document or message.photo or message.video or message.audio or message.voice or message.video_note or message.sticker or message.animation or None
        if media is None: 
            log.error(f"Msg {message_id} has no media.")
            await cancelTask("Msg has no media.", task_ctx)
            return None, message
        else: 
            log.debug(f"Media identified: Type={type(media).__name__}")
            return media, message
    else: return None, None


async def TelegramDownload(link, num, task_ctx: TaskContext = None) -> bool:
    global TRANSFER, BotTimes, Messages, Paths, TaskError, log
    
    if task_ctx:
        _paths = task_ctx.paths
        _messages = task_ctx.messages
        _task_error = task_ctx.error
        _transfer = task_ctx.transfer
        _bot_times = task_ctx.bot_times
        log.info(f"TelegramDownload() using TaskContext for task_id: {task_ctx.task_id}")
    else:
        _paths = Paths
        _messages = Messages
        _task_error = TaskError
        _transfer = TRANSFER
        _bot_times = BotTimes
        log.info("TelegramDownload() using global state")

    media, message = await media_Identifier(link, task_ctx)
    if media is None or message is None:
        log.error(f"Failed identify media for link {link}.")
        failed_info = {"link": link, "filename": "Unknown (Media Identify Fail)", "index": num, "reason": "Failed to identify media"}
        _task_error.failed_links.append(failed_info)
        return False

    name = "Unknown_Telegram_File"
    if hasattr(media, "file_name") and media.file_name: name = media.file_name
    elif hasattr(media, "mime_type") and media.mime_type: ext = media.mime_type.split('/')[-1] or 'bin'; name = f"telegram_{media.file_id or message.id}.{ext}"
    name = clean_filename(name)

    file_size = 0
    if hasattr(media, "file_size") and media.file_size: file_size = media.file_size
    else: log.warning(f"Could not get file size for msg {message.id}")

    _messages.status_head = (
        f"<b>DOWNLOADING FROM TG</b> <i>Link {str(num).zfill(2)}</i>\n\n"
        f"<code>{name}</code>\n"
    )
    log.info(f"Starting TG download: {name} (Size: {sizeUnit(file_size)})")
    os.makedirs(_paths.down_path, exist_ok=True)
    file_path = os.path.join(_paths.down_path, name)

    download_successful = False
    try:
        _bot_times.task_start = datetime.now()
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        async def progress(current, total):
            upload_speed = 0
            if isinstance(_bot_times.task_start, datetime):
                elapsed_time_seconds = (datetime.now() - _bot_times.task_start).seconds
            else:
                elapsed_time_seconds = 0

            current_overall = sum(_transfer.down_bytes) + current

            if current_overall > 0 and elapsed_time_seconds > 0:
                try:
                    upload_speed = current_overall / elapsed_time_seconds
                except ZeroDivisionError:
                    upload_speed = 0

            eta = float('inf')
            display_total = _transfer.total_down_size if _transfer.total_down_size > 0 else total

            remaining_bytes = display_total - current_overall
            if upload_speed > 0 and remaining_bytes > 0:
                try:
                    eta = remaining_bytes / upload_speed
                except ZeroDivisionError:
                    eta = float('inf')

            percentage = 0.0
            if display_total > 0:
                percentage = min(100.0, (current_overall / display_total) * 100)

            speed_string = sizeUnit(upload_speed) + "/s" if upload_speed > 0 else "N/A"

            try:
                formatted_eta_str = getTime(eta)
                await status_bar(
                    down_msg=_messages.status_head,
                    speed=speed_string,
                    percentage=percentage,
                    eta=formatted_eta_str,
                    done=sizeUnit(current_overall),
                    total_size=sizeUnit(display_total),
                    engine="Pyrogram 💥",
                    task_ctx=task_ctx
                )
            except Exception as e:
                log.warning(f"download_progress: Failed to call status_bar: {e}")

        await message.download(progress=progress, in_memory=False, file_name=file_path)
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            log.error(f"Pyrogram download finished for {name} but file is missing or empty.")
            raise Exception("Downloaded file missing or empty")

        download_successful = True
        log.info(f"Finished TG download: {name}")
    except Exception as e:
        error_reason = f"TG Download Error: {str(e)[:100]}"
        log.error(f"Error downloading TG file {name}: {e}", exc_info=True)
        failed_info = {"link": link, "filename": name, "index": num, "reason": error_reason}
        _task_error.failed_links.append(failed_info)
        try:
            if os.path.exists(file_path): os.remove(file_path)
        except OSError as cl_err: log.warning(f"Failed cleanup TG file {file_path}: {cl_err}")
        download_successful = False

    if download_successful:
        actual_size = file_size if file_size > 0 else getSize(file_path) if os.path.exists(file_path) else 0
        _transfer.down_bytes.append(actual_size)
        _transfer.successful_downloads.append({'url': link, 'filename': name})
        return True
    else:
        return False
