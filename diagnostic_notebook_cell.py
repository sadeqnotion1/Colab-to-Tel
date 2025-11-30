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
repo_name = "Telegram-Leecher"
repo_path = f"/content/{repo_name}"
colab_dir_path = os.path.join(repo_path, "colab_leecher")
main_script_path = os.path.join(colab_dir_path, "__main__.py")
requirements_file = os.path.join(repo_path, "requirements.txt")
credentials_path = os.path.join(repo_path, 'credentials.json')
bot_main_module = "colab_leecher"
session_file = os.path.join(repo_path, "my_bot.session")
setup_ok = False
ipython = get_ipython()

if valid_creds and ipython:
     log.info("Required credentials seem present.")
     if os.path.exists("/content/sample_data"): log.info("Removing sample_data..."); shutil.rmtree("/content/sample_data")

     # --- DIAGNOSTIC: Force fresh clone ---
     if os.path.exists(repo_path):
          log.warning(f"Repository already exists at {repo_path}. REMOVING for fresh clone...")
          shutil.rmtree(repo_path)
          log.info("Old repository removed.")

     # --- Git Clone (now always runs) ---
     log.info(f"Cloning repository to {repo_path}...")
     github_user = "theSadeQ"
     repository_name = "Telegram-Leecher"
     branch_name = "feature/multi-task-parallel"
     cmd_clone = f"git clone -b {branch_name} https://github.com/{github_user}/{repository_name} {repo_path}"

     print("\n" + "="*80)
     print(f"RUNNING: {cmd_clone}")
     print("="*80 + "\n")

     proc_clone = subprocess.run(cmd_clone, shell=True, capture_output=False, text=True)

     if proc_clone.returncode != 0:
          log.error(f"Git clone failed with exit code {proc_clone.returncode}!")
          Working = False
     else:
          log.info("✅ Repository cloned successfully.")

     # --- DIAGNOSTIC: Verify directory structure ---
     if Working:
          log.info("\n" + "="*80)
          log.info("DIAGNOSTIC: Verifying cloned repository structure...")
          log.info("="*80)

          print(f"\n📂 Contents of {repo_path}:")
          subprocess.run(f"ls -la {repo_path}", shell=True)

          print(f"\n📂 Contents of {colab_dir_path}:")
          if os.path.exists(colab_dir_path):
               subprocess.run(f"ls -la {colab_dir_path}", shell=True)
          else:
               log.error(f"❌ colab_leecher directory NOT FOUND at {colab_dir_path}!")
               Working = False

          print(f"\n📄 Checking for __init__.py:")
          init_file = os.path.join(colab_dir_path, "__init__.py")
          if os.path.exists(init_file):
               log.info(f"✅ Found {init_file}")
          else:
               log.error(f"❌ __init__.py NOT FOUND at {init_file}!")
               Working = False

          print(f"\n📄 Checking for __main__.py:")
          if os.path.exists(main_script_path):
               log.info(f"✅ Found {main_script_path}")
          else:
               log.error(f"❌ __main__.py NOT FOUND at {main_script_path}!")
               Working = False

     # --- Install Dependencies ---
     if Working and os.path.exists(repo_path):
          print("\n" + "="*80)
          log.info("Installing OS packages...")
          print("="*80 + "\n")

          cmd_apt = "apt-get update && apt-get install -y ffmpeg aria2"
          subprocess.run(cmd_apt, shell=True, capture_output=False, text=True)
          log.info("✅ OS packages installed.")

          print("\n" + "="*80)
          log.info("Installing Mindvalley downloader dependencies...")
          print("="*80 + "\n")

          cmd_mindvalley = "bash /content/Telegram-Leecher/install_mindvalley_deps.sh"
          subprocess.run(cmd_mindvalley, shell=True, capture_output=False, text=True)
          log.info("✅ Mindvalley downloader ready")

          print("\n" + "="*80)
          log.info("Installing Python requirements...")
          print("="*80 + "\n")

          if os.path.exists(requirements_file):
              cmd_pip = f"pip3 install --no-cache-dir -r {requirements_file}"
              proc_pip = subprocess.run(cmd_pip, shell=True, capture_output=False, text=True)
              if proc_pip.returncode != 0:
                   log.error(f"❌ pip install failed with exit code {proc_pip.returncode}!")
                   Working = False
              else:
                   log.info("✅ Python requirements installed.")
          else:
               log.error(f"❌ Requirements file not found: {requirements_file}")
               Working = False

     # --- Write Credentials File ---
     if Working:
         log.info("Writing credentials file...")
         credentials = {
              "API_ID": API_ID,
              "API_HASH": API_HASH,
              "BOT_TOKEN": BOT_TOKEN,
              "USER_ID": USER_ID,
              "DUMP_ID": DUMP_ID,
              "NZBCLOUD_CF_CLEARANCE": NZBCLOUD_CF_CLEARANCE,
              "BITSO_IDENTITY_COOKIE": BITSO_IDENTITY_COOKIE,
              "BITSO_PHPSESSID_COOKIE": BITSO_PHPSESSID_COOKIE
         }
         try:
             os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
             with open(credentials_path, 'w') as file:
                  json.dump(credentials, file, indent=4)
             log.info(f"✅ Credentials written to {credentials_path}")
             setup_ok = True
         except IOError as e:
              log.error(f"❌ Failed to write credentials file: {e}")
              Working = False
elif not ipython:
     log.error("Could not get IPython instance.")
     Working = False

# --- Stop Loading Animation ---
Working = False
_Thread.join()

# --- Final Check and Bot Start ---
if setup_ok:
    if os.path.exists(session_file):
        try:
             os.remove(session_file)
             log.info(f"Removed previous session: {session_file}")
        except OSError as e:
             log.warning(f"Could not remove session file: {e}")

    print("\n" + "="*80)
    log.info("DIAGNOSTIC: Testing module import...")
    print("="*80 + "\n")

    # Test if the module can be imported
    test_result = subprocess.run(
         ['python3', '-c', 'import sys; sys.path.insert(0, "/content/Telegram-Leecher"); import colab_leecher; print("✅ Module import successful!")'],
         capture_output=True,
         text=True
    )

    print("STDOUT:", test_result.stdout)
    if test_result.stderr:
         print("STDERR:", test_result.stderr)
    print("Exit code:", test_result.returncode)

    if test_result.returncode != 0:
         print("\n❌ Module import test FAILED!")
         print("The bot will likely fail to start.")

    print("\n" + "="*80)
    log.info(f"Starting bot module '{bot_main_module}' from {repo_path}...")
    print("="*80 + "\n")

    try:
        # Run and show EVERYTHING
        result = subprocess.run(
            ['python3', '-m', bot_main_module],
            cwd=repo_path,
            capture_output=False,  # Show output directly
            text=True
        )

        print("\n" + "="*80)
        log.info(f"Bot process finished with exit code: {result.returncode}")

        if result.returncode != 0:
            print(f"\n⚠️ Bot exited with error code: {result.returncode}")

    except Exception as e:
        log.critical(f"CRITICAL ERROR during bot startup: {e}", exc_info=True)
        import traceback
        traceback.print_exc()
        print(f"\nBot startup failed: {e}")

elif not valid_creds:
     print("\n-----------------------------------------------\n Bot setup skipped: Invalid credentials.\n-----------------------------------------------")
else:
     print("\n-----------------------------------------------\n Bot setup failed. Check logs above.\n-----------------------------------------------")
