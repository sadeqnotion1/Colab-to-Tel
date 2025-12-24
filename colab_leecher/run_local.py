#!/usr/bin/env python3
"""
Local Bot Startup Script
Runs the Telegram Leecher bot on your local machine (Windows/Linux)
"""

import os
import sys
import json
import logging
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

def check_credentials():
    """Verify credentials.json exists and is valid"""
    creds_path = "credentials.json"

    if not os.path.exists(creds_path):
        log.error(f"❌ credentials.json not found!")
        log.error(f"   Expected location: {os.path.abspath(creds_path)}")
        return False

    try:
        with open(creds_path, 'r') as f:
            creds = json.load(f)

        required = ['API_ID', 'API_HASH', 'BOT_TOKEN', 'USER_ID', 'DUMP_ID']
        missing = [key for key in required if not creds.get(key)]

        if missing:
            log.error(f"❌ Missing required credentials: {', '.join(missing)}")
            return False

        log.info("✅ Credentials loaded successfully")

        # Check Instagram config
        if creds.get('INSTAGRAM_USERNAME') and creds.get('INSTAGRAM_PASSWORD'):
            log.info(f"✅ Instagram Login: {creds['INSTAGRAM_USERNAME']}")
        elif creds.get('INSTAGRAM_SESSIONID'):
            log.info("✅ Instagram Session Cookie configured")
        elif creds.get('INSTAGRAM_COOKIES_FILE'):
            log.info(f"✅ Instagram Cookie File: {creds['INSTAGRAM_COOKIES_FILE']}")
        else:
            log.warning("⚠️  Instagram authentication not configured")

        return True

    except json.JSONDecodeError as e:
        log.error(f"❌ Invalid JSON in credentials.json: {e}")
        return False
    except Exception as e:
        log.error(f"❌ Error reading credentials: {e}")
        return False


def check_dependencies():
    """Check if required Python packages are installed"""
    log.info("Checking dependencies...")

    required_packages = [
        'pyrogram', 'yt_dlp', 'aiohttp', 'aiofiles',
        'Pillow', 'psutil', 'requests'
    ]

    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)

    if missing:
        log.warning(f"⚠️  Missing packages: {', '.join(missing)}")
        log.info("Installing missing packages...")
        try:
            subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
            log.info("✅ Packages installed successfully")
        except subprocess.CalledProcessError:
            log.error("❌ Failed to install packages")
            log.error("   Run: pip install -r requirements.txt")
            return False
    else:
        log.info("✅ All dependencies installed")

    return True


def create_directories():
    """Create necessary working directories"""
    log.info("Creating working directories...")

    work_dir = "BOT_WORK"
    dirs = [
        f"{work_dir}/Downloads",
        f"{work_dir}/Leeched_Files",
        f"{work_dir}/Unzipped_Files",
        f"{work_dir}/leech_temp",
        f"{work_dir}/ytdl_thumbnails",
        f"{work_dir}/dir_leech_temp",
    ]

    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)

    log.info("✅ Directories created")


def update_paths_for_local():
    """Update path configuration for local execution"""
    # The bot will automatically detect Windows and adjust paths
    # No changes needed if running from project root
    pass


def main():
    """Main startup function"""
    print("=" * 60)
    print("  Telegram Leecher Bot - Local Startup")
    print("=" * 60)
    print()

    # Change to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    log.info(f"Working directory: {os.getcwd()}")

    # Perform checks
    if not check_credentials():
        log.error("\n❌ Startup aborted: Credential issues")
        log.info("\nEdit credentials.json with your bot credentials")
        log.info("Get bot token from @BotFather on Telegram")
        input("\nPress Enter to exit...")
        return

    if not check_dependencies():
        log.error("\n❌ Startup aborted: Dependency issues")
        input("\nPress Enter to exit...")
        return

    create_directories()

    print()
    print("=" * 60)
    print("  Starting Bot...")
    print("=" * 60)
    print()
    log.info("🚀 Launching bot: python -m colab_leecher")
    print()

    # Update paths
    update_paths_for_local()

    # Start the bot
    try:
        # Run as module
        subprocess.run([sys.executable, '-m', 'colab_leecher'])
    except KeyboardInterrupt:
        log.info("\n\n⚠️  Bot stopped by user (Ctrl+C)")
    except Exception as e:
        log.error(f"\n\n❌ Bot crashed: {e}")
        import traceback
        traceback.print_exc()
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    main()
