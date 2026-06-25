import requests
import urllib.parse
import re
from pathlib import Path

def parse_cookies_txt(filepath):
    cookies = {}
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or (line.startswith("#") and not line.startswith("#HttpOnly_")):
                continue
            if line.startswith("#HttpOnly_"):
                line = line[len("#HttpOnly_"):]
            parts = re.split(r'\s+', line)
            if len(parts) >= 7:
                name = parts[5]
                value = parts[6]
                cookies[name] = urllib.parse.unquote(value)
    return cookies

def main():
    current_dir = Path(__file__).resolve().parent
    cookies_file = current_dir / "cookies.txt"

    if not cookies_file.exists():
        print("[-] Error: test/cookies.txt not found.")
        return

    cookies = parse_cookies_txt(cookies_file)
    print(f"[*] Parsed cookies: {list(cookies.keys())}")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.instagram.com/",
        "X-IG-App-ID": "936619743392459",  # Instagram Web App ID
    }

    url = "https://www.instagram.com/p/CmUvE7fOf8A/"
    print(f"[*] Fetching HTML page from {url}...")
    
    try:
        res = requests.get(url, cookies=cookies, headers=headers, timeout=15)
        print(f"[+] HTTP Status: {res.status_code}")
        
        html = res.text
        if "not-logged-in" in html:
            print("\n" + "="*50)
            print("[-] Cookies Rejected by Instagram: 'not-logged-in' class found in HTML.")
            print("="*50)
        elif "ds_user_id" in html or "viewerId" in html or res.status_code == 200:
            print("\n" + "="*50)
            print("[SUCCESS] Cookies are accepted by Instagram! Logged-in page served.")
            viewer_match = re.search(r'"viewerId":"(\d+)"', html)
            if viewer_match:
                print(f"  Viewer ID: {viewer_match.group(1)}")
            print("="*50)
        else:
            print(f"[-] Unknown response state. Status: {res.status_code}")
            print(f"    Snippet: {html[:300]}")
    except Exception as req_err:
        print(f"[-] HTTP request failed: {req_err}")

if __name__ == "__main__":
    main()
