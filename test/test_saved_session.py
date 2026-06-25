import os
import sys
from pathlib import Path
from instagrapi import Client

def main():
    current_dir = Path(__file__).resolve().parent
    settings_path = current_dir / "instagrapi_settings_test.json"

    if not settings_path.exists():
        print("[-] Error: Saved settings file not found at test/instagrapi_settings_test.json.")
        return

    cl = Client()
    cl.delay_range = [1, 2]

    print("[*] Loading saved session settings...")
    try:
        cl.load_settings(settings_path)
        cl.get_timeline_feed()
        print("[+] Session loaded and validated successfully!")
    except Exception as e:
        print(f"[-] Session validation failed: {e}")
        return

    post_url = "https://www.instagram.com/p/DZzndRyD82d/"
    print(f"[*] Resolving media PK for URL: {post_url}")
    try:
        media_pk = cl.media_pk_from_url(post_url)
        print(f"[+] Media PK: {media_pk}")
    except Exception as e:
        print(f"[-] Failed to resolve media PK: {e}")
        return

    print("[*] Fetching media info...")
    try:
        media = cl.media_info(media_pk)
        print(f"[+] Media type: {media.media_type}, product_type: {media.product_type}")
    except Exception as e:
        print(f"[-] Failed to get media info: {e}")
        return

    mt = getattr(media, "media_type", None)
    pt = getattr(media, "product_type", "") or ""

    print("[*] Downloading...")
    try:
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
            print(f"[SUCCESS] Downloaded successfully to: {path}")
        else:
            print("[-] Download finished but file not written.")
    except Exception as e:
        print(f"[-] Download failed: {e}")

if __name__ == "__main__":
    main()
