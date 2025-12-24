# 🧪 Local Testing Guide - Instagram Downloader

Complete guide to test the Instagram downloader on your local machine.

---

## 📋 Prerequisites

Before starting, ensure you have:

✅ **Python 3.8+** installed
✅ **Telegram Bot Token** (from @BotFather)
✅ **Your Telegram User ID** (from @userinfobot)
✅ **Telegram API ID & Hash** (from https://my.telegram.org)

---

## 🚀 Quick Start

### Step 1: Install Dependencies

Open Command Prompt in the project directory:

```bash
cd D:\Projects\Colab_Telegram_Leecher
pip install -r requirements.txt
```

### Step 2: Configure Credentials

Your `credentials.json` is already configured with:
- ✅ Bot token
- ✅ User ID
- ✅ API credentials

**Optional:** Add Instagram authentication (see INSTAGRAM_SETUP.md)

### Step 3: Start the Bot

**Option A - Using the startup script (Recommended):**

```bash
python run_bot_local.py
```

**Option B - Direct launch:**

```bash
python -m colab_leecher
```

### Step 4: Test in Telegram

1. **Open Telegram** and find your bot
2. **Send** `/start` to check if bot is alive
3. **Send** `/help` to see all commands
4. **Test Instagram** with `/ig` command

---

## 📸 Testing Instagram Downloads

### Basic Test (No Authentication)

1. **Start Instagram download:**
   ```
   /ig
   ```

2. **Send a public Instagram URL:**
   ```
   https://www.instagram.com/p/POST_ID/
   https://www.instagram.com/reel/REEL_ID/
   ```

3. **Wait for download** - Bot will show progress

4. **Receive files** - Bot uploads to Telegram

### Test Multiple URLs (Batch)

Send multiple URLs at once:
```
https://www.instagram.com/p/POST1/
https://www.instagram.com/reel/REEL1/
https://www.instagram.com/p/POST2/
```

Bot will download all sequentially!

### Test with Authentication

If you configured Instagram login in credentials.json:

1. **Add credentials** to `credentials.json`:
```json
{
  "INSTAGRAM_USERNAME": "your_username",
  "INSTAGRAM_PASSWORD": "your_password"
}
```

2. **Restart the bot**

3. **Test private content:**
   - Stories from accounts you follow
   - Posts from private accounts you follow
   - Age-restricted content

---

## 🔍 How to Get Instagram Post URLs

### Method 1: From Browser

1. Go to Instagram in your browser
2. Click on any post/reel
3. Copy the URL from address bar

**Examples:**
- Post: `https://www.instagram.com/p/C_abc123/`
- Reel: `https://www.instagram.com/reel/Xyz789/`
- IGTV: `https://www.instagram.com/tv/Video123/`

### Method 2: From Mobile App

1. Open Instagram post
2. Tap the **three dots** (⋯)
3. Select **Copy Link**
4. Paste in Telegram

### ⚠️ What DOESN'T Work:

❌ Profile URLs: `https://www.instagram.com/username/`
❌ Hashtag pages: `https://www.instagram.com/explore/tags/...`
❌ Explore pages: `https://www.instagram.com/explore/`

**You need direct post/reel/story URLs!**

---

## 🎯 Available Commands

| Command | Description |
|---------|-------------|
| `/ig` or `/instagram` | Start Instagram download (short) |
| `/igupload` | Start Instagram download (full) |
| `/tupload` | Regular leech (includes auto-detect) |
| `/help` | Show all commands |
| `/settings` | Bot settings |

---

## 📊 What to Expect

### Successful Download:

```
[*] Extracting info...

============================================================
Media Info:
============================================================
Title: Beautiful sunset photo
Uploader: username
Type: single
============================================================

[*] Downloading...
📥 DOWNLOADING FROM INSTAGRAM » Link 01

🏷️ Name » Beautiful sunset photo

⬇️ 2.5 MB / 5.0 MB (50.0%)
⚡ Speed: 1.2 MB/s
⏱️ ETA: 2s

[+] Download Complete!
```

### Multiple Items (Carousel):

```
[*] Found 5 items in album...
[*] Downloading...

📥 Downloading item 1/5...
📥 Downloading item 2/5...
...
[+] All items downloaded!
```

---

## 🐛 Troubleshooting

### Bot doesn't respond

**Check:**
- ✅ Bot is running (no errors in terminal)
- ✅ You're messaging the correct bot
- ✅ Bot token is valid in credentials.json

**Fix:**
```bash
# Restart the bot
Ctrl+C (stop)
python run_bot_local.py (restart)
```

### "Invalid URL" error

**Causes:**
- ❌ Profile URL instead of post URL
- ❌ Deleted/unavailable content
- ❌ Invalid URL format

**Fix:**
Get a direct post/reel URL (see "How to Get URLs" above)

### "Private account" error

**Causes:**
- Content is from private account
- You're not following the account

**Fix:**
1. Add Instagram login credentials
2. Follow the account in Instagram
3. Try again

### Download fails / Rate limit

**Causes:**
- Too many downloads in short time
- Instagram rate limiting

**Fix:**
1. Wait 5-10 minutes
2. Add Instagram authentication (better rate limits)
3. Try again

### Dependencies missing

**Error:**
```
ModuleNotFoundError: No module named 'yt_dlp'
```

**Fix:**
```bash
pip install -r requirements.txt
```

---

## 📁 Where Files are Saved

**During download:**
```
D:\Projects\Colab_Telegram_Leecher\BOT_WORK\Downloads\
```

**After upload to Telegram:**
Files are sent to you in Telegram and optionally deleted from disk.

---

## 🔒 Privacy & Security

### Your credentials:
- ✅ Stored locally only (never sent to third parties)
- ✅ Used only for bot authentication
- ✅ Instagram auth optional (bot works without it)

### Instagram authentication:
- ✅ Credentials used only by yt-dlp (trusted library)
- ✅ No data collection or tracking
- ✅ Respects Instagram's rate limits

### Downloaded content:
- ⚠️ Respect copyright and content creators' rights
- ⚠️ Don't redistribute without permission
- ⚠️ Personal use only

---

## 📝 Testing Checklist

Use this checklist to verify everything works:

- [ ] Bot starts without errors
- [ ] Bot responds to `/start`
- [ ] Bot responds to `/help`
- [ ] `/ig` command shows prompt
- [ ] Single photo post downloads
- [ ] Single video post downloads
- [ ] Reel downloads
- [ ] Carousel/album downloads (multiple items)
- [ ] Batch download (multiple URLs)
- [ ] Progress tracking shows correctly
- [ ] Files upload to Telegram
- [ ] Error handling works (invalid URL)

---

## 🎉 Success!

If all tests pass, your Instagram downloader is working perfectly!

### Next Steps:

1. ✨ **Add authentication** for better access (see INSTAGRAM_SETUP.md)
2. 🚀 **Deploy to Google Colab** for 24/7 operation
3. 📱 **Share with friends** (they can use your bot!)
4. ⭐ **Star the repo** if you find it useful!

---

## 📞 Support

Having issues? Check:

1. **INSTAGRAM_SETUP.md** - Authentication guide
2. **requirements.txt** - All dependencies listed
3. **Bot logs** - Error messages in terminal
4. **Telegram bot** - Send `/help` for command list

---

## 🔄 Stop the Bot

When you're done testing:

**Press:** `Ctrl+C` in the terminal

**Confirm:** Bot will stop gracefully

**Restart:** Run `python run_bot_local.py` again

---

Happy Testing! 🎊
