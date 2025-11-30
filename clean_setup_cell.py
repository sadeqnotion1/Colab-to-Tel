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
Dump_SELECTION = "Files 1 - Margaret"  #@param ["Files 1 - Margaret", "Files 2 - Tate", "Files 3 - Kitty", "Files 4 - Peyton", "Files 5 - Olivia", "Files 6 - Emma"]

DumpToken_Mapping = {
    "Files 1 - Margaret": -1001593908646,
    "Files 2 - Tate": -1001599359953,
    "Files 3 - Kitty": -1001795431409,
    "Files 4 - Peyton": -1001786589126,
    "Files 5 - Olivia": -1001723897427,
    "Files 6 - Emma": -1001792878743,
}

DUMP_ID = DumpToken_Mapping[Dump_SELECTION]

NZBCLOUD_CF_CLEARANCE = ""
BITSO_IDENTITY_COOKIE = ""
BITSO_PHPSESSID_COOKIE = ""

import subprocess
import shutil
import os
import json

print("="*80)
print("CLEAN SETUP - Removing ALL old files and cloning fresh from GitHub")
print("="*80)

# Remove EVERYTHING in /content/Telegram-Leecher
if os.path.exists('/content/Telegram-Leecher'):
    print("\n🗑️  Removing old /content/Telegram-Leecher directory...")
    shutil.rmtree('/content/Telegram-Leecher')
    print("✅ Removed")

# Clone fresh from GitHub
print("\n📥 Cloning from GitHub...")
print("Repository: https://github.com/theSadeQ/Telegram-Leecher")
print("Branch: feature/multi-task-parallel")
print("Destination: /content/Telegram-Leecher")

result = subprocess.run(
    ['git', 'clone', '-b', 'feature/multi-task-parallel',
     'https://github.com/theSadeQ/Telegram-Leecher',
     '/content/Telegram-Leecher'],
    capture_output=True,
    text=True
)

if result.returncode != 0:
    print(f"❌ Clone failed!\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}")
    raise SystemExit("Clone failed")

print("✅ Clone successful")

# Verify structure
print("\n📂 Verifying structure:")
print("\nRoot directory contents:")
subprocess.run(['ls', '-la', '/content/Telegram-Leecher'])

if os.path.exists('/content/Telegram-Leecher/colab_leecher'):
    print("\n✅ colab_leecher directory found at correct location!")
    print("\ncolab_leecher contents:")
    subprocess.run(['ls', '-la', '/content/Telegram-Leecher/colab_leecher'])
else:
    print("\n❌ ERROR: colab_leecher directory NOT found!")
    print("Something is wrong with the repository structure")
    raise SystemExit("Directory structure error")

# Install dependencies
print("\n" + "="*80)
print("Installing dependencies...")
print("="*80)

print("\n📦 Installing system packages...")
subprocess.run(['apt-get', 'update', '-qq'], check=False)
subprocess.run(['apt-get', 'install', '-y', '-qq', 'ffmpeg', 'aria2'], check=False)

print("\n📦 Installing Mindvalley dependencies...")
subprocess.run(['bash', '/content/Telegram-Leecher/install_mindvalley_deps.sh'], check=False)

print("\n📦 Installing Python packages...")
subprocess.run(['pip3', 'install', '--no-cache-dir', '-q', '-r', '/content/Telegram-Leecher/requirements.txt'], check=True)

print("✅ All dependencies installed")

# Write credentials
print("\n📝 Writing credentials...")
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

with open('/content/Telegram-Leecher/credentials.json', 'w') as f:
    json.dump(credentials, f, indent=4)

print("✅ Credentials written")

# Start bot
print("\n" + "="*80)
print("STARTING BOT")
print("="*80 + "\n")

os.chdir('/content/Telegram-Leecher')
subprocess.run(['python3', '-m', 'colab_leecher'])
