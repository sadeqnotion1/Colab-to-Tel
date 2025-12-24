#!/usr/bin/env python3
"""
Unified Instagram Debugging Tool
Combines authentication, command, and URL detection debugging

Usage:
    python instagram_debug.py --auth           # Test authentication
    python instagram_debug.py --command        # Test /ig command handler
    python instagram_debug.py --url            # Test URL detection
    python instagram_debug.py --all            # Run all tests
"""

import argparse
import asyncio
import json
import logging
import os
import sys

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)


def test_auth():
    """Test Instagram authentication and credentials"""
    print("=" * 80)
    print("INSTAGRAM AUTHENTICATION DEBUG")
    print("=" * 80)

    # Check credentials.json
    creds_path = "/content/Telegram-Leecher/credentials.json"
    if not os.path.exists(creds_path):
        creds_path = "credentials.json"

    print(f"\n1. Checking credentials file: {creds_path}")
    print("-" * 80)

    if os.path.exists(creds_path):
        print("✓ credentials.json exists")
        with open(creds_path, 'r') as f:
            creds = json.load(f)

        print(f"\nInstagram credentials:")
        print(f"  INSTAGRAM_USERNAME: '{creds.get('INSTAGRAM_USERNAME', 'NOT SET')}'")
        print(f"  INSTAGRAM_PASSWORD: {'***' if creds.get('INSTAGRAM_PASSWORD') else 'NOT SET'}")
        print(f"  INSTAGRAM_SESSIONID: {'SET (length: ' + str(len(creds.get('INSTAGRAM_SESSIONID', ''))) + ')' if creds.get('INSTAGRAM_SESSIONID') else 'NOT SET'}")
        print(f"  INSTAGRAM_COOKIES_FILE: '{creds.get('INSTAGRAM_COOKIES_FILE', 'NOT SET')}'")
    else:
        print("✗ credentials.json NOT FOUND!")
        creds = {}

    # Check cookies file
    print(f"\n2. Checking cookies file")
    print("-" * 80)

    cookies_file = creds.get('INSTAGRAM_COOKIES_FILE', '')
    content = ""
    if cookies_file:
        if os.path.exists(cookies_file):
            print(f"✓ Cookies file exists: {cookies_file}")

            # Check file size
            size = os.path.getsize(cookies_file)
            print(f"  File size: {size} bytes")

            # Read first few lines
            with open(cookies_file, 'r') as f:
                lines = f.readlines()[:5]
            print(f"  First 5 lines:")
            for line in lines:
                print(f"    {line.rstrip()}")

            # Check for sessionid
            with open(cookies_file, 'r') as f:
                content = f.read()
            if 'sessionid' in content:
                print("  ✓ Contains 'sessionid'")
            else:
                print("  ✗ Does NOT contain 'sessionid'!")
        else:
            print(f"✗ Cookies file NOT FOUND: {cookies_file}")
    else:
        print("✗ No cookies file configured")

    # Check if Instagram downloader can access the settings
    print(f"\n3. Checking bot variables")
    print("-" * 80)

    try:
        from colab_leecher.utility.variables import BOT
        print("✓ BOT imported")
        print(f"\nBOT.Setting attributes:")
        print(f"  instagram_username: '{BOT.Setting.instagram_username}'")
        print(f"  instagram_password: {'***' if BOT.Setting.instagram_password else 'NOT SET'}")
        print(f"  instagram_sessionid: {'SET (length: ' + str(len(BOT.Setting.instagram_sessionid)) + ')' if BOT.Setting.instagram_sessionid else 'NOT SET'}")
        print(f"  instagram_cookies_file: '{BOT.Setting.instagram_cookies_file}'")
    except Exception as e:
        print(f"✗ Failed to import BOT: {e}")

    # Test instaloader with cookies
    print(f"\n4. Testing instaloader with cookies")
    print("-" * 80)

    try:
        import instaloader
        print("✓ instaloader installed")

        if cookies_file and os.path.exists(cookies_file):
            print(f"\nAttempting to load session from: {cookies_file}")
            try:
                L = instaloader.Instaloader()
                print("  Note: Instaloader uses JSON format, Netscape format needs conversion")
            except Exception as e:
                print(f"  ✗ Error: {e}")
        else:
            print("  ⚠️  No cookies file to test")

    except ImportError:
        print("✗ instaloader NOT installed!")

    print("\n" + "=" * 80)
    print("AUTHENTICATION DEBUG COMPLETE")
    print("=" * 80)

    print("\n📋 RECOMMENDATIONS:")
    if not cookies_file or not os.path.exists(cookies_file):
        print("  1. Download cookies file from repo to /content/Telegram-Leecher/")
        print("  2. Update credentials.json with correct path")
    elif content and 'sessionid' not in content:
        print("  1. Cookies file exists but may be invalid")
        print("  2. Check if sessionid cookie is present")
    else:
        print("  1. Cookies file appears valid")
        print("  2. If still getting 401, try extracting sessionid and using INSTAGRAM_SESSIONID instead")
        print("  3. Or convert to JSON format for instaloader")

    print("=" * 80)


async def test_command():
    """Test the /ig command handler"""
    try:
        log.info("=" * 60)
        log.info("DEBUG: Starting /ig command test")
        log.info("=" * 60)

        # Import the bot
        from colab_leecher import colab_bot
        from colab_leecher.utility.variables import BOT
        from colab_leecher.utility.task_manager import task_starter

        log.info("✓ Imports successful")
        log.info(f"  - colab_bot: {colab_bot}")
        log.info(f"  - BOT: {BOT}")
        log.info(f"  - task_starter: {task_starter}")

        # Check bot connection
        if colab_bot.is_connected:
            log.info("✓ Bot is connected to Telegram")
        else:
            log.error("✗ Bot is NOT connected!")
            return

        # Simulate the /ig command handler
        log.info("\nSimulating /ig command handler:")
        log.info("-" * 40)

        # Step 1: Set mode
        log.info("Step 1: Setting mode to 'leech'")
        BOT.Mode.mode = "leech"
        log.info(f"  ✓ BOT.Mode.mode = {BOT.Mode.mode}")

        # Step 2: Set ytdl
        log.info("Step 2: Setting ytdl to False")
        BOT.Mode.ytdl = False
        log.info(f"  ✓ BOT.Mode.ytdl = {BOT.Mode.ytdl}")

        # Step 3: Set service_type
        log.info("Step 3: Setting service_type to 'instagram'")
        BOT.Options.service_type = "instagram"
        log.info(f"  ✓ BOT.Options.service_type = {BOT.Options.service_type}")

        # Step 4: Prepare message text
        log.info("Step 4: Preparing message text")
        text = (
            "<b>📸 Instagram Leech » Send Me LINK(s) 🔗</b>\n\n"
            "**Supported:**\n"
            "• Individual Posts/Reels/IGTV\n"
            "• **ENTIRE PROFILES** (batch download)\n\n"
            "**Examples:**\n"
            "<code>https://instagram.com/username/</code> (all posts)\n"
            "<code>https://instagram.com/p/xyz</code> (single post)\n"
            "<code>https://instagram.com/reel/abc</code> (reel)"
        )
        log.info(f"  ✓ Message text prepared ({len(text)} characters)")

        # Step 5: Check task_starter function
        log.info("Step 5: Checking task_starter function")
        log.info(f"  - task_starter callable: {callable(task_starter)}")
        log.info(f"  - task_starter module: {task_starter.__module__}")

        log.info("\n" + "=" * 60)
        log.info("COMMAND DEBUG TEST COMPLETE")
        log.info("=" * 60)
        log.info("\nIf you see this message, the imports and setup are working.")
        log.info("The issue is likely in task_starter() not sending the message.")
        log.info("\nNext steps:")
        log.info("1. Check if task_starter has any try-except blocks catching errors")
        log.info("2. Check if MSG.status_msg is initialized properly")
        log.info("3. Look for any asyncio/await issues")

    except Exception as e:
        log.error(f"\n❌ ERROR OCCURRED: {e}", exc_info=True)
        log.error("\nFull traceback above ↑")


def test_url():
    """Test Instagram URL detection and routing"""
    print("=" * 80)
    print("INSTAGRAM URL DETECTION DEBUG")
    print("=" * 80)

    # Test URL
    test_url = "https://www.instagram.com/p/DSWJjA9lIlQ/"

    print(f"\n🔍 Testing URL: {test_url}\n")

    # Step 1: Check helper imports
    print("STEP 1: Checking helper.py imports...")
    print("-" * 80)
    try:
        from colab_leecher.utility.helper import is_instagram
        print("✓ is_instagram imported successfully")
        print(f"  - Function: {is_instagram}")
        print(f"  - Module: {is_instagram.__module__}")
    except ImportError as e:
        print(f"✗ FAILED to import is_instagram: {e}")
        return

    # Step 2: Test is_instagram function
    print("\nSTEP 2: Testing is_instagram() function...")
    print("-" * 80)
    try:
        result = is_instagram(test_url)
        print(f"✓ is_instagram('{test_url}') = {result}")
        if not result:
            print("  ⚠️ WARNING: URL not detected as Instagram!")
    except Exception as e:
        print(f"✗ ERROR calling is_instagram(): {e}")
        import traceback
        traceback.print_exc()

    # Step 3: Check instagram.py imports
    print("\nSTEP 3: Checking instagram.py imports...")
    print("-" * 80)
    try:
        from colab_leecher.downlader.instagram import (
            instagram_download,
            instagram_profile_download,
            is_profile_url
        )
        print("✓ Instagram functions imported successfully")
        print(f"  - instagram_download: {instagram_download}")
        print(f"  - instagram_profile_download: {instagram_profile_download}")
        print(f"  - is_profile_url: {is_profile_url}")
    except ImportError as e:
        print(f"✗ FAILED to import Instagram functions: {e}")
        import traceback
        traceback.print_exc()

    # Step 4: Test is_profile_url
    print("\nSTEP 4: Testing is_profile_url() function...")
    print("-" * 80)
    try:
        result = is_profile_url(test_url)
        print(f"✓ is_profile_url('{test_url}') = {result}")
    except Exception as e:
        print(f"✗ ERROR calling is_profile_url(): {e}")
        import traceback
        traceback.print_exc()

    # Step 5: Simulate auto-detection flow
    print("\nSTEP 5: Simulating auto-detection flow...")
    print("-" * 80)
    try:
        from colab_leecher.utility.helper import (
            is_google_drive, is_telegram, is_mega, is_terabox,
            is_instagram, is_torrent
        )

        print(f"Testing URL: {test_url}\n")
        print(f"  is_google_drive(url) = {is_google_drive(test_url)}")
        print(f"  is_telegram(url)     = {is_telegram(test_url)}")
        print(f"  is_mega(url)         = {is_mega(test_url)}")
        print(f"  is_terabox(url)      = {is_terabox(test_url)}")
        print(f"  is_instagram(url)    = {is_instagram(test_url)}")
        print(f"  is_torrent(url)      = {is_torrent(test_url)}")

        if is_instagram(test_url):
            print("\n✓ URL would be routed to Instagram downloader")
        else:
            print("\n✗ URL would fall through to Aria2!")

    except Exception as e:
        print(f"✗ ERROR during simulation: {e}")
        import traceback
        traceback.print_exc()

    # Step 6: Check instaloader availability
    print("\nSTEP 6: Checking instaloader installation...")
    print("-" * 80)
    try:
        import instaloader
        print(f"✓ instaloader is installed")
        print(f"  - Version: {instaloader.__version__ if hasattr(instaloader, '__version__') else 'unknown'}")
        print(f"  - Location: {instaloader.__file__}")
    except ImportError:
        print("✗ instaloader is NOT installed!")
        print("  Run: !pip install instaloader")

    print("\n" + "=" * 80)
    print("URL DETECTION DEBUG COMPLETE")
    print("=" * 80)
    print("\n📋 SUMMARY:")
    print("  1. Copy the output above")
    print("  2. Look for any ✗ or ⚠️ warnings")
    print("  3. Share the output to identify the issue")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description="Instagram debugging tool for Telegram-Leecher bot"
    )
    parser.add_argument("--auth", action="store_true", help="Test Instagram authentication")
    parser.add_argument("--command", action="store_true", help="Test /ig command handler")
    parser.add_argument("--url", action="store_true", help="Test URL detection")
    parser.add_argument("--all", action="store_true", help="Run all tests")

    args = parser.parse_args()

    # If no arguments, show help
    if not any([args.auth, args.command, args.url, args.all]):
        parser.print_help()
        return

    # Run requested tests
    if args.all or args.auth:
        print("\n🔐 Testing Authentication...")
        test_auth()

    if args.all or args.url:
        print("\n🔗 Testing URL Detection...")
        test_url()

    if args.all or args.command:
        print("\n⚙️ Testing Command Handler...")
        asyncio.run(test_command())


if __name__ == "__main__":
    main()
