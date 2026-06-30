#================================================
#FILE: colab_leecher/downlader/ytdl.py
#================================================
import logging
import asyncio
import os
import re
import yt_dlp
from asyncio import sleep
from threading import Thread
from os import makedirs, path as ospath
from pyrogram.errors import MessageNotModified, RPCError
from colab_leecher.utility.handler import cancelTask
from colab_leecher.utility.variables import YTDL, MSG, Messages, Paths, BOT
from colab_leecher.utility.helper import getTime, keyboard, sizeUnit, status_bar, sysINFO
# Interactive cookie-recovery flow. needs_cookies() / site_from_url() are
# defined in cookie_recovery and re-exported here so they remain available in
# the ytdl namespace (per the original design).
from colab_leecher.utility.cookie_recovery import (
    needs_cookies,
    site_from_url,
    attempt_cookie_recovery,
    is_geo_blocked,
)

log = logging.getLogger(__name__)


async def YTDL_Status(link, num, task_ctx=None, max_retries=3):
    global Messages, YTDL

    # Tracks whether we already ran the interactive cookie-recovery flow for
    # this link so we never prompt the owner more than once per link.
    cookie_retry_used = False
    attempt = 0

    while attempt < max_retries:
        try:
            try:
                name = await get_YT_Name(link, task_ctx)
            except Exception as e:
                log.warning(f"Name lookup failed ({e}); using fallback name and continuing to download.")
                name = "YTDL Download"
            from ..utility.message_safety import escape_html
            Messages.status_head = f"<b>\U0001f4e5 DOWNLOADING FROM \u00bb </b><i>\U0001f517Link {str(num).zfill(2)}</i>\n\n<code>{escape_html(name)}</code>\n"

            if attempt > 0:
                log.info(f"Retry attempt {attempt + 1}/{max_retries} for link {num}")
                Messages.status_head += f"\n<i>\u26a0\ufe0f Retry attempt {attempt + 1}/{max_retries}</i>\n"

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
                            engine="Xr-YtDL \U0001f3ee",
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
            if is_geo_blocked(err_str):
                final_err = ("Geo/IP-restricted stream: this signed URL is locked to a "
                             "specific country/IP and cannot be downloaded from Colab. "
                             "Use a proxy in the allowed region (see below).")
                if task_ctx:
                    task_ctx.error.state = True
                    task_ctx.error.text = final_err
                break

            hint = ""
            lower_err = err_str.lower()
            if needs_cookies(err_str):
                hint = " [HINT: YouTube is blocking this request. Please supply a fresh cookies.txt file and/or update yt-dlp]"
            final_err = f"{err_str}{hint}"

            # ---- Interactive cookie recovery (before giving up) ----
            # When the failure looks cookie/auth related, ask the task owner for
            # a fresh Netscape cookies.txt, merge it, and retry the SAME link
            # once more. _build_ydl_opts() re-reads cookies.txt on the retry.
            if needs_cookies(err_str) and not cookie_retry_used and task_ctx is not None:
                cookie_retry_used = True
                log.warning(f"Cookie/auth error for link {num}; requesting cookies from owner.")
                if task_ctx:
                    task_ctx.error.state = False
                    task_ctx.error.text = ""
                try:
                    got_cookies = await attempt_cookie_recovery(link, task_ctx)
                except Exception as recovery_err:
                    log.error(f"Cookie recovery raised: {recovery_err}")
                    got_cookies = False

                if got_cookies:
                    log.info(f"Fresh cookies received for link {num}; retrying the same link.")
                    # Retry WITHOUT consuming the normal retry budget.
                    continue
                else:
                    site = site_from_url(link) or "the requested site"
                    final_err = f"Cookies required but not provided for {site}"
                    log.error(final_err)
                    if task_ctx:
                        task_ctx.error.state = True
                        task_ctx.error.text = final_err
                    break
            # ---- End interactive cookie recovery ----

            if attempt < max_retries - 1:
                log.warning(f"Download failed (attempt {attempt + 1}/{max_retries}): {final_err}")
                if task_ctx:
                    task_ctx.error.state = False
                    task_ctx.error.text = ""
                await sleep(5)
                attempt += 1
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
            YTDL.header = f"\n\u23f3 __Getting Video Information {msgs[-3]} of {msgs[-1]}__"

    @staticmethod
    def warning(msg):
        log.warning(f"[yt-dlp] {msg}")

    @staticmethod
    def error(msg):
        log.error(f"[yt-dlp] {msg}")


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


def _build_ydl_opts(output_template, task_ctx=None):
    import shutil
    if shutil.which("deno") is None:
        log.warning("\u26a0\ufe0f WARNING: 'deno' executable was not found on PATH! The 'ejs:github' solver requires Deno to run. Downloads may fail with 'DRM protected' or format errors.")

    opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": output_template,
        "trim_file_name": 150,

        "extractor_args": {
            "tiktok": {"webpage_download": True},
            "youtube": {
                "player_client": ["android", "ios"],
            }
        },
        "cache_dir": False,
        "remote_components": ["ejs:github"],

        "concurrent_fragment_downloads": 10,
        "http_chunk_size": 10485760,
        "updatetime": False,

        "retries": 10,
        "fragment_retries": 10,
        "skip_unavailable_fragments": False,
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
        # Override the impersonate target via env (e.g. "chrome-124",
        # "chrome:windows-10") without code changes. Bare "chrome" can raise
        # an AssertionError on some yt-dlp/curl_cffi combos; YouTubeDL() below
        # already retries with impersonation disabled if construction fails.
        _imp_target = os.environ.get("YTDL_IMPERSONATE", "chrome")
        try:
            # yt-dlp library API needs an ImpersonateTarget instance, not a
            # bare string: a str trips `assert isinstance(target,
            # ImpersonateTarget)` -> AssertionError -> impersonation silently
            # disabled -> HTTP 403 on every fragment. Fall back to the raw
            # string on older yt-dlp that still accepts it.
            from yt_dlp.networking.impersonate import ImpersonateTarget
            opts["impersonate"] = ImpersonateTarget.from_str(_imp_target)
        except Exception:
            opts["impersonate"] = _imp_target

    cookie_file = "cookies.txt"
    if ospath.exists(cookie_file):
        opts["cookiefile"] = cookie_file

    # Fix #5: apply the user-selected YTDL quality / audio-only preference.
    try:
        if task_ctx and hasattr(task_ctx, "bot") and task_ctx.bot:
            _quality = getattr(task_ctx.bot.Options, "ytdl_quality", None) or getattr(task_ctx.bot.Setting, "ytdl_quality", "best")
        else:
            _quality = getattr(BOT.Options, "ytdl_quality", None) or getattr(BOT.Setting, "ytdl_quality", "best")
    except Exception:
        _quality = "best"
    _quality = str(_quality or "best").lower()
    if _quality in ("720", "480", "360"):
        opts["format"] = f"bestvideo[height<={_quality}]+bestaudio/best[height<={_quality}]"
    elif _quality in ("audio", "audio_only", "audioonly", "mp3"):
        opts["format"] = "bestaudio/best"
        opts["merge_output_format"] = "mp3"
        # Extract audio to MP3 instead of converting into a video container.
        opts["postprocessors"] = [
            {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
            {"key": "FFmpegMetadata", "add_metadata": True},
            {"key": "EmbedThumbnail", "already_have_thumbnail": False},
        ]
    # else: keep the default "bestvideo+bestaudio/best"

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
        elif d.get("fragment_count"):
            percent = round(d.get("fragment_index", 0) * 100 / d["fragment_count"], 2)
        else:
            percent = 0

        YTDL.header = ""
        YTDL.speed = sizeUnit(speed) if speed else "N/A"
        YTDL.percentage = percent
        YTDL.eta = getTime(eta) if eta else "N/A"
        YTDL.done = sizeUnit(dl_bytes) if dl_bytes else "N/A"
        YTDL.left = sizeUnit(total_bytes) if total_bytes else "N/A"

    elif d["status"] == "finished":
        log.info(f"Finished downloading: {d.get('filename', 'unknown')}")


def _split_multiext(basename):
    """Split a filename, keeping language-coded subtitle suffixes intact."""
    lower = basename.lower()
    for known in (".en.srt", ".ar.srt", ".en.vtt", ".ar.vtt", ".en.ass", ".ar.ass"):
        if lower.endswith(known):
            return basename[:-len(known)], basename[-len(known):]
    stem, ext = ospath.splitext(basename)
    return stem, ext


def _apply_youtube_only_naming(files, info_dict, down_path):
    """Fix #4: rename file(s) to 'Title [With Brackets]{YYYY-MM-DD}.ext'."""
    if not info_dict:
        return None
    title = info_dict.get("title")
    if not title:
        return None
    bracket_title = str(title).replace("(", "[").replace(")", "]")
    bracket_title = re.sub(r'[\\/:*?"<>|]+', "_", bracket_title).strip().rstrip(".")
    if not bracket_title:
        return None

    upload_date = info_dict.get("upload_date")
    if upload_date and str(upload_date).isdigit() and len(str(upload_date)) == 8:
        d = str(upload_date)
        date_part = "{" + f"{d[:4]}-{d[4:6]}-{d[6:8]}" + "}"
    else:
        date_part = ""

    new_base = f"{bracket_title}{date_part}"
    renamed = []
    for f in sorted(files):
        try:
            if not ospath.exists(f):
                renamed.append(f)
                continue
            dir_name = ospath.dirname(f)
            base_name = ospath.basename(f)
            _stem, ext = _split_multiext(base_name)
            target = ospath.join(dir_name, f"{new_base}{ext}")
            if ospath.abspath(target) != ospath.abspath(f) and ospath.exists(target):
                target = ospath.join(dir_name, f"{new_base}_{_stem[:8]}{ext}")
            if ospath.abspath(target) == ospath.abspath(f):
                renamed.append(f)
                continue
            os.rename(f, target)
            renamed.append(target)
            log.info(f"Renamed YouTube-only file -> {ospath.basename(target)}")
        except Exception as e:
            log.warning(f"Could not rename {f}: {e}")
            renamed.append(f)
    return renamed


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

    base_template = f"{down_path}/%(upload_date>%Y-%m-%d,unknown_date)s_%(title,id).120B.%(ext)s"
    fallback_template = f"{down_path}/%(id).150B.%(ext)s"
    thumb_template = f"{thumbnail_ytdl}/%(id).150B.%(ext)s"

    ydl_opts = _build_ydl_opts(base_template, task_ctx)
    ydl_opts["outtmpl"] = {
        "default": base_template,
        "thumbnail": thumb_template,
    }

    try:
        ydl = yt_dlp.YoutubeDL(ydl_opts)
    except Exception as e:
        log.warning(f"Failed to init yt-dlp ({type(e).__name__}: {e!r}). Retrying without impersonation.")
        ydl_opts.pop("impersonate", None)
        ydl = yt_dlp.YoutubeDL(ydl_opts)

    with ydl:
        try:
            info_dict = ydl.extract_info(url, download=False)
            YTDL.header = "\u231b __Please WAIT a bit...__"

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

                    entry_opts = _build_ydl_opts(fallback_template, task_ctx)
                    # For playlists, keep ignoreerrors / no_abort_on_error to True so one failing item doesn't crash the whole run
                    entry_opts["ignoreerrors"] = True
                    entry_opts["no_abort_on_error"] = True
                    entry_opts["outtmpl"] = {
                        "default": f"{playlist_dir}/%(title,id).120B.%(ext)s",
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

                # Fix #4: clean naming for YouTube-only Gist downloads.
                try:
                    is_playlist = bool(info_dict and info_dict.get("_type") == "playlist")
                    if task_ctx and task_ctx.metadata.get("youtube_only_gist") and not is_playlist:
                        renamed = _apply_youtube_only_naming(list(new_files), info_dict, down_path)
                        if renamed:
                            result["files"] = renamed
                except Exception as rename_err:
                    log.warning(f"YouTube-only naming skipped: {rename_err}")
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
            if needs_cookies(err_str):
                hint = " [HINT: YouTube is blocking this request. Please supply a fresh cookies.txt file and/or update yt-dlp]"
            result["error"] = f"{err_str}{hint}"


def _get_YT_Name_sync(link, task_ctx=None):
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "logger": SilentLogger(),
    }
    proxy = os.environ.get("YTDL_PROXY") or os.environ.get("HTTPS_PROXY")
    if proxy:
        ydl_opts["proxy"] = proxy
    ydl_opts["geo_bypass"] = True
    ydl_opts["geo_bypass_country"] = os.environ.get("YTDL_GEO_COUNTRY", "US")
    if has_impersonate:
        _imp_target = os.environ.get("YTDL_IMPERSONATE", "chrome")
        try:
            # yt-dlp library API needs an ImpersonateTarget instance, not a
            # bare string: a str trips `assert isinstance(target,
            # ImpersonateTarget)` -> AssertionError -> impersonation silently
            # disabled -> HTTP 403 on every fragment. Fall back to the raw
            # string on older yt-dlp that still accepts it.
            from yt_dlp.networking.impersonate import ImpersonateTarget
            ydl_opts["impersonate"] = ImpersonateTarget.from_str(_imp_target)
        except Exception:
            ydl_opts["impersonate"] = _imp_target
    if ospath.exists("cookies.txt"):
        ydl_opts["cookiefile"] = "cookies.txt"

    try:
        ydl = yt_dlp.YoutubeDL(ydl_opts)
    except Exception as e:
        log.warning(f"Failed to init yt-dlp in get_YT_Name ({type(e).__name__}: {e!r}). Retrying without impersonation.")
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


async def get_YT_Name(link, task_ctx=None):
    return await asyncio.to_thread(_get_YT_Name_sync, link, task_ctx)
