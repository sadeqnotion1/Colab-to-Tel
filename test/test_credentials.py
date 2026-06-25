import os
import sys
import urllib.parse
from pathlib import Path
from instagrapi import Client
from instagrapi.exceptions import TwoFactorRequired

def main():
    current_dir = Path(__file__).resolve().parent

    username = input("Enter your Instagram username: ").strip()
    password = input("Enter your Instagram password: ").strip()

    if not username or not password:
        print("[-] Username and password are required. Exiting.")
        return

    cl = Client()
    cl.delay_range = [1, 2]
    cl.request_timeout = 15

    # Setup device settings to avoid flag
    cl.set_device({
        "app_version": "269.0.0.18.230",
        "android_version": "29",
        "android_release": "10",
        "dpi": "480dpi",
        "resolution": "1080x1920",
        "manufacturer": "Samsung",
        "device": "galaxy-s20",
        "model": "SM-G981B",
        "cpu": "exynos990",
        "version_code": "443228304"
    })

    print("\n[*] Attempting login using username and password...")
    logged_in = False
    try:
        cl.login(username, password)
        logged_in = True
    except TwoFactorRequired as tfa_err:
        print(f"\n[!] Two-Factor Authentication is required for this account.")
        verification_code = input("Enter your 2FA verification code: ").strip()
        if verification_code:
            try:
                # Log in using the 2FA code
                cl.login(username, password, verification_code=verification_code)
                logged_in = True
            except Exception as tfa_login_err:
                print(f"[-] 2FA Login failed: {tfa_login_err}")
        else:
            print("[-] No 2FA verification code entered.")
    except Exception as login_err:
        print(f"[-] Login failed: {login_err}")

    if not logged_in:
        print("[-] Authentication unsuccessful.")
        return

    print("[SUCCESS] Logged in successfully!")
    
    # Save the session settings
    settings_path = current_dir / "instagrapi_settings_test.json"
    cl.dump_settings(settings_path)
    print(f"[+] Saved valid session settings to {settings_path}")

    # Verify session works by fetching a post
    post_url = "https://www.instagram.com/p/DaAVZyQj-nE/"
    print(f"\n[*] Testing download for post: {post_url}")
    try:
        media_pk = cl.media_pk_from_url(post_url)
        media = cl.media_info(media_pk)
        print(f"[+] Fetched media. Downloading...")
        
        mt = getattr(media, "media_type", None)
        pt = getattr(media, "product_type", "") or ""
        
        if mt == 1:
            path = cl.photo_download(media_pk, folder=current_dir)
        elif mt == 8:
            paths = cl.album_download(media_pk, folder=current_dir)
            path = paths[0] if paths else None
        elif mt == 2:
            if pt == "clips":
                path = cl.clip_download(media_pk, folder=current_dir)
            else:
                path = cl.video_download(media_pk, folder=current_dir)
        else:
            path = cl.video_download(media_pk, folder=current_dir)

        if path and os.path.exists(path):
            print(f"\n[SUCCESS] Downloaded successfully to: {path}")
        else:
            print("[-] Download finished but file not written.")
    except Exception as e:
        print(f"[-] Test download failed: {e}")

if __name__ == "__main__":
    main()
