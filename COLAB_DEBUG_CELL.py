# ============================================================================
# INSTAGRAM DEBUG CELL - Paste this entire cell into Colab
# ============================================================================

import logging
import sys
import os

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

print("=" * 80)
print("🔍 INSTAGRAM URL DETECTION DEBUG")
print("=" * 80)

test_url = "https://www.instagram.com/p/DSWJjA9lIlQ/"
print(f"\nTesting: {test_url}\n")

# Change to correct directory
os.chdir('/content/Telegram-Leecher')
sys.path.insert(0, '/content/Telegram-Leecher')

# Test 1: Import is_instagram
print("=" * 80)
print("TEST 1: Import is_instagram from helper.py")
print("=" * 80)
try:
    from colab_leecher.utility.helper import is_instagram
    print("✓ PASS: is_instagram imported")
    result = is_instagram(test_url)
    print(f"✓ is_instagram('{test_url}') = {result}")
    if not result:
        print("⚠️  WARNING: Instagram URL NOT detected!")
except Exception as e:
    print(f"✗ FAIL: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check all URL detectors
print("\n" + "=" * 80)
print("TEST 2: All URL detection functions")
print("=" * 80)
try:
    from colab_leecher.utility.helper import (
        is_google_drive, is_telegram, is_mega, is_terabox,
        is_instagram, is_torrent
    )

    print(f"is_google_drive = {is_google_drive(test_url)}")
    print(f"is_telegram     = {is_telegram(test_url)}")
    print(f"is_mega         = {is_mega(test_url)}")
    print(f"is_terabox      = {is_terabox(test_url)}")
    print(f"is_instagram    = {is_instagram(test_url)} ← SHOULD BE TRUE")
    print(f"is_torrent      = {is_torrent(test_url)}")

    if is_instagram(test_url):
        print("\n✓ URL will route to Instagram downloader")
    else:
        print("\n✗ URL will fall through to Aria2!")
except Exception as e:
    print(f"✗ FAIL: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check Instagram module
print("\n" + "=" * 80)
print("TEST 3: Instagram downloader module")
print("=" * 80)
try:
    from colab_leecher.downlader.instagram import (
        instagram_download, is_profile_url
    )
    print("✓ instagram_download imported")
    print("✓ is_profile_url imported")

    is_profile = is_profile_url(test_url)
    print(f"is_profile_url('{test_url}') = {is_profile}")
except Exception as e:
    print(f"✗ FAIL: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Check instaloader
print("\n" + "=" * 80)
print("TEST 4: Instaloader installation")
print("=" * 80)
try:
    import instaloader
    print(f"✓ instaloader installed")
except ImportError:
    print("✗ instaloader NOT installed!")
    print("Run: !pip install instaloader")

# Test 5: Check Instagram cookies
print("\n" + "=" * 80)
print("TEST 5: Instagram authentication")
print("=" * 80)
try:
    import json

    cred_path = "/content/Telegram-Leecher/colab_leecher/credentials.json"
    if os.path.exists(cred_path):
        print(f"✓ credentials.json found")
        with open(cred_path, 'r') as f:
            creds = json.load(f)

        if 'instagram' in creds and 'cookies_file' in creds['instagram']:
            cookies_path = creds['instagram']['cookies_file']
            print(f"  Cookies path: {cookies_path}")

            if os.path.exists(cookies_path):
                print(f"  ✓ Cookies file exists")
                with open(cookies_path, 'r') as f:
                    cookies = json.load(f)
                print(f"  ✓ {len(cookies)} cookies loaded")

                sessionid = [c for c in cookies if c.get('name') == 'sessionid']
                if sessionid:
                    print(f"  ✓ sessionid found")
                else:
                    print(f"  ✗ sessionid NOT found!")
            else:
                print(f"  ✗ Cookies file NOT found!")
        else:
            print("  ✗ Instagram config missing!")
    else:
        print(f"✗ credentials.json NOT found at: {cred_path}")
except Exception as e:
    print(f"✗ FAIL: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 80)
print("DEBUG COMPLETE - Share this output")
print("=" * 80)
