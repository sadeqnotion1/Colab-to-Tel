#!/usr/bin/env python3
"""
Test the extract logic without running the bot
"""
import re
from urllib.parse import urlparse

# Simulate the isLink function
def isLink(text):
    """Checks if the message text is likely a downloadable link or path."""
    if text:
        text = str(text)
        # Allow commands and local paths starting with / or ~ (for dir-leech etc.)
        if text.startswith("/") or text.startswith("~"):
            print(f"  [OK] isLink: TRUE (starts with / or ~)")
            return True
        # Check for magnet links
        elif text.startswith("magnet:?xt=urn:btih:"):
            print(f"  [OK] isLink: TRUE (magnet link)")
            return True
        # Check for standard URL formats
        try:
            parsed = urlparse(text)
            # Requires a scheme (http, https, ftp, etc.) AND a netloc (domain name)
            if parsed.scheme and parsed.netloc:
                print(f"  [OK] isLink: TRUE (valid URL)")
                return True
        except ValueError:
            print(f"  [FAIL] isLink: FALSE (parse error)")
            return False

    print(f"  [FAIL] isLink: FALSE (no match)")
    return False

# Simulate the command filter logic
def is_command_not_path(text):
    """Check if text is a command vs a file path"""
    if text and text.startswith('/'):
        parts = text.split(None, 1)
        first_part = parts[0]
        has_more_slashes = '/' in first_part[1:]
        print(f"  first_part: '{first_part}'")
        print(f"  has_more_slashes: {has_more_slashes}")
        print(f"  len(first_part): {len(first_part)}")

        if len(parts[0]) <= 20 and not has_more_slashes:
            print(f"  ==> Detected as COMMAND (will be ignored)")
            return True
        else:
            print(f"  ==> Detected as FILE PATH (will be processed)")
            return False
    return False

# Simulate multi-part detection
def detect_multipart(archive_path):
    """Test multi-part RAR detection"""
    print(f"\n3. Testing multi-part detection for: {archive_path}")

    if '.part' in archive_path.lower() and archive_path.lower().endswith('.rar'):
        print("  [OK] Detected as multi-part RAR")

        # Extract base name and suffix
        match = re.search(r'(.*)\.part\d+(.*\.rar)$', archive_path, flags=re.IGNORECASE)
        if match:
            base = match.group(1)
            suffix = match.group(2)
            print(f"  Base: '{base}'")
            print(f"  Suffix: '{suffix}'")

            potential_first_parts = [
                f"{base}.part01{suffix}",
                f"{base}.part001{suffix}",
                f"{base}.part1{suffix}"
            ]
            print(f"  Will look for: {potential_first_parts}")
            return potential_first_parts
        else:
            print("  [FAIL] Regex didn't match multi-part pattern")
    else:
        print("  [FAIL] Not a multi-part RAR")

    return None

# Test cases
test_path = "/content/drive/MyDrive/Colab Files/Udemy_CBT_Practitioner_Training_Cognitive_and_Behaviour_Therapy_2024_11.part01_Downloadly.ir.rar"

print("="*80)
print("EXTRACT LOGIC DEBUG TEST")
print("="*80)

print(f"\nTest path: {test_path}")

print("\n1. Testing isLink filter:")
result = isLink(test_path)
print(f"   Result: {result}")

print("\n2. Testing command vs path detection:")
is_cmd = is_command_not_path(test_path)

if result and not is_cmd:
    print("\n[SUCCESS] Path should trigger handle_url and be processed")
    detect_multipart(test_path)
else:
    print("\n[ERROR] Path will NOT be processed!")
    if not result:
        print("   Reason: isLink returned False")
    if is_cmd:
        print("   Reason: Detected as command")

print("\n" + "="*80)
