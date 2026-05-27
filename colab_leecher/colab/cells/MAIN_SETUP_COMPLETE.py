# ============================================================================
# TELEGRAM LEECHER BOT - COMPLETE COLAB SETUP
# ============================================================================
# @markdown ### **Required Credentials**
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

BOT_SELECTION = "Bot 1 - 7772724138" #@param ["Bot 1 - 7772724138", "Bot 2 - 7789803613", "Bot 3 - 7801279758", "Bot 4 - 8142502027", "Bot 5 - 8026493824", "Bot 6 - 8153061743", "Bot 7 - 8040105081", "Bot 8 - 7976702554", "Bot 9 - 8076591114", "Bot 10 - 7690538451", "Bot 11 - 7435181907", "Bot 12 - 8083239087", "Bot 13 - 8050092737"]

token_mapping = {
    "Bot 1 - 7772724138": "7772724138:AAHGfrzxM9RFmOzhbqqeEyRhrUeJuUJ698g",
    "Bot 2 - 7789803613": "7789803613:AAFJPcmDfmYls3ZPYSfoMQFKwtmQ5i5b2Xc",
    "Bot 3 - 7801279758": "7801279758:AAGvHGP46D5HZvdReOPGgipz_tEj8O7vFW4",
    "Bot 4 - 8142502027": "8142502027:AAFB3m4AHwnilQfMd3qzF--qRWIGNEV9TaQ",
    "Bot 5 - 8026493824": "8026493824:AAF9JeONzV026Vneom47ehyqiH6I_o5D_84",
    "Bot 6 - 8153061743": "8153061743:AAGEKt2V-Dc0cQVVTpaXSZ965Ens3ZWzT7A",
    "Bot 7 - 8040105081": "8040105081:AAE6UhR4SfCQn8lpTkUERdfrJZkXTxXhHB4",
    "Bot 8 - 7976702554": "7976702554:AAE5jPU_TEh-sqTq-_t7DhOss12KC0WAOzM",
    "Bot 9 - 8076591114": "8076591114:AAH8NiD1Yky3YsCq7j8mN_8a8BlaPIQ4wVQ",
    "Bot 10 - 7690538451": "7690538451:AAFV-yUo72Pt6EIoe3cXqKbdPON39qqjEgo",
    "Bot 11 - 7435181907": "7435181907:AAHHfzGp7chcgxnknQwbJe-kXprEtYntUag",
    "Bot 12 - 8083239087": "8083239087:AAFr7xex7TwzNlD7DZ5DQah0zihT93MtI3Q",
    "Bot 13 - 8050092737": "8050092737:AAHeoUOhivEJSY7VvqCdTy4O8HsapEB5-rs"
}

BOT_TOKEN = token_mapping[BOT_SELECTION]
USER_ID = 121110934

Dump_SELECTION = "Files 1 - Margaret" #@param ["Files 1 - Margaret", "Files 2 - Tate", "Files 3 - Kitty", "Files 4 - Peyton", "Files 5 - Olivia", "Files 6 - Emma"]

DumpToken_Mapping = {
    "Files 1 - Margaret": -1001593908646,
    "Files 2 - Tate": -1001599359953,
    "Files 3 - Kitty": -1001795431409,
    "Files 4 - Peyton": -1001786589126,
    "Files 5 - Olivia": -1001723897427,
    "Files 6 - Emma": -1001792878743,
}

DUMP_ID = DumpToken_Mapping[Dump_SELECTION]

# @markdown ### **Repository Settings**
USE_PUBLIC_REPO = True #@param {type:"boolean"}
# @markdown If using private repo, provide token below (get at: https://github.com/settings/tokens)
GITHUB_TOKEN = "" #@param {type:"string"}

# @markdown ### **Optional Downloader Cookies**
NZBCLOUD_CF_CLEARANCE = "" #@param {type:"string"}
BITSO_IDENTITY_COOKIE = "" #@param {type:"string"}
BITSO_PHPSESSID_COOKIE = "" #@param {type:"string"}

# ============================================================================
# SETUP SCRIPT - DO NOT MODIFY BELOW THIS LINE
# ============================================================================
import subprocess
import time
import json
import shutil
import os
import logging
from IPython import get_ipython
from IPython.display import clear_output, HTML, display
from threading import Thread

Working = True

# Logging setup
log = logging.getLogger('ColabLeecherSetup')
log.setLevel(logging.INFO)
if log.hasHandlers():
    log.handlers.clear()
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

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

# Keep alive audio
def keep_alive(url):
    display(HTML(f'<audio src="{url}" controls autoplay style="display:none"></audio>'))

def Loading():
    white = 37
    while Working:
        black = 74 - 2 * white
        print("\r" + "\u2593"*white + "\u2592\u2593" + "\u2592"*black + "\u2592\u2593" + "\u2593"*white, end="", flush=True)
        white = (white - 1) if white != 0 else 37
        time.sleep(0.5)
    clear_output()

audio_url = "https://raw.githubusercontent.com/KoboldAI/KoboldAI-Client/main/colab/silence.m4a"
audio_thread = Thread(target=keep_alive, args=(audio_url,))
audio_thread.start()
_Thread = Thread(target=Loading, name="Prepare", args=())
_Thread.start()

# Credentials validation
log.info("Validating credentials...")
valid_creds = True
if not all([API_ID > 0, API_HASH, BOT_TOKEN, USER_ID != 0, DUMP_ID != 0]):
    log.error("One or more required credentials missing/invalid!")
    valid_creds = False
    Working = False

if isinstance(DUMP_ID, int) and DUMP_ID != 0:
    if len(str(abs(DUMP_ID))) >= 10 and not str(DUMP_ID).startswith("-100"):
        n_dump = int("-100" + str(abs(DUMP_ID)))
        log.warning(f"Correcting DUMP_ID format: {DUMP_ID} -> {n_dump}")
        DUMP_ID = n_dump

# Repository configuration
if USE_PUBLIC_REPO:
    github_user = "theSadeQ"
    repository_name = "Colab-to-Tel"
    branch_name = "master"
    log.info("📦 Using PUBLIC repository: Colab-to-Tel")
else:
    github_user = "theSadeQ"
    repository_name = "Telegram-Leecher"
    branch_name = "feature/multi-task-parallel"
    log.info("📦 Using PRIVATE repository: Telegram-Leecher")
    if not GITHUB_TOKEN or not GITHUB_TOKEN.strip():
        log.warning("⚠️ Private repo selected but no GitHub token provided!")
        log.warning("💡 Get token at: https://github.com/settings/tokens")

repo_path = f"/content/{repository_name}"
requirements_file = os.path.join(repo_path, "requirements.txt")
credentials_path = os.path.join(repo_path, 'credentials.json')
bot_main_module = "colab_leecher"
session_file = os.path.join(repo_path, "my_bot.session")
setup_ok = False
ipython = get_ipython()

if valid_creds and ipython:
    log.info("✅ Required credentials present.")

    # Remove sample_data
    if os.path.exists("/content/sample_data"):
        log.info("🗑️ Removing sample_data...")
        shutil.rmtree("/content/sample_data")

    # Build clone URL
    if GITHUB_TOKEN and GITHUB_TOKEN.strip():
        clone_url = f"https://{GITHUB_TOKEN}@github.com/{github_user}/{repository_name}"
        log.info("🔑 Using GitHub token for authentication")
    else:
        clone_url = f"https://github.com/{github_user}/{repository_name}"

    # Clone or pull repository
    if not os.path.exists(repo_path):
        log.info(f"📥 Cloning {github_user}/{repository_name} (branch: {branch_name})...")
        cmd_clone = f"git clone -b {branch_name} {clone_url} {repo_path}"
        proc_clone = subprocess.run(cmd_clone, shell=True)

        if proc_clone.returncode != 0:
            log.error(f"❌ Git clone failed:\n{proc_clone.stderr}")
            if "could not read Username" in proc_clone.stderr or "Authentication failed" in proc_clone.stderr:
                log.error("💡 This is a private repository. Solutions:")
                log.error("   1. Set USE_PUBLIC_REPO = True (recommended)")
                log.error("   2. Provide GitHub token at: https://github.com/settings/tokens")
            Working = False
        else:
            log.info("✅ Repository cloned successfully")
    else:
        log.info(f"📂 Repository exists, pulling latest changes...")
        os.chdir(repo_path)

        # Update remote URL with token if provided
        if GITHUB_TOKEN and GITHUB_TOKEN.strip():
            cmd_set_url = f"git remote set-url origin {clone_url}"
            subprocess.run(cmd_set_url, shell=True)

        cmd_pull = f"git pull origin {branch_name}"
        proc_pull = subprocess.run(cmd_pull, shell=True)

        if proc_pull.returncode != 0:
            log.warning(f"⚠️ Git pull issues:\n{proc_pull.stderr}")
        else:
            log.info("✅ Repository updated to latest version")

    # Install system dependencies
    if Working and os.path.exists(repo_path):
        log.info("📦 Installing system packages (ffmpeg, aria2)...")
        cmd_apt = "add-apt-repository -y universe && apt-get update && apt-get install -y ffmpeg aria2 megatools"
        proc_apt = subprocess.run(cmd_apt, shell=True)

        if proc_apt.returncode != 0:
            log.warning(f"⚠️ Some apt packages may have issues:\n{proc_apt.stderr[:200]}")
        else:
            log.info("✅ System packages installed")

        # Install Python requirements
        log.info("🐍 Installing Python dependencies...")
        if os.path.exists(requirements_file):
            cmd_pip = f"pip3 install --no-cache-dir -r {requirements_file}"
            proc_pip = subprocess.run(cmd_pip, shell=True)

            if proc_pip.returncode != 0:
                log.error(f"❌ pip install failed:\n{proc_pip.stderr}")
                Working = False
            else:
                log.info("✅ Python packages installed")
        else:
            log.warning(f"⚠️ requirements.txt not found at {requirements_file}")

        # Install additional packages
        log.info("📸 Installing instaloader (Instagram support)...")
        cmd_insta = "pip3 install --no-cache-dir instaloader"
        subprocess.run(cmd_insta, shell=True)
        log.info("✅ Additional packages installed")

    # Write credentials file
    if Working:
        log.info("📝 Writing credentials file...")
        credentials = {
            "API_ID": API_ID,
            "API_HASH": API_HASH,
            "BOT_TOKEN": BOT_TOKEN,
            "USER_ID": USER_ID,
            "OWNER_ID": USER_ID,
            "DUMP_ID": DUMP_ID,
            "GDRIVE_FOLDER_ID": "",
            "INDEX_URL": "",
            "NZBCLOUD_CF_CLEARANCE": NZBCLOUD_CF_CLEARANCE,
            "BITSO_IDENTITY_COOKIE": BITSO_IDENTITY_COOKIE,
            "BITSO_PHPSESSID_COOKIE": BITSO_PHPSESSID_COOKIE,
            "INSTAGRAM": {
                "USERNAME": "",
                "COOKIES_FILE": ""
            }
        }

        try:
            os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
            with open(credentials_path, 'w') as file:
                json.dump(credentials, file, indent=4)
            log.info(f"✅ Credentials saved to {credentials_path}")
            setup_ok = True
        except IOError as e:
            log.error(f"❌ Failed to write credentials: {e}")
            Working = False

elif not ipython:
    log.error("❌ Could not get IPython instance")
    Working = False

# Stop loading animation
Working = False
_Thread.join()

# Start bot
if setup_ok:
    # Remove old session
    if os.path.exists(session_file):
        try:
            os.remove(session_file)
            log.info(f"🗑️ Removed old session file")
        except OSError as e:
            log.warning(f"⚠️ Could not remove session: {e}")

    log.info("="*70)
    log.info("🚀 STARTING BOT...")
    log.info("="*70)

    # Change to repo directory
    if os.getcwd() != repo_path:
        ipython.run_line_magic('cd', repo_path)
        log.info(f"📂 Changed directory to {repo_path}")

    # Run bot
    try:
        log.info(f"▶️ Executing: python3 -m {bot_main_module}")
        log.info("="*70 + "\n")
        exit_code = ipython.system(f'python3 -m {bot_main_module}')
        log.info(f"\n{'='*70}")
        log.info(f"Bot finished (exit code: {exit_code})")
        log.info("="*70)
    except Exception as e:
        log.critical(f"❌ Bot startup error: {e}", exc_info=True)

elif not valid_creds:
    print("\n" + "="*70)
    print("❌ SETUP FAILED: Invalid or missing credentials")
    print("="*70)
    print("Please check:")
    print("  • API_ID and API_HASH are set")
    print("  • BOT_TOKEN is selected")
    print("  • USER_ID is configured")
    print("  • DUMP_ID is selected")
    print("="*70)
else:
    print("\n" + "="*70)
    print("❌ SETUP FAILED: Check error logs above")
    print("="*70)
