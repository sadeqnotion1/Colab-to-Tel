# Effortless Parallel Task Testing Guide

## Quick Start (5 Minutes)

### Prerequisites
- Bot running (start with `python -m colab_leecher`)
- Telegram app open
- A small test file URL (use these free test files)

---

## Test Files You Can Use

**Small Files (Quick Download):**
```
https://speed.hetzner.de/100MB.bin (100MB)
https://speed.hetzner.de/1GB.bin (1GB - only if you have space)
```

**YouTube Videos (yt-dlp test):**
```
https://www.youtube.com/watch?v=jNQXAC9IVRw (Me at the zoo - 19 sec)
https://www.youtube.com/watch?v=dQw4w9WgXcQ (Rick Roll - 3:33)
```

**Google Drive (if configured):**
```
https://drive.google.com/file/d/1XXXXXXXXXX/view
```

---

## 🚀 5-Minute Core Test

### Test 1: Single Task (Baseline)
**Time:** 1 minute

1. Send to bot: `/tupload`
2. Choose: `🔽 Normal`
3. Paste URL: `https://speed.hetzner.de/100MB.bin`
4. **Expected:** Downloads and uploads successfully

✅ **Pass if:** File uploads to Telegram without errors

---

### Test 2: Parallel Tasks (2 tasks)
**Time:** 2 minutes

1. Send: `/tupload` → `🔽 Normal` → `https://speed.hetzner.de/100MB.bin`
2. **Immediately** send: `/tupload` → `🔽 Normal` → `https://speed.hetzner.de/100MB.bin`
3. **Expected:** See summary dashboard with 2 active tasks

✅ **Pass if:**
- Both tasks run simultaneously
- Dashboard shows `🚀 Parallel Downloads (2 active)`
- Both complete successfully

---

### Test 3: Rate Limiting
**Time:** 1 minute

1. Rapidly send `/tupload` 15 times in a row
2. **Expected:** After 10 commands, you get rate limit message

✅ **Pass if:** See message: `⏱️ Rate limit exceeded. You can create 10 tasks per minute. Please wait...`

---

### Test 4: Task Limits
**Time:** 1 minute

1. Start 5 tasks (your user limit)
2. Try to start a 6th task
3. **Expected:** Error message about max tasks

✅ **Pass if:** See message: `You have 5/5 tasks active. Please wait for some to complete.`

---

## 🎯 Advanced Tests (Optional - 10 Minutes)

### Test 5: Concurrent Different Services
**Time:** 3 minutes

Start these in rapid succession:
1. `/tupload` → Telegram file
2. `/ytupload` → YouTube video
3. `/gdupload` → Google Drive file (if configured)

✅ **Pass if:** All 3 run in parallel, dashboard updates correctly

---

### Test 6: Error Handling
**Time:** 2 minutes

1. Send `/tupload` with invalid URL: `https://invalid-url-that-doesnt-exist.com/file.zip`
2. **Expected:** Task fails gracefully, workspace cleaned up

✅ **Pass if:**
- Error message sent
- Dashboard removes failed task
- `BOT_WORK/` folder doesn't have leftover directories

---

### Test 7: Cancellation
**Time:** 2 minutes

1. Start a large download: `/tupload` → large file
2. While downloading, send: `/cancel`
3. **Expected:** Task stops, cleanup happens

✅ **Pass if:**
- Download stops
- Workspace directory deleted
- Dashboard updates

---

### Test 8: Memory/Cleanup (Long Running)
**Time:** Wait 1+ hours

1. Complete 5-10 tasks over an hour
2. Check logs for: `"Running periodic cleanup of old completed tasks..."`
3. Check `BOT_WORK/` folder - should be empty or minimal

✅ **Pass if:**
- Cleanup message appears in logs every hour
- Old task directories deleted
- Memory usage stays stable

---

## 📊 What to Watch in Logs

Start bot and watch for these key messages:

### ✅ Good Signs (Should See These)

```
Started periodic cleanup background task
Task [xxxxxxxx] registered in TASK_QUEUE. Total active: 2
Summary dashboard updated (2 tasks)
Task [xxxxxxxx] removed from TASK_QUEUE. Remaining: 1
Successfully cleaned up workspace: BOT_WORK/xxxxx
Running periodic cleanup of old completed tasks...
```

### ⚠️ Warning Signs (Should NOT See)

```
Error in periodic cleanup
Failed to cleanup workspace
Unhandled exception in background task
Error adding task (should use lock)
Message not modified (dashboard race condition)
```

---

## 🐛 Quick Troubleshooting

### Problem: "Rate limit exceeded" immediately
**Fix:** Wait 60 seconds, limit resets

### Problem: Can't start 2nd task
**Check:** First task might not have fully started
**Fix:** Wait for dashboard to appear

### Problem: Tasks not cleaning up
**Check:** Look in `BOT_WORK/` folder
**Fix:** Restart bot (cleanup runs on startup)

### Problem: Dashboard not updating
**Check:** Tasks might be running but not reporting progress
**Fix:** Try with smaller files for faster feedback

---

## 📝 Automated Test Script (Ultimate Lazy Mode)

Save this as `test_parallel.py` in your project folder:

```python
#!/usr/bin/env python3
"""
Automated parallel task test script
Usage: python test_parallel.py
"""

import time
from telethon.sync import TelegramClient
from telethon.tl.types import Message

# === CONFIGURE THESE ===
API_ID = 12345  # Your API ID
API_HASH = "your_api_hash"  # Your API hash
BOT_USERNAME = "@YourBotUsername"  # Your bot's username
PHONE = "+1234567890"  # Your phone number
# ======================

TEST_URLS = [
    "https://speed.hetzner.de/100MB.bin",
    "https://speed.hetzner.de/100MB.bin",
    "https://speed.hetzner.de/100MB.bin",
]

def run_tests():
    print("🚀 Starting Parallel Task Tests...")

    with TelegramClient('test_session', API_ID, API_HASH) as client:
        print(f"✅ Connected as {client.get_me().first_name}")

        # Test 1: Single task
        print("\n📝 Test 1: Single Task")
        client.send_message(BOT_USERNAME, "/tupload")
        time.sleep(2)
        # Click "Normal" button (would need to handle callbacks)
        client.send_message(BOT_USERNAME, TEST_URLS[0])
        time.sleep(5)
        print("✅ Test 1 sent")

        # Test 2: Parallel tasks
        print("\n📝 Test 2: Parallel Tasks (3 simultaneous)")
        for i, url in enumerate(TEST_URLS, 1):
            print(f"  Launching task {i}...")
            client.send_message(BOT_USERNAME, "/tupload")
            time.sleep(1)
            client.send_message(BOT_USERNAME, url)
            time.sleep(0.5)
        print("✅ Test 2 sent - check bot for parallel execution")

        # Test 3: Rate limiting
        print("\n📝 Test 3: Rate Limiting (15 rapid commands)")
        for i in range(15):
            client.send_message(BOT_USERNAME, "/tupload")
            time.sleep(0.1)
        print("✅ Test 3 sent - should see rate limit after 10th")

        print("\n🎉 All tests dispatched! Check your bot for results.")
        print("\nExpected:")
        print("- Task 1: Completes normally")
        print("- Task 2: 3 tasks run in parallel")
        print("- Task 3: Rate limit message after 10th command")

if __name__ == "__main__":
    run_tests()
```

**To use:**
1. Install: `pip install telethon`
2. Edit API_ID, API_HASH, BOT_USERNAME, PHONE
3. Run: `python test_parallel.py`
4. Watch your bot handle everything automatically!

---

## ✅ Success Checklist

After testing, you should have seen:

- [ ] Single task completes successfully
- [ ] 2+ tasks run in parallel
- [ ] Dashboard shows all active tasks
- [ ] Rate limiting kicks in at 10 tasks/minute
- [ ] Per-user limit works (5 tasks max)
- [ ] Failed tasks clean up workspace
- [ ] Cancelled tasks clean up workspace
- [ ] Periodic cleanup runs (check logs after 1 hour)
- [ ] No memory leaks (if running long-term)

---

## 🎯 Minimum Viable Test (30 Seconds)

**Too lazy for all that? Just do this:**

1. Start bot
2. Send: `/tupload` → `🔽 Normal` → `https://speed.hetzner.de/100MB.bin`
3. **Immediately** send another: `/tupload` → `🔽 Normal` → `https://speed.hetzner.de/100MB.bin`
4. Watch dashboard appear with 2 tasks

**If both tasks complete:** ✅ System works!
**If something crashes:** ❌ Check logs for errors

---

## 📞 Need Help?

If tests fail:
1. Check logs for ERROR messages
2. Check `BOT_WORK/` folder for orphaned directories
3. Restart bot and try again
4. Check that all fixes from audit are applied

---

**Happy Testing! 🎉**
