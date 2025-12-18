#!/usr/bin/env python3
"""
Secure Colab Setup Cell for Telegram Leecher Bot
- Uses Colab Secrets for credentials (no hardcoded tokens!)
- Pulls latest code from GitHub
- Installs all dependencies
"""

import os
import sys
import time
import logging
import subprocess
from threading import Thread
from IPython.display import HTML, display, clear_output

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

# Banner
banner = r'''
 _____    _                                 _                     _
|_   _|__| | ___  __ _ _ __ __ _ _ __ ___ | |    ___  ___  ___| |__   ___ _ __
  | |/ _ \ |/ _ \/ _` | '__/ _` | '_ ` _ \| |   / _ \/ _ \/ __| '_ \ / _ \ '__|
  | |  __/ |  __/ (_| | | | (_| | | | | | | |__|  __/  __/ (__| | | |  __/ |
  |_|\___|_|\___|\__, |_|  \__,_|_| |_| |_|_____\___|\___|\___|_| |_|\___|_|
                 |___/
'''
print(banner)

Working = True

# =============================================================================
# CREDENTIALS - Using Colab Secrets (Secure Method)
# =============================================================================
# Add these in Colab Secrets (🔑 icon in left sidebar):
# - API_ID
# - API_HASH
# - BOT_TOKEN
# - USER_ID
# - DUMP_ID
# - OWNER_ID (optional, defaults to USER_ID)

try:
    from google.colab import userdata

    log.info("Loading credentials from Colab Secrets...")
    API_ID = int(userdata.get('API_ID'))
    API_HASH = userdata.get('API_HASH')
    BOT_TOKEN = userdata.get('BOT_TOKEN')
    USER_ID = int(userdata.get('USER_ID'))
    DUMP_ID = int(userdata.get('DUMP_ID'))

    # Optional: Get owner ID (defaults to USER_ID if not set)
    try:
        OWNER_ID = int(userdata.get('OWNER_ID'))
    except:
        OWNER_ID = USER_ID
        log.info(f"OWNER_ID not set, using USER_ID: {OWNER_ID}")

    log.info("✅ Credentials loaded from Colab Secrets")

except Exception as e:
    log.error(f"❌ Failed to load credentials from Colab Secrets: {e}")
    log.error("Please add credentials to Colab Secrets (🔑 icon on left):")
    log.error("  Required: API_ID, API_HASH, BOT_TOKEN, USER_ID, DUMP_ID")
    Working = False

# =============================================================================
# Keep-Alive Audio (Prevents Colab from disconnecting)
# =============================================================================
def keep_alive(url):
    display(HTML(f'<audio src="{url}" controls autoplay style="display:none"></audio>'))

def Loading():
    white = 37
    black = 0
    while Working:
        print("\r" + "▓"*white + "▒▓"+ "▒"*black + "▒▓" + "▓"*white, end="")
        black = (black + 2) % 75
        white = (white - 1) if white != 0 else 37
        time.sleep(0.5)
    clear_output()

audio_url = "https://raw.githubusercontent.com/KoboldAI/KoboldAI-Client/main/colab/silence.m4a"
audio_thread = Thread(target=keep_alive, args=(audio_url,))
audio_thread.start()
_Thread = Thread(target=Loading, name="Prepare", args=())
_Thread.start()

# =============================================================================
# Credentials Validation
# =============================================================================
log.info("Validating credentials...")
valid_creds = True

if not Working:
    valid_creds = False
elif not all([API_ID > 0, API_HASH, BOT_TOKEN, USER_ID != 0, DUMP_ID != 0]):
    log.error("One or more required credentials missing/invalid!")
    valid_creds = False
    Working = False

# Fix DUMP_ID format if needed
if valid_creds and isinstance(DUMP_ID, int) and DUMP_ID != 0:
    if len(str(abs(DUMP_ID))) >= 10 and not str(DUMP_ID).startswith("-100"):
        n_dump = int("-100" + str(abs(DUMP_ID)))
        log.warning(f"Correcting DUMP_ID format: {DUMP_ID} -> {n_dump}")
        DUMP_ID = n_dump

if valid_creds:
    log.info("✅ Credentials validated")

# =============================================================================
# Repository Setup
# =============================================================================
if Working and valid_creds:
    repo_url = "https://github.com/theSadeQ/Telegram-Leecher.git"
    branch = "feature/multi-task-parallel"
    repo_path = "/content/Telegram-Leecher"

    log.info(f"Setting up repository at {repo_path}...")

    # Clone or update repository
    if not os.path.exists(repo_path):
        log.info(f"Cloning repository from {repo_url}...")
        cmd_clone = f"git clone -b {branch} {repo_url} {repo_path}"
        proc_clone = subprocess.run(cmd_clone, shell=True, capture_output=True, text=True)

        if proc_clone.returncode != 0:
            log.error(f"Git clone failed:\n{proc_clone.stderr}")
            Working = False
        else:
            log.info("✅ Repository cloned successfully")
    else:
        log.info("Repository exists. Pulling latest changes...")
        os.chdir(repo_path)

        # Reset any local changes
        cmd_reset = "git reset --hard HEAD"
        subprocess.run(cmd_reset, shell=True, capture_output=True, text=True)

        # Pull latest changes
        cmd_pull = f"git pull origin {branch}"
        proc_pull = subprocess.run(cmd_pull, shell=True, capture_output=True, text=True)

        if proc_pull.returncode != 0:
            log.warning(f"Git pull issues:\n{proc_pull.stderr}")
            log.info("Attempting fresh clone...")
            os.chdir("/content")
            subprocess.run(f"rm -rf {repo_path}", shell=True)
            subprocess.run(f"git clone -b {branch} {repo_url} {repo_path}", shell=True)
        else:
            log.info("✅ Repository updated to latest version")

# =============================================================================
# Install Dependencies
# =============================================================================
if Working and os.path.exists(repo_path):
    os.chdir(repo_path)

    # Install OS packages
    log.info("Installing system packages (ffmpeg, aria2)...")
    cmd_apt = "apt-get update -qq && apt-get install -y -qq ffmpeg aria2"
    proc_apt = subprocess.run(cmd_apt, shell=True, capture_output=True, text=True)
    if proc_apt.returncode != 0:
        log.warning(f"Apt install issues:\n{proc_apt.stderr}")
    else:
        log.info("✅ System packages installed")

    # Install Mindvalley downloader dependencies
    mindvalley_script = os.path.join(repo_path, "install_mindvalley_deps.sh")
    if os.path.exists(mindvalley_script):
        log.info("Installing Mindvalley downloader dependencies...")
        cmd_mindvalley = f"bash {mindvalley_script}"
        proc_mindvalley = subprocess.run(cmd_mindvalley, shell=True, capture_output=True, text=True)
        if proc_mindvalley.returncode != 0:
            log.warning(f"Mindvalley deps install issues:\n{proc_mindvalley.stderr}")
        else:
            log.info("✅ Mindvalley downloader ready")

    # Install Python requirements
    requirements_file = os.path.join(repo_path, "requirements.txt")
    if os.path.exists(requirements_file):
        log.info("Installing Python packages...")
        cmd_pip = f"pip3 install --no-cache-dir -q -r {requirements_file}"
        proc_pip = subprocess.run(cmd_pip, shell=True, capture_output=True, text=True)
        if proc_pip.returncode != 0:
            log.error(f"pip install failed:\n{proc_pip.stderr}")
            Working = False
        else:
            log.info("✅ Python packages installed")

    # Install instaloader for Instagram downloads
    log.info("Installing instaloader for Instagram support...")
    cmd_insta = "pip3 install --no-cache-dir -q instaloader"
    subprocess.run(cmd_insta, shell=True, capture_output=True, text=True)
    log.info("✅ Instaloader installed")

# =============================================================================
# Setup Credentials File
# =============================================================================
if Working and os.path.exists(repo_path):
    import json

    credentials_path = os.path.join(repo_path, "colab_leecher", "credentials.json")
    log.info(f"Creating credentials file at {credentials_path}...")

    credentials = {
        "api_id": API_ID,
        "api_hash": API_HASH,
        "bot_token": BOT_TOKEN,
        "user_id": USER_ID,
        "owner_id": OWNER_ID,
        "dump_id": DUMP_ID,
        "gdrive_folder_id": "",
        "index_url": "",
        "instagram": {
            "username": "",
            "cookies_file": ""
        }
    }

    try:
        with open(credentials_path, 'w') as f:
            json.dump(credentials, f, indent=4)
        log.info("✅ Credentials file created")
    except Exception as e:
        log.error(f"Failed to create credentials file: {e}")
        Working = False

# =============================================================================
# Start Bot
# =============================================================================
if Working and valid_creds:
    Working = False  # Stop loading animation
    time.sleep(1)
    clear_output()

    print(banner)
    print("=" * 80)
    print("🚀 STARTING TELEGRAM LEECHER BOT")
    print("=" * 80)
    print(f"Repository: {repo_path}")
    print(f"Branch: {branch}")
    print(f"User ID: {USER_ID}")
    print(f"Dump ID: {DUMP_ID}")
    print("=" * 80)
    print("\n")

    os.chdir(repo_path)

    try:
        log.info("Starting bot...")
        # Use python3 -m to run the module
        exit_code = os.system("python3 -m colab_leecher")
        log.info(f"Bot process finished (exit code: {exit_code})")
    except KeyboardInterrupt:
        log.info("Bot stopped by user")
    except Exception as e:
        log.error(f"Bot startup error: {e}", exc_info=True)

elif not valid_creds:
    Working = False
    time.sleep(1)
    clear_output()
    print("\n" + "=" * 80)
    print("❌ BOT SETUP SKIPPED: Invalid or missing credentials")
    print("=" * 80)
    print("\nPlease add the following to Colab Secrets (🔑 icon on left):")
    print("  • API_ID")
    print("  • API_HASH")
    print("  • BOT_TOKEN")
    print("  • USER_ID")
    print("  • DUMP_ID")
    print("=" * 80)
else:
    Working = False
    time.sleep(1)
    clear_output()
    print("\n" + "=" * 80)
    print("❌ BOT SETUP FAILED - Check logs above")
    print("=" * 80)
