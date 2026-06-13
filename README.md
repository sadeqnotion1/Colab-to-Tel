# Colab Telegram YTDL Downloader

A manual Python script (`ytdl.py`) designed to run in Google Colab (or any Python environment) to download videos using `yt-dlp` and upload them to a Telegram chat/channel via a Telegram bot.

## Manual Colab YTDL Script (`ytdl.py`)

If you want to download a video and upload it to Telegram manually using a simple script, you can use the [ytdl.py](ytdl.py) script directly in a Google Colab cell.

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

## License

GPL-3.0 License - see [LICENSE](LICENSE) file

## Disclaimer

This tool is for educational purposes only. Users are responsible for complying with the terms of service of the platforms they download from. Downloading copyrighted content without permission may be illegal in your jurisdiction.
