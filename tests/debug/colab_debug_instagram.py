#!/usr/bin/env python3
"""
Comprehensive debug script for Instagram URL detection in Colab
Run this in a Colab cell to see exactly what's happening
"""

import logging
import sys

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

print("=" * 80)
print("INSTAGRAM URL DETECTION DEBUG SCRIPT")
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
    sys.exit(1)

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

# Step 5: Check manager.py imports
print("\nSTEP 5: Checking manager.py imports...")
print("-" * 80)
try:
    from colab_leecher.downlader import manager
    print("✓ manager module imported successfully")

    # Check if is_instagram is available in manager
    if hasattr(manager, 'is_instagram'):
        print("✓ is_instagram is available in manager module")
    else:
        print("✗ WARNING: is_instagram NOT found in manager module")
        print("  Available attributes:")
        attrs = [a for a in dir(manager) if not a.startswith('_')]
        for attr in attrs[:20]:  # Show first 20
            print(f"    - {attr}")

except ImportError as e:
    print(f"✗ FAILED to import manager: {e}")
    import traceback
    traceback.print_exc()

# Step 6: Check Instagram cookies
print("\nSTEP 6: Checking Instagram authentication...")
print("-" * 80)
try:
    import os
    import json

    # Check credentials.json
    cred_path = "/content/Telegram-Leecher/colab_leecher/credentials.json"
    if not os.path.exists(cred_path):
        cred_path = "colab_leecher/credentials.json"

    if os.path.exists(cred_path):
        print(f"✓ Found credentials.json at: {cred_path}")
        with open(cred_path, 'r') as f:
            creds = json.load(f)

        if 'instagram' in creds:
            print("✓ Instagram section found in credentials")
            ig_config = creds['instagram']

            if 'cookies_file' in ig_config:
                cookies_path = ig_config['cookies_file']
                print(f"  - Cookies file configured: {cookies_path}")

                # Check if cookies file exists
                if os.path.exists(cookies_path):
                    print(f"  ✓ Cookies file exists")

                    # Check if it's JSON format
                    try:
                        with open(cookies_path, 'r') as f:
                            cookies = json.load(f)
                        print(f"  ✓ Cookies file is valid JSON ({len(cookies)} cookies)")

                        # Check for sessionid
                        sessionid = [c for c in cookies if c.get('name') == 'sessionid']
                        if sessionid:
                            print(f"  ✓ Found sessionid cookie")
                        else:
                            print(f"  ✗ WARNING: No sessionid cookie found!")
                    except json.JSONDecodeError:
                        print(f"  ✗ Cookies file is NOT JSON format")
                else:
                    print(f"  ✗ Cookies file does NOT exist!")
            else:
                print("  ✗ No cookies_file configured")
        else:
            print("✗ No instagram section in credentials")
    else:
        print(f"✗ credentials.json not found at: {cred_path}")

except Exception as e:
    print(f"✗ ERROR checking Instagram auth: {e}")
    import traceback
    traceback.print_exc()

# Step 7: Simulate the auto-detection flow
print("\nSTEP 7: Simulating auto-detection flow...")
print("-" * 80)
try:
    from colab_leecher.utility.helper import (
        is_google_drive, is_telegram, is_mega, is_terabox,
        is_instagram, is_torrent
    )

    test_url = "https://www.instagram.com/p/DSWJjA9lIlQ/"

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

# Step 8: Check instaloader availability
print("\nSTEP 8: Checking instaloader installation...")
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
print("DEBUG SCRIPT COMPLETE")
print("=" * 80)
print("\n📋 SUMMARY:")
print("  1. Copy the output above")
print("  2. Look for any ✗ or ⚠️ warnings")
print("  3. Share the output to identify the issue")
print("=" * 80)
