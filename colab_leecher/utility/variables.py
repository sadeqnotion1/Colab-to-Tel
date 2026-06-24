from __future__ import annotations
# ================================================
# FILE: colab_leecher/utility/variables.py
# ================================================
# /content/Telegram-Leecher/colab_leecher/utility/variables.py
# Defines global state objects and paths
# Includes fix for TaskError instantiation
# Includes TRANSFER instance import/creation
# Includes the original YTDL class definition

import os as _os
from time import time
from datetime import datetime
# Use try-except for optional type hinting import
try:
    from pyrogram.types import Message
except ImportError:
    Message = None  # Define as None if pyrogram types are not available at definition time

# Import the Transfer class definition (ensure relative path is correct)
try:
    from .transfer_state import Transfer
except ImportError:
    # Define a dummy Transfer class if import fails
    class Transfer:
        def reset(self): pass
    print("WARNING: Could not import Transfer class from transfer_state.py")

"""
Legacy BOT container used by taskScheduler/task_manager.

Active setup/reply flows are migrating to per-user state maps in `__main__.py` and
`utility/reply_state.py`. Global fields such as `BOT.SOURCE` and
`BOT.Options.filenames/service_type` are now treated as task-launch compatibility
bridges and should only be hydrated immediately before starting a legacy task.
"""
# Define BOT class structure for settings, options, mode, and state


class BOT:
    SOURCE = []  # Legacy compatibility bridge; avoid setup-phase writes.
    TASK = None

    class Setting:
        stream_upload = "Media"
        convert_video = "No"  # Default conversion is OFF
        convert_quality = "Low"
        caption = "Monospace"
        split_video = "Split Videos"
        prefix = ""
        suffix = ""
        thumbnail = False
        concurrency = "Parallel"
        nzb_cf_clearance = ""
        nzb_user_agent = ""
        bitso_identity_cookie = ""
        bitso_phpsessid_cookie = ""
        # Instagram Authentication
        instagram_username = ""
        instagram_password = ""
        instagram_sessionid = ""  # Alternative: use session cookie instead
        # Path to cookies.txt file (Netscape format)
        instagram_cookies_file = ""
        # NZB/Usenet Settings (Multi-Provider Support)
        nzb_providers = {}  # Dict of provider configs
        nzb_active_provider = "default"  # Currently selected provider

    class Options:
        stream_upload = True  # Keep this consistent with Setting unless logic changes it
        convert_video = False  # Default conversion OFF internally
        convert_quality = False  # False for Low
        is_split = True
        caption = "code"
        video_out = "mp4"
        custom_name = ""
        zip_pswd = ""
        unzip_pswd = ""
        concurrency = "parallel"
        # Options: "zip", "rar", "7z" (default: 7z - best compression, works on
        # all platforms, less corruption)
        archive_format = "7z"
        delta_extract_filenames = True
        bitso_extract_filenames = True
        filenames = []
        # --- Includes service_type from earlier modification ---
        # e.g., 'direct', 'delta', 'nzbcloud', 'bitso', 'ytdl', 'local',
        # 'gdrive', 'mega'
        service_type = None
        # --- END ---

    class Mode:
        # Possible values: "leech" (Telegram upload), "mirror" (local copy),
        # "gdrive" (Google Drive upload)
        mode = "leech"
        type = "normal"
        ytdl = False

    class State:
        started = False
        task_going = False
        prefix = False
        suffix = False
        # Legacy compatibility flags retained to avoid breaking external
        # callers.
        expecting_nzb_filenames = False
        expecting_Debrid_filenames = False
        expecting_bitso_filenames = False
        mindvalley_waiting = False
        extract_waiting = False
        nzb_waiting = False
        password_waiting = False
        password_retry_context = None
        reply_prompt_msg_id = None


# --- Original YTDL State Class (Restored as requested) ---
class YTDL:
    """Holds state for the original YTDL progress reporting."""
    header = ""
    speed = ""
    percentage = 0.0
    eta = ""
    done = ""
    left = ""
# --- END RESTORED SECTION ---


# --- TaskError class definition and instance (with modifications) ---
class _TaskErrorState:
    """Holds error state for the current task."""
    state = False
    text = ""
    failed_links = []  # Keep the list for failed links

    def reset(self):
        """Resets the error state for a new task."""
        self.state = False
        self.text = ""
        self.failed_links = []


# Create the single global instance of the error state
TaskError = _TaskErrorState()
# --- END TaskError Fix ---


# Define BotTimes class for tracking timestamps
class BotTimes:
    """Holds various timestamps related to bot operation."""
    current_time = time()
    start_time = datetime.now()
    task_start = datetime.now()


# Define Paths class for storing file system paths
class Paths:
    """Stores relevant file system paths used by the bot."""
    # Auto-detect environment (Windows or Linux/Colab)
    # Use dynamic path detection for both Windows and Linux/Colab
    _ROOT_PATH = _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__)))
    _BASE_PATH = _os.path.join(_ROOT_PATH, "BOT_WORK")

    WORK_PATH = _BASE_PATH
    THMB_PATH = _os.path.join(_ROOT_PATH, "colab_leecher", "Thumbnail.jpg")
    VIDEO_FRAME = _os.path.join(_BASE_PATH, "video_frame.jpg")
    HERO_IMAGE = _os.path.join(_BASE_PATH, "Hero.jpg")
    DEFAULT_HERO = _os.path.join(_ROOT_PATH, "custom_thmb.jpg")
    MOUNTED_DRIVE = _os.path.join(
        "/content",
        "drive") if _os.name != 'nt' else _os.path.join(
        _ROOT_PATH,
        "drive")
    down_path = _os.path.join(_BASE_PATH, "Downloads")
    temp_dirleech_path = _os.path.join(_BASE_PATH, "dir_leech_temp")
    mirror_dir = _os.path.join(
        "/content",
        "Mirrored_Files") if _os.name != 'nt' else _os.path.join(
        _ROOT_PATH,
        "Mirrored_Files")
    temp_zpath = _os.path.join(_BASE_PATH, "Leeched_Files")
    temp_unzip_path = _os.path.join(_BASE_PATH, "Unzipped_Files")
    temp_files_dir = _os.path.join(_BASE_PATH, "leech_temp")
    thumbnail_ytdl = _os.path.join(_BASE_PATH, "ytdl_thumbnails")
    access_token = _os.path.join(
        "/content",
        "token.pickle") if _os.name != 'nt' else _os.path.join(
        _ROOT_PATH,
        "token.pickle")


# Define Messages class for storing message content fragments
class Messages:
    """Stores strings and context related to messages."""
    # FIX #1: removed orphaned </b> tag (was </b></i>, should be </i>)
    caution_msg = "\n\n<i>\U0001f496\u2728 \u00a1Hala Madrid!...y nada m\u00e1s \u2728\U0001f496</i>"
    download_name = ""
    task_msg = ""
    # FIX #7: unified » spacing — both now use '<b>LABEL »</b>' (no trailing space before </b>)
    status_head = f"<b>\U0001f4e5 DOWNLOADING \u00bb</b>\n"
    extract_head = f"<b>\U0001f4c2 EXTRACTING \u00bb</b>\n"
    dump_task = ""
    src_link = ""
    link_p = ""


# Define MSG class for storing key message objects
class MSG:
    """Stores important Pyrogram message objects."""
    sent_msg: Message | None = None
    status_msg: Message | None = None


# Define Aria2c class for aria2 related state/settings
class Aria2c:
    """Stores state and settings related to Aria2c downloader."""
    link_info = False
    pic_dwn_url = "https://simp6.jpg5.su/images3/githube6efd630a79b894a.jpg"


# Define Gdrive class (placeholder for potential GDrive service object)
class Gdrive:
    """Placeholder for Google Drive API service object."""
    service = None


# Create a global instance of the Transfer class (imported from
# transfer_state.py)
try:
    TRANSFER = Transfer()
except NameError:
    # Handle case where Transfer class import failed
    print("ERROR: Transfer class not defined. Transfer statistics will not work.")

    class _DummyTransfer:
        down_bytes = [0]
        up_bytes = [0]
        total_down_size = 0
        sent_file = []
        sent_file_names = []
        def reset(self): pass
    TRANSFER = _DummyTransfer()


# Global shared setup session state to prevent circular/duplicate module namespace imports (e.g. __main__ vs colab_leecher.__main__)
import asyncio
setup_sessions = {}
setup_sessions_lock = asyncio.Lock()

def _clone_setup_session(state: dict | None) -> dict | None:
    """Return a defensive copy of per-user setup session state."""
    if not state:
        return None
    return {
        "mode": state.get("mode"),
        "source_links": list(state.get("source_links", [])),
        "service_type": state.get("service_type"),
        "filenames": list(state.get("filenames", [])),
        "custom_name": state.get("custom_name", ""),
        "zip_pswd": state.get("zip_pswd", ""),
        "unzip_pswd": state.get("unzip_pswd", ""),
        "archive_format": state.get("archive_format", "7z"),
    }

async def _get_setup_session(user_id: int) -> dict | None:
    """Fetch per-user setup session state."""
    async with setup_sessions_lock:
        return _clone_setup_session(setup_sessions.get(user_id))

async def _update_setup_session(user_id: int, **updates) -> dict:
    """Create/update per-user setup session state."""
    async with setup_sessions_lock:
        current = setup_sessions.get(user_id, {})
        merged = {
            "mode": current.get("mode"),
            "source_links": list(current.get("source_links", [])),
            "service_type": current.get("service_type"),
            "filenames": list(current.get("filenames", [])),
            "custom_name": current.get("custom_name", ""),
            "zip_pswd": current.get("zip_pswd", ""),
            "unzip_pswd": current.get("unzip_pswd", ""),
            "archive_format": current.get("archive_format", "7z"),
        }
        for key, value in updates.items():
            if key in {"source_links", "filenames"}:
                merged[key] = list(value or [])
            else:
                merged[key] = value
        setup_sessions[user_id] = merged
        return _clone_setup_session(merged) or {}

async def _clear_setup_session(user_id: int) -> dict | None:
    """Clear per-user setup session state."""
    async with setup_sessions_lock:
        state = setup_sessions.pop(user_id, None)
    return _clone_setup_session(state)
