#================================================
#FILE: colab_leecher/utility/variables.py
#================================================
# /content/Telegram-Leecher/colab_leecher/utility/variables.py
# Defines global state objects and paths
# Includes fix for TaskError instantiation
# Includes TRANSFER instance import/creation
# Includes the original YTDL class definition

from time import time
from datetime import datetime
# Use try-except for optional type hinting import
try:
    from pyrogram.types import Message
except ImportError:
    Message = None # Define as None if pyrogram types are not available at definition time

# Import the Transfer class definition (ensure relative path is correct)
try:
    from .transfer_state import Transfer
except ImportError:
    # Define a dummy Transfer class if import fails
    class Transfer:
        def reset(self): pass
    print("WARNING: Could not import Transfer class from transfer_state.py")

# Define BOT class structure for settings, options, mode, and state
class BOT:
    SOURCE = []
    TASK = None
    class Setting:
        stream_upload = "Media"
        convert_video = "No" # Default conversion is OFF
        convert_quality = "Low"
        caption = "Monospace"
        split_video = "Split Videos"
        prefix = ""
        suffix = ""
        thumbnail = False
        nzb_cf_clearance = ""
        bitso_identity_cookie = ""
        bitso_phpsessid_cookie = ""
        # NZB/Usenet Settings (Multi-Provider Support)
        nzb_providers = {}  # Dict of provider configs
        nzb_active_provider = "default"  # Currently selected provider

    class Options:
        stream_upload = True # Keep this consistent with Setting unless logic changes it
        convert_video = False # Default conversion OFF internally
        convert_quality = False # False for Low
        is_split = True
        caption = "code"
        video_out = "mp4"
        custom_name = ""
        zip_pswd = ""
        unzip_pswd = ""
        delta_extract_filenames = True
        bitso_extract_filenames = True
        filenames = []
        # --- Includes service_type from earlier modification ---
        service_type = None # e.g., 'direct', 'delta', 'nzbcloud', 'bitso', 'ytdl', 'local', 'gdrive', 'mega'
        # --- END ---
    class Mode:
        mode = "leech"  # Possible values: "leech" (Telegram upload), "mirror" (local copy), "gdrive" (Google Drive upload)
        type = "normal"
        ytdl = False
    class State:
        started = False
        task_going = False
        prefix = False
        suffix = False
        expecting_nzb_filenames = False
        expecting_Debrid_filenames = False
        expecting_bitso_filenames = False
        mindvalley_waiting = False
        extract_waiting = False  # Waiting for extract path input
        nzb_waiting = False  # Waiting for NZB file/URL


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
    failed_links = [] # Keep the list for failed links

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
    WORK_PATH = "/content/Telegram-Leecher/BOT_WORK"
    THMB_PATH = "/content/Telegram-Leecher/colab_leecher/Thumbnail.jpg"
    VIDEO_FRAME = f"{WORK_PATH}/video_frame.jpg"
    HERO_IMAGE = f"{WORK_PATH}/Hero.jpg"
    DEFAULT_HERO = "/content/Telegram-Leecher/custom_thmb.jpg"
    MOUNTED_DRIVE = "/content/drive"
    down_path = f"{WORK_PATH}/Downloads"
    temp_dirleech_path = f"{WORK_PATH}/dir_leech_temp"
    # --- CHOOSE ONE mirror_dir ---
    mirror_dir = "/content/Mirrored_Files" # Default GDupload path
    # mirror_dir = "/content/Colab Leecher Uploads" # Example local path (needs mount check removed in task_manager)
    # --- End mirror_dir choice ---
    temp_zpath = f"{WORK_PATH}/Leeched_Files"
    temp_unzip_path = f"{WORK_PATH}/Unzipped_Files"
    temp_files_dir = f"{WORK_PATH}/leech_temp"
    thumbnail_ytdl = f"{WORK_PATH}/ytdl_thumbnails"
    access_token = "/content/token.pickle"


# Define Messages class for storing message content fragments
class Messages:
    """Stores strings and context related to messages."""
    caution_msg = "\n\n<i>💖✨ ¡Hala Madrid!...y nada más ✨💖</b></i>"
    download_name = ""
    task_msg = ""
    status_head = f"<b>📥 DOWNLOADING » </b>\n" # Default status head
    extract_head = f"<b>📂 EXTRACTING »</b>\n" # Extraction status head
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


# Create a global instance of the Transfer class (imported from transfer_state.py)
try:
    TRANSFER = Transfer()
except NameError:
    # Handle case where Transfer class import failed
    print("ERROR: Transfer class not defined. Transfer statistics will not work.")
    class _DummyTransfer:
        down_bytes = [0]; up_bytes = [0]; total_down_size = 0
        sent_file = []; sent_file_names = []
        def reset(self): pass
    TRANSFER = _DummyTransfer()

