"""
Quick script to check SABnzbd setup logs from the full log file

Run this in Colab after running colab_setup_cell.py to see what happened with SABnzbd
"""

import os

log_file = '/content/setup_full.log'

if not os.path.exists(log_file):
    print("❌ Log file not found!")
    print(f"   Expected: {log_file}")
    print("\n Run colab_setup_cell.py first to generate the log file.")
else:
    print("=" * 70)
    print("SABnzbd Setup Logs")
    print("=" * 70)
    print()

    with open(log_file, 'r') as f:
        lines = f.readlines()

    # Find SABnzbd section
    sabnzbd_start = None
    for i, line in enumerate(lines):
        if 'Setting up SABnzbd' in line:
            sabnzbd_start = i
            break

    if sabnzbd_start is None:
        print("⚠️ SABnzbd setup section NOT FOUND in logs!")
        print()
        print("This means SABnzbd setup was skipped.")
        print()
        print("Possible reasons:")
        print("  1. setup_ok was False (credentials not written)")
        print("  2. Working was False (dependency install failed)")
        print("  3. The code never reached SABnzbd setup section")
        print()
        print("Checking for error messages...")
        print()

        # Look for errors/warnings
        errors_found = False
        for line in lines:
            if any(word in line for word in ['ERROR', 'WARNING', 'Failed', 'failed']):
                print(line.strip())
                errors_found = True

        if not errors_found:
            print("No obvious errors found. Check full log:")
            print(f"  !cat {log_file}")
    else:
        print(f"✅ SABnzbd setup section found at line {sabnzbd_start + 1}")
        print()
        print("SABnzbd Setup Output:")
        print("-" * 70)

        # Print 100 lines from SABnzbd section (or until end)
        end_line = min(sabnzbd_start + 100, len(lines))
        for line in lines[sabnzbd_start:end_line]:
            print(line.rstrip())

        print()
        print("-" * 70)
        print()

        # Check for success/failure indicators
        sabnzbd_section = ''.join(lines[sabnzbd_start:end_line])

        if 'SABnzbd configured successfully' in sabnzbd_section:
            print("✅ SABnzbd configured successfully!")
        elif 'SABnzbd setup failed' in sabnzbd_section:
            print("❌ SABnzbd setup FAILED!")
            print()
            # Find the error message
            for line in lines[sabnzbd_start:end_line]:
                if 'SABnzbd setup failed:' in line:
                    print("Error message:")
                    print(f"  {line.strip()}")
        else:
            print("⚠️ SABnzbd setup status unclear - check logs above")

        print()
        print(f"Full log file: {log_file}")

    print()
    print("=" * 70)
