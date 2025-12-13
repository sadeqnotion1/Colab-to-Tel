"""
Error Logger Cell for Colab - Captures all bot logs and errors
Run this cell BEFORE running the bot setup cell to capture all output
"""

import sys
import logging
import traceback
from datetime import datetime
from io import StringIO
import contextlib

# Create timestamped log file
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = f"/content/bot_error_log_{timestamp}.txt"

print(f"📝 Error logging initialized")
print(f"📁 Log file: {log_file}")
print("="*70)

# Create a custom handler that writes to both file and console
class DualOutputHandler(logging.Handler):
    def __init__(self, filename):
        super().__init__()
        self.terminal = sys.stdout
        self.log_file = open(filename, 'w', encoding='utf-8')

    def emit(self, record):
        msg = self.format(record)
        self.log_file.write(msg + '\n')
        self.log_file.flush()

    def close(self):
        self.log_file.close()
        super().close()

# Set up dual logging
file_handler = DualOutputHandler(log_file)
file_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add to root logger
logging.root.addHandler(file_handler)
logging.root.setLevel(logging.DEBUG)

# Also capture stdout and stderr
class TeeOutput:
    def __init__(self, name, file_handler):
        self.name = name
        self.terminal = getattr(sys, name)
        self.log_file = file_handler.log_file

    def write(self, message):
        if message.strip():  # Only write non-empty messages
            self.terminal.write(message)
            self.log_file.write(f"[{self.name.upper()}] {message}")
            self.log_file.flush()

    def flush(self):
        self.terminal.flush()
        self.log_file.flush()

# Redirect stdout and stderr
sys.stdout = TeeOutput('stdout', file_handler)
sys.stderr = TeeOutput('stderr', file_handler)

print("✅ Error logging active - all output will be saved to log file")
print("="*70)

# Function to display log when done
def show_error_log():
    """Call this function to display the saved log"""
    print("\n" + "="*70)
    print("📋 DISPLAYING ERROR LOG")
    print("="*70)
    try:
        with open(log_file, 'r') as f:
            content = f.read()
            print(content)
        print("="*70)
        print(f"✅ Log saved to: {log_file}")
        print("="*70)
    except Exception as e:
        print(f"❌ Could not read log: {e}")

# Auto-display helper
def auto_display_on_error():
    """Automatically show log if there's an error"""
    if sys.exc_info()[0] is not None:
        show_error_log()

# Register cleanup
import atexit
atexit.register(show_error_log)

print("💡 Run show_error_log() anytime to display the current log")
print("💡 Log will automatically display when kernel stops")
print("="*70 + "\n")
