# @markdown ### **Required Credentials**
# @markdown ⚠️ **SECURITY WARNING:** Replace these placeholder values with your actual credentials
# @markdown Get API_ID and API_HASH from: https://my.telegram.org/apps
# @markdown Get BOT_TOKEN from: @BotFather on Telegram

API_ID = 0  # @param {type:"integer"}
API_HASH = ""  # @param {type:"string"}
BOT_TOKEN = ""  # @param {type:"string"}
USER_ID = 0  # @param {type:"integer"}
DUMP_ID = 0  # @param {type:"integer"}

# @markdown ---
# @markdown **Alternative: Use bot/channel selection** (if you have multiple bots/channels)
# @markdown Leave above fields as 0/"" if using selections below

USE_SELECTION = False  # @param {type:"boolean"}

# Bot selection (only used if USE_SELECTION = True)
BOT_SELECTION = "Bot 1" #@param ["Bot 1", "Bot 2", "Bot 3"]
token_mapping = {
    "Bot 1": "YOUR_BOT_1_TOKEN_HERE",
    "Bot 2": "YOUR_BOT_2_TOKEN_HERE",
    "Bot 3": "YOUR_BOT_3_TOKEN_HERE"
}

# Channel selection (only used if USE_SELECTION = True)
Dump_SELECTION = "Channel 1"  #@param ["Channel 1", "Channel 2", "Channel 3"]
DumpToken_Mapping = {
    "Channel 1": -1001234567890,
    "Channel 2": -1001234567891,
    "Channel 3": -1001234567892,
}

# Apply selections if enabled
if USE_SELECTION:
    BOT_TOKEN = token_mapping[BOT_SELECTION]
    DUMP_ID = DumpToken_Mapping[Dump_SELECTION]

# @markdown ### **GitHub Access (For Private Repos)**
# @markdown Leave blank if repository is public. Get token from: https://github.com/settings/tokens
GITHUB_TOKEN = "" # @param {type:"string"}
GITHUB_USER = "theSadeQ" # @param {type:"string"}
GITHUB_REPO = "Colab-to-Tel" # @param {type:"string"}
GITHUB_BRANCH = "master" # @param {type:"string"}

# @markdown ### **Optional Downloader Cookies**
NZBCLOUD_CF_CLEARANCE = "" # @param {type:"string"}
BITSO_IDENTITY_COOKIE = "" # @param {type:"string"}
BITSO_PHPSESSID_COOKIE = "" # @param {type:"string"}


import subprocess, time, json, shutil, os, logging
from IPython import get_ipython
from IPython.display import clear_output, HTML, display
from threading import Thread

Working = True

# --- Basic logging setup ---
log = logging.getLogger('ColabLeecherSetup')
log.setLevel(logging.INFO)
if log.hasHandlers(): log.handlers.clear()

# Console handler
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
log.addHandler(handler)

# File handler - saves ALL logs so they don't disappear in Colab
log_file_path = '/content/setup_full.log'
file_handler = logging.FileHandler(log_file_path, mode='w')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
log.addHandler(file_handler)
# --- End logging setup ---

log.info("=" * 70)
log.info(f"📝 Full setup log will be saved to: {log_file_path}")
log.info("=" * 70)


banner = '''


              _____     __     __     __              __
             / ___/__  / /__ _/ /    / / ___ ___ ____/ /  ___ ____
            / /__/ _ \\/ / _ `/ _ \\  / /_/ -_) -_) __/ _ \\/ -_) __/
            \\___/\\___/_/\\_,_/_.__/ /____|__/\\__/\\__/_//_/\\__/_/



'''

print(banner)

def keep_alive(url):
    display(HTML(f'<audio src="{url}" controls autoplay style="display:none"></audio>'))

def Loading():
    white = 37
    black = 0
    while Working:
        print("\r" + "▓"*white + "▒▓"+ "▒"*black + "▒▓" + "▓"*white, end="")
        black = (black + 2) % 75
        white = (white -1) if white != 0 else 37
        time.sleep(2)
    # Only clear if everything is fine, otherwise keep logs for debugging
    if setup_ok:
        clear_output()
    else:
        print("\n") # Just a newline to stop the spinner line

audio_url    = "https://raw.githubusercontent.com/KoboldAI/KoboldAI-Client/main/colab/silence.m4a"
audio_thread = Thread(target=keep_alive, args=(audio_url,))
audio_thread.start()
_Thread = Thread(target=Loading, name="Prepare", args=())
_Thread.start()


# --- Credentials Validation ---
log.info("Validating credentials...")
valid_creds = True
if not all([API_ID > 0, API_HASH, BOT_TOKEN, USER_ID != 0, DUMP_ID != 0]):
     log.error("One or more required credentials missing/invalid (must be non-zero/non-empty)!")
     valid_creds = False; Working = False
if isinstance(DUMP_ID, int) and DUMP_ID != 0:
    if len(str(abs(DUMP_ID))) >= 10 and not str(DUMP_ID).startswith("-100"):
        n_dump = int("-100" + str(abs(DUMP_ID)))
        log.warning(f"Correcting DUMP_ID format: {DUMP_ID} -> {n_dump}"); DUMP_ID = n_dump
    elif not str(DUMP_ID).startswith("-100"):
         log.warning(f"DUMP_ID {DUMP_ID} not standard chat ID.")
else:
     if valid_creds: log.error("DUMP_ID missing/invalid."); valid_creds = False; Working = False

# --- Environment Setup ---
# Use repository name from editable parameters
repo_name = GITHUB_REPO
repo_path = f"/content/{repo_name}"
# --- END MODIFICATION ---
# --- CORRECTED PATH BASED ON IMAGE ---
colab_dir_path = os.path.join(repo_path, "colab_leecher") # Points to the directory containing __main__.py
# --- END CORRECTION ---
main_script_path = os.path.join(colab_dir_path, "__main__.py")
requirements_file = os.path.join(repo_path, "requirements.txt")
credentials_path = os.path.join(repo_path, 'credentials.json')
bot_main_module = "colab_leecher" # This module name is correct based on image
session_file = os.path.join(repo_path, "my_bot.session")
setup_ok = False
ipython = get_ipython()

if valid_creds and ipython:
     log.info("Required credentials seem present.")
     if os.path.exists("/content/sample_data"): log.info("Removing sample_data..."); shutil.rmtree("/content/sample_data")

     # --- Conditional Git Clone with CORRECT URL ---
     if not os.path.exists(repo_path):
          log.info(f"Repository not found at {repo_path}. Cloning YOUR repo...")

          # Use editable parameters from top of cell
          github_user = GITHUB_USER
          repository_name = GITHUB_REPO
          branch_name = GITHUB_BRANCH

          log.info(f"📦 Cloning {github_user}/{repository_name} (branch: {branch_name})")

          # Build git URL with token if provided (for private repos)
          if GITHUB_TOKEN:
              git_url = f"https://{GITHUB_TOKEN}@github.com/{github_user}/{repository_name}"
              log.info("🔐 Using GitHub token for private repository access")
          else:
              git_url = f"https://github.com/{github_user}/{repository_name}"
              log.info("🌐 Cloning public repository")

          # Construct the git clone command
          cmd_clone = f"git clone -b {branch_name} {git_url} {repo_path}"
          # --- END MODIFICATION ---
          proc_clone = subprocess.run(cmd_clone, shell=True, capture_output=True, text=True)
          if proc_clone.returncode != 0:
              log.error(f"Git clone failed:\n{proc_clone.stderr}")
              if "could not read Username" in proc_clone.stderr or "Authentication failed" in proc_clone.stderr:
                  log.error("=" * 70)
                  log.error("🚨 AUTHENTICATION ERROR:")
                  log.error("The repository appears to be PRIVATE.")
                  log.error("")
                  log.error("Solutions:")
                  log.error("1. Make repo public: Settings → Danger Zone → Change visibility")
                  log.error("2. Add GitHub token above (get from: github.com/settings/tokens)")
                  log.error("=" * 70)
              Working = False
          else:
              log.info("✅ Repository cloned successfully")
              log.info(f"📁 Repository path: {repo_path}")

     else:
         log.warning(f"Repository already exists at {repo_path}. Skipping clone.")

     # --- Install Dependencies ---
     if Working and os.path.exists(repo_path):
          log.info("Checking/Installing OS packages..."); cmd_apt = "add-apt-repository -y universe && apt-get update && apt-get install -y ffmpeg aria2 megatools"; proc_apt = subprocess.run(cmd_apt, shell=True, capture_output=True, text=True)
          if proc_apt.returncode != 0: log.warning(f"Apt install issues:\n{proc_apt.stderr}")
          else: log.info("OS packages checked/installed.")

          log.info("Installing Mindvalley downloader dependencies...")
          cmd_mindvalley = f"bash {repo_path}/install_mindvalley_deps.sh"
          proc_mindvalley = subprocess.run(cmd_mindvalley, shell=True, capture_output=True, text=True)
          if proc_mindvalley.returncode != 0:
              log.warning(f"Mindvalley deps install issues:\n{proc_mindvalley.stderr}")
          else:
              log.info("✅ Mindvalley downloader ready (N_m3u8DL-RE + FFmpeg)")

          log.info("Installing Python requirements...");
          if os.path.exists(requirements_file):
              cmd_pip = f"pip3 install --no-cache-dir -r {requirements_file}"; proc_pip = subprocess.run(cmd_pip, shell=True, capture_output=True, text=True)
              if proc_pip.returncode != 0: log.error(f"pip install failed:\n{proc_pip.stderr}"); Working = False
              else: log.info("Python requirements installed.")
          else: log.error(f"Requirements file not found: {requirements_file}"); Working = False
     elif not os.path.exists(repo_path): log.error("Repo dir not found, cannot install dependencies."); Working = False

     # --- Write Credentials File with NZB Support ---
     if Working:
         log.info("Writing credentials file with NZB configuration...")

         # Base credentials
         credentials = {
             "API_ID": API_ID,
             "API_HASH": API_HASH,
             "BOT_TOKEN": BOT_TOKEN,
             "USER_ID": USER_ID,
             "DUMP_ID": DUMP_ID,
             "NZBCLOUD_CF_CLEARANCE": NZBCLOUD_CF_CLEARANCE,
             "BITSO_IDENTITY_COOKIE": BITSO_IDENTITY_COOKIE,
             "BITSO_PHPSESSID_COOKIE": BITSO_PHPSESSID_COOKIE,

             # --- ADDED: NZB Provider Configuration ---
             # NZB_PROVIDERS should be configured in credentials.json
             # See credentials.json.example for the format
             "NZB_PROVIDERS": {},
             "NZB_DEFAULT_PROVIDER": ""
             # --- END ADDED ---
         }

         try:
             # Ensure parent directory exists before writing
             os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
             with open(credentials_path, 'w') as file:
                 json.dump(credentials, file, indent=4)
             log.info(f"✅ Credentials written to {credentials_path}")
             log.info(f"⚙️  Configure NZB providers in credentials.json (see credentials.json.example)")
             setup_ok = True
         except IOError as e:
             log.error(f"Failed to write credentials file: {e}")
             Working = False

     # --- SABnzbd Setup for NZB Downloads ---
     if Working and setup_ok:
         log.info("=" * 70)
         log.info("Setting up SABnzbd for NZB downloads...")
         log.info("=" * 70)

         try:
             # Install SABnzbd system dependencies
             log.info("Installing SABnzbd system dependencies...")
             cmd_apt_sabnzbd = "apt-get update -qq && apt-get install -y -qq python3-pip python3-dev par2 unrar unzip p7zip-full"
             proc_apt_sab = subprocess.run(cmd_apt_sabnzbd, shell=True, capture_output=True, text=True)
             if proc_apt_sab.returncode != 0:
                 log.warning(f"SABnzbd apt install issues:\n{proc_apt_sab.stderr}")
                 raise Exception("Failed to install SABnzbd system dependencies")
             log.info("✅ SABnzbd system dependencies installed")

             # Install SABnzbd Python package
             log.info("Installing SABnzbd Python package...")
             cmd_pip_sabnzbd = "pip3 install sabnzbd --quiet"
             proc_pip_sab = subprocess.run(cmd_pip_sabnzbd, shell=True, capture_output=True, text=True)
             if proc_pip_sab.returncode != 0:
                 log.warning(f"SABnzbd pip install issues:\n{proc_pip_sab.stderr}")
                 raise Exception("Failed to install SABnzbd Python package")
             log.info("✅ SABnzbd Python package installed")

             # Import SABnzbd setup modules (need to import after pip install)
             import sys
             sys.path.insert(0, repo_path)  # Ensure our repo is in path
             from colab_leecher.utility.sabnzbd_setup import setup_sabnzbd
             from colab_leecher.downlader.sabnzbd_downloader import set_sabnzbd_config

             # Setup and start SABnzbd
             log.info("Configuring and starting SABnzbd...")
             sabnzbd_config = setup_sabnzbd()

             if sabnzbd_config and sabnzbd_config.get('base_url'):
                 set_sabnzbd_config(sabnzbd_config)
                 log.info(f"✅ SABnzbd configured successfully")
                 log.info(f"   Base URL: {sabnzbd_config['base_url']}")
                 log.info(f"   API Key: {sabnzbd_config['api_key'][:8]}...")

                 # Save URL to file so bot can send it via Telegram on startup
                 # Prefer public URL, fallback to local URL
                 url_to_save = sabnzbd_config.get('public_url') or sabnzbd_config.get('base_url')
                 sabnzbd_info_file = os.path.join(repo_path, '.sabnzbd_url.txt')

                 if url_to_save:
                     with open(sabnzbd_info_file, 'w') as f:
                         f.write(f"{url_to_save}\n")
                         f.write(f"{sabnzbd_config['api_key']}\n")
                         # Add a flag to indicate if it's local or public
                         f.write(f"{'public' if sabnzbd_config.get('public_url') else 'local'}\n")

                     url_type = "public" if sabnzbd_config.get('public_url') else "local"
                     log.info(f"   Saved {url_type} URL info for Telegram notification")

                 # Display URL info
                 if sabnzbd_config.get('public_url'):
                     log.info("=" * 70)
                     log.info(f"🌐 SABnzbd Web UI (Public): {sabnzbd_config['public_url']}")
                     log.info(f"🔑 API Key: {sabnzbd_config['api_key']}")
                     log.info("=" * 70)
                 else:
                     log.info("=" * 70)
                     log.info(f"🏠 SABnzbd Web UI (Local): {sabnzbd_config.get('base_url', 'N/A')}")
                     log.info(f"🔑 API Key: {sabnzbd_config['api_key']}")
                     log.info("=" * 70)

                 log.info(f"✅ SABnzbd is ready for NZB downloads")
             else:
                 log.warning("⚠️ SABnzbd setup returned invalid config")
                 raise Exception("SABnzbd configuration failed")

         except Exception as e:
             log.warning("=" * 70)
             log.warning(f"⚠️ SABnzbd setup failed: {e}")
             log.warning("⚠️ Bot will use custom NNTP downloader as fallback")
             log.warning("=" * 70)
             # Don't set Working = False, just continue without SABnzbd

elif not ipython: log.error("Could not get IPython instance."); Working = False

# --- Stop Loading Animation ---
Working = False; _Thread.join()

# --- Final Check and Bot Start ---
if setup_ok:
    if os.path.exists(session_file):
        try: os.remove(session_file); log.info(f"Removed previous session: {session_file}")
        except OSError as e: log.warning(f"Could not remove session file: {e}")

    log.info("--- Verifying code before execution ---")
    # Use corrected paths for verification
    log.info(f"Current Directory (before cd): {os.getcwd()}") # Log current dir before changing
    if os.getcwd() != repo_path: ipython.run_line_magic('cd', repo_path); log.info(f"Changed directory to {repo_path}")
    else: log.info(f"Already in correct directory: {repo_path}")

    log.info(f"Listing contents of {colab_dir_path}:") # List corrected path
    ipython.system(f'ls -l "{colab_dir_path}"')
    log.info(f"First 15 lines of {main_script_path}:") # Read from corrected path
    ipython.system(f'head -n 15 "{main_script_path}"')
    log.info("--- Verification END ---")

    log.info(f"Attempting to start bot module '{bot_main_module}' from {repo_path}...")
    try:
        # Ensure we are in the repo_path directory before running the module
        if os.getcwd() != repo_path:
             log.warning(f"Directory changed unexpectedly? Attempting cd back to {repo_path}")
             ipython.run_line_magic('cd', repo_path)

        log.info(f"Executing: python3 -m {bot_main_module}") # Use correct module name
        exit_code = ipython.system(f'python3 -m {bot_main_module}')
        log.info(f"Bot process finished (exit code: {exit_code}).")

        # Print log file location
        log.info("=" * 70)
        log.info(f"Complete setup log saved: {log_file_path}")
        log.info("To view SABnzbd setup logs: !grep -A 50 'Setting up SABnzbd' /content/setup_full.log")
        log.info("=" * 70)
    except Exception as e: log.critical(f"CRITICAL ERROR during bot startup: {e}", exc_info=True); print(f"\n Bot startup failed: {e}")

elif not valid_creds: print("\n-----------------------------------------------\n Bot setup skipped: Invalid credentials.\n-----------------------------------------------")
else: print("\n-----------------------------------------------\n Bot setup failed. Check logs above.\n-----------------------------------------------")
