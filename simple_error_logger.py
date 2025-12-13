"""
SIMPLE Error Logger - Paste this BEFORE your bot setup cell
Captures everything to a file
"""

import sys
from datetime import datetime

# Create log file
log_file = f"/content/bot_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

# Simple file writer
class LogWriter:
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, 'a', encoding='utf-8')

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()

# Capture both stdout and stderr
sys.stdout = LogWriter(log_file)
sys.stderr = LogWriter(log_file)

print("="*70)
print(f"📝 Logging to: {log_file}")
print("="*70)
print("\n✅ All output will be saved. Run your bot setup cell now.\n")

# Function to view log
def view_log():
    print("\n" + "="*70)
    print("📋 LOG CONTENTS")
    print("="*70)
    with open(log_file, 'r') as f:
        print(f.read())
    print("="*70)

print("💡 Run view_log() to display the saved log anytime\n")
