# Fix /nzb Command Not Responding in Telegram Bot

## Problem Summary
The `/nzb` command handler exists in the code but doesn't respond when users send `/nzb` to the bot. The bot is running old code from before the NZB handler was added. The bot needs to restart to load the new handlers.

## Root Cause
- NZB handler is defined in `colab_leecher/__main__.py` at line 2032
- Handler code exists in GitHub repo (committed)
- Bot is currently running in Google Colab with OLD code (before NZB was added)
- Bot must restart to register the new handler

## Critical Files
- `/content/Telegram-Leecher/colab_leecher/__main__.py` (contains NZB handler at line 2032-2283)
- `/content/Telegram-Leecher/colab_leecher/downlader/nzb.py` (NZB downloader implementation)
- `/content/Telegram-Leecher/credentials.json` (contains NZB provider config)

---

## SOLUTION: Restart Bot in Google Colab

### STEP 1: Stop Current Bot Process
**ACTION:** In Google Colab, find the cell where bot is running (shows "Executing: python3 -m colab_leecher")

**DO THIS:**
1. Click the **STOP** button (⏹️ square icon) on that cell
2. OR click the **Runtime** menu → **Interrupt execution**
3. Wait 3 seconds for process to stop

**VERIFY:** Cell should no longer show "Executing..." or spinning icon

---

### STEP 2: Pull Latest Code from GitHub
**ACTION:** Create a NEW Colab cell and paste this EXACT code:

```python
%cd /content/Telegram-Leecher
!git pull origin feature/multi-task-parallel
```

**RUN THE CELL**

**VERIFY:** Output should show:
- "Already up to date" OR
- "Updating [commit hash]..[commit hash]"
- Should NOT show merge conflicts or errors

**IF ERRORS APPEAR:** Run this instead:
```python
%cd /content/Telegram-Leecher
!git fetch origin
!git reset --hard origin/feature/multi-task-parallel
```

---

### STEP 3: Verify NZB Handler Exists in Code
**ACTION:** Create a NEW Colab cell and paste this EXACT code:

```python
# Verify NZB handler exists
!grep -n "def nzb_download" /content/Telegram-Leecher/colab_leecher/__main__.py
!grep -n '@colab_bot.on_message(filters.command("nzb")' /content/Telegram-Leecher/colab_leecher/__main__.py
```

**RUN THE CELL**

**EXPECTED OUTPUT:**
```
2033:async def nzb_download(client, message):
2032:@colab_bot.on_message(filters.command("nzb") & filters.private)
```

**IF NO OUTPUT:** Code is missing - need to re-clone repo (see Alternative Fix #1)

---

### STEP 4: Verify NZB Module File Exists
**ACTION:** Create a NEW Colab cell and paste this EXACT code:

```python
import os
nzb_file = "/content/Telegram-Leecher/colab_leecher/downlader/nzb.py"
print(f"NZB file exists: {os.path.exists(nzb_file)}")
if os.path.exists(nzb_file):
    print(f"File size: {os.path.getsize(nzb_file)} bytes")
else:
    print("❌ FILE MISSING - Need to re-clone repo!")
```

**RUN THE CELL**

**EXPECTED OUTPUT:**
```
NZB file exists: True
File size: [some number > 20000] bytes
```

**IF FILE MISSING:** Re-clone repo (see Alternative Fix #1)

---

### STEP 5: Restart Bot with New Code
**ACTION:** Re-run your bot setup cell (the cell with all your credentials: API_ID, API_HASH, BOT_TOKEN, etc.)

**WHICH CELL:** The cell that has these lines:
```python
API_ID = 2040
API_HASH = "b18441a1ff607e10a989891a5462e627"
BOT_SELECTION = "Bot 1 - 7772724138"
...
```

**DO THIS:**
1. Scroll to find that cell
2. Click on the cell
3. Press **Shift + Enter** OR click the ▶️ play button
4. Wait for bot to start (should see "Executing: python3 -m colab_leecher")

**VERIFY:** Look for these log lines in output:
```
INFO:colab_leecher:Credentials loaded successfully.
INFO:colab_leecher:Loaded 1 Usenet provider(s)
INFO:colab_leecher:Active Provider: sunnyusenet
```

---

### STEP 6: Test /nzb Command
**ACTION:** Open Telegram and message your bot

**DO THIS IN ORDER:**
1. Send: `/start`
   - **Expected:** Bot replies with "Yo! 👋🏼 It's Colab Leecher"

2. Send: `/help`
   - **Expected:** Help message shows, should include line: `/nzb - Download from Usenet (NZB files)`

3. Send: `/nzb`
   - **Expected:** Bot replies with:
   ```
   📰 NZB Usenet Downloader

   Upload your .nzb file or send NZB URL

   📌 Requirements:
   • Valid Usenet account configured in credentials.json
   • NZB file with valid article IDs

   💡 Tip: Supports multi-part RAR archives!
   ⚠️ Note: Missing articles will be skipped

   Active Provider: sunnyusenet
   ```

4. Upload your `.nzb` file (2_Broke_Girls_S05_1080p_AMZN_WEB_DL_DD_Plu...nzb)
   - **Expected:** Bot starts downloading and shows progress bar

---

## SUCCESS CRITERIA
✅ `/nzb` command responds with help message
✅ Bot shows "Active Provider: sunnyusenet"
✅ Uploading .nzb file starts download process
✅ Progress bar appears with thumbnail

---

## ALTERNATIVE FIX #1: Complete Re-clone (If Steps 3-4 Show Missing Files)

**ONLY DO THIS IF:** NZB handler or nzb.py file is missing

**ACTION:** Create a NEW Colab cell and paste this EXACT code:

```python
import shutil
import os

# Remove old repo
if os.path.exists('/content/Telegram-Leecher'):
    print("Removing old repo...")
    shutil.rmtree('/content/Telegram-Leecher')
    print("✅ Removed")

# Clone fresh repo
print("Cloning fresh repo...")
!git clone -b feature/multi-task-parallel https://github.com/theSadeQ/Telegram-Leecher

# Verify NZB files exist
print("\n🔍 Verifying NZB files...")
!ls -lh /content/Telegram-Leecher/colab_leecher/downlader/nzb.py
!grep -c "def nzb_download" /content/Telegram-Leecher/colab_leecher/__main__.py

print("\n✅ Re-clone complete - Now re-run your bot setup cell")
```

**RUN THE CELL**

**THEN:** Go back to STEP 5 (restart bot)

---

## ALTERNATIVE FIX #2: Quick Restart (Minimal Steps)

**ONLY DO THIS IF:** You're confident code is up to date

**ACTION:** Create a NEW Colab cell and paste this EXACT code:

```python
# Quick restart with latest code
%cd /content/Telegram-Leecher
!git pull origin feature/multi-task-parallel
!python3 -m colab_leecher
```

**RUN THE CELL**

**VERIFY:** Bot starts and shows credentials loaded

**THEN:** Go to STEP 6 (test /nzb)

---

## TROUBLESHOOTING

### Issue: `/nzb` still doesn't respond after restart

**FIX:** Run this diagnostic cell:

```python
import sys
sys.path.insert(0, '/content/Telegram-Leecher')

from colab_leecher import colab_bot
from colab_leecher.utility.variables import BOT

print("📋 NZB Configuration:")
print(f"   Providers: {list(BOT.Setting.nzb_providers.keys())}")
print(f"   Active: {BOT.Setting.nzb_active_provider}")

print("\n📡 Checking handlers...")
found = False
for group_id, handlers in colab_bot.dispatcher.groups.items():
    for handler in handlers:
        if hasattr(handler, 'callback'):
            if 'nzb' in handler.callback.__name__.lower():
                print(f"   ✅ Found: {handler.callback.__name__}")
                found = True

if not found:
    print("   ❌ NZB handler NOT registered!")
    print("   → Need to RESTART bot (see STEP 5)")
```

### Issue: `ImportError: No module named 'sabyenc'`

**FIX:** Run this cell:

```python
!pip install sabyenc>=3.3.6
```

Then restart bot (STEP 5)

### Issue: "Usenet Not Configured" error

**FIX:** Run this cell to check credentials:

```python
import json
with open('/content/Telegram-Leecher/credentials.json', 'r') as f:
    creds = json.load(f)

print("NZB Providers:", creds.get('NZB_PROVIDERS', {}))
print("Default Provider:", creds.get('NZB_DEFAULT_PROVIDER', 'None'))
```

**If empty:** Re-run bot setup cell (STEP 5) - it will recreate credentials.json

---

## EXECUTION NOTES FOR AI ASSISTANT (GEMINI)

**YOU MUST:**
1. Follow steps in EXACT order (1 → 2 → 3 → 4 → 5 → 6)
2. Wait for each cell to complete before moving to next step
3. READ the output of each step to verify success
4. If ANY step fails, STOP and use the appropriate Alternative Fix
5. Copy code blocks EXACTLY as written (don't modify)
6. After STEP 6, verify ALL success criteria are met

**DO NOT:**
- Skip steps
- Modify the code blocks
- Assume steps worked without checking output
- Continue if verification fails

**DECISION TREE:**
- STEP 3 or 4 fails → Use Alternative Fix #1 (re-clone)
- STEP 5 succeeds but STEP 6 fails → Run Troubleshooting diagnostic
- STEP 6 succeeds → DONE ✅

---

## FINAL VERIFICATION CHECKLIST

After completing all steps, verify:

- [ ] Bot is running in Colab (cell shows "Executing: python3 -m colab_leecher")
- [ ] `/start` command works
- [ ] `/help` shows `/nzb` in command list
- [ ] `/nzb` responds with help message
- [ ] Help message shows "Active Provider: sunnyusenet"
- [ ] Uploading .nzb file triggers download

**IF ALL CHECKED:** ✅ **SUCCESS - /nzb command is fixed!**

**IF ANY UNCHECKED:** Review Troubleshooting section
