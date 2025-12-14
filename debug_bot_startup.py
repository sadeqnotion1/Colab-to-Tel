"""
Debug script for bot startup - Use this in Colab to capture detailed error logs
Add this as a new cell in your Colab notebook
"""

import sys
import traceback
from datetime import datetime
import logging

# Set up detailed logging
log_filename = f"/content/bot_startup_debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

# Create file handler for all logs
file_handler = logging.FileHandler(log_filename, mode='w')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# Add to root logger
logging.root.addHandler(file_handler)
logging.root.setLevel(logging.DEBUG)

print(f"📝 Logging all output to: {log_filename}")
print("="*70)

try:
    print("🔄 Attempting to import and start bot...")

    # Import the bot
    from colab_leecher import colab_bot
    from colab_leecher.__main__ import main

    print("✅ Bot imported successfully")
    print(f"Bot object: {colab_bot}")

    # Try to start
    print("🚀 Starting bot main()...")
    main()

except FileNotFoundError as e:
    error_msg = f"❌ FileNotFoundError: {e}"
    print(error_msg)
    print(f"\n📋 Full traceback:\n{traceback.format_exc()}")

    # Check if credentials file exists
    import os
    cred_path = "/content/Telegram-Leecher/credentials.json"
    print(f"\n🔍 Checking credentials file: {cred_path}")
    print(f"   Exists: {os.path.exists(cred_path)}")

    if os.path.exists(cred_path):
        print(f"   Size: {os.path.getsize(cred_path)} bytes")
        try:
            with open(cred_path, 'r') as f:
                print(f"   First 200 chars: {f.read(200)}")
        except Exception as read_err:
            print(f"   Could not read: {read_err}")

except json.JSONDecodeError as e:
    error_msg = f"❌ JSON Parse Error: {e}"
    print(error_msg)
    print(f"\n📋 Full traceback:\n{traceback.format_exc()}")

    # Try to read and show the credentials file
    try:
        with open("/content/Telegram-Leecher/credentials.json", 'r') as f:
            content = f.read()
            print(f"\n📄 credentials.json content:\n{content}")
    except Exception as read_err:
        print(f"Could not read credentials.json: {read_err}")

except SystemExit as e:
    error_msg = f"❌ SystemExit: {e}"
    print(error_msg)
    print(f"\n📋 Full traceback:\n{traceback.format_exc()}")

except Exception as e:
    error_msg = f"❌ Unexpected Error: {type(e).__name__}: {e}"
    print(error_msg)
    print(f"\n📋 Full traceback:\n{traceback.format_exc()}")

finally:
    # Save and display the log
    print("\n" + "="*70)
    print(f"📊 Log saved to: {log_filename}")

    try:
        with open(log_filename, 'r') as f:
            log_content = f.read()
            print("\n📋 Full Log Contents:\n")
            print(log_content)
    except Exception as e:
        print(f"Could not read log file: {e}")
