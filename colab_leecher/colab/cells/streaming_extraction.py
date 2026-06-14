# ═══════════════════════════════════════════════════════════════════════
# 📦 STREAMING ZIP EXTRACTION - Built-in Cell
# Memory-safe extraction for large archives (65+ GB)
# Add this cell to your notebook for instant streaming extraction!
# ═══════════════════════════════════════════════════════════════════════

from zipfile import ZipFile
from pathlib import Path
import os
import time

def format_size(bytes_size):
    """Convert bytes to human-readable format"""
    from colab_leecher.utility.formatting import format_bytes
    return format_bytes(bytes_size)

def format_time(seconds):
    """Convert seconds to human-readable format"""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"

def extract_zip_streaming(
    zip_path,
    extract_to=None,
    file_filter=None,
    chunk_size=1024*1024,  # 1 MB chunks
    remove_zip=False,
    max_files=None  # Limit extraction (useful for testing)
):
    """
    Stream-extract ZIP files with progress tracking

    Args:
        zip_path: Path to ZIP file
        extract_to: Where to extract (default: same folder as ZIP)
        file_filter: List of extensions to extract (e.g., ['.csv', '.json'])
        chunk_size: Chunk size in bytes (default: 1 MB)
        remove_zip: Remove ZIP after extraction (default: False)
        max_files: Max files to extract (None = all)

    Returns:
        dict: Statistics about extraction
    """

    # Validate ZIP exists
    if not os.path.exists(zip_path):
        print(f"❌ ZIP not found: {zip_path}")
        return None

    # Default extract location
    if extract_to is None:
        extract_to = os.path.dirname(zip_path)

    Path(extract_to).mkdir(parents=True, exist_ok=True)

    zip_name = os.path.basename(zip_path)
    zip_size = os.path.getsize(zip_path)

    print("="*70)
    print(f"📦 STREAMING ZIP EXTRACTION")
    print("="*70)
    print(f"📁 Source: {zip_name}")
    print(f"📏 Size: {format_size(zip_size)}")
    print(f"📂 Extract to: {extract_to}")
    print()

    start_time = time.time()
    files_extracted = 0
    files_skipped = 0
    bytes_extracted = 0

    try:
        with ZipFile(zip_path, 'r') as zip_ref:
            # Get all files (skip directories)
            all_members = [m for m in zip_ref.infolist() if not m.is_dir()]
            total_files = len(all_members)

            print(f"📊 Total files in archive: {total_files}")

            # Apply file filter if specified
            if file_filter:
                members_to_extract = [
                    m for m in all_members
                    if any(m.filename.lower().endswith(ext.lower()) for ext in file_filter)
                ]
                print(f"🔍 Filter applied: {file_filter}")
                print(f"✅ Matched files: {len(members_to_extract)}/{total_files}")
            else:
                members_to_extract = all_members
                print(f"✅ Extracting all files")

            # Limit files if specified
            if max_files and len(members_to_extract) > max_files:
                members_to_extract = members_to_extract[:max_files]
                print(f"⚠️  Limited to first {max_files} files (testing mode)")

            total_to_extract = len(members_to_extract)

            if total_to_extract == 0:
                print("❌ No files match the filter!")
                return None

            print()
            print("="*70)
            print("🚀 Starting extraction...")
            print("="*70)
            print()

            # Extract each file with streaming
            for idx, member in enumerate(members_to_extract, 1):
                try:
                    # Calculate progress
                    percentage = (idx / total_to_extract) * 100
                    elapsed = time.time() - start_time

                    # Estimate ETA
                    if idx > 1:
                        eta_seconds = (elapsed / (idx - 1)) * (total_to_extract - idx + 1)
                        eta_str = format_time(eta_seconds)
                    else:
                        eta_str = "Calculating..."

                    # Progress bar
                    bar_length = 30
                    filled = int(bar_length * percentage / 100)
                    bar = '█' * filled + '░' * (bar_length - filled)

                    # Print progress
                    print(f"\r[{bar}] {percentage:5.1f}% | File {idx:>4}/{total_to_extract} | ETA: {eta_str:>8} | {member.filename[:40]:40}", end='', flush=True)

                    # Create target path
                    target_path = Path(extract_to) / member.filename
                    target_path.parent.mkdir(parents=True, exist_ok=True)

                    # Stream extract in chunks
                    with zip_ref.open(member, 'r') as source, open(target_path, 'wb') as target:
                        while True:
                            chunk = source.read(chunk_size)
                            if not chunk:
                                break
                            target.write(chunk)
                            bytes_extracted += len(chunk)

                    files_extracted += 1

                except Exception as e:
                    print(f"\n❌ Failed to extract {member.filename}: {e}")
                    files_skipped += 1
                    continue

            # Final newline after progress bar
            print()
            print()
            print("="*70)
            print("✅ EXTRACTION COMPLETE!")
            print("="*70)

            # Statistics
            total_time = time.time() - start_time
            avg_speed = bytes_extracted / total_time if total_time > 0 else 0

            stats = {
                'files_extracted': files_extracted,
                'files_skipped': files_skipped,
                'bytes_extracted': bytes_extracted,
                'total_time': total_time,
                'avg_speed': avg_speed
            }

            print(f"📊 Files extracted: {files_extracted}")
            print(f"⚠️  Files skipped: {files_skipped}")
            print(f"📦 Total size: {format_size(bytes_extracted)}")
            print(f"⏱️  Time elapsed: {format_time(total_time)}")
            print(f"⚡ Average speed: {format_size(avg_speed)}/s")
            print("="*70)

            # Remove ZIP if requested
            if remove_zip:
                try:
                    os.remove(zip_path)
                    print(f"🗑️  Removed source ZIP: {zip_name}")
                except Exception as e:
                    print(f"⚠️  Could not remove ZIP: {e}")

            return stats

    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
        import traceback
        traceback.print_exc()
        return None


# ═══════════════════════════════════════════════════════════════════════
# 🎯 QUICK START EXAMPLES
# ═══════════════════════════════════════════════════════════════════════

def example_inspect_zip(zip_path):
    """Inspect ZIP contents without extracting"""
    from collections import Counter

    print("="*70)
    print("🔍 INSPECTING ZIP ARCHIVE")
    print("="*70)

    if not os.path.exists(zip_path):
        print(f"❌ ZIP not found: {zip_path}")
        return

    zip_size = os.path.getsize(zip_path)
    print(f"📁 File: {os.path.basename(zip_path)}")
    print(f"📏 Size: {format_size(zip_size)}")
    print()

    with ZipFile(zip_path, 'r') as z:
        all_files = [m for m in z.infolist() if not m.is_dir()]
        print(f"📊 Total files: {len(all_files)}")
        print()

        # Count by extension
        exts = Counter(os.path.splitext(m.filename)[1].lower() for m in all_files)
        print("📂 File types:")
        for ext, count in exts.most_common(10):
            print(f"   {ext or '(no extension)':15} : {count:>6} files")
        print()

        # Calculate total uncompressed size
        total_size = sum(m.file_size for m in all_files)
        print(f"📦 Uncompressed size: {format_size(total_size)}")
        print(f"🗜️  Compression ratio: {(1 - zip_size/total_size)*100:.1f}%")
        print()

        # Show first 10 files
        print("📄 First 10 files:")
        for m in all_files[:10]:
            print(f"   {m.filename[:60]:60} {format_size(m.file_size):>10}")

        if len(all_files) > 10:
            print(f"   ... and {len(all_files) - 10} more files")

    print("="*70)


# ═══════════════════════════════════════════════════════════════════════
# 📝 USAGE INSTRUCTIONS
# ═══════════════════════════════════════════════════════════════════════

print("""
╔═══════════════════════════════════════════════════════════════════════╗
║           📦 STREAMING ZIP EXTRACTION - READY TO USE!                 ║
╚═══════════════════════════════════════════════════════════════════════╝

🎯 EXAMPLE 1: Inspect Your FINRA Archive (No Extraction)
─────────────────────────────────────────────────────────────────────────
# First, inspect what's inside
example_inspect_zip("/content/drive/My Drive/finra/FINRA_archive.zip")


🎯 EXAMPLE 2: Extract Only CSV Files (Recommended for Testing)
─────────────────────────────────────────────────────────────────────────
# Extract only CSVs, limit to first 10 files for testing
extract_zip_streaming(
    zip_path="/content/drive/My Drive/finra/FINRA_archive.zip",
    extract_to="/content/drive/My Drive/finra/extracted",
    file_filter=['.csv'],      # Only CSV files
    max_files=10,              # Test with 10 files first
    remove_zip=False
)


🎯 EXAMPLE 3: Extract All CSV Files (Full Run)
─────────────────────────────────────────────────────────────────────────
# When ready, extract all CSVs
extract_zip_streaming(
    zip_path="/content/drive/My Drive/finra/FINRA_archive.zip",
    extract_to="/content/drive/My Drive/finra/extracted",
    file_filter=['.csv'],      # Only CSV files
    max_files=None,            # Extract all matching files
    remove_zip=False
)


🎯 EXAMPLE 4: Extract Everything
─────────────────────────────────────────────────────────────────────────
# Extract all files (no filter)
extract_zip_streaming(
    zip_path="/content/drive/My Drive/finra/FINRA_archive.zip",
    extract_to="/content/drive/My Drive/finra/extracted",
    file_filter=None,          # All file types
    remove_zip=False
)


🎯 EXAMPLE 5: Multiple File Types
─────────────────────────────────────────────────────────────────────────
# Extract CSVs and JSONs only
extract_zip_streaming(
    zip_path="/content/drive/My Drive/finra/FINRA_archive.zip",
    extract_to="/content/drive/My Drive/finra/extracted",
    file_filter=['.csv', '.json', '.txt'],
    remove_zip=False
)


💡 TIPS:
─────────────────────────────────────────────────────────────────────────
• Always inspect first with example_inspect_zip()
• Test with max_files=10 before full extraction
• Use file_filter to extract only what you need
• Memory usage stays constant (1-4 MB) - perfect for Colab!
• Progress bar shows ETA and current file
• Works with 65+ GB archives without issues


🚀 READY TO START!
─────────────────────────────────────────────────────────────────────────
1. Mount your Google Drive (if not already):
   from google.colab import drive
   drive.mount('/content/drive')

2. Update the paths in examples above
3. Run example_inspect_zip() first
4. Then run extract_zip_streaming() with your settings

═══════════════════════════════════════════════════════════════════════
""")
