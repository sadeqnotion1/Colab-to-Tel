#================================================
#FILE: colab_leecher/downlader/ytdl.py
#================================================
import logging
import yt_dlp
from asyncio import sleep
from threading import Thread
from os import makedirs, path as ospath
from pyrogram.errors import MessageNotModified, RPCError
from colab_leecher.utility.handler import cancelTask
from colab_leecher.utility.variables import YTDL, MSG, Messages, Paths
from colab_leecher.utility.helper import getTime, keyboard, sizeUnit, status_bar, sysINFO

# Logger instance
log = logging.getLogger(__name__)


async def YTDL_Status(link, num, task_ctx=None, max_retries=3):
    """
    Download status tracker with retry logic

    Args:
        link: URL to download
        num: Link number for tracking
        max_retries: Maximum retry attempts (default: 3)
    """
    global Messages, YTDL

    for attempt in range(max_retries):
        try:
            name = await get_YT_Name(link, task_ctx)
            Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{name}</code>\n"

            if attempt > 0:
                log.info(f"Retry attempt {attempt + 1}/{max_retries} for link {num}")
                Messages.status_head += f"\n<i>⚠️ Retry attempt {attempt + 1}/{max_retries}</i>\n"

            YTDL_Thread = Thread(target=YouTubeDL, name="YouTubeDL", args=(link,))
            YTDL_Thread.start()

            while YTDL_Thread.is_alive():  # Until ytdl is downloading
                if YTDL.header:
                    sys_text = sysINFO()
                    message = YTDL.header
                    try:
                        await MSG.status_msg.edit_text(text=Messages.task_msg + Messages.status_head + message + sys_text, reply_markup=keyboard())
                    except AttributeError as status_msg_err:
                        log.debug(
                            "Skipping YTDL status edit; status message is not available",
                            extra={
                                "component": "ytdl_status",
                                "link_index": num,
                                "attempt": attempt + 1,
                                "error_type": type(status_msg_err).__name__,
                            },
                        )
                    except (MessageNotModified, RPCError, TypeError, ValueError) as status_edit_err:
                        log.debug(
                            "Skipping YTDL status edit update",
                            extra={
                                "component": "ytdl_status",
                                "link_index": num,
                                "attempt": attempt + 1,
                                "error_type": type(status_edit_err).__name__,
                            },
                        )
                else:
                    try:
                        await status_bar(
                            down_msg=Messages.status_head,
                            speed=YTDL.speed,
                            percentage=float(YTDL.percentage),
                            eta=YTDL.eta,
                            done=YTDL.done,
                            left=YTDL.left,
                            engine="Xr-YtDL 🏮",
                        )
                    except (MessageNotModified, RPCError, AttributeError, TypeError, ValueError) as status_bar_err:
                        log.debug(
                            "Skipping YTDL status_bar update",
                            extra={
                                "component": "ytdl_status",
                                "link_index": num,
                                "attempt": attempt + 1,
                                "error_type": type(status_bar_err).__name__,
                            },
                        )

                await sleep(2.5)

            # Download completed successfully
            log.info(f"✅ YTDL download completed for link {num}")
            break  # Exit retry loop on success

        except yt_dlp.utils.DownloadError as e:
            if attempt < max_retries - 1:
                log.warning(f"Download failed (attempt {attempt + 1}/{max_retries}): {e}")
                await sleep(5)  # Wait 5 seconds before retry
            else:
                log.error(f"Download failed after {max_retries} attempts: {e}")
                await cancelTask(f"Download failed after {max_retries} attempts: {str(e)[:100]}", task_ctx)

        except Exception as e:
            log.error(f"Unexpected error in YTDL_Status: {e}", exc_info=True)
            await cancelTask(f"YouTube download error: {str(e)[:100]}", task_ctx)
            break  # Don't retry on unexpected errors


class MyLogger:
    def __init__(self):
        pass

    def debug(self, msg):
        global YTDL
        if "item" in str(msg):
            msgs = msg.split(" ")
            YTDL.header = f"\n⏳ __Getting Video Information {msgs[-3]} of {msgs[-1]}__"

    @staticmethod
    def warning(msg):
        pass

    @staticmethod
    def error(msg):
        # if msg != "ERROR: Cancelling...":
        # print(msg)
        pass


def YouTubeDL(url):
    global YTDL

    def my_hook(d):
        global YTDL

        if d["status"] == "downloading":
            total_bytes = d.get("total_bytes", 0)  # Use 0 as default if total_bytes is None
            dl_bytes = d.get("downloaded_bytes", 0)
            percent = d.get("downloaded_percent", 0)
            speed = d.get("speed", "N/A")
            eta = d.get("eta", 0)

            if total_bytes:
                percent = round((float(dl_bytes) * 100 / float(total_bytes)), 2)

            YTDL.header = ""
            YTDL.speed = sizeUnit(speed) if speed else "N/A"
            YTDL.percentage = percent
            YTDL.eta = getTime(eta) if eta else "N/A"
            YTDL.done = sizeUnit(dl_bytes) if dl_bytes else "N/A"
            YTDL.left = sizeUnit(total_bytes) if total_bytes else "N/A"

        elif d["status"] == "downloading fragment":
            # log_str = d["message"]
            # print(log_str, end="")
            pass
        else:
            logging.info(d)

    # Check for curl_cffi availability for impersonation
    try:
        import curl_cffi
        has_impersonate = True
    except ImportError:
        has_impersonate = False

    ydl_opts = {
        # Format selection - better quality/size balance with MP4 preference
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",

        # Browser Impersonation - Bypasses bot detection (requires curl_cffi)
        "impersonate": "chrome" if has_impersonate else None,

        # Cookies - Load automatically if file exists
        "cookiefile": "cookies.txt" if ospath.exists("cookies.txt") else None,

        # Extractor Tuning - Fixes for specific sites like TikTok
        "extractor_args": {
            "tiktok": {"webpage_download": True},
            "youtube": {"skip": ["hls", "dash"]}
        },

        # Performance improvements
        "concurrent_fragment_downloads": 10,
        "http_chunk_size": 10485760,  # 10MB chunks for better speed
        "updatetime": False,         # Equivalent to --no-mtime

        # Retry configuration for reliability
        "retries": 10,
        "fragment_retries": 10,
        "skip_unavailable_fragments": True,
        "ignoreerrors": True,        # Don't crash entire batch on one error
        "no_abort_on_error": True,

        # Persistence - Avoid re-downloading same files
        "download_archive": "downloaded_archive.txt",

        # Subtitle improvements
        "writesubtitles": True,
        "writeautomaticsub": True,  # Auto-download auto-generated subs
        "subtitleslangs": ["en", "ar"],  # Configurable languages
        "subtitlesformat": "srt/best",

        # Thumbnail and metadata
        "writethumbnail": True,
        "embedthumbnail": True,  # Embed in video file
        "addmetadata": True,
        "embedmetadata": True,

        # Stream options
        "allow_multiple_video_streams": True,
        "allow_multiple_audio_streams": True,
        "allow_playlist_files": True,

        # Post-processing
        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail", "already_have_thumbnail": False}
        ],

        # Overwrite and hooks
        "overwrites": True,
        "progress_hooks": [my_hook],
        "logger": MyLogger(),
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        if not ospath.exists(Paths.thumbnail_ytdl):
            makedirs(Paths.thumbnail_ytdl)
        try:
            info_dict = ydl.extract_info(url, download=False)
            YTDL.header = "⌛ __Please WAIT a bit...__"
            
            # Sophisticated Output Template for better organization
            # Format: extractor/uploader/date_title_id.ext
            template_str = f"{Paths.down_path}/%(extractor_key,unknown_site)s/%(uploader,unknown_uploader)s/%(upload_date>%Y-%m-%d,unknown_date)s_%(title,id)s.%(ext)s"
            
            if "_type" in info_dict and info_dict["_type"] == "playlist":
                playlist_name = info_dict["title"] 
                if not ospath.exists(ospath.join(Paths.down_path, playlist_name)):
                    makedirs(ospath.join(Paths.down_path, playlist_name))
                ydl_opts["outtmpl"] = {
                    "default": template_str,
                    "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                }
                for entry in info_dict["entries"]:
                    video_url = entry["webpage_url"]
                    try:
                        ydl.download([video_url])
                    except yt_dlp.utils.DownloadError as e:
                        if e.exc_info[0] == 36:
                            ydl_opts["outtmpl"] = {
                                "default": f"{Paths.down_path}/%(id)s.%(ext)s",
                                "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                            }
                            ydl.download([video_url])
            else:
                YTDL.header = ""
                ydl_opts["outtmpl"] = {
                    "default": template_str,
                    "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                }
                try:
                    ydl.download([url])
                except yt_dlp.utils.DownloadError as e:
                    if e.exc_info[0] == 36:
                        ydl_opts["outtmpl"] = {
                            "default": f"{Paths.down_path}/%(id)s.%(ext)s",
                            "thumbnail": f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s",
                        }
                        ydl.download([url])
        except Exception as e:
            logging.error(f"YTDL ERROR: {e}")


async def get_YT_Name(link, task_ctx=None):
    with yt_dlp.YoutubeDL({"logger": MyLogger()}) as ydl:
        try:
            info = ydl.extract_info(link, download=False)
            if "title" in info and info["title"]: 
                return info["title"]
            else:
                return "UNKNOWN DOWNLOAD NAME"
        except Exception as e:
            await cancelTask(f"Can't Download from this link. Because: {str(e)}", task_ctx)
            return "UNKNOWN DOWNLOAD NAME"
