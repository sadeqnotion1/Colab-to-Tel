#!/usr/bin/env python3
"""
ytdl.py - Download a video with yt-dlp and upload it to Telegram.

Designed to run inside Google Colab (or any normal Python environment).
There is NO GitHub Action involved — you just run this file directly.

--------------------------------------------------------------------------
QUICK START (in a Google Colab cell):

    !pip install -q yt-dlp pyrogram tgcrypto
    !python ytdl.py "https://youtu.be/XXXXXXXX"

or import and call from a cell:

    from ytdl import download_and_upload
    download_and_upload("https://youtu.be/XXXXXXXX")
--------------------------------------------------------------------------

CONFIG: set these as environment variables, or fill the defaults below.
  API_ID / API_HASH  -> from https://my.telegram.org  (apps)
  BOT_TOKEN          -> from @BotFather
  CHAT_ID            -> target chat / channel id (e.g. -1001234567890)
                        or a username like "@mychannel"

Notes:
  * A bot can upload files up to 2 GB.
  * The bot must be a member/admin of the target chat or channel.
"""

import os
import sys
import glob
import time

# ---------------------------------------------------------------------------
# Configuration (env vars take priority; otherwise edit the fallback strings)
# ---------------------------------------------------------------------------
API_ID = int(os.environ.get("API_ID", "0") or 0)
API_HASH = os.environ.get("API_HASH", "")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
CHAT_ID = os.environ.get("CHAT_ID", "")

DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads")
COOKIES_FILE = os.environ.get("COOKIES_FILE", "")


def _human_size(num_bytes):
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def download(url, download_dir=DOWNLOAD_DIR):
    """Download the given URL with yt-dlp. Returns the output file path."""
    import yt_dlp

    os.makedirs(download_dir, exist_ok=True)
    outtmpl = os.path.join(download_dir, "%(title)s.%(ext)s")

    cookies = COOKIES_FILE
    if not cookies and os.path.exists("cookies.txt"):
        cookies = "cookies.txt"

    ydl_opts = {
        # Best video+audio merged into a single mp4 when possible.
        "format": "bv*+ba/b",
        "merge_output_format": "mp4",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": False,
        "no_warnings": False,
    }
    if cookies:
        ydl_opts["cookiefile"] = cookies
        print(f"[ytdl] Using cookies from: {cookies}")

    print(f"[ytdl] Downloading: {url}")
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)

    # After merge the extension may have changed to .mp4
    if not os.path.exists(filepath):
        base = os.path.splitext(filepath)[0]
        candidates = glob.glob(base + ".*")
        if candidates:
            filepath = max(candidates, key=os.path.getsize)

    print(f"[ytdl] Saved: {filepath} ({_human_size(os.path.getsize(filepath))})")
    return filepath, info


def upload(filepath, info=None):
    """Upload a local file to Telegram via a bot using Pyrogram."""
    from pyrogram import Client

    if not (API_ID and API_HASH and BOT_TOKEN and CHAT_ID):
        raise SystemExit(
            "[ytdl] Missing Telegram config. Set API_ID, API_HASH, "
            "BOT_TOKEN and CHAT_ID (env vars or in the file)."
        )

    chat = CHAT_ID
    try:
        chat = int(CHAT_ID)  # numeric chat id
    except (TypeError, ValueError):
        pass  # keep as @username string

    caption = None
    if info:
        caption = info.get("title")

    last = {"t": 0.0}

    def progress(current, total):
        now = time.time()
        if now - last["t"] >= 1 or current == total:
            pct = (current / total * 100) if total else 0
            print(f"[ytdl] Uploading: {pct:5.1f}% "
                  f"({_human_size(current)}/{_human_size(total)})")
            last["t"] = now

    print("[ytdl] Connecting to Telegram...")
    app = Client(
        "ytdl_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        in_memory=True,
    )
    with app:
        app.send_video(
            chat_id=chat,
            video=filepath,
            caption=caption,
            progress=progress,
        )
    print("[ytdl] Upload complete.")


def download_and_upload(url):
    filepath, info = download(url)
    upload(filepath, info)
    return filepath


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: python ytdl.py <video_url> [more_urls...]")
        return 1
    for url in argv:
        download_and_upload(url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
