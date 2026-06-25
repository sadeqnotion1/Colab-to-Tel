import os
import sys
import urllib.parse
from pathlib import Path
from instagrapi import Client

def parse_cookies_txt(filepath):
    cookies = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Ignore empty lines and lines that are comments BUT NOT HttpOnly comments
            if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
                continue
            
            # If it's a HttpOnly cookie, remove the #HttpOnly_ prefix
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            
            parts = line.split("\t")
            if len(parts) < 7:
                import re
                parts = re.split(r'\s+', line)
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6]
                cookies[name] = urllib.parse.unquote(value)
    return cookies

def main():
    current_dir = Path(__file__).resolve().parent
    cookies_file = current_dir / "cookies.txt"
    sessionid_file = current_dir / "sessionid.txt"

    if not cookies_file.exists():
        print(f"[-] Eror: test/cookies.txt not found.")
        return

    print("[*] Parsing test/cookies.txt...")
    cookies = parse_cookies_txt(cookies_file)
    print(f"[+] Loaded {len(cookies)} cookies from cookies.txt:")
    for k, v in cookies.items():
        print(f"  - {k}: {v[:8]}... ({len(v)} chars)")

    # Override sessionid with the new one from sessionid.txt if available
    if sessionid_file.exists():
        new_sessionid = sessionid_file.read_text(encoding="utf-8").strip()
        new_sessionid = urllib.parse.unquote(new_sessionid)
        if new_sessionid:
            cookies["sessionid"] = new_sessionid
            print(f"[+] Overrode sessionid with new value from sessionid.txt: {new_sessionid[:8]}...")

    if "sessionid" not in cookies:
        print("[-] Error: No sessionid found in cookies.txt or sessionid.txt.")
        return

    cl = Client()
    cl.delay_range = [1, 2]

    print("\n[*] Loading complete cookie set into instagrapi...")
    # Load cookies into instagrapi's HTTP session cookie jar with the correct domain
    for k, v in cookies.items():
        cl.private.cookies.set(k, v, domain=".instagram.com")
        cl.public.cookies.set(k, v, domain=".instagram.com")

    print("[*] Verifying session validity...")
    try:
        cl.get_timeline_feed()
        print("[SUCCESS] Full Cookie Authentication Successful! Session is active and working.")
        
        # Save this working session as instagrapi settings format
        settings_path = current_dir / "instagrapi_settings_test.json"
        cl.dump_settings(settings_path)
        print(f"[+] Saved valid session settings to {settings_path}")
    except Exception as e:
        print(f"[-] Authentication Failed: {e}")
        print("    This means Instagram rejected the cookie set. Ensure they are exported from a fresh, active browser session.")

if __name__ == "__main__":
    main()
