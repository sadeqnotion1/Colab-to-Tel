import os
import sys
import urllib.parse
from pathlib import Path
from instagrapi import Client

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from test_instagram_grapi import parse_sessionid

def main():
    current_dir = Path(__file__).resolve().parent
    sessionid_file = current_dir / "sessionid.txt"
    sessionid = ""

    # 1. Try reading from sessionid.txt
    if sessionid_file.exists():
        sessionid = sessionid_file.read_text(encoding="utf-8").strip()
        print(f"[+] Loaded session ID from sessionid.txt")
    
    # 2. Try parsing other cookie files in the test directory
    if not sessionid:
        cookie_files = list(current_dir.glob("*cookie*"))
        for f in cookie_files:
            sessionid = parse_sessionid(f)
            if sessionid:
                print(f"[+] Parsed session ID from cookie file: {f.name}")
                break

    # 3. Prompt user if still missing
    if not sessionid:
        sessionid = input("\nEnter your Instagram sessionid cookie manually: ").strip()

    if not sessionid:
        print("[-] No sessionid provided. Exiting.")
        return

    # Automatically decode in case it is URL-encoded
    sessionid = urllib.parse.unquote(sessionid)
    print(f"[*] Decoded sessionid: {sessionid[:8]}...{sessionid[-8:] if len(sessionid) > 16 else ''}")

    cl = Client()
    cl.delay_range = [1, 2]
    cl.request_timeout = 15

    print("[*] Logging in...")
    try:
        cl.login_by_sessionid(sessionid)
        cl.get_timeline_feed()
        print("[+] Logged in successfully.")
    except Exception as login_err:
        print(f"[-] Login failed: {login_err}")
        print("    If you get 'Exceeded 30 redirects', Instagram may be enforcing a security challenge (checkpoint) on this account.")
        return

    post_url = "https://www.instagram.com/p/DaAVZyQj-nE/"
    print(f"[*] Resolving media PK for URL: {post_url}")
    try:
        media_pk = cl.media_pk_from_url(post_url)
        print(f"[+] Media PK: {media_pk}")
    except Exception as resolve_err:
        print(f"[-] Failed to resolve media PK from URL: {resolve_err}")
        return

    print("[*] Fetching media info...")
    try:
        media = cl.media_info(media_pk)
        print(f"[+] Media type: {media.media_type}, product_type: {media.product_type}")
    except Exception as info_err:
        print(f"[-] Failed to get media info: {info_err}")
        return

    folder = str(current_dir)
    os.makedirs(folder, exist_ok=True)

    mt = getattr(media, "media_type", None)
    pt = getattr(media, "product_type", "") or ""

    print("[*] Downloading...")
    try:
        if mt == 1:
            path = cl.photo_download(media_pk, folder=folder)
            print(f"[SUCCESS] Downloaded photo: {path}")
        elif mt == 8:
            paths = cl.album_download(media_pk, folder=folder)
            print(f"[SUCCESS] Downloaded album: {paths}")
        elif mt == 2:
            if pt == "clips":
                path = cl.clip_download(media_pk, folder=folder)
            else:
                path = cl.video_download(media_pk, folder=folder)
            print(f"[SUCCESS] Downloaded video/clip: {path}")
        else:
            path = cl.video_download(media_pk, folder=folder)
            print(f"[SUCCESS] Downloaded: {path}")
    except Exception as dl_err:
        print(f"[-] Download failed: {dl_err}")

if __name__ == "__main__":
    main()
