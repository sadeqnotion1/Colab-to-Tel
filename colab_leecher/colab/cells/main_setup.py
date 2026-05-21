# copyright 2023 © Xron Trix | https://github.com/Xrontrix10
# Adapted for https://github.com/theSadeQ/Telegram-Leecher


# @title 🖥️ Main Colab Leech Code (v4 - Correct Repo)

# @title Main Code
# @markdown <div><center><img src="https://user-images.githubusercontent.com/125879861/255391401-371f3a64-732d-4954-ac0f-4f093a6605e1.png" height=80></center></div>
# @markdown <center><h4><a href="https://github.com/theSadeQ/Telegram-Leecher/wiki/INSTRUCTIONS">READ</a> How to use</h4></center>

# @markdown ---
# @markdown ### **Required Credentials**
API_ID = 0  # @param {type: "integer"}
API_HASH = ""  # @param {type: "string"}
BOT_TOKEN = ""  # @param {type: "string"}
USER_ID = 0  # @param {type: "integer"}
DUMP_ID = 0  # @param {type: "integer"}

# @markdown ---
# @markdown ### **Optional Downloader Cookies**
# @markdown *Leave blank if not needed.*
NZBCLOUD_CF_CLEARANCE = "" # @param {type: "string"}
BITSO_IDENTITY_COOKIE = "" # @param {type: "string"}
BITSO_PHPSESSID_COOKIE = "" # @param {type: "string"}
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


banner = '''/* ... Banner ... */''' # Banner text omitted for brevity
print(banner)

def Loading():
    spinner = ['/', '-', '\\', '|']; i = 0
    while Working: print("\r" + f"Preparing Environment... {spinner[i % len(spinner)]}", end=""); i += 1; time.sleep(0.2)
    if setup_ok:
        clear_output()
    else:
        print("\n")


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
repo_name = "Colab-to-Tel" # Assuming this is the folder name created by clone
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
          cmd_clone = "git clone https://github.com/theSadeQ/Colab-to-Tel"
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
          log.info("Checking/Installing OS packages..."); cmd_apt = "add-apt-repository -y universe && apt-get update && apt-get install -y ffmpeg aria2 megatools"; proc_apt = subprocess.run(cmd_apt, shell=True, capture_output=True, text=True)
          if proc_apt.returncode != 0: log.warning(f"Apt install issues:\n{proc_apt.stderr}")
          else: log.info("OS packages checked/installed.")

          log.info("Installing Python requirements...");
          if os.path.exists(requirements_file):
              cmd_pip = f"pip3 install --no-cache-dir -r {requirements_file}"; proc_pip = subprocess.run(cmd_pip, shell=True, capture_output=True, text=True)
              if proc_pip.returncode != 0: log.error(f"pip install failed:\n{proc_pip.stderr}"); Working = False
              else: log.info("Python requirements installed.")
          else: log.error(f"Requirements file not found: {requirements_file}"); Working = False

          # --- Install Mindvalley Dependencies ---
          if Working:
              mindvalley_script = os.path.join(repo_path, "install_mindvalley_deps.sh")
              if os.path.exists(mindvalley_script):
                  log.info("Installing Mindvalley dependencies (N_m3u8DL-RE)...")
                  subprocess.run(f"chmod +x {mindvalley_script}", shell=True)
                  cmd_mindvalley = f"bash {mindvalley_script}"
                  proc_mindvalley = subprocess.run(cmd_mindvalley, shell=True, capture_output=True, text=True)
                  if proc_mindvalley.returncode != 0:
                      log.warning(f"Mindvalley dependencies install issues:\n{proc_mindvalley.stderr}")
                      log.warning("Mindvalley downloads may not work without N_m3u8DL-RE")
                  else:
                      log.info("Mindvalley dependencies installed successfully.")
                      log.info(proc_mindvalley.stdout)
              else:
                  log.warning(f"Mindvalley install script not found: {mindvalley_script}")
                  log.warning("Mindvalley downloads will not be available.")
     elif not os.path.exists(repo_path): log.error("Repo dir not found, cannot install dependencies."); Working = False

     # --- Write Credentials File ---
     if Working:
         log.info("Writing credentials file..."); credentials = {"API_ID": API_ID, "API_HASH": API_HASH, "BOT_TOKEN": BOT_TOKEN, "USER_ID": USER_ID, "DUMP_ID": DUMP_ID, "NZBCLOUD_CF_CLEARANCE": NZBCLOUD_CF_CLEARANCE, "BITSO_IDENTITY_COOKIE": BITSO_IDENTITY_COOKIE, "BITSO_PHPSESSID_COOKIE": BITSO_PHPSESSID_COOKIE}
         try:
             # Ensure parent directory exists before writing
             os.makedirs(os.path.dirname(credentials_path), exist_ok=True)
             with open(credentials_path, 'w') as file: json.dump(credentials, file, indent=4)
             log.info(f"Credentials written to {credentials_path}")
             setup_ok = True
         except IOError as e: log.error(f"Failed to write credentials file: {e}"); Working = False
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
