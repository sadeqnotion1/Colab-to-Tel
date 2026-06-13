# Telegram-Leecher

A powerful Telegram bot for downloading and uploading files from various sources, designed to run on Google Colab.

## Features

- **Multiple Download Sources**
  - Direct HTTP/HTTPS links
  - Magnet links & Torrents
  - Telegram files
  - Mega.nz
  - Google Drive
  - YouTube & YouTube-DL supported sites
  - Terabox
  - **Mindvalley Courses** (M3U8 streams)
  - Debrid services
  - NZB files

- **Upload Options**
  - Upload to Telegram (Leech)
  - Mirror to Google Drive
  - Upload from local Colab directory

- **File Processing**
  - Normal upload
  - Compress to ZIP
  - Extract archives
  - Custom filenames
  - Thumbnail support
  - Password-protected archives

## Quick Start (Google Colab)

1. Open the provided Colab notebook: `COtoTEL_v1_00_02_U1.ipynb`
2. Fill in your Telegram API credentials in the form
3. Select your bot from the dropdown
4. Run the setup cell - it will:
   - Clone the repository
   - Install dependencies (ffmpeg, aria2, N_m3u8DL-RE)
   - Set up the bot
   - Start automatically

5. Send `/start` to your bot on Telegram to begin!

## Manual Colab YTDL Script (`ytdl.py`)

As a lightweight alternative to running the full Telegram bot listener, you can run a single manual download/upload execution using the [ytdl.py](ytdl.py) script directly in a Google Colab cell.

### Quick Start (in a Google Colab cell)

1. Install the required dependencies:
   ```bash
   !pip install -q yt-dlp pyrogram tgcrypto
   ```

2. Run the script with your credentials and video URL:
   ```bash
   !API_ID="your_api_id" API_HASH="your_api_hash" BOT_TOKEN="your_bot_token" CHAT_ID="your_chat_or_channel_id" python ytdl.py "https://youtu.be/XXXXXXXX"
   ```

Or you can import it and run it inside a Python cell:
```python
import os
os.environ["API_ID"] = "your_api_id"
os.environ["API_HASH"] = "your_api_hash"
os.environ["BOT_TOKEN"] = "your_bot_token"
os.environ["CHAT_ID"] = "your_chat_or_channel_id"

from ytdl import download_and_upload
download_and_upload("https://youtu.be/XXXXXXXX")
```

> [!NOTE]
> * **API_ID** and **API_HASH**: Obtain these from [my.telegram.org](https://my.telegram.org) under API development tools.
> * **BOT_TOKEN**: Obtain this from [@BotFather](https://t.me/BotFather) on Telegram.
> * **CHAT_ID**: The destination chat or channel ID (e.g., `-1001234567890`) or username (e.g., `@mychannel`). The bot must be added to this chat/channel with appropriate send permissions.
> * **Action Secrets**: Any previously configured GitHub repository Action secrets are no longer used by the codebase since the GitHub Action workflow has been removed.

## Commands

### Download Commands

- `/tupload` - Leech files to Telegram
  - Supports: Direct links, Magnet, Mega, GDrive, Debrid, NZB, Bitso, Mindvalley
  - You'll be asked to select service type after command

- `/gdupload` - Mirror files to Google Drive
  - Same sources as tupload
  - Files uploaded to your connected GDrive

- `/ytupload` - Download from YouTube and other sites
  - Supports 1000+ sites via yt-dlp
  - Best quality by default

- `/drupload` - Upload from Colab directory
  - Upload files already in your Colab environment
  - Send folder path after command

- `/mindvalley <video_url> [audio_url] [subtitle_url]` - Download Mindvalley courses
  - Downloads M3U8 video streams
  - Automatically merges video + audio + subtitles
  - Uploads to dump channel

### Configuration Commands

- `/settings` - View and modify bot settings
- `/setname <name>` - Set custom filename
- `/zipaswd <password>` - Set ZIP password
- `/unzipaswd <password>` - Set unzip password
- `/help` - Show help message

## Mindvalley Course Downloader

### Overview

The Mindvalley downloader allows you to download video courses from Mindvalley using M3U8 stream URLs.

### Prerequisites

1. **Browser Extension** (for detecting streams)
   - Get it from: [MindvalleyDownloaderExtension](https://github.com/theSadeQ/MindvalleyDownloaderExtension)
   - Installation:
     1. Download/clone the extension repository
     2. Open Chrome/Edge: `chrome://extensions/`
     3. Enable "Developer mode"
     4. Click "Load unpacked"
     5. Select the extension folder
     6. Extension icon will appear in toolbar

2. **Dependencies** (auto-installed in Colab)
   - N_m3u8DL-RE (M3U8 downloader)
   - FFmpeg (video/audio merger)
   - Both are installed automatically when running the Colab notebook

### How to Use

#### Step 1: Detect Streams with Browser Extension

1. Install the browser extension (see above)
2. Go to Mindvalley and open a course
3. Start playing a video lesson
4. The extension will automatically detect M3U8 streams
5. Click the extension icon to see detected streams
6. Copy the M3U8 URLs you need:
   - Video URL (required)
   - Audio URL (if separate)
   - Subtitle URL (optional)

#### Step 2: Download with Bot

Send the URLs to your Telegram bot:

```
/mindvalley <video_url> [audio_url] [subtitle_url]
```

**Examples:**

```
# Video only (audio embedded)
/mindvalley https://example.com/video.m3u8

# Video + separate audio
/mindvalley https://example.com/video.m3u8 https://example.com/audio.m3u8

# Video + audio + subtitles
/mindvalley https://example.com/video.m3u8 https://example.com/audio.m3u8 https://example.com/subtitle.m3u8
```

#### Step 3: Get Your File

The bot will:
1. Download all streams
2. Merge video + audio + subtitles (if provided)
3. Upload the final MP4 to your dump channel
4. Send you a link to access the file

### Browser Extension Features

- **Automatic Detection**: Detects M3U8 streams as they load
- **Quality Selection**: Shows all available quality options (1080p, 720p, 480p, etc.)
- **Multiple Formats**: Detects video, audio, and subtitle streams
- **One-Click Copy**: Easy copy buttons for URLs
- **Visual Feedback**: Floating notification when streams are detected

### Troubleshooting

**Extension not detecting streams:**
- Make sure the video is playing
- Refresh the page and try again
- Check browser console for errors

**Download fails:**
- Verify URLs are valid M3U8 playlists
- Check network connection
- Ensure URLs are not expired (Mindvalley URLs may have limited validity)

**Merge fails:**
- This usually means incompatible codecs
- Try downloading video only first
- Report the issue with stream URLs

## Configuration

### Required Credentials

Create a `credentials.json` file (auto-generated in Colab) with:

```json
{
  "API_ID": "your_telegram_api_id",
  "API_HASH": "your_telegram_api_hash",
  "BOT_TOKEN": "your_bot_token",
  "USER_ID": your_user_id,
  "DUMP_ID": your_dump_channel_id
}
```

### Optional Credentials

For additional downloaders:
- `NZBCLOUD_CF_CLEARANCE` - NZB Cloud cookie
- `BITSO_IDENTITY_COOKIE` - Bitso identity cookie
- `BITSO_PHPSESSID_COOKIE` - Bitso session cookie

## File Structure

```
Telegram-Leecher/
├── colab_leecher/            # Main bot module (everything consolidated here)
│   ├── __init__.py
│   ├── __main__.py           # Command handlers and bot entry point
│   ├── run_local.py          # Local bot runner script
│   ├── aliases.py            # Command aliases
│   ├── gdrive_utils.py       # Google Drive utilities
│   │
│   ├── colab/                # Colab setup scripts
│   │   ├── setup_cell.py    # Main Colab setup script
│   │   ├── sabnzbd_setup.py # SABnzbd setup for Colab
│   │   └── cells/           # Notebook cells
│   │       ├── main_setup.py     # Alternative main setup
│   │       ├── error_logger.py   # Error logging (simple + full modes)
│   │       ├── streaming_extraction.py  # Streaming ZIP extraction
│   │       └── fixed_notebook.py # Fixed notebook cell
│   │
│   ├── downlader/            # Download handlers
│   │   ├── base.py          # BaseDownloader (shared functionality)
│   │   ├── aria2.py
│   │   ├── gdrive.py
│   │   ├── instagram.py
│   │   ├── mega.py
│   │   ├── mindvalley.py    # Mindvalley M3U8 downloader
│   │   ├── nzb.py           # Native NZB downloader
│   │   ├── sabnzbd_downloader.py  # SABnzbd-based downloader
│   │   ├── telegram.py
│   │   ├── terabox.py
│   │   ├── ytdl.py
│   │   ├── requests_dl.py   # Simple HTTP downloader
│   │   └── manager.py       # Auto-detection and routing
│   │
│   ├── uploader/             # Upload handlers
│   │   ├── telegram.py      # Telegram uploader
│   │   └── gdrive.py        # Google Drive uploader
│   │
│   ├── utility/              # Helper functions
│   │   ├── handler.py       # Message handlers
│   │   ├── helper.py        # General utilities (status_bar, URL detection)
│   │   ├── variables.py     # Global state (BOT, MSG, Paths)
│   │   ├── task_manager.py  # Task orchestration
│   │   ├── task_context.py  # Multi-task support
│   │   ├── task_dashboard.py # Task progress visualization
│   │   ├── transfer_state.py # Upload/download state
│   │   ├── converters.py    # File format converters
│   │   ├── sabnzbd_client.py # SABnzbd API client
│   │   ├── sabnzbd_setup.py # SABnzbd configuration
│   │   └── sabnzbd_autodetect.py # SABnzbd auto-detection
│   │
│   └── scripts/              # Utility scripts
│       ├── downloaders/      # Download scripts
│       │   └── download_from_downloadly.py
│       └── utils/            # Utility tools
│           ├── capture_existing_logs.py
│           ├── convert_cookies.py
│           ├── extract_finra_simple.py
│           └── streaming_extract_function.py
│
├── tests/                    # Test files
│   ├── test_*.py            # Unit tests
│   ├── quick_test.py        # Quick integration test
│   ├── debug/               # Debug scripts
│   │   ├── instagram_debug.py  # Instagram debugging (unified)
│   │   ├── check_bot_info.py
│   │   ├── check_sabnzbd_logs.py
│   │   ├── debug_bot_startup.py
│   │   └── debug_nzb_command.py
│   └── fixtures/            # Test data
├── docs/                     # Documentation
│   ├── features/             # Feature guides
│   │   ├── COLAB_SABNZBD_GUIDE.md
│   │   ├── DOWNLOADLY_GUIDE.md
│   │   ├── SABNZBD_CONFIG.md
│   │   ├── SABNZBD_INTEGRATION.md
│   │   └── streaming.md
│   ├── setup/                # Setup guides
│   │   ├── getting-started.md
│   │   ├── colab-setup.md
│   │   ├── local-testing.md
│   │   └── instagram.md
│   ├── development/          # Development docs
│   │   ├── ARCHITECTURE.md  # System architecture
│   │   ├── CLAUDE.md        # Claude Code guidelines
│   │   ├── CONTRIBUTING.md  # Contribution guide
│   │   ├── REORGANIZATION_SUMMARY.md  # Reorganization report
│   │   └── mirror_function.txt  # Mirror mode docs
│   ├── tutorials/            # User tutorials
│   │   └── QUICK_START.txt  # Quick start guide
│   ├── ROADMAP.md            # Project roadmap
│   └── README.md             # Documentation index
├── notebooks/                # Jupyter notebooks
├── install_mindvalley_deps.sh  # Mindvalley dependencies installer
├── requirements.txt          # Python dependencies
├── credentials.json          # Bot credentials (gitignored)
├── credentials.json.example  # Credentials template
└── README.md                  # This file
```

## Development

### Adding New Downloaders

1. Create a new file in `colab_leecher/downlader/`
2. Implement download logic
3. Add command handler in `__main__.py`
4. Update manager.py for auto-detection (if applicable)
5. Add helper functions in `utility/helper.py`

### Running Locally

```bash
# Install dependencies
pip install -r requirements.txt
apt-get install ffmpeg aria2

# For Mindvalley support
bash install_mindvalley_deps.sh

# Create credentials.json from template
cp credentials.json.example credentials.json
# Edit credentials.json with your actual credentials

# Install commit-time security hooks
pip install pre-commit
pre-commit install

# Run bot (choose one method)
python -m colab_leecher              # Method 1: As module
python -m colab_leecher.run_local    # Method 2: Direct script
```

### Testing and Gates

```bash
# Unit tests (default)
pytest -q tests/unit

# Integration scaffold tests (opt-in)
pytest -q tests/integration -m integration --runintegration

# Security guardrails
python scripts/security/block_sensitive_files.py
pre-commit run --all-files

# Dependency audit (local)
python scripts/security/run_dependency_audit.py --requirements requirements.txt --report-dir audit/raw/local
```

## Credits

- Original Telegram-Leecher: [XronTrix10](https://github.com/XronTrix10/Telegram-Leecher)
- Mindvalley Integration: [theSadeQ](https://github.com/theSadeQ)
- N_m3u8DL-RE: [nilaoda](https://github.com/nilaoda/N_m3u8DL-RE)

## License

GPL-3.0 License - see [LICENSE](LICENSE) file

## Disclaimer

This tool is for educational purposes only. Users are responsible for complying with the terms of service of the platforms they download from. Downloading copyrighted content without permission may be illegal in your jurisdiction.
