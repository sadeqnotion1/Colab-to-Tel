# SABnzbd Integration for Google Colab - Complete Guide

## Quick Start

### Step 1: Run the Setup Cell

The main `colab_setup_cell.py` includes SABnzbd setup automatically. Just run it:

```python
# In your Colab notebook
%run colab_setup_cell.py
```

This will:
- ✅ Install SABnzbd and dependencies
- ✅ Configure SABnzbd with your Usenet providers
- ✅ Start SABnzbd daemon
- ✅ Create cloudflared tunnel for public access
- ✅ Extract public URL
- ✅ Create `.sabnzbd_url.txt` notification file
- ✅ Start the bot
- ✅ Send SABnzbd URL to your Telegram

### Step 2: Check Telegram

Within 3 seconds of the bot starting, you should receive:

```
🌐 SABnzbd Web UI Ready!

🔗 URL: https://abc-123-xyz.trycloudflare.com
🔑 API Key: your_api_key_here

Click the URL to manage NZB downloads in your browser.
```

---

## If It Doesn't Work - Debugging

### Debug Script

Run this in a new Colab cell to diagnose issues:

```python
%run colab_sabnzbd_debug.py
```

This will check:
1. ✅ SABnzbd process running
2. ✅ SABnzbd API accessible
3. ✅ Cloudflared tunnel running
4. ✅ Tunnel log file and URL
5. ✅ Notification file created
6. ✅ File contents

### Common Issues

#### Issue 1: "SABnzbd process NOT running"

**Cause**: SABnzbd failed to start

**Fix**:
```python
# Check SABnzbd logs
!cat /content/sabnzbd/config/sabnzbd.log | tail -50
```

Common reasons:
- Invalid Usenet provider configuration
- Port 8080 already in use
- Missing dependencies

#### Issue 2: "Cloudflared process NOT running"

**Cause**: Tunnel setup failed

**Fix**:
```python
# Try manually starting cloudflared
!cloudflared tunnel --url http://127.0.0.1:8080 > /tmp/tunnel.log 2>&1 &

# Wait 10 seconds
import time
time.sleep(10)

# Check log
!cat /tmp/tunnel.log
```

Look for the `trycloudflare.com` URL in the output.

#### Issue 3: "No trycloudflare.com URL found in log"

**Cause**: Cloudflared running but URL not extracted

**Possible reasons**:
- Cloudflared output format changed
- Not enough wait time
- URL in stdout/stderr instead of log file

**Fix**: Run debug script above, it will show log contents

#### Issue 4: "Notification file NOT found"

**Cause**: File creation code didn't run or failed

**This is the main issue!** Check setup logs for:
- "Creating notification file for Telegram..."
- "File created successfully"

If you see errors, the setup script will show exactly what went wrong.

#### Issue 5: "Bot doesn't send Telegram message"

**Possible causes**:
1. Notification file deleted before bot started
2. Bot crashed before reading file
3. send_sabnzbd_url_to_telegram() function failed

**Fix**:
```python
# Check if file exists right before starting bot
import os
if os.path.exists('.sabnzbd_url.txt'):
    print("✅ File exists")
    with open('.sabnzbd_url.txt', 'r') as f:
        print(f.read())
else:
    print("❌ File missing")

# Then start bot and check logs immediately
```

---

## Manual Setup (Alternative)

If automatic setup fails, try manual setup:

### 1. Install SABnzbd

```python
!apt-get update -qq
!apt-get install -y -qq python3-pip python3-dev par2 unrar unzip p7zip-full
!pip install sabnzbd --quiet
```

### 2. Configure SABnzbd

```python
from colab_leecher.utility.sabnzbd_setup import SABnzbdManager

manager = SABnzbdManager()
manager.generate_config()  # Creates config from credentials.json
manager.start_sabnzbd()    # Starts SABnzbd
```

### 3. Setup Tunnel

```python
manager.setup_tunnel()  # Creates public URL

# Get the URL
config = manager.get_config_info()
if config.get('public_url'):
    print(f"Public URL: {config['public_url']}")
    print(f"API Key: {config['api_key']}")
else:
    print("Tunnel failed, using local URL")
    print(f"Local URL: {config['base_url']}")
```

### 4. Create Notification File

```python
from pathlib import Path

# Create .sabnzbd_url.txt
repo_root = Path('/content/Telegram-Leecher')
notification_file = repo_root / '.sabnzbd_url.txt'

url = config.get('public_url') or config.get('base_url')
api_key = config['api_key']
url_type = 'public' if config.get('public_url') else 'local'

with open(notification_file, 'w') as f:
    f.write(f"{url}\n")
    f.write(f"{api_key}\n")
    f.write(f"{url_type}\n")

print(f"✅ Created: {notification_file}")
```

### 5. Start Bot

```python
!python -m colab_leecher
```

---

## Improved Debugging Features

The updated code now includes:

### 1. Better Tunnel URL Extraction

- Tries for up to **15 seconds** (instead of 8)
- Uses **multiple regex patterns**
- Shows **progress updates** every 3 seconds
- Displays **log preview** if URL not found

### 2. Verbose File Creation

When creating `.sabnzbd_url.txt`, you'll see:

```
📝 Creating notification file for Telegram...
   Repository root: /content/Telegram-Leecher
   File path: /content/Telegram-Leecher/.sabnzbd_url.txt
   Public URL: https://abc-123.trycloudflare.com
   Base URL: http://127.0.0.1:8080
   URL to save: https://abc-123.trycloudflare.com
   API Key: abc123xyz...
   ✅ File created successfully (95 bytes)
   ✅ Saved public URL info for Telegram notification

   File contents:
      Line 1: https://abc-123.trycloudflare.com
      Line 2: abc123xyz... (truncated)
      Line 3: public
```

### 3. Auto-Detection on Bot Startup

If you run the bot without running setup first, it will:
- Auto-detect if SABnzbd is running
- Create notification file if found
- Send Telegram message

This is useful if bot crashes and you restart it.

---

## Step-by-Step Troubleshooting Workflow

1. **Run colab_setup_cell.py**
   - Watch for errors in output
   - Look for "✅ File created successfully"

2. **If setup completes but no Telegram message**:
   ```python
   # Check if file exists
   !ls -la .sabnzbd_url.txt
   !cat .sabnzbd_url.txt
   ```

3. **If file doesn't exist**:
   ```python
   # Run debug script
   %run colab_sabnzbd_debug.py
   ```

4. **If tunnel URL not found**:
   ```python
   # Check cloudflared is installed
   !which cloudflared

   # Try manual tunnel
   !cloudflared tunnel --url http://127.0.0.1:8080 > /tmp/test_tunnel.log 2>&1 &
   !sleep 10
   !cat /tmp/test_tunnel.log | grep trycloudflare
   ```

5. **If file exists but bot doesn't send**:
   ```python
   # Check bot logs
   # Look for "send_sabnzbd_url_to_telegram" in logs
   # The message should be sent within 3 seconds of bot start
   ```

---

## Expected Output Timeline

**T+0s**: Setup starts
```
📦 Installing SABnzbd...
```

**T+30s**: SABnzbd installed
```
✅ SABnzbd installed successfully
⚙️ Generating SABnzbd configuration...
```

**T+40s**: SABnzbd started
```
✅ SABnzbd started successfully at http://127.0.0.1:8080
🌐 Setting up public tunnel for SABnzbd web UI...
```

**T+50s**: Cloudflared installed
```
✅ Cloudflared installed
   Waiting for tunnel URL...
   Still waiting... (3s)
   Still waiting... (6s)
```

**T+55s**: Tunnel URL found
```
✅ Public URL: https://abc-123.trycloudflare.com
   (Found after 7 seconds)
```

**T+56s**: Notification file created
```
📝 Creating notification file for Telegram...
   ✅ File created successfully (95 bytes)
   ✅ Saved public URL info for Telegram notification
```

**T+60s**: Bot starts
```
Colab Leecher Script Starting as main...
colab_bot instance found, attempting run()...
```

**T+63s**: Telegram message sent
```
✅ Sent SABnzbd public URL to owner via Telegram
```

---

## Files Reference

- `colab_setup_cell.py` - Main Colab setup (includes SABnzbd)
- `colab_sabnzbd_setup.py` - Standalone SABnzbd-only setup
- `colab_sabnzbd_debug.py` - Debug script (run after setup)
- `colab_leecher/utility/sabnzbd_setup.py` - Core setup logic
- `colab_leecher/__main__.py` - Bot entry point (sends Telegram message)
- `.sabnzbd_url.txt` - Notification file (auto-created, auto-deleted)

---

## Need Help?

Run the debug script and share the output:
```python
%run colab_sabnzbd_debug.py
```

This will show exactly what's working and what's not!
