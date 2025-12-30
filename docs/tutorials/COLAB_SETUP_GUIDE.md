# Google Colab Setup Guide

Complete guide to running Telegram Leecher Bot in Google Colab.

## 🚀 Quick Start

### 1. Open Google Colab
Go to: https://colab.research.google.com/

### 2. Create New Notebook
Click: **File** → **New notebook**

### 3. Paste Setup Cell
Copy the entire content of `MAIN_SETUP_COMPLETE.py` into the first cell.

### 4. Configure Settings
In the form fields at the top, set:
- ✅ **USE_PUBLIC_REPO** = True (recommended)
- Select your **BOT_SELECTION**
- Select your **Dump_SELECTION**

### 5. Run the Cell
Click the ▶️ play button or press `Ctrl+Enter`

## 📋 Configuration Options

### Repository Settings

**Option 1: Public Repository (Recommended)**
```python
USE_PUBLIC_REPO = True  # Uses github.com/theSadeQ/Colab-to-Tel
GITHUB_TOKEN = ""       # Leave empty
```

**Option 2: Private Repository**
```python
USE_PUBLIC_REPO = False  # Uses private Telegram-Leecher repo
GITHUB_TOKEN = "ghp_..."  # Required! Get from github.com/settings/tokens
```

### Bot Credentials

Your credentials are already configured in the cell:
- `API_ID` and `API_HASH` - Telegram API credentials
- `BOT_TOKEN` - Selected from dropdown
- `USER_ID` - Your Telegram user ID
- `DUMP_ID` - Selected from dropdown

### Optional Cookies

For specialized downloaders:
- `NZBCLOUD_CF_CLEARANCE` - NZBCloud Cloudflare bypass
- `BITSO_IDENTITY_COOKIE` - Bitso downloader
- `BITSO_PHPSESSID_COOKIE` - Bitso session

## 🔧 Troubleshooting

### Error: "Git clone failed: could not read Username"

**Cause:** Trying to clone a private repository without authentication.

**Solution 1 (Recommended):**
```python
USE_PUBLIC_REPO = True
```

**Solution 2:**
Get a GitHub token:
1. Go to https://github.com/settings/tokens
2. Click "Generate new token (classic)"
3. Check `repo` scope
4. Copy token and paste in `GITHUB_TOKEN` field

### Error: "pip install failed"

**Cause:** Network issues or package conflicts.

**Solution:**
1. Runtime → Restart runtime
2. Run the cell again
3. If persists, check the error details in the log

### Error: "Bot startup error"

**Cause:** Missing or invalid credentials.

**Solution:**
1. Check all credentials are filled
2. Verify BOT_TOKEN is valid
3. Ensure DUMP_ID has `-100` prefix

### Bot Disconnects After Some Time

**Cause:** Colab idle timeout.

**Solution:**
The cell includes auto-play silent audio to keep session alive.
If it still disconnects:
1. Keep the Colab tab open
2. Interact with the page occasionally
3. Use Colab Pro for longer runtimes

## 📊 Monitoring

### View Logs in Real-Time

The setup cell shows real-time progress:
```
📦 Installing system packages...
✅ System packages installed
🐍 Installing Python dependencies...
✅ Python packages installed
🚀 STARTING BOT...
```

### Check Bot Status

After bot starts, you'll see:
```
Bot is alive...
Waiting for downloads...
```

### Download Error Logs

If you set up the error logger (separate cell), use:
```python
show_log()        # View recent logs
show_errors()     # View only errors
download_log()    # Download log file
```

## 🎯 Best Practices

### 1. Use Public Repo
Always set `USE_PUBLIC_REPO = True` unless you specifically need private features.

### 2. Keep Session Alive
Don't close the Colab tab while bot is running.

### 3. Monitor Resources
Check Colab RAM/Disk usage:
```python
!df -h /content      # Check disk space
!free -h             # Check RAM
```

### 4. Regular Restarts
For long sessions, restart runtime every few hours:
- Runtime → Restart runtime
- Re-run setup cell

### 5. Save Important Files
Download completed files before session ends:
```python
from google.colab import files
files.download('/content/downloaded_file.mp4')
```

## 🔗 Links

- **Public Repository:** https://github.com/theSadeQ/Colab-to-Tel
- **GitHub Tokens:** https://github.com/settings/tokens
- **Colab:** https://colab.research.google.com/

## 📞 Support

If you encounter issues:
1. Check the error logs
2. Verify all credentials are correct
3. Try restarting the runtime
4. Check GitHub repository for updates

## ⚙️ Advanced Options

### Custom Repository Branch

Edit in the cell:
```python
branch_name = "master"  # Change to your branch
```

### Custom Installation

Add custom packages after line with pip install:
```python
log.info("Installing custom package...")
subprocess.run("pip install custom-package", shell=True)
```

### Mount Google Drive

Add this before the bot starts:
```python
from google.colab import drive
drive.mount('/content/drive')
```
