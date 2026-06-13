#================================================
#FILE: colab_leecher/downlader/ytdl.py
#================================================
import logging
import os
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

            YTDL_Thread = Thread(target=YouTubeDL, name="YouTubeDL", args=(link, task_ctx))
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

            # Check outcome from the task_ctx metadata
            res = task_ctx.metadata.get("ytdl_results", {}).get(link, {}) if task_ctx else {}
            if not res.get("success", False):
                error_msg = res.get("error", "Unknown YTDL error")
                raise yt_dlp.utils.DownloadError(error_msg)

            log.info(f"YTDL download completed for link {num}")
            break

        except Exception as e:
            err_str = str(e)
            hint = ""
            lower_err = err_str.lower()
            if any(term in lower_err for term in ["sign in to confirm", "confirm you're not a bot", "format is not available", "403", "forbidden", "player response", "bot"]):
                hint = " [HINT: YouTube is blocking this request. Please supply a fresh cookies.txt file and/or update yt-dlp]"
            final_err = f"{err_str}{hint}"

            if attempt < max_retries - 1:
                log.warning(f"Download failed (attempt {attempt + 1}/{max_retries}): {final_err}")
                if task_ctx:
                    task_ctx.error.state = False
                    task_ctx.error.text = ""
                await sleep(5)
            else:
                log.error(f"Download failed after {max_retries} attempts: {final_err}")
                if task_ctx:
                    task_ctx.error.state = True
                    task_ctx.error.text = final_err
                break


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
    import shutil
    if shutil.which("deno") is None:
        log.warning("⚠️ WARNING: 'deno' executable was not found on PATH! The 'ejs:github' solver requires Deno to run. Downloads may fail with 'DRM protected' or format errors.")

    opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,

        "extractor_args": {
            "tiktok": {"webpage_download": True},
        },
        "remote_components": "ejs:github",

        "concurrent_fragment_downloads": 10,
        "http_chunk_size": 10485760,
        "updatetime": False,

        "retries": 10,
        "fragment_retries": 10,
        "skip_unavailable_fragments": True,
        "ignoreerrors": False,
        "no_abort_on_error": False,

        "writesubtitles": True,
        "writeautomaticsub": False,
        "subtitleslangs": ["en", "ar"],
        "subtitlesformat": "srt/best",
        "sleep_interval_subtitles": 3,   # throttle subtitle requests to avoid HTTP 429

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

    elif d["status"] == "finished":
        log.info(f"Finished downloading: {d.get('filename', 'unknown')}")


def YouTubeDL(url, task_ctx=None):
    global YTDL

    down_path = task_ctx.paths.down_path if task_ctx else Paths.down_path
    thumbnail_ytdl = task_ctx.paths.thumbnail_ytdl if task_ctx else Paths.thumbnail_ytdl

    if not ospath.exists(thumbnail_ytdl):
        makedirs(thumbnail_ytdl)

    def get_files_in_dir(directory):
        files = set()
        if ospath.exists(directory):
            for root, _, filenames in os.walk(directory):
                for f in filenames:
                    files.add(ospath.join(root, f))
        return files

    files_before = get_files_in_dir(down_path)

    # Initialize results dict in metadata
    result = {"success": False, "error": "Unknown error", "files": []}
    if task_ctx:
        if "ytdl_results" not in task_ctx.metadata:
            task_ctx.metadata["ytdl_results"] = {}
        task_ctx.metadata["ytdl_results"][url] = result

    base_template = f"{down_path}/%(extractor_key,unknown_site)s/%(uploader,unknown_uploader)s/%(upload_date>%Y-%m-%d,unknown_date)s_%(title,id)s.%(ext)s"
    fallback_template = f"{down_path}/%(id)s.%(ext)s"
    thumb_template = f"{thumbnail_ytdl}/%(id)s.%(ext)s"

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
                    # For playlists, keep ignoreerrors / no_abort_on_error to True so one failing item doesn't crash the whole run
                    entry_opts["ignoreerrors"] = True
                    entry_opts["no_abort_on_error"] = True
                    entry_opts["outtmpl"] = {
                        "default": f"{playlist_dir}/%(title,id)s.%(ext)s",
                        "thumbnail": thumb_template,
                    }
                    entry_opts["progress_hooks"] = ydl_opts["progress_hooks"]
                    entry_opts["logger"] = ydl_opts["logger"]

                    try:
                        with yt_dlp.YoutubeDL(entry_opts) as entry_ydl:
                            entry_ydl.download([video_url])
                    except Exception as e:
                        err_msg = str(e).lower()
                        if "subtitle" in err_msg or "429" in err_msg:
                            log.warning(f"Playlist item failed with subtitle/429 error: {e}. Retrying with subtitles disabled.")
                            entry_opts["writesubtitles"] = False
                            entry_opts["writeautomaticsub"] = False
                            try:
                                with yt_dlp.YoutubeDL(entry_opts) as entry_ydl_nosub:
                                    entry_ydl_nosub.download([video_url])
                            except Exception as e_nosub:
                                log.warning(f"Playlist item fallback with disabled subtitles failed: {e_nosub}. Retrying with fallback template.")
                                entry_opts["outtmpl"]["default"] = fallback_template
                                try:
                                    with yt_dlp.YoutubeDL(entry_opts) as entry_ydl_fallback:
                                        entry_ydl_fallback.download([video_url])
                                except Exception as e2:
                                    log.error(f"Playlist item fallback with disabled subtitles failed again: {e2}")
                        else:
                            log.warning(f"Playlist item failed: {e}. Retrying with fallback template.")
                            entry_opts["outtmpl"]["default"] = fallback_template
                            try:
                                with yt_dlp.YoutubeDL(entry_opts) as entry_ydl_fallback:
                                    entry_ydl_fallback.download([video_url])
                            except Exception as e2:
                                err_msg2 = str(e2).lower()
                                if "subtitle" in err_msg2 or "429" in err_msg2:
                                    log.warning(f"Playlist item fallback failed with subtitle/429 error: {e2}. Retrying with subtitles disabled.")
                                    entry_opts["writesubtitles"] = False
                                    entry_opts["writeautomaticsub"] = False
                                    try:
                                        with yt_dlp.YoutubeDL(entry_opts) as entry_ydl_nosub:
                                            entry_ydl_nosub.download([video_url])
                                    except Exception as e3:
                                        log.error(f"Playlist item fallback with disabled subtitles failed again: {e3}")
                                else:
                                    log.error(f"Playlist item failed again: {e2}")
            else:
                YTDL.header = ""
                try:
                    ydl.download([url])
                except Exception as e:
                    err_msg = str(e).lower()
                    if "subtitle" in err_msg or "429" in err_msg:
                        log.warning(f"Download failed due to subtitle or 429 error: {e}. Retrying with subtitles disabled.")
                        ydl_opts["writesubtitles"] = False
                        ydl_opts["writeautomaticsub"] = False
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl_nosub:
                                ydl_nosub.download([url])
                        except Exception as e_nosub:
                            log.warning(f"Download with disabled subtitles failed: {e_nosub}. Retrying with fallback template.")
                            ydl_opts["outtmpl"]["default"] = fallback_template
                            try:
                                with yt_dlp.YoutubeDL(ydl_opts) as ydl_fallback:
                                    ydl_fallback.download([url])
                            except Exception as e2:
                                log.error(f"Fallback download with disabled subtitles failed: {e2}")
                                raise e2
                    else:
                        log.warning(f"Download failed: {e}. Retrying with fallback template.")
                        ydl_opts["outtmpl"]["default"] = fallback_template
                        try:
                            with yt_dlp.YoutubeDL(ydl_opts) as ydl2:
                                ydl2.download([url])
                        except Exception as e2:
                            err_msg_fallback = str(e2).lower()
                            if "subtitle" in err_msg_fallback or "429" in err_msg_fallback:
                                log.warning(f"Fallback failed due to subtitle or 429 error: {e2}. Retrying with subtitles disabled.")
                                ydl_opts["writesubtitles"] = False
                                ydl_opts["writeautomaticsub"] = False
                                try:
                                    with yt_dlp.YoutubeDL(ydl_opts) as ydl2_nosub:
                                        ydl2_nosub.download([url])
                                except Exception as e3:
                                    log.error(f"Fallback download with disabled subtitles failed: {e3}")
                                    raise e3
                            else:
                                log.error(f"Fallback download failed: {e2}")
                                raise e2

            # Verify if any files were produced
            files_after = get_files_in_dir(down_path)
            new_files = files_after - files_before
            if new_files:
                result["success"] = True
                result["error"] = None
                result["files"] = list(new_files)
            else:
                if info_dict and info_dict.get("_type") == "playlist":
                    result["success"] = False
                    result["error"] = "Playlist completed, but no new files were downloaded."
                else:
                    result["success"] = False
                    result["error"] = "Download completed but no file was produced on disk."

        except Exception as e:
            log.error(f"YTDL ERROR: {e}")
            result["success"] = False
            err_str = str(e)
            hint = ""
            lower_err = err_str.lower()
            if any(term in lower_err for term in ["sign in to confirm", "confirm you're not a bot", "format is not available", "403", "forbidden", "player response", "bot"]):
                hint = " [HINT: YouTube is blocking this request. Please supply a fresh cookies.txt file and/or update yt-dlp]"
            result["error"] = f"{err_str}{hint}"


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
            log.warning(f"get_YT_Name metadata extraction failed: {e}")
            raise e
