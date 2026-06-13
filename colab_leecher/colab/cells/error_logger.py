"""
Error Logger Cell for Colab - Captures all bot logs and errors
Run this cell BEFORE running the bot setup cell to capture all output

Two modes available:
1. SIMPLE mode (simple=True): Basic stdout/stderr capture
2. FULL mode (simple=False, default): Advanced logging with handlers
"""

import sys
import logging
import traceback
from datetime import datetime
from io import StringIO
import contextlib

# ============================================================================
# Configuration
# ============================================================================
SIMPLE_MODE = False  # Set to True for simple logging, False for advanced

# Create timestamped log file
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = f"/content/bot_error_log_{timestamp}.txt"

print(f"📝 Error logging initialized ({'SIMPLE' if SIMPLE_MODE else 'FULL'} mode)")
print(f"📁 Log file: {log_file}")
print("="*70)

# ============================================================================
# SIMPLE MODE - Basic stdout/stderr capture
# ============================================================================
class SimpleLogWriter:
    """Simple file writer that captures stdout/stderr"""
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, 'a', encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()

# ============================================================================
# FULL MODE - Advanced logging with handlers
# ============================================================================
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

# ============================================================================
# Activate chosen mode
# ============================================================================
if SIMPLE_MODE:
    # Simple mode: Just capture stdout and stderr
    sys.stdout = SimpleLogWriter(log_file)
    sys.stderr = SimpleLogWriter(log_file)
    print("✅ Simple logging active - all output will be saved to log file")
    print("="*70)
else:
    # Full mode: Advanced logging with handlers
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

    print("✅ Advanced logging active - all output will be saved to log file")
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
