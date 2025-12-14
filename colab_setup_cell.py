# @markdown ### **Required Credentials**
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"

BOT_SELECTION = "Bot 1 - 7772724138" #@param ["Bot 1 - 7772724138", "Bot 2 - 7789803613", "Bot 3 - 7801279758", "Bot 4 - 8142502027", "Bot 5 - 8026493824", "Bot 6 - 8153061743", "Bot 7 - 8040105081", "Bot 8 - 7976702554", "Bot 9 - 8076591114", "Bot 10 - 7690538451", "Bot 11 - 7435181907", "Bot 12 - 8083239087", "Bot 13 - 8050092737"]

# Dictionary to map selected bot names to their corresponding tokens
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

# Use the selection to get the bot token
BOT_TOKEN = token_mapping[BOT_SELECTION]
USER_ID = 121110934
Dump_SELECTION = "Files 1 - Margaret"  #@param ["Files 1 - Margaret", "Files 2 - Tate", "Files 3 - Kitty", "Files 4 - Peyton", "Files 5 - Olivia", "Files 6 - Emma"] {type: "string"}

# Dictionary to map selected bot names to their corresponding tokens
DumpToken_Mapping = {
    "Files 1 - Margaret": -1001593908646,
    "Files 2 - Tate": -1001599359953,
    "Files 3 - Kitty": -1001795431409,
    "Files 4 - Peyton": -1001786589126,
    "Files 5 - Olivia": -1001723897427,
    "Files 6 - Emma": -1001792878743,
}

# Use the selection to get the bot token
DUMP_ID = DumpToken_Mapping[Dump_SELECTION]



#  ---
#  ### **Optional Downloader Cookies**
#  *Leave blank if not needed.*
NZBCLOUD_CF_CLEARANCE = ""
BITSO_IDENTITY_COOKIE = ""
BITSO_PHPSESSID_COOKIE = ""
# @markdown ---


import subprocess, time, json, shutil, os, logging
from IPython import get_ipython
from IPython.display import clear_output
from threading import Thread

Working = True

# --- Basic logging setup ---
log = logging.getLogger('ColabLeecherSetup')
log.setLevel(logging.INFO)
if log.hasHandlers(): log.handlers.clear()
handler = logging.StreamHandler(); formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'); handler.setFormatter(formatter); log.addHandler(handler)
# --- End logging setup ---


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
    clear_output()

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
# --- MODIFICATION: Use correct repository name for path ---
repo_name = "Telegram-Leecher" # Assuming this is the folder name created by clone
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
          # --- MODIFICATION: Correct clone URL ---
          github_user = "theSadeQ" #@param ["theSadeQ","SadeQ710", "XronTrix10"]

          # Base repository name
          repository_name = "Telegram-Leecher"

          # Branch name
          branch_name = "feature/multi-task-parallel" #@param ["feature/multi-task-parallel", "VanDamme", "main"]

          # Construct the git clone command based on the selected user
          cmd_clone = f"git clone -b {branch_name} https://github.com/{github_user}/{repository_name}"
          # --- END MODIFICATION ---
          proc_clone = subprocess.run(cmd_clone, shell=True, capture_output=True, text=True)
          if proc_clone.returncode != 0: log.error(f"Git clone failed:\n{proc_clone.stderr}"); Working = False
          else: log.info("Repository cloned.")
          # --- MODIFICATION: Ensure repo_path matches cloned directory name ---
          # If the cloned repo creates a folder with a different name, adjust repo_path here if needed
          # Example: if clone creates "TheSadeQ-Telegram-Leecher", then:
          # actual_repo_name = "TheSadeQ-Telegram-Leecher" # Determine actual name
          # repo_path = f"/content/{actual_repo_name}"
          # Re-calculate other paths based on the actual repo_path
          # colab_dir_path = os.path.join(repo_path, "colab_leecher") # Adjusted here too
          # main_script_path = os.path.join(colab_dir_path, "__main__.py")
          # requirements_file = os.path.join(repo_path, "requirements.txt")
          # credentials_path = os.path.join(repo_path, 'credentials.json')
          # session_file = os.path.join(repo_path, "my_bot.session")
          log.info(f"Using repository path: {repo_path}")
          # --- END MODIFICATION ---

     else:
         log.warning(f"Repository already exists at {repo_path}. Skipping clone.")

     # --- Install Dependencies ---
     if Working and os.path.exists(repo_path):
          log.info("Checking/Installing OS packages..."); cmd_apt = "apt-get update && apt-get install -y ffmpeg aria2"; proc_apt = subprocess.run(cmd_apt, shell=True, capture_output=True, text=True)
          if proc_apt.returncode != 0: log.warning(f"Apt install issues:\n{proc_apt.stderr}")
          else: log.info("OS packages checked/installed.")

          log.info("Installing Mindvalley downloader dependencies...")
          cmd_mindvalley = "bash /content/Telegram-Leecher/install_mindvalley_deps.sh"
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
             "NZB_PROVIDERS": {
                 "sunnyusenet": {
                     "host": "news.sunnyusenet.com",
                     "port": 563,
                     "username": "3Z6U440PH1EJ",
                     "password": "nhx*fXtjagTSc5@",
                     "ssl": True,
                     "connections": 40
                 }
             },
             "NZB_DEFAULT_PROVIDER": "sunnyusenet"
             # --- END ADDED ---
         }

         try:
             # Ensure parent directory exists before writing
             os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
             with open(credentials_path, 'w') as file:
                 json.dump(credentials, file, indent=4)
             log.info(f"✅ Credentials written to {credentials_path}")
             log.info(f"✅ NZB Provider configured: sunnyusenet (40 connections)")
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

                 # Display public URL if tunnel was created
                 if sabnzbd_config.get('public_url'):
                     log.info("=" * 70)
                     log.info(f"🌐 SABnzbd Web UI: {sabnzbd_config['public_url']}")
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
    except Exception as e: log.critical(f"CRITICAL ERROR during bot startup: {e}", exc_info=True); print(f"\n Bot startup failed: {e}")

elif not valid_creds: print("\n-----------------------------------------------\n Bot setup skipped: Invalid credentials.\n-----------------------------------------------")
else: print("\n-----------------------------------------------\n Bot setup failed. Check logs above.\n-----------------------------------------------")
