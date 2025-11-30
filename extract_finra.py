#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
FINRA Archive Streaming Extraction
Ready-to-use script for extracting your 65 GB FINRA archive

Instructions:
1. Copy this to Google Colab
2. Update the paths below
3. Run and monitor progress
"""

from zipfile import ZipFile
from pathlib import Path
import time
import os

print("=" * 70)
print("FINRA ARCHIVE - STREAMING EXTRACTION")
print("=" * 70)

# ============================================================================
# CONFIGURATION - Update these paths for your setup
# ============================================================================

# Path to your FINRA ZIP archive
ZIP_PATH = "/content/drive/My Drive/finra/FINRA_archive.zip"

# Where to extract files
EXTRACT_TO = "/content/drive/My Drive/finra/extracted"

# File filter (what types to extract)
# Examples:
#   ['.csv']              - Only CSV files
#   ['.csv', '.json']     - CSV and JSON files
#   None                  - Extract ALL files (will take longer!)
FILE_FILTER = ['.csv']  # Start with CSVs only

# Chunk size for reading/writing (1 MB is good for most cases)
CHUNK_SIZE = 1024 * 1024  # 1 MB

# ============================================================================
# STEP 1: Verify ZIP file exists
# ============================================================================

print(f"\n[Step 1] Checking ZIP file...")
print(f"Path: {ZIP_PATH}")

if not os.path.exists(ZIP_PATH):
    print(f"\n❌ ERROR: ZIP file not found!")
    print(f"Please update ZIP_PATH in the script to point to your archive.")
    exit(1)

zip_size_gb = os.path.getsize(ZIP_PATH) / (1024**3)
print(f"✅ Found archive: {zip_size_gb:.2f} GB")

# ============================================================================
# STEP 2: Inspect archive contents (don't extract yet)
# ============================================================================

print(f"\n[Step 2] Inspecting archive contents...")
print("This may take a moment for large archives...\n")

with ZipFile(ZIP_PATH, 'r') as z:
    all_members = z.infolist()
    all_files = [m for m in all_members if not m.is_dir()]

    print(f"📊 Archive statistics:")
    print(f"   Total files: {len(all_files)}")

    # Count by extension
    from collections import Counter
    extensions = Counter()
    for m in all_files:
        ext = os.path.splitext(m.filename)[1].lower()
        extensions[ext or '(no extension)'] += 1

    print(f"\n📁 Files by type:")
    for ext, count in extensions.most_common(10):
        print(f"   {ext}: {count} files")

    # Show sample files
    print(f"\n📄 Sample files (first 10):")
    for m in all_files[:10]:
        size_mb = m.file_size / (1024**2)
        print(f"   - {m.filename} ({size_mb:.2f} MB)")

    # Apply filter
    if FILE_FILTER:
        filtered_members = [
            m for m in all_files
            if any(m.filename.lower().endswith(ext.lower()) for ext in FILE_FILTER)
        ]
        print(f"\n🔍 Filter applied: {FILE_FILTER}")
        print(f"   Matched: {len(filtered_members)}/{len(all_files)} files")

        if len(filtered_members) == 0:
            print(f"\n❌ ERROR: No files match the filter!")
            print(f"Available extensions: {list(extensions.keys())}")
            exit(1)

        members_to_extract = filtered_members
    else:
        print(f"\n⚠️  No filter - will extract ALL {len(all_files)} files")
        members_to_extract = all_files

    # Estimate size
    total_size_bytes = sum(m.file_size for m in members_to_extract)
    total_size_gb = total_size_bytes / (1024**3)
    print(f"\n📦 Extraction plan:")
    print(f"   Files to extract: {len(members_to_extract)}")
    print(f"   Estimated size: {total_size_gb:.2f} GB")

# ============================================================================
# STEP 3: Confirm before starting
# ============================================================================

print("\n" + "=" * 70)
print("READY TO EXTRACT")
print("=" * 70)
print(f"From: {ZIP_PATH}")
print(f"To: {EXTRACT_TO}")
print(f"Files: {len(members_to_extract)}")
print(f"Size: {total_size_gb:.2f} GB")
print(f"Filter: {FILE_FILTER or 'None (extract all)'}")
print("=" * 70)

# In Colab, this will proceed automatically
# If running locally, you could add: input("Press Enter to start...")

print("\n[Step 3] Starting extraction...")
print("This will take a while. Progress updates every file:\n")

# ============================================================================
# STEP 4: Stream extraction
# ============================================================================

Path(EXTRACT_TO).mkdir(parents=True, exist_ok=True)

start_time = time.time()
files_extracted = 0
files_failed = 0
bytes_extracted = 0

with ZipFile(ZIP_PATH, 'r') as z:
    total = len(members_to_extract)

    for idx, member in enumerate(members_to_extract, 1):
        try:
            # Calculate progress
            percentage = (idx / total) * 100
            elapsed = time.time() - start_time

            # Calculate ETA
            if idx > 1:
                avg_time_per_file = elapsed / (idx - 1)
                remaining_files = total - idx + 1
                eta_seconds = avg_time_per_file * remaining_files
                eta_minutes = eta_seconds / 60

                if eta_minutes >= 60:
                    eta_str = f"{eta_minutes/60:.1f}h"
                elif eta_minutes >= 1:
                    eta_str = f"{eta_minutes:.1f}m"
                else:
                    eta_str = f"{eta_seconds:.0f}s"
            else:
                eta_str = "Calculating..."

            # Progress line
            elapsed_min = elapsed / 60
            size_mb = member.file_size / (1024**2)

            print(f"[{percentage:5.1f}%] File {idx:4d}/{total} | "
                  f"ETA: {eta_str:8s} | "
                  f"Elapsed: {elapsed_min:5.1f}m | "
                  f"{member.filename} ({size_mb:.1f} MB)")

            # Create target path
            target_path = Path(EXTRACT_TO) / member.filename
            target_path.parent.mkdir(parents=True, exist_ok=True)

            # Stream extract in chunks
            with z.open(member, 'r') as source, open(target_path, 'wb') as target:
                while True:
                    chunk = source.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    target.write(chunk)
                    bytes_extracted += len(chunk)

            files_extracted += 1

        except Exception as e:
            print(f"   ❌ FAILED: {member.filename} - {str(e)}")
            files_failed += 1
            continue

# ============================================================================
# STEP 5: Summary
# ============================================================================

total_time = time.time() - start_time
total_time_min = total_time / 60
extracted_gb = bytes_extracted / (1024**3)
speed_gb_per_min = extracted_gb / total_time_min if total_time_min > 0 else 0

print("\n" + "=" * 70)
print("EXTRACTION COMPLETE!")
print("=" * 70)
print(f"✅ Files extracted: {files_extracted}")
if files_failed > 0:
    print(f"❌ Files failed: {files_failed}")
print(f"📦 Total size: {extracted_gb:.2f} GB")
print(f"⏱️  Time: {total_time_min:.1f} minutes ({total_time/3600:.2f} hours)")
print(f"⚡ Average speed: {speed_gb_per_min:.2f} GB/min")
print(f"📂 Location: {EXTRACT_TO}")
print("=" * 70)

# Show extracted files structure
print(f"\n📁 Extracted file structure (first 20):")
extracted_files = []
for root, dirs, files in os.walk(EXTRACT_TO):
    for file in files:
        full_path = os.path.join(root, file)
        rel_path = os.path.relpath(full_path, EXTRACT_TO)
        extracted_files.append(rel_path)

for f in extracted_files[:20]:
    print(f"   - {f}")

if len(extracted_files) > 20:
    print(f"   ... and {len(extracted_files) - 20} more files")

print(f"\n🎉 Done! Your FINRA data is ready to use.")
print(f"Location: {EXTRACT_TO}")
