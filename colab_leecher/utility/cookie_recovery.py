# ================================================================
# FILE: colab_leecher/utility/cookie_recovery.py
# ================================================================
#
# Interactive cookie-recovery flow for the yt-dlp downloader.
#
# When a YouTube / yt-dlp download fails with an authentication / cookie-type
# error, the bot asks the task owner in Telegram for a Netscape cookies.txt,
# waits for their reply, merges it into the shared repo-root cookies.txt and
# lets the caller retry the same link instead of failing the task.
#
# This module is fully self-contained. The only changes required in the rest of
# the codebase are:
#   * transfer_state.py  -> hosts the AWAITING_COOKIES registry + lock
#   * ytdl.py            -> calls attempt_cookie_recovery() in YTDL_Status
#   * __main__.py        -> registers a private-chat reply handler
#
# Parallel-safe: every read/write of the shared registry is guarded by an
# asyncio.Lock, and entries are keyed per user_id.
# ================================================================

from __future__ import annotations

import logging
import os
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from .transfer_state import AWAITING_COOKIES, AWAITING_COOKIES_LOCK

log = logging.getLogger(__name__)

# Path used by _build_ydl_opts() in ytdl.py. Keep cookies.txt at the repo root.
COOKIES_PATH = "cookies.txt"
NETSCAPE_HEADER = "# Netscape HTTP Cookie File"
COOKIE_WAIT_TIMEOUT = 300  # seconds (5 minutes)

# Lowercased substrings that indicate an authentication / cookie problem.
_COOKIE_ERROR_MARKERS = (
    "sign in to confirm",
    "confirm you're not a bot",
    "login required",
    "private video",
    "members-only",
    "this video is only available",
    "drm protected",
    "requested format is not available",
    "403",
    "forbidden",
    "http error 429",
    "cookies",
)

# Errors that look like 403 but are NOT fixable with cookies.
_GEO_IP_MARKERS = (
    "geolocation restrict",
    "geo restrict",
    "geo-restrict",
    "not available in your",
    "not available from your location",
    "blocked it in your country",
    "this video is not available in your country",
)


def is_geo_blocked(error_str: str) -> bool:
    if not error_str:
        return False
    return any(m in str(error_str).lower() for m in _GEO_IP_MARKERS)


# A small set of common multi-label public suffixes so site_from_url() returns a
# sensible registrable domain (e.g. bbc.co.uk -> bbc.co.uk, not co.uk).
_TWO_LEVEL_SUFFIXES = {
    "co.uk", "org.uk", "ac.uk", "gov.uk", "me.uk", "ltd.uk", "plc.uk",
    "co.jp", "or.jp", "ne.jp", "ac.jp", "go.jp",
    "com.au", "net.au", "org.au", "edu.au", "gov.au",
    "co.nz", "net.nz", "org.nz",
    "com.br", "com.cn", "com.tr", "com.mx", "com.ar", "com.sg", "com.hk",
    "co.in", "co.kr", "co.za", "co.il",
}


# ----------------------------------------------------------------------------
# 1. Error classifier
# ----------------------------------------------------------------------------
def needs_cookies(error_str: str) -> bool:
    """Return True when the (lowercased) error text looks cookie/auth related."""
    if not error_str:
        return False
    low = str(error_str).lower()
    if is_geo_blocked(low):      # geo/IP block -> cookies won't help
        return False
    return any(marker in low for marker in _COOKIE_ERROR_MARKERS)


# ----------------------------------------------------------------------------
# 2. Domain detection
# ----------------------------------------------------------------------------
def _registrable_domain(netloc: str) -> str:
    netloc = (netloc or "").lower().strip()
    if not netloc:
        return ""
    # Strip userinfo + port
    if "@" in netloc:
        netloc = netloc.split("@", 1)[1]
    netloc = netloc.split(":", 1)[0]
    netloc = netloc.strip(".")
    parts = [p for p in netloc.split(".") if p]
    if len(parts) <= 2:
        return ".".join(parts)
    last_two = ".".join(parts[-2:])
    if last_two in _TWO_LEVEL_SUFFIXES:
        return ".".join(parts[-3:])
    return last_two


def site_from_url(url: str) -> str:
    """Return the registrable domain for a URL (e.g. youtube.com, twitter.com)."""
    try:
        parsed = urlparse(url if "//" in str(url) else f"//{url}")
        netloc = parsed.netloc or parsed.path
    except Exception:
        return ""
    return _registrable_domain(netloc)


# ----------------------------------------------------------------------------
# Netscape cookies.txt parsing / validation / merging
# ----------------------------------------------------------------------------
def _normalize_cookie_domain(domain: str) -> str:
    d = (domain or "").strip()
    if d.lower().startswith("#httponly_"):
        d = d[len("#httponly_"):]
    return d.lstrip(".").lower()


def _split_cookie_line(line: str):
    """Split a Netscape cookie line into >=7 columns (tab first, then spaces)."""
    cols = line.split("\t")
    if len(cols) < 7:
        cols = line.split()
    return cols


def _is_cookie_line(stripped: str) -> bool:
    if not stripped:
        return False
    if stripped.startswith("#HttpOnly_"):
        return True
    if stripped.startswith("#"):
        return False
    return True


def looks_like_netscape_cookies(text: str) -> bool:
    """Heuristic validation of a Netscape cookie file / pasted contents."""
    if not text:
        return False
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return False
    if lines[0].strip().lower().startswith("# netscape http cookie file"):
        return True
    for ln in lines:
        stripped = ln.strip()
        if not _is_cookie_line(stripped):
            continue
        cols = _split_cookie_line(ln)
        if len(cols) >= 7 and cols[1].strip().upper() in ("TRUE", "FALSE"):
            return True
    return False


def _parse_cookie_lines(text: str):
    """Parse cookie lines into an ordered dict keyed by (domain, name).

    Returns (cookies, order) where cookies maps key -> normalized 7-column line
    (tab separated) and order preserves first-seen order.
    """
    cookies = {}
    order = []
    for raw in (text or "").splitlines():
        stripped = raw.strip()
        if not _is_cookie_line(stripped):
            continue
        cols = _split_cookie_line(raw.rstrip("\n"))
        if len(cols) < 7:
            continue
        cols = [c.strip() for c in cols[:7]]
        domain = cols[0]
        name = cols[5]
        key = (_normalize_cookie_domain(domain), name)
        if key not in cookies:
            order.append(key)
        cookies[key] = "\t".join(cols)
    return cookies, order


def domain_in_cookies(site: str, cookies_path: str = COOKIES_PATH) -> bool:
    """Return True if cookies_path already has at least one line for `site`."""
    if not site or not os.path.exists(cookies_path):
        return False
    try:
        with open(cookies_path, "r", encoding="utf-8", errors="replace") as fh:
            existing, _ = _parse_cookie_lines(fh.read())
    except OSError as exc:
        log.warning(f"Could not read {cookies_path} for domain check: {exc}")
        return False
    for (domain, _name) in existing.keys():
        if domain == site or domain.endswith("." + site) or _registrable_domain(domain) == site:
            return True
    return False


def merge_cookie_text(existing_text: str, new_text: str) -> str:
    """Merge two Netscape cookie blobs.

    New values overwrite existing ones with the same (domain, name) key, while
    every other domain/cookie is kept intact. A single header is emitted.
    """
    existing, order = _parse_cookie_lines(existing_text)
    new_cookies, new_order = _parse_cookie_lines(new_text)
    for key in new_order:
        if key not in existing:
            order.append(key)
        existing[key] = new_cookies[key]
    out_lines = [NETSCAPE_HEADER, ""]
    out_lines.extend(existing[key] for key in order)
    return "\n".join(out_lines).rstrip("\n") + "\n"


def save_merged_cookies(new_text: str, cookies_path: str = COOKIES_PATH) -> None:
    """Merge `new_text` into cookies_path and write it back atomically."""
    existing_text = ""
    if os.path.exists(cookies_path):
        try:
            with open(cookies_path, "r", encoding="utf-8", errors="replace") as fh:
                existing_text = fh.read()
        except OSError as exc:
            log.warning(f"Could not read existing {cookies_path}; starting fresh: {exc}")
            existing_text = ""
    merged = merge_cookie_text(existing_text, new_text)
    tmp_path = f"{cookies_path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.write(merged)
    os.replace(tmp_path, cookies_path)
    log.info(f"Merged refreshed cookies into {cookies_path}.")


# ----------------------------------------------------------------------------
# 3. Awaiting-cookies state (registry lives in transfer_state.py)
# ----------------------------------------------------------------------------
@dataclass
class CookieWaiter:
    future: asyncio.Future
    site: str
    domain: str
    task_id: Optional[str] = None
    cookies_path: str = COOKIES_PATH
    prompt_message_id: Optional[int] = None
    chat_id: Optional[int] = None


async def has_pending_cookie_request(user_id: int) -> bool:
    async with AWAITING_COOKIES_LOCK:
        return user_id in AWAITING_COOKIES


# ----------------------------------------------------------------------------
# 4. Request flow
# ----------------------------------------------------------------------------
def _build_prompt_text(site: str, have_existing: bool) -> str:
    if have_existing:
        state_line = (
            "Your stored cookies for this site look \u26a0\ufe0f expired/insufficient \u2014 "
            "please send fresh ones."
        )
    else:
        state_line = "No cookies are stored for this site yet \u2014 they appear to be missing."
    return (
        f"\U0001f36a This download needs cookies for {site}.\n\n"
        f"{state_line}\n\n"
        "Reply to this message with your Netscape cookies.txt \u2014 either upload the file "
        "or paste its contents.\n"
        "Export with the 'Get cookies.txt LOCALLY' browser extension.\n\n"
        "(Waiting up to 5 minutes\u2026)"
    )


async def request_cookies_and_wait(
    client,
    owner_id: int,
    url: str,
    task_id: Optional[str] = None,
    cookies_path: str = COOKIES_PATH,
    timeout: int = COOKIE_WAIT_TIMEOUT,
) -> bool:
    """Prompt the owner for cookies and await their reply.

    Returns True if valid cookies were received and merged, False on timeout.
    """
    site = site_from_url(url) or "the requested site"
    have_existing = domain_in_cookies(site, cookies_path)
    text = _build_prompt_text(site, have_existing)

    loop = asyncio.get_event_loop()
    future: asyncio.Future = loop.create_future()

    prompt_msg = None
    try:
        prompt_msg = await client.send_message(owner_id, text)
    except Exception as exc:
        log.error(f"Failed to send cookie-request message to {owner_id}: {exc}")
        return False

    waiter = CookieWaiter(
        future=future,
        site=site,
        domain=site,
        task_id=task_id,
        cookies_path=cookies_path,
        prompt_message_id=getattr(prompt_msg, "id", None),
        chat_id=owner_id,
    )

    async with AWAITING_COOKIES_LOCK:
        # If a stale waiter exists for this user, cancel it first.
        stale = AWAITING_COOKIES.get(owner_id)
        if stale is not None and not stale.future.done():
            stale.future.cancel()
        AWAITING_COOKIES[owner_id] = waiter

    try:
        result = await asyncio.wait_for(future, timeout=timeout)
        return bool(result)
    except asyncio.TimeoutError:
        log.warning(f"Cookie request for {site} (user {owner_id}) timed out after {timeout}s.")
        return False
    except asyncio.CancelledError:
        return False
    finally:
        async with AWAITING_COOKIES_LOCK:
            if AWAITING_COOKIES.get(owner_id) is waiter:
                AWAITING_COOKIES.pop(owner_id, None)


async def attempt_cookie_recovery(
    link: str,
    task_ctx=None,
    cookies_path: str = COOKIES_PATH,
    timeout: int = COOKIE_WAIT_TIMEOUT,
) -> bool:
    """High-level helper called from YTDL_Status.

    Resolves the Telegram client + task owner, then prompts and waits.
    """
    try:
        from .. import colab_bot, OWNER
    except Exception as exc:
        log.error(f"Cookie recovery unavailable (import failed): {exc}")
        return False

    owner_id = getattr(task_ctx, "user_id", 0) or OWNER
    if not owner_id:
        log.warning("Cookie recovery skipped: no task owner / OWNER configured.")
        return False

    task_id = getattr(task_ctx, "task_id", None)
    return await request_cookies_and_wait(
        colab_bot, int(owner_id), link, task_id, cookies_path, timeout
    )


# ----------------------------------------------------------------------------
# 5. Receiving cookies (called from the __main__.py handler)
# ----------------------------------------------------------------------------
async def _extract_cookie_text(message) -> Optional[str]:
    """Return cookie text from an uploaded .txt document or pasted text."""
    document = getattr(message, "document", None)
    if document is not None:
        filename = (getattr(document, "file_name", "") or "").lower()
        if not filename.endswith(".txt"):
            return None
        downloaded_path = None
        try:
            downloaded_path = await message.download()
            with open(downloaded_path, "r", encoding="utf-8", errors="replace") as fh:
                return fh.read()
        except Exception as exc:
            log.error(f"Failed to download/read cookie document: {exc}")
            return None
        finally:
            if downloaded_path and os.path.exists(downloaded_path):
                try:
                    os.remove(downloaded_path)
                except OSError:
                    pass
    text = getattr(message, "text", None) or getattr(message, "caption", None)
    return text


async def _delete_message_safely(message) -> None:
    try:
        await message.delete()
    except Exception as exc:
        log.debug(f"Could not delete cookie message: {exc}")


async def _delete_prompt_safely(client, chat_id, message_id) -> None:
    if not chat_id or not message_id:
        return
    try:
        prompt = await client.get_messages(chat_id, message_id)
        if prompt:
            await prompt.delete()
    except Exception as exc:
        log.debug(f"Could not delete cookie prompt {message_id}: {exc}")


async def handle_cookie_reply(client, message) -> bool:
    """Handle a reply from a user that has a pending AWAITING_COOKIES entry.

    Returns True if the message belonged to a cookie request (and was consumed),
    False if there was no pending request (caller should let it propagate).
    """
    user = getattr(message, "from_user", None)
    user_id = getattr(user, "id", None)
    if user_id is None:
        return False

    async with AWAITING_COOKIES_LOCK:
        waiter = AWAITING_COOKIES.get(user_id)
    if waiter is None:
        return False

    cookie_text = await _extract_cookie_text(message)
    if not cookie_text or not looks_like_netscape_cookies(cookie_text):
        try:
            await message.reply_text(
                "\u274c That doesn't look like a valid Netscape cookies.txt.\n"
                "Please upload the .txt file exported by 'Get cookies.txt LOCALLY', "
                "or paste its full contents. (Still waiting\u2026)"
            )
        except Exception as exc:
            log.debug(f"Could not send invalid-cookie reply: {exc}")
        # Consumed: do not let other handlers treat secret text as a URL.
        return True

    try:
        save_merged_cookies(cookie_text, waiter.cookies_path)
    except Exception as exc:
        log.error(f"Failed to merge cookies: {exc}")
        try:
            await message.reply_text(
                "\u274c Could not save those cookies. Please try sending them again."
            )
        except Exception:
            pass
        return True

    # The message contains secrets -> delete it (and the prompt) once stored.
    await _delete_message_safely(message)
    await _delete_prompt_safely(client, waiter.chat_id, waiter.prompt_message_id)

    if not waiter.future.done():
        waiter.future.set_result(True)

    async with AWAITING_COOKIES_LOCK:
        if AWAITING_COOKIES.get(user_id) is waiter:
            AWAITING_COOKIES.pop(user_id, None)

    try:
        await client.send_message(user_id, f"\u2705 Cookies saved for {waiter.site}. Retrying\u2026")
    except Exception as exc:
        log.debug(f"Could not send cookie-saved confirmation: {exc}")

    return True
