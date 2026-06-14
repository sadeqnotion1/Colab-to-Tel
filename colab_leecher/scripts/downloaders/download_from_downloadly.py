#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Download from downloadly.ir with proper headers
Handles restrictions and resume capability
"""

import requests
import os
import sys
from pathlib import Path
import time

def format_size(bytes_size):
    """Convert bytes to human-readable format"""
    from colab_leecher.utility.formatting import format_bytes
    return format_bytes(bytes_size)

def format_speed(bytes_per_sec):
    """Convert bytes/sec to human-readable format"""
    from colab_leecher.utility.formatting import format_speed
    return format_speed(bytes_per_sec)

def download_file(url, output_path=None, chunk_size=1024*1024):
    """
    Download file from downloadly.ir with resume support

    Args:
        url: Download URL
        output_path: Where to save (default: current directory)
        chunk_size: Download chunk size (default: 1 MB)
    """

    # Extract filename from URL
    if output_path is None:
        filename = url.split('/')[-1].split('?')[0]
        output_path = filename

    # Check if file exists (for resume)
    if os.path.exists(output_path):
        resume_from = os.path.getsize(output_path)
        print(f"📂 Found existing file: {format_size(resume_from)}")
        print(f"🔄 Resuming download...")
        mode = 'ab'
    else:
        resume_from = 0
        mode = 'wb'

    # Headers to bypass restrictions
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,fa;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Referer': 'https://downloadly.ir/',
        'DNT': '1',
    }

    # Add range header for resume
    if resume_from > 0:
        headers['Range'] = f'bytes={resume_from}-'

    print("="*70)
    print("📥 DOWNLOADING FROM DOWNLOADLY.IR")
    print("="*70)
    print(f"🔗 URL: {url[:60]}...")
    print(f"💾 Save to: {output_path}")
    print()

    try:
        # Make request with headers
        print("🔍 Connecting...")
        response = requests.get(url, headers=headers, stream=True, timeout=30)

        # Check response
        if response.status_code == 403:
            print("❌ ERROR: Access forbidden (403)")
            print("💡 The site might be blocking Colab/datacenter IPs")
            print("💡 Try downloading from your browser instead")
            return False
        elif response.status_code == 404:
            print("❌ ERROR: File not found (404)")
            return False
        elif response.status_code not in [200, 206]:
            print(f"❌ ERROR: HTTP {response.status_code}")
            print(f"   Response: {response.text[:200]}")
            return False

        # Get file size
        if 'Content-Length' in response.headers:
            total_size = int(response.headers['Content-Length'])
            if resume_from > 0:
                total_size += resume_from
        else:
            total_size = 0
            print("⚠️  Warning: File size unknown")

        # Check if resume worked
        if response.status_code == 206:
            print(f"✅ Resume supported! Starting from {format_size(resume_from)}")
        elif resume_from > 0:
            print("⚠️  Resume not supported, restarting download")
            resume_from = 0
            mode = 'wb'

        print(f"📦 Total size: {format_size(total_size) if total_size else 'Unknown'}")
        print()
        print("🚀 Starting download...")
        print()

        # Download with progress
        downloaded = resume_from
        start_time = time.time()
        last_print = start_time

        with open(output_path, mode) as f:
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)

                    # Update progress every 0.5 seconds
                    current_time = time.time()
                    if current_time - last_print >= 0.5:
                        elapsed = current_time - start_time
                        speed = (downloaded - resume_from) / elapsed if elapsed > 0 else 0

                        if total_size > 0:
                            percentage = (downloaded / total_size) * 100
                            eta_seconds = (total_size - downloaded) / speed if speed > 0 else 0

                            # Progress bar
                            bar_len = 40
                            filled = int(bar_len * percentage / 100)
                            bar = '█' * filled + '░' * (bar_len - filled)

                            # Format ETA
                            if eta_seconds < 60:
                                eta_str = f"{eta_seconds:.0f}s"
                            elif eta_seconds < 3600:
                                eta_str = f"{eta_seconds/60:.1f}m"
                            else:
                                eta_str = f"{eta_seconds/3600:.1f}h"

                            print(f"\r[{bar}] {percentage:5.1f}% | {format_size(downloaded)} / {format_size(total_size)} | {format_speed(speed)} | ETA: {eta_str}", end='', flush=True)
                        else:
                            print(f"\r📦 Downloaded: {format_size(downloaded)} | {format_speed(speed)}", end='', flush=True)

                        last_print = current_time

        print()
        print()

        # Done
        total_time = time.time() - start_time
        avg_speed = (downloaded - resume_from) / total_time if total_time > 0 else 0

        print("="*70)
        print("✅ DOWNLOAD COMPLETE!")
        print("="*70)
        print(f"💾 File: {output_path}")
        print(f"📦 Size: {format_size(downloaded)}")
        print(f"⏱️  Time: {total_time/60:.1f} minutes")
        print(f"⚡ Average speed: {format_speed(avg_speed)}")
        print("="*70)

        return True

    except requests.exceptions.RequestException as e:
        print(f"\n❌ Download failed: {e}")
        return False
    except KeyboardInterrupt:
        print(f"\n⚠️  Download interrupted!")
        print(f"💾 Partial file saved: {output_path}")
        print(f"🔄 Run again to resume from {format_size(downloaded)}")
        return False


if __name__ == "__main__":
    # Your downloadly.ir URL
    URL = "https://dl1.downloadly.ir/Files/Elearning/Udemy_CBT_Practitioner_Training_Cognitive_and_Behaviour_Therapy_2024_11.part02_Downloadly.ir.rar?nocache=1764337339784"

    # Output path (optional - will use filename from URL)
    OUTPUT = None  # or "/content/drive/My Drive/Downloads/file.rar"

    print("Starting download from downloadly.ir...")
    print()

    success = download_file(URL, OUTPUT)

    if not success:
        print()
        print("💡 TROUBLESHOOTING:")
        print("   1. Check if the link is still valid")
        print("   2. Try downloading from your browser first")
        print("   3. If it's an IP restriction, use a VPN")
        print("   4. Make sure you have enough storage space")
        sys.exit(1)
