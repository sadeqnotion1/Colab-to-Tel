#!/usr/bin/env python3
"""
test_instagram_grapi.py - Minimal Windows diagnostic test for the instagrapi engine.

This script parses cookies (JSON or Netscape format) to retrieve the Instagram
`sessionid`, authenticates instagrapi, and downloads the latest post from a
target Instagram profile to verify that the private API connection works.

Usage:
  1. Export your Instagram cookies to a JSON file (e.g. using EditThisCookie)
     or a Netscape cookies.txt file and place it in the same directory as this script.
  2. Run the script:
     python test_instagram_grapi.py
"""
import os
import sys
import json
import shutil
import urllib.parse
from pathlib import Path

# Add project root to sys.path to allow imports from colab_leecher if needed
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def parse_sessionid(cookie_path: Path) -> str:
    """Parse JSON or Netscape cookies to extract the sessionid cookie value."""
    if not cookie_path.exists():
        return ""

    content = cookie_path.read_text(encoding="utf-8").strip()

    # Try parsing as JSON first
    try:
        data = json.loads(content)
        # Handle list of cookies
        if isinstance(data, list):
            for cookie in data:
                if cookie.get("name") == "sessionid":
                    return cookie.get("value", "") or ""
        # Handle dict of cookies
        elif isinstance(data, dict):
            return data.get("sessionid", "") or ""
    except json.JSONDecodeError:
        pass

    # Parse as Netscape cookies.txt format
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 7:
            name = parts[5]
            value = parts[6]
            if name == "sessionid":
                return value
        elif len(parts) >= 2:  # simple key-value/split
            name = parts[0]
            value = parts[1]
            if name == "sessionid":
                return value

    return ""


def main():
    print("=" * 60)
    print("        INSTAGRAM IN-PLACE COOKIES DIAGNOSTIC TEST")
    print("=" * 60)

    # 1. Install/Import instagrapi
    try:
        from instagrapi import Client
    except ImportError:
        print("[!] instagrapi is not installed locally. Installing it now...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "instagrapi>=2.0.0"])
        from instagrapi import Client
        print("[+] instagrapi installed successfully.\n")

    # 2. Look for cookie files in the test directory
    current_dir = Path(__file__).resolve().parent
    cookie_files = list(current_dir.glob("*cookie*"))

    sessionid = ""
    cookie_file_used = None

    if cookie_files:
        print("[*] Found the following cookie/credential candidates:")
        for idx, f in enumerate(cookie_files, 1):
            print(f"  [{idx}] {f.name}")
        
        selection = input("\nSelect a cookie file (Enter number) or press Enter to skip: ").strip()
        if selection.isdigit() and 1 <= int(selection) <= len(cookie_files):
            cookie_file_used = cookie_files[int(selection) - 1]
            sessionid = parse_sessionid(cookie_file_used)
            if sessionid:
                print(f"[+] Successfully extracted sessionid: {sessionid[:8]}...{sessionid[-8:] if len(sessionid) > 16 else ''}")
            else:
                print("[-] Could not find a 'sessionid' cookie inside the selected file.")

    # 3. Fallback to manual entry
    if not sessionid:
        sessionid = input("\nEnter your Instagram sessionid cookie value manually: ").strip()
        if sessionid.startswith("sessionid="):
            sessionid = sessionid.split("sessionid=")[1].split(";")[0]

    if not sessionid:
        print("[-] No sessionid provided. Cannot authenticate instagrapi. Exiting.")
        return

    # 4. Authenticate
    try:
        from colab_leecher.downlader.instagram_grapi import _patch_instagrapi_extractors
        _patch_instagrapi_extractors()
    except Exception as patch_err:
        print(f"[-] Could not apply extractor patch: {patch_err}")

    print("\n[*] Initializing instagrapi client...")
    cl = Client()
    cl.delay_range = [1, 2]
    cl.request_timeout = 15

    try:
        print("[*] Attempting login by sessionid...")
        sessionid = urllib.parse.unquote(sessionid)
        cl.login_by_sessionid(sessionid)
        # Test the session validity by calling get_timeline_feed or similar
        cl.get_timeline_feed()
        print("[+] Authentication Successful! Cookie is valid.")
    except Exception as auth_err:
        print(f"[-] Authentication Failed: {auth_err}")
        print("    Please verify that your sessionid cookie is fresh and correct.")
        return

    # 5. Get username/profile to test download
    profile_input = input("\nEnter an Instagram profile URL or username to test download: ").strip()
    if not profile_input:
        print("[-] No username provided. Skipping test download.")
        return

    # Extract username
    username = profile_input
    if "instagram.com" in profile_input:
        parsed = urllib.parse.urlparse(profile_input)
        path_parts = [p for p in parsed.path.split("/") if p]
        if path_parts:
            username = path_parts[0]

    print(f"\n[*] Resolving user ID for @{username}...")
    try:
        user_id = cl.user_id_from_username(username)
        print(f"[+] Found User ID: {user_id}")
    except Exception as e:
        print(f"[-] Failed to resolve username @{username}: {e}")
        return

    # 6. Fetch and download latest post
    print(f"[*] Fetching the latest post from @{username}...")
    try:
        medias = cl.user_medias(user_id, amount=1)
        if not medias:
            print("[-] No posts found on this profile.")
            return
        
        media = medias[0]
        print(f"[+] Found post PK: {media.pk} (Type: {media.media_type})")
        
        test_dl_dir = current_dir / "test_downloads"
        if test_dl_dir.exists():
            shutil.rmtree(test_dl_dir)
        test_dl_dir.mkdir(parents=True, exist_ok=True)
        
        print(f"[*] Downloading post to {test_dl_dir}...")
        mt = getattr(media, "media_type", None)
        pt = getattr(media, "product_type", "") or ""
        
        if mt == 1:
            paths = [cl.photo_download(media.pk, folder=test_dl_dir)]
        elif mt == 8:
            paths = list(cl.album_download(media.pk, folder=test_dl_dir))
        elif mt == 2:
            if pt == "clips":
                paths = [cl.clip_download(media.pk, folder=test_dl_dir)]
            else:
                paths = [cl.video_download(media.pk, folder=test_dl_dir)]
        else:
            paths = [cl.video_download(media.pk, folder=test_dl_dir)]

        downloaded_files = [p for p in paths if p and os.path.exists(p)]
        if downloaded_files:
            print("\n" + "="*50)
            print("[SUCCESS] Test download completed successfully!")
            print("Downloaded files:")
            for idx, filepath in enumerate(downloaded_files, 1):
                print(f"  [{idx}] {os.path.basename(filepath)}")
            print("="*50)
        else:
            print("[-] Download finished but no files were written to disk.")

    except Exception as dl_err:
        print(f"[-] Download failed: {dl_err}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Test cancelled.")
