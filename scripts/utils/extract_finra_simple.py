#!/usr/bin/env python3
"""
SIMPLE FINRA ZIP EXTRACTOR
Just update the 3 paths below and run!
"""

# ═══════════════════════════════════════════════════════════════════════
# ⚙️ CONFIGURATION - UPDATE THESE 3 LINES ONLY
# ═══════════════════════════════════════════════════════════════════════

ZIP_FILE = "/content/drive/My Drive/finra/FINRA_archive.zip"
EXTRACT_TO = "/content/drive/My Drive/finra/extracted"
ONLY_CSV = True  # True = only CSVs, False = all files

# ═══════════════════════════════════════════════════════════════════════
# 🚀 RUN THE EXTRACTION (Don't change anything below)
# ═══════════════════════════════════════════════════════════════════════

from zipfile import ZipFile
from pathlib import Path
import os
import time

print("="*70)
print("📦 SIMPLE ZIP EXTRACTOR")
print("="*70)
print()

# Check ZIP exists
if not os.path.exists(ZIP_FILE):
    print(f"❌ ERROR: ZIP file not found!")
    print(f"   Looking for: {ZIP_FILE}")
    print()
    print("💡 Make sure:")
    print("   1. Google Drive is mounted")
    print("   2. Path is correct")
    print("   3. File exists in Drive")
    exit(1)

# Create output folder
Path(EXTRACT_TO).mkdir(parents=True, exist_ok=True)

# Get ZIP info
zip_size = os.path.getsize(ZIP_FILE) / (1024**3)  # GB
print(f"✅ Found ZIP: {os.path.basename(ZIP_FILE)}")
print(f"📏 Size: {zip_size:.2f} GB")
print(f"📂 Extract to: {EXTRACT_TO}")
print()

# Open ZIP and count files
with ZipFile(ZIP_FILE, 'r') as z:
    all_files = [m for m in z.infolist() if not m.is_dir()]

    if ONLY_CSV:
        files_to_extract = [m for m in all_files if m.filename.lower().endswith('.csv')]
        print(f"📊 Total files in ZIP: {len(all_files)}")
        print(f"📊 CSV files: {len(files_to_extract)}")
    else:
        files_to_extract = all_files
        print(f"📊 Files to extract: {len(files_to_extract)}")

    print()

    if len(files_to_extract) == 0:
        print("❌ No files to extract!")
        exit(1)

    print("🚀 Starting extraction...")
    print()

    start_time = time.time()

    # Extract each file
    for idx, member in enumerate(files_to_extract, 1):
        # Progress
        percentage = (idx / len(files_to_extract)) * 100
        bar_len = 40
        filled = int(bar_len * percentage / 100)
        bar = '█' * filled + '░' * (bar_len - filled)

        # ETA
        elapsed = time.time() - start_time
        if idx > 1:
            eta = (elapsed / (idx - 1)) * (len(files_to_extract) - idx + 1)
            eta_min = eta / 60
            eta_str = f"{eta_min:.1f}m" if eta_min >= 1 else f"{eta:.1f}s"
        else:
            eta_str = "..."

        # Print progress
        print(f"\r[{bar}] {percentage:5.1f}% | {idx}/{len(files_to_extract)} | ETA: {eta_str:>6}", end='')

        # Extract file
        target = Path(EXTRACT_TO) / member.filename
        target.parent.mkdir(parents=True, exist_ok=True)

        # Stream in 1MB chunks
        with z.open(member) as source, open(target, 'wb') as dest:
            while True:
                chunk = source.read(1024 * 1024)
                if not chunk:
                    break
                dest.write(chunk)

    print()
    print()

    # Done
    total_time = time.time() - start_time
    print("="*70)
    print("✅ EXTRACTION COMPLETE!")
    print("="*70)
    print(f"📊 Files extracted: {len(files_to_extract)}")
    print(f"⏱️  Time: {total_time/60:.1f} minutes")
    print(f"📂 Location: {EXTRACT_TO}")
    print("="*70)
