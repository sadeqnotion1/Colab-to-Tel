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

async def test_download(url, cf_clearance=None, user_agent=None, max_mb=25.0, out_dir=None):
    print("\n" + "="*50)
    print("  NZBCloud Standalone Downloader (PC Test Version)")
    print("="*50)

    pre_determined_name = None
    # Auto-parse GitHub Gist
    if "gist.github" in url.lower():
        print("[*] Detected Gist URL. Fetching content to parse...")
        try:
            async with AsyncSession(impersonate="chrome") as session:
                res = await session.get(url)
                if res.status_code == 200:
                    for line in res.text.split("\n"):
                        line = line.strip()
                        if line.startswith("TITLE="):
                            pre_determined_name = line.split("TITLE=", 1)[1].strip()
                        elif line.startswith("http://") or line.startswith("https://"):
                            url = line
                    print(f"[+] Parsed Gist. File: {pre_determined_name}")
                else:
                    print(f"[-] Failed to fetch Gist. HTTP status: {res.status_code}")
                    return False
        except Exception as gist_err:
            print(f"[-] Error fetching Gist: {gist_err}")
            return False

    # Determine filename
    parsed_url = urllib.parse.urlparse(url)
    filename = os.path.basename(urllib.parse.unquote(parsed_url.path))
    if not filename or filename == "play":
        filename = pre_determined_name or "downloaded_file.mkv"
    
    # Clean the filename
    filename = "".join([c for c in filename if c.isalpha() or c.isdigit() or c in '._- ']).strip()

    # Determine destination path
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        file_path = os.path.join(out_dir, filename)
    else:
        file_path = filename

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
    print(f"[*] Output File: {file_path}")
    print(f"[*] User-Agent: {headers['User-Agent']}")
    limit_bytes = int(max_mb * 1024 * 1024) if max_mb > 0 else 0
    print(f"[*] Limit: {format_size(limit_bytes) if limit_bytes > 0 else 'Unlimited'}")
    print("[*] Initiating connection via curl_cffi (impersonate='chrome')...")

    start_time = time.time()
    try:
        async with AsyncSession(impersonate="chrome") as session:
            response = await session.get(url, headers=headers, stream=True, allow_redirects=True)
            print(f"[+] Response Status: {response.status_code}")
            if response.status_code >= 400:
                print(f"[-] Download failed with HTTP error: {response.status_code}")
                return False
            
            content_len = response.headers.get("content-length") or response.headers.get("Content-Length")
            total_size = int(content_len) if content_len else 0
            print(f"[+] Content-Length: {format_size(total_size) if total_size else 'Unknown'}")
            
            downloaded = 0
            last_update = time.time()
            
            print("\nDownloading:")
            with open(file_path, "wb") as f:
                async for chunk in response.aiter_content(chunk_size=512*1024):
                    if chunk:
                        bytes_to_write = len(chunk)
                        if limit_bytes > 0:
                            bytes_to_write = min(len(chunk), limit_bytes - downloaded)
                        
                        f.write(chunk[:bytes_to_write])
                        downloaded += bytes_to_write
                        
                        now = time.time()
                        # Update progress bar
                        if now - last_update > 0.5 or (limit_bytes > 0 and downloaded >= limit_bytes) or downloaded == total_size:
                            last_update = now
                            elapsed = now - start_time
                            speed = downloaded / elapsed if elapsed > 0 else 0
                            
                            # Progress bar percentage
                            display_total = limit_bytes if limit_bytes > 0 else total_size
                            if display_total > 0:
                                pct = (downloaded / display_total) * 100
                                bar_len = 30
                                filled_len = int(bar_len * downloaded // display_total)
                                bar = '█' * filled_len + '-' * (bar_len - filled_len)
                                eta = (display_total - downloaded) / speed if speed > 0 else 0
                                eta_str = f"{int(eta)}s" if eta < 60 else f"{int(eta//60)}m {int(eta%60)}s"
                                sys.stdout.write(f"\r[{bar}] {pct:.1f}% | {format_size(downloaded)}/{format_size(display_total)} | {format_size(speed)}/s | ETA: {eta_str}    ")
                            else:
                                sys.stdout.write(f"\rDownloaded: {format_size(downloaded)} | Speed: {format_size(speed)}/s    ")
                            sys.stdout.flush()
                        
                        if limit_bytes > 0 and downloaded >= limit_bytes:
                            print(f"\n[!] Reached the {max_mb} MB limit. Stopping download to save traffic.")
                            break
            
            print("\n")
            # Stub sniffer
            if downloaded < 10240:
                with open(file_path, "wb") as f:
                    head = f.read(512)
                head_text = head.decode('utf-8', errors='replace').strip().lower()
                if "<html" in head_text or "<!doctype html" in head_text:
                    print("[-] Warning: The downloaded file is a HTML document (likely Cloudflare block/login page).")
                    return False
            
            print(f"[+] Download completed successfully!")
            print(f"[+] Saved to: {os.path.abspath(file_path)}")
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
    url = input("\nPaste NZBCloud direct file URL or Gist URL: ").strip()
    if not url:
        print("[-] URL is required!")
        return

    # 2. Get Output Directory
    out_dir = input("\nEnter output directory path (Press Enter for current directory): ").strip()
    if not out_dir:
        out_dir = "."

    # 3. Get Size Limit
    limit_str = input("\nEnter download size limit in MB (Press Enter for 25 MB): ").strip()
    if not limit_str:
        max_mb = 25.0
    else:
        try:
            max_mb = float(limit_str)
        except ValueError:
            print("[!] Invalid size. Using 25 MB limit.")
            max_mb = 25.0

    # 4. Get cf_clearance (Optional)
    cf = input("\nPaste cf_clearance cookie value (Press Enter to skip/none): ").strip()
    if cf.startswith("cf_clearance="):
        cf = cf.split("cf_clearance=")[1].split(";")[0]

    # 5. Get User-Agent (Optional)
    ua = input("\nPaste User-Agent (Press Enter for default Chrome 149): ").strip()
    if not ua:
        ua = None

    asyncio.run(test_download(url, cf_clearance=cf, user_agent=ua, max_mb=max_mb, out_dir=out_dir))

if __name__ == "__main__":
    main()
