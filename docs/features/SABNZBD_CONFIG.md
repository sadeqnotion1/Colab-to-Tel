# SABnzbd Configuration Guide

## Quick Setup

The bot now **auto-detects** SABnzbd if it's running locally. No manual configuration needed!

### Option 1: Auto-Detection (Easiest)

1. **Install SABnzbd** on your machine: https://sabnzbd.org/downloads
2. **Start SABnzbd** (it will run on http://localhost:8080 by default)
3. **Start the bot**: `python -m colab_leecher`
4. **Done!** The bot will auto-detect SABnzbd and send you the URL in Telegram

### Option 2: Manual Configuration

If SABnzbd is running on a different host/port or you want to configure it explicitly:

1. **Add to credentials.json**:

```json
{
  "API_ID": "your_api_id",
  "API_HASH": "your_api_hash",
  ...

  "SABNZBD": {
    "host": "127.0.0.1",
    "port": 8080,
    "api_key": "your_sabnzbd_api_key"
  }
}
```

2. **Get your SABnzbd API key**:
   - Open SABnzbd web UI
   - Go to Config → General
   - Copy the API Key

3. **Start the bot**: `python -m colab_leecher`

## How It Works

### On Bot Startup:

```
Bot starts
   ↓
Check credentials.json for SABNZBD config
   ↓
Try to connect to SABnzbd
   ↓
If found:
   ✅ Configure bot to use SABnzbd
   ✅ Send URL to Telegram
   ✅ Use SABnzbd for /nzb downloads

If not found:
   ℹ️ Use custom NNTP downloader (fallback)
```

### Auto-Detection Attempts:

1. **credentials.json** - Manual config (if specified)
2. **localhost:8080** - Default SABnzbd port
3. **localhost:8085** - Alternative port
4. **localhost:9090** - Alternative port
5. **localhost:8888** - Alternative port

## Installation

### Windows

1. Download SABnzbd installer: https://sabnzbd.org/downloads
2. Install and run SABnzbd
3. Configure your Usenet provider in SABnzbd
4. Start the bot - it will auto-detect!

### Linux

```bash
sudo apt-get install sabnzbd
sudo systemctl start sabnzbd
```

### macOS

```bash
brew install sabnzbd
sabnzbd
```

## Telegram Notification

When SABnzbd is detected, you'll receive a message like:

```
🏠 SABnzbd Web UI Ready (Local Access)

🔗 URL: http://127.0.0.1:8080
🔑 API Key: abc123xyz...

⚠️ Local URL only - accessible from this machine only.
```

## Troubleshooting

### "SABnzbd not detected"

**Check if SABnzbd is running**:
```bash
curl http://localhost:8080/sabnzbd/api?mode=version
```

If you get a response, SABnzbd is running. If not:
- Make sure SABnzbd is started
- Check if it's running on a different port
- Add manual configuration to credentials.json

### "SABnzbd auto-detection failed"

Check the bot logs for the specific error. Common issues:
- SABnzbd not installed
- Wrong host/port
- Firewall blocking connection
- Missing API key (required for remote connections)

### Want to use custom NNTP downloader instead?

Just don't run SABnzbd! The bot will automatically fall back to the custom NNTP downloader.

## Features

### With SABnzbd:
✅ Reliable downloads
✅ Automatic PAR2 repair
✅ Automatic RAR extraction
✅ Multi-server support
✅ Smart retry logic
✅ Web UI for management

### Without SABnzbd (Fallback):
✅ Direct NNTP connection
✅ Basic retry logic
✅ Multi-server support
⚠️ No PAR2 repair
⚠️ No automatic RAR extraction

## Example credentials.json

```json
{
  "API_ID": 12345,
  "API_HASH": "abc123...",
  "BOT_TOKEN": "123:ABC...",
  "USER_ID": 12345678,
  "DUMP_ID": -1001234567890,

  "NZB_PROVIDERS": {
    "provider1": {
      "host": "news.provider.com",
      "port": 563,
      "username": "user",
      "password": "pass",
      "ssl": true,
      "connections": 30
    }
  },

  "SABNZBD": {
    "host": "127.0.0.1",
    "port": 8080,
    "api_key": "your_api_key_here"
  }
}
```

## Notes

- SABnzbd setup is **completely optional**
- Bot works fine without SABnzbd using custom downloader
- Auto-detection runs on every bot startup
- Notification is sent only once per bot session
- File `.sabnzbd_url.txt` is auto-deleted after sending

---

**Need help?** Check bot logs for detailed information about SABnzbd detection.
