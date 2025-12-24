"""
CAPTURE EXISTING LOGS - Run this AFTER an error to capture what went wrong
Use when you forgot to enable logging before running the bot
"""

import logging
import sys
import traceback
from datetime import datetime

log_file = f"/content/error_capture_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

print("="*70)
print("🔍 Capturing Existing Error Information")
print("="*70)

with open(log_file, 'w') as f:
    f.write(f"Error Capture - {datetime.now()}\n")
    f.write("="*70 + "\n\n")

    # 1. Check if there's an active exception
    f.write("1️⃣ Checking for active exception...\n")
    exc_info = sys.exc_info()
    if exc_info[0] is not None:
        f.write("✅ Found active exception:\n")
        f.write(f"   Type: {exc_info[0].__name__}\n")
        f.write(f"   Message: {exc_info[1]}\n\n")
        f.write("Traceback:\n")
        traceback.print_exception(*exc_info, file=f)
        f.write("\n" + "="*70 + "\n\n")
    else:
        f.write("❌ No active exception found\n\n")

    # 2. Capture all logger states
    f.write("2️⃣ Capturing logger information...\n")
    for logger_name in sorted(logging.root.manager.loggerDict):
        logger = logging.getLogger(logger_name)
        if logger.handlers or logger.level != 0:
            f.write(f"\nLogger: {logger_name}\n")
            f.write(f"  Level: {logging.getLevelName(logger.level)}\n")
            f.write(f"  Handlers: {len(logger.handlers)}\n")
            for i, handler in enumerate(logger.handlers):
                f.write(f"    Handler {i}: {type(handler).__name__}\n")

    f.write("\n" + "="*70 + "\n\n")

    # 3. Check for common bot files/logs
    f.write("3️⃣ Checking for existing log files...\n")
    import os
    import glob

    log_patterns = [
        '/content/*.log',
        '/content/*log*.txt',
        '/content/Telegram-Leecher/*.log',
        '/content/Telegram-Leecher/*.session',
    ]

    found_files = []
    for pattern in log_patterns:
        found_files.extend(glob.glob(pattern))

    if found_files:
        f.write(f"Found {len(found_files)} potential log/session files:\n")
        for file_path in found_files:
            f.write(f"\n📄 {file_path}\n")
            try:
                size = os.path.getsize(file_path)
                f.write(f"   Size: {size} bytes\n")
                if size > 0 and size < 100000 and file_path.endswith(('.log', '.txt')):
                    f.write(f"   Contents (first 1000 chars):\n")
                    with open(file_path, 'r') as lf:
                        f.write(lf.read(1000))
                    f.write("\n")
            except Exception as e:
                f.write(f"   Error reading: {e}\n")
    else:
        f.write("No log files found\n")

    f.write("\n" + "="*70 + "\n\n")

    # 4. Check bot process status
    f.write("4️⃣ Checking for bot processes...\n")
    try:
        import subprocess
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        bot_processes = [line for line in result.stdout.split('\n') if 'python' in line.lower() and ('bot' in line.lower() or 'colab_leecher' in line.lower())]
        if bot_processes:
            f.write("Found bot-related processes:\n")
            for proc in bot_processes:
                f.write(f"  {proc}\n")
        else:
            f.write("No active bot processes found\n")
    except Exception as e:
        f.write(f"Could not check processes: {e}\n")

    f.write("\n" + "="*70 + "\n")

print(f"\n✅ Error information captured to: {log_file}\n")

# Display the log
print("="*70)
print("📋 CAPTURED ERROR INFORMATION")
print("="*70)
with open(log_file, 'r') as f:
    print(f.read())
print("="*70)
print(f"\n💾 Full log saved to: {log_file}\n")
