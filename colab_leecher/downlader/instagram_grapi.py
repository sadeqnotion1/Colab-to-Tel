# ================================================
# FILE: colab_leecher/downlader/instagram_grapi.py
# ================================================
from __future__ import annotations
"""
Instagram profile -> single ZIP engine, powered by `instagrapi`.

Goal: given an Instagram *profile/username URL*, download ALL of that user's
photos and videos, then hand a single ZIP to the existing leech/upload pipeline.

Design rules (per project Delivery Standard):
- Additive: this is a brand-new module. It does NOT modify existing behavior.
- We do NOT write our own scraping/parsing/download logic. Every fetch and
  download is delegated to instagrapi's Client methods. The only logic here is
  orchestration: auth -> list media -> dispatch download -> zip.
- Safe fallback: grapi_profile_download(...) returns None when the engine
  cannot be used (instagrapi missing, no usable auth, or username unresolved),
  so the caller can fall back to the legacy instaloader/yt-dlp path untouched.

Public entry point:
    await grapi_profile_download(url, num, max_posts) -> True | False | None
        True  = profile downloaded and zipped successfully
        False = engine ran but produced nothing (failure recorded in TaskError)
        None  = engine unusable -> caller should fall back
"""

import os
import shutil
import logging
from threading import Thread
from asyncio import sleep

from ..utility.variables import BOT, Messages, Paths, TRANSFER, TaskError, MSG
from ..utility.helper import keyboard, sysINFO

log = logging.getLogger(__name__)

# Where instagrapi caches its authenticated session between runs.
_SETTINGS_PATH = os.path.join(Paths.WORK_PATH, "instagrapi_settings.json")
_REPO_SETTINGS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "instagrapi_settings.json"))


class _State:
    """Progress state shared between the worker thread and the async monitor."""
    header = ""


_state = _State()


def _reset_state():
    _state.header = ""


def _extract_username(url: str) -> str:
    """Reuse the project's existing username extractor (no new logic)."""
    try:
        from .instagram import extract_username
        return extract_username(url) or ""
    except Exception:
        import re
        m = re.search(r"instagram\.com/([^/?#]+)", url or "")
        return m.group(1) if m else ""


def _safe_dump(cl, path):
    """Persist the instagrapi session so we don't re-login every run."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        cl.dump_settings(path)
    except Exception as e:
        log.debug(f"Could not persist instagrapi session: {e}")


def _sessionid_from_cookies_file() -> str:
    """Pull a sessionid out of the existing JSON cookies file, if present."""
    cookies_file = getattr(BOT.Setting, "instagram_cookies_file", "") or ""
    if not cookies_file:
        return ""
    json_path = cookies_file.replace(".txt", ".json")
    for candidate in (json_path, cookies_file):
        try:
            if candidate and os.path.exists(candidate):
                import json
                with open(candidate, "r") as f:
                    data = json.load(f)
                for cookie in data:
                    if cookie.get("name") == "sessionid":
                        return cookie.get("value", "") or ""
        except Exception as e:
            log.debug(f"Could not read cookies file {candidate}: {e}")
    return ""


def _build_client():
    """
    Build an authenticated instagrapi Client using, in priority order:
      1) a previously saved session   (load_settings)
      2) INSTAGRAM_SESSIONID setting   (login_by_sessionid)
      3) sessionid found in cookies file
      4) username + password           (login)
    Returns the Client on success, or None if no method works.
    """
    try:
        from instagrapi import Client
    except ImportError:
        log.warning("instagrapi is not installed - cannot use the instagrapi engine.")
        return None

    cl = Client()
    cl.delay_range = [1, 3]  # be gentle with the private API
    cl.request_timeout = 15  # increase from default of 1s to prevent timeouts

    # 1) Reuse a saved session if we have one.
    try:
        active_settings_path = None
        if os.path.exists(_SETTINGS_PATH):
            active_settings_path = _SETTINGS_PATH
        elif os.path.exists(_REPO_SETTINGS_PATH):
            active_settings_path = _REPO_SETTINGS_PATH

        if not active_settings_path:
            raw_session = getattr(BOT.Setting, "instagram_session", "") or ""
            if raw_session.strip():
                try:
                    import json
                    session_data = json.loads(raw_session.strip())
                    os.makedirs(os.path.dirname(_SETTINGS_PATH), exist_ok=True)
                    with open(_SETTINGS_PATH, "w", encoding="utf-8") as sf:
                        json.dump(session_data, sf, indent=4)
                    active_settings_path = _SETTINGS_PATH
                    log.info("instagrapi: recreated settings file from credentials.json session.")
                except Exception as parse_err:
                    log.warning(f"instagrapi: failed to parse session from credentials: {parse_err}")

        if active_settings_path:
            cl.load_settings(active_settings_path)
            cl.request_timeout = 15  # override timeout loaded from settings
            cl.get_timeline_feed()  # validates the session
            log.info(f"instagrapi: reused saved session from {active_settings_path}.")
            if active_settings_path == _REPO_SETTINGS_PATH:
                _safe_dump(cl, _SETTINGS_PATH)
            return cl
    except Exception as e:
        log.info(f"instagrapi: saved session invalid, will re-auth: {e}")
        cl = Client()
        cl.delay_range = [1, 3]
        cl.request_timeout = 15

    # 2) sessionid setting, else 3) sessionid from cookies file.
    sessionid = getattr(BOT.Setting, "instagram_sessionid", "") or ""
    if not sessionid:
        sessionid = _sessionid_from_cookies_file()
    if sessionid:
        try:
            import urllib.parse
            sessionid = urllib.parse.unquote(sessionid)
            cl.login_by_sessionid(sessionid)
            _safe_dump(cl, _SETTINGS_PATH)
            log.info("instagrapi: logged in via sessionid.")
            return cl
        except Exception as e:
            log.warning(f"instagrapi: sessionid login failed: {e}")

    # 4) username + password.
    user = getattr(BOT.Setting, "instagram_username", "") or ""
    pwd = getattr(BOT.Setting, "instagram_password", "") or ""
    if user and pwd:
        try:
            cl.login(user, pwd)
            _safe_dump(cl, _SETTINGS_PATH)
            log.info("instagrapi: logged in via username/password.")
            return cl
        except Exception as e:
            log.warning(f"instagrapi: username/password login failed: {e}")

    log.warning("instagrapi: no usable authentication - cannot use engine.")
    return None


def _download_one(cl, media, folder):
    """
    Dispatch a single media item to the correct instagrapi download method.
    Returns a list of downloaded file paths (album -> many). This dispatch is
    the only 'logic' we own; the actual downloading is all instagrapi.
    """
    mt = getattr(media, "media_type", None)
    pt = getattr(media, "product_type", "") or ""
    pk = media.pk

    if mt == 1:                      # photo
        return [cl.photo_download(pk, folder=folder)]
    if mt == 8:                      # album / carousel (mixed photos + videos)
        return list(cl.album_download(pk, folder=folder))
    if mt == 2:                      # video family
        if pt == "clips":
            return [cl.clip_download(pk, folder=folder)]
        if pt == "igtv":
            return [cl.igtv_download(pk, folder=folder)]
        return [cl.video_download(pk, folder=folder)]
    # Unknown type: best-effort generic video download.
    return [cl.video_download(pk, folder=folder)]


def _profile_worker(cl, username, max_posts, profile_dir, result):
    """Runs in a thread: list the user's media and download every item."""
    try:
        _state.header = f"🔎 __Resolving @{username}...__"
        user_id = cl.user_id_from_username(username)

        amount = max_posts if (isinstance(max_posts, int) and max_posts > 0) else 0
        _state.header = f"📡 __Fetching media list for @{username}...__"
        medias = cl.user_medias(user_id, amount=amount)
        total = len(medias)

        if total == 0:
            result["error"] = "No media found on this profile."
            return

        os.makedirs(profile_dir, exist_ok=True)
        for i, media in enumerate(medias, start=1):
            _state.header = f"📥 __Downloading {i}/{total} from @{username}...__"
            try:
                paths = _download_one(cl, media, profile_dir)
                for p in paths:
                    if p:
                        result["files"].append(str(p))
            except Exception as item_err:
                log.warning(f"instagrapi: failed item {getattr(media, 'pk', '?')}: {item_err}")
                TaskError.failed_links.append({
                    "link": "instagram:" + str(getattr(media, "code", "") or getattr(media, "pk", "")),
                    "filename": f"{username}_{getattr(media, 'pk', 'item')}",
                    "reason": f"instagrapi item error: {str(item_err)[:100]}",
                })
        result["done"] = True
    except Exception as e:
        log.error(f"instagrapi: profile worker error: {e}", exc_info=True)
        result["error"] = str(e)


async def _render():
    """Update the Telegram status message with current progress."""
    try:
        if _state.header and MSG.status_msg is not None:
            await MSG.status_msg.edit_text(
                text=Messages.task_msg + Messages.status_head + _state.header + sysINFO(),
                reply_markup=keyboard(),
            )
    except Exception as e:
        log.debug(f"instagrapi: status render failed: {e}")


async def grapi_profile_download(url: str, num: int, max_posts: int = 50):
    """See module docstring. Returns True / False / None."""
    username = _extract_username(url)
    if not username:
        return None  # can't resolve a username -> let caller fall back

    cl = _build_client()
    if cl is None:
        return None  # engine unusable -> fall back to legacy path

    Messages.download_name = f"{username}_profile"
    Messages.status_head = f" 📸 DOWNLOADING INSTAGRAM PROFILE » @{username} \n\n"
    _reset_state()

    os.makedirs(Paths.down_path, exist_ok=True)
    profile_dir = os.path.join(Paths.down_path, f"{username}_profile")

    result = {"files": [], "done": False, "error": None}
    worker = Thread(
        target=_profile_worker,
        name="InstagrapiProfileDL",
        args=(cl, username, max_posts, profile_dir, result),
    )
    worker.start()

    while worker.is_alive():
        await _render()
        await sleep(2.5)
    await _render()

    files = result["files"]
    if not files:
        reason = result.get("error") or "No files downloaded"
        log.error(f"instagrapi: nothing downloaded for @{username}: {reason}")
        TaskError.failed_links.append({
            "link": url,
            "filename": f"{username}_profile",
            "index": num,
            "reason": f"instagrapi: {str(reason)[:100]}",
        })
        # Engine ran but produced nothing -> report failure (do not fall back).
        return False

    # Zip everything into a single archive next to the downloads so the
    # existing uploader sends one ZIP.
    _state.header = f"🗜️ __Zipping {len(files)} files for @{username}...__"
    await _render()
    try:
        zip_base = os.path.join(Paths.down_path, username)
        archive = shutil.make_archive(
            base_name=zip_base,
            format="zip",
            root_dir=Paths.down_path,
            base_dir=f"{username}_profile",
        )
        # Remove the raw folder so only the ZIP gets uploaded.
        shutil.rmtree(profile_dir, ignore_errors=True)
        TRANSFER.successful_downloads.append(
            {"url": url, "filename": os.path.basename(archive)}
        )
        log.info(f"instagrapi: created {archive} with {len(files)} files.")
        _state.header = f"✅ __Done: {os.path.basename(archive)} ({len(files)} files)__"
        return True
    except Exception as e:
        log.error(f"instagrapi: zipping failed: {e}", exc_info=True)
        # ZIP failed but files exist on disk -> let the normal pipeline take them.
        for f in files:
            TRANSFER.successful_downloads.append(
                {"url": url, "filename": os.path.basename(f)}
            )
        TaskError.failed_links.append({
            "link": url,
            "filename": f"{username}.zip",
            "index": num,
            "reason": f"Zip failed: {str(e)[:100]}",
        })
        return True


async def grapi_post_download(url: str, num: int) -> bool | None:
    """
    Download a single Instagram post/reel/story/IGTV using `instagrapi`.
    Returns:
        True  = post downloaded successfully
        False = engine ran but failed to download
        None  = engine unusable -> fallback to legacy path
    """
    cl = _build_client()
    if cl is None:
        return None  # engine unusable -> fall back

    import re
    # Clean the URL to extract shortcode and generate a clean post URL
    match = re.search(r'/(?:p|reel|tv|stories)/([^/?#\s]+)', url)
    cleaned_url = url
    if match:
        shortcode = match.group(1)
        cleaned_url = f"https://www.instagram.com/p/{shortcode}/"
    else:
        log.warning(f"instagrapi: could not extract shortcode from {url}")
        return None

    try:
        media_pk = cl.media_pk_from_url(cleaned_url)
    except Exception as e:
        log.warning(f"instagrapi: failed to resolve media PK from {cleaned_url}: {e}")
        return None  # let fallback try

    try:
        media = cl.media_info(media_pk)
        owner_username = getattr(media.user, "username", "instagram_post")
        name = f"{owner_username}_{media_pk}"
    except Exception as e:
        log.warning(f"instagrapi: failed to fetch media info for PK {media_pk}: {e}")
        name = f"instagram_{media_pk}"
        media = None

    if media is None:
        return None

    Messages.download_name = name
    from ..utility.message_safety import escape_html
    Messages.status_head = f"<b>📥 DOWNLOADING FROM INSTAGRAM » </b><i>🔗Link {str(num).zfill(2)}</i>\n\n<code>{escape_html(name)}</code>\n"
    _reset_state()

    os.makedirs(Paths.down_path, exist_ok=True)
    result = {"files": [], "done": False, "error": None}

    def worker_func():
        try:
            _state.header = f"📥 __Downloading media {media_pk}...__"
            paths = _download_one(cl, media, Paths.down_path)
            for p in paths:
                if p:
                    result["files"].append(str(p))
            result["done"] = True
        except Exception as e:
            log.error(f"instagrapi: post worker error: {e}", exc_info=True)
            result["error"] = str(e)

    worker = Thread(
        target=worker_func,
        name="InstagrapiPostDL",
    )
    worker.start()

    while worker.is_alive():
        await _render()
        await sleep(2.5)
    await _render()

    files = result["files"]
    if not files:
        reason = result.get("error") or "No files downloaded"
        log.error(f"instagrapi: post download failed: {reason}")
        TaskError.failed_links.append({
            "link": url,
            "filename": name,
            "index": num,
            "reason": f"instagrapi: {str(reason)[:100]}",
        })
        return False

    for f in files:
        TRANSFER.successful_downloads.append({
            "url": url,
            "filename": os.path.basename(f)
        })
    log.info(f"instagrapi: downloaded {len(files)} files for post.")
    _state.header = f"✅ __Done: downloaded {len(files)} files__"
    return True

