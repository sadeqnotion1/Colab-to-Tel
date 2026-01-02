#================================================
#FILE: colab_leecher/__init__.py
#================================================
# copyright 2023 © Xron Trix | https://github.com/Xrontrix10

import logging, json, asyncio, os
# uvloop only works on Linux/Mac, not Windows
try:
    from uvloop import install as uvloop_install
except ImportError:
    uvloop_install = None  # Windows doesn't support uvloop
from pyrogram.client import Client
# --- ADDED: Import BOT object to set settings ---
from .utility.variables import BOT
# --- END ADDED ---

# Set up logging
logging.basicConfig(
     level=logging.INFO,
     format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__) # Use a logger instance


# Read the dictionary from the credentials file
# Use dynamic path detection for all platforms
credentials_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "credentials.json")
credentials = {}
try:
    with open(credentials_path, "r") as file:
        credentials = json.loads(file.read())
    log.info("Credentials loaded successfully.")
except FileNotFoundError:
     log.critical(f"CRITICAL ERROR: Credentials file not found at {credentials_path}. Bot cannot start.")
     # Exit or raise an exception to prevent the bot from continuing without credentials
     raise SystemExit("Credentials file missing.")
except json.JSONDecodeError as e:
     log.critical(f"CRITICAL ERROR: Failed to parse credentials file {credentials_path}: {e}. Bot cannot start.")
     raise SystemExit(f"Invalid credentials file: {e}")
except Exception as e:
     log.critical(f"CRITICAL ERROR: An unexpected error occurred loading credentials: {e}", exc_info=True)
     raise SystemExit(f"Unexpected error loading credentials: {e}")


# --- Assign credentials to variables ---
# Required credentials
API_ID = credentials.get("API_ID")
API_HASH = credentials.get("API_HASH")
BOT_TOKEN = credentials.get("BOT_TOKEN")
OWNER = credentials.get("USER_ID")
DUMP_ID = credentials.get("DUMP_ID")

# Validate required credentials
if not all([API_ID, API_HASH, BOT_TOKEN, OWNER, DUMP_ID]):
     missing = [k for k, v in {'API_ID': API_ID, 'API_HASH': API_HASH, 'BOT_TOKEN': BOT_TOKEN, 'USER_ID': OWNER, 'DUMP_ID': DUMP_ID}.items() if not v]
     log.critical(f"CRITICAL ERROR: Missing required credentials in {credentials_path}: {', '.join(missing)}. Bot cannot start.")
     raise SystemExit(f"Missing required credentials: {', '.join(missing)}")


# --- MODIFICATION: Load Optional Cookies and set them in BOT.Setting ---
log.info("Loading optional downloader cookies...")
BOT.Setting.nzb_cf_clearance = credentials.get("NZBCLOUD_CF_CLEARANCE", "") # Default to empty string if not found
BOT.Setting.bitso_identity_cookie = credentials.get("BITSO_IDENTITY_COOKIE", "")
BOT.Setting.bitso_phpsessid_cookie = credentials.get("BITSO_PHPSESSID_COOKIE", "")

log.info(f"NZBCloud CF Cookie: {'Set' if BOT.Setting.nzb_cf_clearance else 'Not Set'}")
log.info(f"Bitso Identity Cookie: {'Set' if BOT.Setting.bitso_identity_cookie else 'Not Set'}")
log.info(f"Bitso PHPSESSID Cookie: {'Set' if BOT.Setting.bitso_phpsessid_cookie else 'Not Set'}")

# --- Load Instagram Authentication ---
log.info("Loading Instagram authentication...")
BOT.Setting.instagram_username = credentials.get("INSTAGRAM_USERNAME", "")
BOT.Setting.instagram_password = credentials.get("INSTAGRAM_PASSWORD", "")
BOT.Setting.instagram_sessionid = credentials.get("INSTAGRAM_SESSIONID", "")
BOT.Setting.instagram_cookies_file = credentials.get("INSTAGRAM_COOKIES_FILE", "")

if BOT.Setting.instagram_username and BOT.Setting.instagram_password:
    log.info(f"Instagram Login: Configured (Username: {BOT.Setting.instagram_username})")
elif BOT.Setting.instagram_sessionid:
    log.info("Instagram Login: Configured (Session Cookie)")
elif BOT.Setting.instagram_cookies_file:
    log.info(f"Instagram Login: Configured (Cookie File: {BOT.Setting.instagram_cookies_file})")
else:
    log.info("Instagram Login: Not Configured (Limited access)")

# --- Load TeraBox Authentication ---
log.info("Loading TeraBox authentication...")
BOT.Setting.terabox_cookie = credentials.get("TERABOX_COOKIE", "")

if BOT.Setting.terabox_cookie:
    log.info("TeraBox Cookie: Configured (Enhanced downloader enabled)")
else:
    log.info("TeraBox Cookie: Not Configured (will use API fallback)")

# --- Load Usenet/NZB Provider Configurations ---
log.info("Loading Usenet provider configurations...")
nzb_providers_config = credentials.get("NZB_PROVIDERS", {})

if nzb_providers_config:
    BOT.Setting.nzb_providers = nzb_providers_config
    default_provider = credentials.get("NZB_DEFAULT_PROVIDER", list(nzb_providers_config.keys())[0] if nzb_providers_config else "")
    BOT.Setting.nzb_active_provider = default_provider
    log.info(f"Loaded {len(nzb_providers_config)} Usenet provider(s)")
    log.info(f"Active Provider: {default_provider if default_provider else 'None'}")
else:
    BOT.Setting.nzb_providers = {}
    BOT.Setting.nzb_active_provider = ""
    log.warning("No Usenet providers configured in credentials.json")
# --- END MODIFICATION ---


# Install uvloop (only on Linux/Mac, not Windows)
if uvloop_install:
    try:
         uvloop_install()
         log.info("uvloop installed.")
    except Exception as e:
         log.warning(f"Could not install uvloop: {e}")
else:
     log.info("uvloop not available (Windows) - using standard asyncio event loop")

# Fix for Python 3.12: Ensure event loop exists
try:
     loop = asyncio.get_event_loop()
     if loop.is_closed():
          raise RuntimeError("Event loop is closed")
except RuntimeError:
     log.info("Creating new event loop for Python 3.12+ compatibility...")
     loop = asyncio.new_event_loop()
     asyncio.set_event_loop(loop)
     log.info("Event loop created and set.")

# Initialize Pyrogram Client
try:
    log.info("Initializing Pyrogram client...")
    # Use consistent session name to prevent duplicate bot instances
    # This ensures only ONE bot session exists at a time
    session_name = "colab_bot"

    colab_bot = Client(
        session_name,  # Consistent session name
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        # --- Keep only valid parameters ---
        workers=16  # Increase worker threads (default is 4)
        # --- Removed retry_delay=1 ---
        # --- Removed sleep_threshold=10 ---
    )
    log.info("Pyrogram client initialized.")
    # ... (rest of the __init__.py) ...

except Exception as e:
    log.critical(f"Failed to initialize Pyrogram client: {e}", exc_info=True)
    colab_bot = None 
