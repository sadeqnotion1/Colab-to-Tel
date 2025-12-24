# SABnzbd Integration for NZB Downloads

## Overview

This bot now supports **two methods** for downloading NZB files:

1. **SABnzbd Backend** (Recommended) - Uses mature, production-ready SABnzbd software
2. **Custom NNTP Downloader** (Fallback) - Direct NNTP implementation

The bot automatically uses SABnzbd if it's configured, otherwise falls back to the custom downloader.

## Why SABnzbd?

✅ **Production-ready** - Used by millions of users worldwide
✅ **Handles all NNTP edge cases** - No more 412/423 errors
✅ **Built-in PAR2 repair** - Automatically repairs damaged files
✅ **Smart retry logic** - Handles failed articles intelligently
✅ **Multi-provider support** - Seamless fallback between providers
✅ **Progress tracking** - Real-time download progress in Telegram

## Setup Instructions

### For Google Colab

#### Step 1: Clone and Install Bot

```python
# Clone repository
!git clone -b feature/multi-task-parallel https://github.com/theSadeQ/Telegram-Leecher.git
%cd Telegram-Leecher

# Install dependencies
!pip install -r requirements.txt
```

#### Step 2: Configure credentials.json

Create `/content/Telegram-Leecher/credentials.json`:

```json
{
  "API_ID": "your_api_id",
  "API_HASH": "your_api_hash",
  "BOT_TOKEN": "your_bot_token",
  "USER_ID": your_user_id,
  "DUMP_ID": your_dump_id,
  "NZB_PROVIDERS": {
    "sunnyusenet": {
      "host": "news.sunnyusenet.com",
      "port": 563,
      "username": "your_username",
      "password": "your_password",
      "ssl": true,
      "connections": 20
    },
    "giganews": {
      "host": "news.giganews.com",
      "port": 563,
      "username": "your_username",
      "password": "your_password",
      "ssl": true,
      "connections": 30
    }
  },
  "NZB_DEFAULT_PROVIDER": "sunnyusenet"
}
```

#### Step 3: Set Up SABnzbd

```python
# Run SABnzbd setup
%run colab_sabnzbd_setup.py
```

This will:
- Install SABnzbd and dependencies (par2, unrar, p7zip)
- Configure SABnzbd with your Usenet providers
- Start SABnzbd daemon
- Generate API key
- Configure the bot to use SABnzbd

#### Step 4: Start the Bot

```python
# Start the bot
!python -m colab_leecher
```

#### Step 5: Use /nzb Command

1. Send `/nzb` to your bot
2. Upload a `.nzb` file
3. SABnzbd will download it automatically
4. Bot will upload files to Telegram when complete

## Architecture

```
┌─────────────────┐
│  Telegram Bot   │
│   (Frontend)    │
└────────┬────────┘
         │
         ├──> SABnzbd Available?
         │         │
         │    ┌────┴─────┐
         │   YES         NO
         │    │           │
         v    v           v
    ┌────────────┐   ┌────────────┐
    │  SABnzbd   │   │   Custom   │
    │  Backend   │   │    NNTP    │
    │(Preferred) │   │ (Fallback) │
    └─────┬──────┘   └──────┬─────┘
          │                 │
          v                 v
    ┌─────────────────────────┐
    │   Usenet Servers        │
    │ (news.provider.com)     │
    └─────────────────────────┘
```

## Features

### Progress Tracking

The bot shows real-time download progress in Telegram:

```
📦 NZB Download (SABnzbd) »

📄 File » your_file.mkv

╭「████████░░░░」 » 66.7%
├⚡️ Speed » 25.3 MB/s
├⚙️ Engine » SABnzbd
├⏳ ETA » 2m 15s
├⏱️ Elapsed » 4m 30s
├✅ Done » Downloading... 66.7%
╰📦 Total » 1.5 GB
```

### Multi-Provider Support

SABnzbd automatically:
- Distributes connections across all providers
- Falls back to alternate providers for missing articles
- Handles server errors gracefully

### Automatic File Handling

After download completes:
- ✅ PAR2 repair (if needed)
- ✅ Unrar archives automatically
- ✅ Upload to Telegram
- ✅ Clean up temp files

## File Structure

```
colab_leecher/
├── utility/
│   ├── sabnzbd_setup.py       # SABnzbd installation & config
│   └── sabnzbd_client.py       # SABnzbd API wrapper
├── downlader/
│   ├── sabnzbd_downloader.py  # SABnzbd-based NZB downloader
│   └── nzb.py                  # Custom NNTP downloader (fallback)
└── __main__.py                 # Main bot (uses SABnzbd if available)

colab_sabnzbd_setup.py          # Colab setup cell
```

## Configuration

### SABnzbd Settings

Default configuration:
- **Host**: 127.0.0.1
- **Port**: 8080
- **Download Dir**: `/content/Telegram-Leecher/BOT_WORK/Downloads`
- **Auto-generated API key**

### Provider Configuration

Providers are automatically configured from `credentials.json`:
- All providers with valid `host` field are added
- Connections are distributed across providers
- Providers with `connections: 0` are skipped

## Troubleshooting

### SABnzbd Not Starting

Check logs for errors:
```python
!cat /content/sabnzbd/config/sabnzbd.log
```

### Download Stuck

Check SABnzbd queue:
```python
from colab_leecher.utility.sabnzbd_client import SABnzbdClient
client = SABnzbdClient(api_key="your_api_key")
print(client.get_queue())
```

### Fallback to Custom Downloader

If SABnzbd isn't configured, the bot automatically uses the custom NNTP downloader. Check logs:
```
INFO - Using custom NNTP downloader (SABnzbd not configured)
```

## Comparison

| Feature | SABnzbd Backend | Custom NNTP |
|---------|----------------|-------------|
| **Reliability** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **Error Handling** | Automatic retry, smart fallback | Basic retry |
| **PAR2 Repair** | ✅ Built-in | ❌ No |
| **Unrar** | ✅ Automatic | ❌ Manual |
| **Multi-Provider** | ✅ Seamless | ✅ Basic |
| **Setup Complexity** | Medium (requires setup) | Low (works out-of-box) |
| **Performance** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |

## Benefits of Hybrid Approach

1. **Flexibility**: Use SABnzbd in Colab, custom downloader locally
2. **No Breaking Changes**: Existing functionality preserved
3. **Automatic Selection**: Bot chooses best available method
4. **Easy Migration**: Can switch between methods anytime

## Advanced Usage

### Manual SABnzbd Access

Get API info:
```python
from colab_leecher.downlader.sabnzbd_downloader import get_sabnzbd_config
config = get_sabnzbd_config()
print(f"API URL: {config['base_url']}")
print(f"API Key: {config['api_key']}")
```

### Submit NZB Directly

```python
from colab_leecher.utility.sabnzbd_client import SABnzbdClient

client = SABnzbdClient(api_key="your_api_key")
success, nzo_id = client.add_nzb_file("/path/to/file.nzb")
print(f"Download ID: {nzo_id}")
```

### Monitor Progress

```python
status = client.get_download_status(nzo_id)
print(f"Progress: {status['percentage']}%")
print(f"Speed: {status['speed']}")
print(f"ETA: {status['eta']}")
```

## Credits

- **SABnzbd**: https://sabnzbd.org/
- **Integration**: Built for Telegram-Leecher bot

## Support

For issues:
1. Check SABnzbd logs
2. Verify Usenet provider credentials
3. Test with a small NZB first
4. Report issues on GitHub

---

**Happy downloading! 🚀**
