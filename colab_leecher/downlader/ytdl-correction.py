#================================================
#FILE: colab_leecher/downloader/ytdl.py
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

log = logging.getLogger(__name__)


async def YTDL_Status(link, num, task_ctx=None, max_retries=3):
    global Messages, YTDL

    for attempt in range(max_retries):
        try:
            name = await get_YT_Name(link, task_ctx)
            from ..utility.message_safety import escape_html
            Messages.status_head = f"<b>📥 DOWNLOADING FROM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{escape_html(name)}</code>\n"

            if attempt > 0:
                log.info(f"Retry attempt {attempt + 1}/{max_retries} for link {num}")
                Messages.status_head += f"\n<i>⚠️ Retry attempt {attempt + 1}/{max_retries}</i>\n"

            YTDL.task_ctx = task_ctx
            YTDL_Thread = Thread(target=YouTubeDL, name="YouTubeDL", args=(link,))
            YTDL_Thread.start()

            while YTDL_Thread.is_alive():
                if YTDL.header:
                    sys_text = sysINFO()
                    message = YTDL.header
                    try:
                        await MSG.status_msg.edit_text(text=Messages.task_msg + Messages.status_head + message + sys_text, reply_markup=keyboard())
                    except AttributeError:
                        log.debug("Skipping YTDL status edit; status message is not available")
                    except (MessageNotModified, RPCError, TypeError, ValueError):
                        log.debug("Skipping YTDL status edit update")
                else:
                    try:
                        await status_bar(
                            down_msg=Messages.status_head,
                            speed=YTDL.speed,
                            percentage=float(YTDL.percentage),
                            eta=YTDL.eta,
                            done=YTDL.done,
                            total_size=YTDL.left,
                            engine="Xr-YtDL 🏮",
                        )
                    except (MessageNotModified, RPCError, AttributeError, TypeError, ValueError):
                        log.debug("Skipping YTDL status_bar update")

                await sleep(2.5)

            log.info(f"YTDL download completed for link {num}")
            break

        except yt_dlp.utils.DownloadError as e:
            if attempt < max_retries - 1:
                log.warning(f"Download failed (attempt {attempt + 1}/{max_retries}): {e}")
                await sleep(5)
            else:
                log.error(f"Download failed after {max_retries} attempts: {e}")
                await cancelTask(f"Download failed after {max_retries} attempts: {str(e)[:100]}", task_ctx)

        except Exception as e:
            log.error(f"Unexpected error in YTDL_Status: {e}", exc_info=True)
            await cancelTask(f"YouTube download error: {str(e)[:100]}", task_ctx)
            break
        finally:
            if hasattr(YTDL, "task_ctx"):
                YTDL.task_ctx = None


class MyLogger:
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
        pass


class SilentLogger:
    def debug(self, msg): pass
    def warning(self, msg): pass
    def error(self, msg): pass


has_impersonate = False
try:
    import curl_cffi
    has_impersonate = True
except ImportError:
    has_impersonate = False


def _build_ydl_opts(output_template):
    opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,

        "extractor_args": {
            "tiktok": {"webpage_download": True},
            "youtube": {"player_client": ["web", "tv"]},
        },
        "remote_components": "ejs:github",

        "concurrent_fragment_downloads": 10,
        "http_chunk_size": 10485760,
        "updatetime": False,

        "retries": 10,
        "fragment_retries": 10,
        "skip_unavailable_fragments": True,
        "ignoreerrors": True,
        "no_abort_on_error": True,

        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": ["en", "ar"],
        "subtitlesformat": "srt/best",

        "writethumbnail": True,
        "embedthumbnail": True,
        "addmetadata": True,
        "embedmetadata": True,

        "allow_multiple_video_streams": True,
        "allow_multiple_audio_streams": True,
        "allow_playlist_files": True,

        "postprocessors": [
            {"key": "FFmpegVideoConvertor", "preferedformat": "mp4"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail", "already_have_thumbnail": False},
        ],

        "overwrites": True,
        "progress_hooks": [lambda d: _progress_hook(d)],
        "logger": MyLogger(),
    }

    if has_impersonate:
        opts["impersonate"] = "chrome"

    cookie_file = "cookies.txt"
    if ospath.exists(cookie_file):
        opts["cookiefile"] = cookie_file

    return opts


def _progress_hook(d):
    global YTDL

    if d["status"] == "downloading":
        total_bytes = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
        dl_bytes = d.get("downloaded_bytes", 0)
        speed = d.get("speed")
        eta = d.get("eta")

        if total_bytes:
            percent = round((dl_bytes * 100 / total_bytes), 2)
        else:
            percent = d.get("downloaded_percent", 0)

        YTDL.header = ""
        YTDL.speed = sizeUnit(speed) if speed else "N/A"
        YTDL.percentage = percent
        YTDL.eta = getTime(eta) if eta else "N/A"
        YTDL.done = sizeUnit(dl_bytes) if dl_bytes else "N/A"
        YTDL.left = sizeUnit(total_bytes) if total_bytes else "N/A"

        # >>> ADD: feed the unified pipeline with RAW bytes <<<
        task_ctx = getattr(YTDL, "task_ctx", None)
        if task_ctx is not None:
            try:
                task_ctx.transfer.update_progress(
                    int(dl_bytes),
                    int(total_bytes) if total_bytes else None,
                )
            except Exception:
                pass

    elif d["status"] == "finished":
        log.info(f"Finished downloading: {d.get('filename', 'unknown')}")


def YouTubeDL(url):
    global YTDL

    if not ospath.exists(Paths.thumbnail_ytdl):
        makedirs(Paths.thumbnail_ytdl)

    base_template = f"{Paths.down_path}/%(extractor_key,unknown_site)s/%(uploader,unknown_uploader)s/%(upload_date>%Y-%m-%d,unknown_date)s_%(title,id)s.%(ext)s"
    fallback_template = f"{Paths.down_path}/%(id)s.%(ext)s"
    thumb_template = f"{Paths.thumbnail_ytdl}/%(id)s.%(ext)s"

    ydl_opts = _build_ydl_opts(base_template)
    ydl_opts["outtmpl"] = {
        "default": base_template,
        "thumbnail": thumb_template,
    }

    try:
        ydl = yt_dlp.YoutubeDL(ydl_opts)
    except Exception as e:
        log.warning(f"Failed to init yt-dlp: {e}. Retrying without impersonation.")
        ydl_opts.pop("impersonate", None)
        ydl = yt_dlp.YoutubeDL(ydl_opts)

    with ydl:
        try:
            info_dict = ydl.extract_info(url, download=False)
            YTDL.header = "⌛ __Please WAIT a bit...__"

            if info_dict and info_dict.get("_type") == "playlist":
                playlist_name = info_dict.get("title", "playlist")
                playlist_dir = ospath.join(Paths.down_path, playlist_name)
                if not ospath.exists(playlist_dir):
                    makedirs(playlist_dir)

                for entry in info_dict.get("entries", []):
                    if not entry:
                        continue
                    video_url = entry.get("webpage_url") or entry.get("url")
                    if not video_url:
                        continue

                    entry_opts = _build_ydl_opts(fallback_template)
                    entry_opts["outtmpl"] = {
                        "default": f"{playlist_dir}/%(title,id)s.%(ext)s",
                        "thumbnail": thumb_template,
                    }
                    entry_opts["progress_hooks"] = ydl_opts["progress_hooks"]
                    entry_opts["logger"] = ydl_opts["logger"]

                    try:
                        with yt_dlp.YoutubeDL(entry_opts) as entry_ydl:
                            entry_ydl.download([video_url])
                    except yt_dlp.utils.DownloadError as e:
                        log.warning(f"Playlist item failed: {e}. Retrying with fallback template.")
                        entry_opts["outtmpl"]["default"] = fallback_template
                        try:
                            with yt_dlp.YoutubeDL(entry_opts) as entry_ydl:
                                entry_ydl.download([video_url])
                        except Exception as e2:
                            log.error(f"Playlist item failed again: {e2}")
            else:
                YTDL.header = ""
                try:
                    ydl.download([url])
                except yt_dlp.utils.DownloadError as e:
                    log.warning(f"Download failed: {e}. Retrying with fallback template.")
                    ydl_opts["outtmpl"]["default"] = fallback_template
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                        ydl2.download([url])

        except Exception as e:
            log.error(f"YTDL ERROR: {e}")


async def get_YT_Name(link, task_ctx=None):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": SilentLogger(),
    }
    if has_impersonate:
        ydl_opts["impersonate"] = "chrome"
    if ospath.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"

    try:
        ydl = yt_dlp.YoutubeDL(ydl_opts)
    except Exception as e:
        log.warning(f"Failed to init yt-dlp in get_YT_Name: {e}. Retrying without impersonation.")
        ydl_opts.pop("impersonate", None)
        ydl = yt_dlp.YoutubeDL(ydl_opts)

    with ydl:
        try:
            info = ydl.extract_info(link, download=False)
            if info and info.get("title"):
                return info["title"]
            return "UNKNOWN DOWNLOAD NAME"
        except Exception as e:
            await cancelTask(f"Can't Download from this link. Because: {str(e)}", task_ctx)
            return "UNKNOWN DOWNLOAD NAME"
