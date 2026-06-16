import os
import sys
import time
import urllib.parse
import asyncio
from curl_cffi.requests import AsyncSession

# Clear screen utility
def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def format_size(bytes_size):
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

async def test_download(url, cf_clearance=None, user_agent=None):
    print("\n" + "="*50)
    print("  NZBCloud Standalone Downloader (PC Test Version)")
    print("="*50)

    # Determine filename
    parsed_url = urllib.parse.urlparse(url)
    filename = os.path.basename(urllib.parse.unquote(parsed_url.path))
    if not filename:
        filename = "downloaded_file.mkv"
    
    # Setup headers
    headers = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://app.nzbcloud.com/",
        "Sec-Fetch-Dest": "video",
        "Sec-Fetch-Mode": "no-cors",
        "Sec-Fetch-Site": "same-site",
    }
    
    if user_agent:
        headers["User-Agent"] = user_agent
    else:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36"

    if cf_clearance:
        headers["Cookie"] = f"cf_clearance={cf_clearance}"
        print(f"[*] Cookie set: cf_clearance={cf_clearance[:10]}...{cf_clearance[-10:] if len(cf_clearance) > 20 else ''}")

    print(f"[*] Target URL: {url[:80]}...")
    print(f"[*] Output File: {filename}")
    print(f"[*] User-Agent: {headers['User-Agent']}")
    print("[*] Initiating connection via curl_cffi (impersonate='chrome')...")

    start_time = time.time()
    try:
        async with AsyncSession(impersonate="chrome") as session:
            async with session.get(url, headers=headers, stream=True, follow_redirects=True) as r:
                print(f"[+] Response Status: {r.status_code}")
                if r.status_code >= 400:
                    print(f"[-] Download failed with HTTP error: {r.status_code}")
                    return False
                
                content_len = r.headers.get("content-length") or r.headers.get("Content-Length")
                total_size = int(content_len) if content_len else 0
                print(f"[+] Content-Length: {format_size(total_size) if total_size else 'Unknown'}")
                
                downloaded = 0
                last_update = time.time()
                
                print("\nDownloading:")
                with open(filename, "wb") as f:
                    async for chunk in r.aiter_content(chunk_size=1024*1024):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            
                            now = time.time()
                            # Update progress bar
                            if now - last_update > 0.5 or downloaded == total_size:
                                last_update = now
                                elapsed = now - start_time
                                speed = downloaded / elapsed if elapsed > 0 else 0
                                
                                # Progress bar percentage
                                if total_size > 0:
                                    pct = (downloaded / total_size) * 100
                                    bar_len = 30
                                    filled_len = int(bar_len * downloaded // total_size)
                                    bar = '█' * filled_len + '-' * (bar_len - filled_len)
                                    eta = (total_size - downloaded) / speed if speed > 0 else 0
                                    eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta//60)}m {int(eta%60)}s"
                                    sys.stdout.write(f"\r[{bar}] {pct:.1f}% | {format_size(downloaded)}/{format_size(total_size)} | {format_size(speed)}/s | ETA: {eta_str}    ")
                                else:
                                    sys.stdout.write(f"\rDownloaded: {format_size(downloaded)} | Speed: {format_size(speed)}/s    ")
                                sys.stdout.flush()
                
                print("\n")
                # Stub sniffer
                if downloaded < 10240:
                    with open(filename, "rb") as f:
                        head = f.read(512)
                    head_text = head.decode('utf-8', errors='replace').strip().lower()
                    if "<html" in head_text or "<!doctype html" in head_text:
                        print("[-] Warning: The downloaded file is a small HTML document (likely a Cloudflare block page or error message).")
                        print("    Please check the link, cookie, and user agent.")
                        return False
                
                print(f"[+] Download finished successfully in {time.time() - start_time:.2f} seconds!")
                print(f"[+] Saved as: {os.path.abspath(filename)}")
                return True
                
    except Exception as e:
        print(f"\n[-] Exception occurred during download: {e}")
        return False

def main():
    clear_screen()
    print("="*60)
    print("         NZBCLOUD STANDALONE DOWNLOAD TESTER (PC)")
    print("="*60)
    
    # 1. Get URL
    url = input("\nPaste NZBCloud direct file URL: ").strip()
    if not url:
        print("[-] URL is required!")
        return

    # 2. Get cf_clearance (Optional)
    cf = input("\nPaste cf_clearance cookie value (Press Enter to skip/none): ").strip()
    if cf.startswith("cf_clearance="):
        cf = cf.split("cf_clearance=")[1].split(";")[0]

    # 3. Get User-Agent (Optional)
    ua = input("\nPaste User-Agent (Press Enter for default Chrome 149): ").strip()
    if not ua:
        ua = None

    asyncio.run(test_download(url, cf_clearance=cf, user_agent=ua))

if __name__ == "__main__":
    main()
