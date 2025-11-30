# How to Download from Downloadly.ir Using Your Bot

## ✅ Method 1: Use Your Existing Bot (Try This First!)

Your bot **already supports direct downloads** with `/tupload`!

### Steps:

1. **Start your bot in Colab**
2. **Send command:**
   ```
   /tupload
   ```

3. **Send the downloadly.ir link:**
   ```
   https://dl1.downloadly.ir/Files/Elearning/Udemy_CBT_Practitioner_Training_Cognitive_and_Behaviour_Therapy_2024_11.part02_Downloadly.ir.rar?nocache=1764337339784
   ```

4. **Select service:** Choose **Aria** (best for direct downloads)

5. **Wait for download!**

---

## ⚠️ If You Get "403 Forbidden" or Errors

Downloadly.ir might block Colab IPs. Here's how to fix it:

### Option A: Add Headers to Your Bot (Recommended)

I'll add downloadly.ir support to your bot's downloader.

### Option B: Download via Browser Then Upload

1. Download on your PC using browser
2. Upload to Google Drive
3. Use bot to leech from Drive

### Option C: Use Standalone Script

If bot doesn't work, use the simple script I created:
`download_from_downloadly.py`

---

## 🔧 Let's Fix It Together

**Try Method 1 first**, then tell me:
- What error message you get?
- Does it start downloading?
- Does it say "403" or "404"?

Then I'll know exactly how to fix it!

---

## 💡 Why Your Bot Should Work

Your bot has:
- ✅ Direct link support (`/tupload`)
- ✅ aria2c downloader (fast & reliable)
- ✅ requests library (with headers support)
- ✅ Progress tracking
- ✅ Resume capability

**The downloadly.ir link should work directly!**

---

## 🎯 Quick Commands Reference

```
/tupload          - Download and upload to Telegram
/gdupload         - Download and upload to Google Drive
```

Both support direct links like downloadly.ir!
