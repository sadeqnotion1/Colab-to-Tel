"""
Enhanced Error Logger for Google Colab
========================================
Paste this cell at the TOP of your Colab notebook, BEFORE running the bot.

Features:
- Captures all errors, warnings, and logs
- Saves to timestamped file in /content/
- Auto-downloads log file when errors occur
- Provides real-time log viewing
- Tracks task reports and download failures
"""

# ============================================================================
# SETUP - Run this cell first
# ============================================================================
import sys
import logging
import traceback
from datetime import datetime
from pathlib import Path
import re

# Configuration
LOG_LEVEL = logging.DEBUG  # Change to logging.INFO for less verbose output
SAVE_TO_DRIVE = False  # Set True to also save to Google Drive

# Create log file with timestamp
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_filename = f"bot_error_log_{timestamp}.txt"
log_path = Path("/content") / log_filename

print("="*80)
print("🔧 ENHANCED ERROR LOGGER INITIALIZED")
print("="*80)
print(f"📁 Log file: {log_path}")
print(f"📊 Log level: {logging.getLevelName(LOG_LEVEL)}")
print(f"💾 Auto-download on error: Enabled")
print("="*80 + "\n")

# ============================================================================
# Custom Handler - Captures everything
# ============================================================================
class ColabLogHandler(logging.Handler):
    """Custom handler that saves logs and tracks errors"""

    def __init__(self, log_file):
        super().__init__()
        self.log_file = log_file
        self.error_count = 0
        self.warning_count = 0
        self.task_failures = []

        # Create/clear log file
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write(f"Bot Error Log - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("="*80 + "\n\n")

    def emit(self, record):
        try:
            msg = self.format(record)

            # Track statistics
            if record.levelno >= logging.ERROR:
                self.error_count += 1
            elif record.levelno >= logging.WARNING:
                self.warning_count += 1

            # Detect task failures
            if "failed" in msg.lower() or "error" in msg.lower():
                if any(x in msg.lower() for x in ["terabox", "youtube", "aria2", "download"]):
                    self.task_failures.append(msg)

            # Write to file
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')

                # Add traceback for errors
                if record.exc_info:
                    f.write(''.join(traceback.format_exception(*record.exc_info)))
                    f.write('\n')

        except Exception as e:
            print(f"⚠️ Error in log handler: {e}")

# ============================================================================
# Output Capture - Redirects stdout/stderr
# ============================================================================
class TeeOutput:
    """Captures output while still displaying it"""

    def __init__(self, original, log_file, prefix=""):
        self.original = original
        self.log_file = log_file
        self.prefix = prefix

    def write(self, message):
        # Display to console
        self.original.write(message)

        # Save to file
        if message.strip():
            with open(self.log_file, 'a', encoding='utf-8') as f:
                if self.prefix:
                    f.write(f"[{self.prefix}] {message}")
                else:
                    f.write(message)

    def flush(self):
        self.original.flush()

# ============================================================================
# Initialize Logging System
# ============================================================================
# Create handler
handler = ColabLogHandler(log_path)
handler.setLevel(LOG_LEVEL)
formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%H:%M:%S'
)
handler.setFormatter(formatter)

# Add to root logger
root_logger = logging.getLogger()
root_logger.setLevel(LOG_LEVEL)
root_logger.addHandler(handler)

# Redirect stdout/stderr
original_stdout = sys.stdout
original_stderr = sys.stderr
sys.stdout = TeeOutput(original_stdout, log_path, "STDOUT")
sys.stderr = TeeOutput(original_stderr, log_path, "STDERR")

print("✅ Logging system active - all output is being captured")
print("="*80 + "\n")

# ============================================================================
# Helper Functions
# ============================================================================
def show_log(lines=50, filter_level=None):
    """
    Display the current log

    Args:
        lines: Number of lines to show (default: 50, use None for all)
        filter_level: Only show specific level ('ERROR', 'WARNING', etc.)
    """
    print("\n" + "="*80)
    print("📋 CURRENT ERROR LOG")
    print("="*80)

    try:
        with open(log_path, 'r', encoding='utf-8') as f:
            content = f.readlines()

        # Filter by level if specified
        if filter_level:
            content = [line for line in content if filter_level.upper() in line]

        # Show last N lines
        if lines:
            content = content[-lines:]

        print(''.join(content))

        print("="*80)
        print(f"📊 Stats: {handler.error_count} errors, {handler.warning_count} warnings")
        print(f"📁 Full log: {log_path}")
        print("="*80)

    except Exception as e:
        print(f"❌ Could not read log: {e}")

def show_errors_only():
    """Show only ERROR level messages"""
    show_log(lines=None, filter_level='ERROR')

def show_warnings_only():
    """Show only WARNING level messages"""
    show_log(lines=None, filter_level='WARNING')

def download_log():
    """Download the log file (Colab only)"""
    try:
        from google.colab import files
        print(f"📥 Downloading log file: {log_filename}")
        files.download(str(log_path))
        print("✅ Download started!")
    except ImportError:
        print("⚠️ Not running in Colab - cannot auto-download")
        print(f"📁 Log saved at: {log_path}")

def save_to_drive():
    """Save log to Google Drive"""
    try:
        from google.colab import drive
        drive_path = Path("/content/drive/MyDrive/bot_logs")
        drive_path.mkdir(parents=True, exist_ok=True)

        import shutil
        dest = drive_path / log_filename
        shutil.copy2(log_path, dest)

        print(f"✅ Log saved to Drive: {dest}")
        return dest
    except Exception as e:
        print(f"❌ Could not save to Drive: {e}")

def get_summary():
    """Get a summary of errors and warnings"""
    print("\n" + "="*80)
    print("📊 LOG SUMMARY")
    print("="*80)
    print(f"Total Errors: {handler.error_count}")
    print(f"Total Warnings: {handler.warning_count}")
    print(f"Task Failures Detected: {len(handler.task_failures)}")

    if handler.task_failures:
        print("\n🔴 Recent Task Failures:")
        for i, failure in enumerate(handler.task_failures[-5:], 1):
            # Extract just the relevant part
            short_msg = failure[:100] + "..." if len(failure) > 100 else failure
            print(f"  {i}. {short_msg}")

    print("="*80)

def auto_download_on_error():
    """Auto-download if errors detected"""
    if handler.error_count > 0:
        print(f"\n⚠️ Detected {handler.error_count} errors - auto-downloading log...")
        download_log()

# Register auto-download on exit
import atexit
atexit.register(auto_download_on_error)

# ============================================================================
# Usage Instructions
# ============================================================================
print("📖 USAGE:")
print("  show_log()              - View last 50 lines")
print("  show_log(lines=100)     - View last 100 lines")
print("  show_errors_only()      - View only errors")
print("  show_warnings_only()    - View only warnings")
print("  download_log()          - Download log file")
print("  get_summary()           - Show error summary")
print("")
print("💡 Log will auto-download if errors occur")
print("="*80 + "\n")

# Log start of session
logging.info("="*80)
logging.info("BOT SESSION STARTED")
logging.info("="*80)
