# ============================================================================
# ERROR LOGGER - Single Cell Version
# Copy-paste this entire cell into Colab and run it to start logging
# ============================================================================
import sys
import logging
from datetime import datetime
from pathlib import Path

# Create log file
timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = Path(f"/content/bot_error_log_{timestamp}.txt")

print("="*70)
print("📝 ERROR LOGGER ACTIVATED")
print(f"📁 Log file: {log_file}")
print("="*70)

# Capture class
class LogCapture:
    def __init__(self, original, log_path):
        self.original = original
        self.log_path = log_path
        # Initialize log file
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write(f"Bot Error Log - {datetime.now()}\n{'='*70}\n\n")

    def write(self, message):
        self.original.write(message)
        if message.strip():
            with open(self.log_path, 'a', encoding='utf-8') as f:
                f.write(message)

    def flush(self):
        self.original.flush()

# Redirect output
sys.stdout = LogCapture(sys.stdout, log_file)
sys.stderr = LogCapture(sys.stderr, log_file)

# Also capture Python logging
file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
logging.root.addHandler(file_handler)
logging.root.setLevel(logging.DEBUG)

print("✅ Now capturing all output and errors\n")

# Helper functions
def show_log(lines=50):
    """Show last N lines of log"""
    print(f"\n{'='*70}\n📋 LOG (last {lines} lines)\n{'='*70}")
    with open(log_file, 'r') as f:
        content = f.readlines()
        print(''.join(content[-lines:]))
    print(f"{'='*70}\n📁 {log_file}\n{'='*70}")

def download_log():
    """Download log file"""
    try:
        from google.colab import files
        files.download(str(log_file))
        print(f"✅ Downloading: {log_file.name}")
    except:
        print(f"📁 Log saved at: {log_file}")

def show_errors():
    """Show only error lines"""
    print(f"\n{'='*70}\n🔴 ERRORS ONLY\n{'='*70}")
    with open(log_file, 'r') as f:
        errors = [line for line in f if 'ERROR' in line or 'Error' in line or 'failed' in line.lower()]
        print(''.join(errors[-30:]))  # Last 30 errors
    print(f"{'='*70}\n📁 {log_file}\n{'='*70}")

# Print usage
print("📖 Usage:")
print("  show_log()       - View last 50 lines")
print("  show_log(100)    - View last 100 lines")
print("  show_errors()    - Show only error lines")
print("  download_log()   - Download log file")
print("="*70 + "\n")
