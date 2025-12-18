#!/usr/bin/env python3
"""
Debug Instagram authentication in Colab
Run this to see what credentials are loaded
"""

import json
import os

print("=" * 80)
print("INSTAGRAM AUTHENTICATION DEBUG")
print("=" * 80)

# Check credentials.json
creds_path = "/content/Telegram-Leecher/credentials.json"
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

# Check cookies file
print(f"\n2. Checking cookies file")
print("-" * 80)

cookies_file = creds.get('INSTAGRAM_COOKIES_FILE', '')
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

            # Try to import session from cookies
            # This is a test - actual implementation uses JSON format
            print("  Note: Instaloader uses JSON format, Netscape format needs conversion")

        except Exception as e:
            print(f"  ✗ Error: {e}")
    else:
        print("  ⚠️  No cookies file to test")

except ImportError:
    print("✗ instaloader NOT installed!")

print("\n" + "=" * 80)
print("DEBUG COMPLETE")
print("=" * 80)

print("\n📋 RECOMMENDATIONS:")
if not cookies_file or not os.path.exists(cookies_file):
    print("  1. Download cookies file from repo to /content/Telegram-Leecher/")
    print("  2. Update credentials.json with correct path")
elif 'sessionid' not in content:
    print("  1. Cookies file exists but may be invalid")
    print("  2. Check if sessionid cookie is present")
else:
    print("  1. Cookies file appears valid")
    print("  2. If still getting 401, try extracting sessionid and using INSTAGRAM_SESSIONID instead")
    print("  3. Or convert to JSON format for instaloader")

print("=" * 80)
