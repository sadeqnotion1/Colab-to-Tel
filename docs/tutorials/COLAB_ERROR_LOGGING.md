# Error Logging in Google Colab

This guide shows how to capture all bot errors and logs in Google Colab.

## 📋 Quick Start

### Cell 1: Setup Error Logger (Run FIRST)

```python
# ============================================================================
# ERROR LOGGER CELL - Run this FIRST, before the bot setup
# ============================================================================
!wget -q https://raw.githubusercontent.com/theSadeQ/Colab-to-Tel/master/colab_leecher/colab/cells/error_logger_enhanced.py
%run error_logger_enhanced.py
```

**OR** paste the content of `error_logger_enhanced.py` directly into this cell.

### Cell 2: Run Your Bot Normally

```python
# Your normal bot setup cell
!git clone https://github.com/theSadeQ/Colab-to-Tel.git
%cd Colab-to-Tel
!pip install -r requirements.txt
# ... rest of your setup
```

### Cell 3: View Logs Anytime

```python
# View last 50 lines of log
show_log()

# View only errors
show_errors_only()

# View summary
get_summary()

# Download log file
download_log()
```

## 🎯 Features

### Auto-Capture Everything
- ✅ All Python logging output
- ✅ stdout/stderr (print statements, errors)
- ✅ Tracebacks and exceptions
- ✅ Task reports and download failures

### Smart Detection
- Tracks error counts
- Detects TeraBox/YouTube/aria2 failures
- Highlights task failures in red

### Easy Download
- Auto-downloads if errors occur
- Manual download with `download_log()`
- Optional Google Drive backup

## 📖 Usage Examples

### Example 1: Quick Error Check
```python
# After bot runs, check for errors
get_summary()
```

Output:
```
📊 LOG SUMMARY
================================================================================
Total Errors: 2
Total Warnings: 5
Task Failures Detected: 2

🔴 Recent Task Failures:
  1. TeraBox download failed: name 'log' is not defined
  2. Aria2 success code 0 but expected output file invalid/missing/empty
================================================================================
```

### Example 2: View Recent Errors
```python
# Show only error messages
show_errors_only()
```

### Example 3: Download Full Log
```python
# Download to your computer
download_log()
```

### Example 4: Save to Google Drive
```python
# Mount Drive first
from google.colab import drive
drive.mount('/content/drive')

# Save log
save_to_drive()
```

## 🔧 Configuration

At the top of `error_logger_enhanced.py`, you can customize:

```python
# Configuration
LOG_LEVEL = logging.DEBUG  # Change to INFO for less verbose
SAVE_TO_DRIVE = False      # Auto-save to Drive
```

**Log Levels:**
- `logging.DEBUG` - Everything (very verbose)
- `logging.INFO` - General info + warnings + errors
- `logging.WARNING` - Only warnings + errors
- `logging.ERROR` - Only errors

## 📂 Log File Format

Logs are saved with timestamps:
```
bot_error_log_20251224_145230.txt
```

**Format:**
```
Bot Error Log - 2024-12-24 14:52:30
================================================================================

14:52:35 | INFO     | root | Bot session started
14:52:40 | ERROR    | terabox | name 'log' is not defined
14:52:40 | ERROR    | aria2 | File not found: expected_filename
```

## 🚨 Common Issues

### Issue 1: Log not showing everything
**Solution:** Make sure you run the error logger cell BEFORE the bot setup cell.

### Issue 2: Download not working
**Solution:** Only works in Google Colab. Locally, check `/content/bot_error_log_*.txt`

### Issue 3: Too verbose
**Solution:** Change `LOG_LEVEL = logging.INFO` in the configuration.

## 💡 Tips

1. **Run logger first** - Always run the error logger cell before starting the bot
2. **Check summary** - Run `get_summary()` to quickly see if there were issues
3. **Download immediately** - If you see errors, run `download_log()` before the session ends
4. **Save to Drive** - For long-running sessions, use `save_to_drive()` periodically

## 🔗 Related Files

- `colab_leecher/colab/cells/error_logger_enhanced.py` - Main logger
- `colab_leecher/colab/cells/error_logger.py` - Simple version
- `colab_leecher/colab/cells/main_setup.py` - Bot setup cell

## 📞 Troubleshooting

If logging isn't working:

```python
# Check if logger is active
import sys
print(type(sys.stdout))  # Should show TeeOutput

# Check log file exists
!ls -lh /content/bot_error_log_*.txt

# View raw file
!cat /content/bot_error_log_*.txt
```
