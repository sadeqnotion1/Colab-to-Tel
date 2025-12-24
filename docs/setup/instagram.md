# Instagram Authentication Setup

Instagram authentication enables better download capabilities including:
- ✅ **Batch download entire profiles** (all posts from instagram.com/username/)
- ✅ Access to private accounts you follow
- ✅ Download stories from accounts you follow
- ✅ Higher quality media downloads
- ✅ Better rate limit handling
- ✅ More reliable downloads
- ✅ Access to age-restricted content

## Setup Options

You have **three options** for authentication (listed by priority):

### Option 1: Cookie File (Most Secure & Recommended)

Export all Instagram cookies to a file and let yt-dlp handle everything:

#### Using Browser Extension (Easy Method):

1. **Install a cookie export extension**:
   - Chrome: [Get cookies.txt LOCALLY](https://chrome.google.com/webstore/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
   - Chrome: [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg) - Export as JSON
   - Firefox: [cookies.txt](https://addons.mozilla.org/en-US/firefox/addon/cookies-txt/)

2. **Login to Instagram** in your browser

3. **Export cookies**:
   - **Netscape format (.txt)**: Click the extension icon → Export as `instagram_cookies.txt`
   - **JSON format (.json)**: Use EditThisCookie → Export as `instagram_cookies.json`

4. **Place the file** in your project directory:
   - Windows: `D:\Projects\Colab_Telegram_Leecher\instagram_cookies.txt` (or `.json`)
   - Colab: `/content/Telegram-Leecher/instagram_cookies.txt` (or `.json`)

5. **Update credentials.json**:
```json
{
  "INSTAGRAM_USERNAME": "",
  "INSTAGRAM_PASSWORD": "",
  "INSTAGRAM_SESSIONID": "",
  "INSTAGRAM_COOKIES_FILE": "instagram_cookies.json"
}
```

**Note:** Both Netscape (.txt) and JSON (.json) formats are supported!

**✅ Benefits:**
- Most secure (no password in plaintext)
- Includes all authentication cookies
- Best compatibility with Instagram
- Easier to update (just re-export)

---

### Option 2: Username & Password

1. Open `credentials.json`
2. Add your Instagram credentials:
```json
{
  "INSTAGRAM_USERNAME": "your_instagram_username",
  "INSTAGRAM_PASSWORD": "your_instagram_password",
  "INSTAGRAM_SESSIONID": ""
}
```

**⚠️ Security Notes:**
- Use a dedicated Instagram account if possible
- Never share your credentials.json file
- Keep credentials.json in .gitignore
- Instagram may send login verification email

### Option 3: Session Cookie (Quick Method)

If you don't want to save your password, you can use a session cookie:

#### Step-by-Step:

1. **Login to Instagram** in your browser (Chrome/Firefox)

2. **Open Developer Tools**:
   - Chrome: Press `F12` or `Ctrl+Shift+I`
   - Firefox: Press `F12` or `Ctrl+Shift+K`

3. **Go to Application/Storage tab**:
   - Chrome: Click "Application" → "Cookies" → "https://www.instagram.com"
   - Firefox: Click "Storage" → "Cookies" → "https://www.instagram.com"

4. **Find the `sessionid` cookie**:
   - Look for a cookie named `sessionid`
   - Copy the **Value** (long alphanumeric string)

5. **Add to credentials.json**:
```json
{
  "INSTAGRAM_USERNAME": "",
  "INSTAGRAM_PASSWORD": "",
  "INSTAGRAM_SESSIONID": "paste_your_sessionid_here",
  "INSTAGRAM_COOKIES_FILE": ""
}
```

## Authentication Priority

The bot checks authentication in this order:

1. **Cookie File** → If `INSTAGRAM_COOKIES_FILE` is set and file exists
2. **Username/Password** → If both are provided
3. **Session Cookie** → If `INSTAGRAM_SESSIONID` is provided
4. **No Auth** → Downloads without login (limited access)

**Recommendation:** Use Cookie File (Option 1) for best results!

## Verification

After adding credentials, restart the bot. Check the logs:

```
Instagram Login: Configured (Username: your_username)
```
or
```
Instagram Login: Configured (Session Cookie)
```

If you see:
```
Instagram Login: Not Configured (Limited access)
```
Then authentication is not set up (bot will still work but with limited access).

## Troubleshooting

### Login Failed / Challenge Required

If Instagram blocks the login:
1. Try logging in manually from the same IP first
2. Complete any security challenges in browser
3. Use Session Cookie method instead

### Session Cookie Expired

Session cookies typically last 90 days. If downloads stop working:
1. Get a new sessionid from browser
2. Update credentials.json
3. Restart the bot

### Account Locked

If your account gets locked:
1. Instagram may flag automated logins
2. Use Session Cookie method (safer)
3. Consider using a secondary account
4. Complete Instagram's security verification

## Best Practices

✅ **DO:**
- Use a secondary Instagram account
- Rotate session cookies every 30-60 days
- Keep credentials.json private
- Use 2FA on your Instagram account

❌ **DON'T:**
- Share your credentials.json file
- Commit credentials to git
- Use your main Instagram account
- Download copyrighted content without permission

## Commands

Once authenticated, use these commands:

- `/ig` or `/instagram` - Start Instagram download
- `/igupload` - Alternative command

All Instagram content types supported:
- **Entire Profiles** (batch download all posts from instagram.com/username/)
- Posts (photos/videos)
- Reels
- Stories (requires authentication)
- IGTV
- Carousels/Albums

**Examples:**
- Profile: `https://instagram.com/username/` (downloads all posts)
- Single post: `https://instagram.com/p/xyz123`
- Reel: `https://instagram.com/reel/abc456`

## Privacy & Security

Your credentials are:
- ✅ Stored locally only (never sent to third parties)
- ✅ Used only for yt-dlp Instagram authentication
- ✅ Never logged in plain text
- ✅ Protected by file system permissions

Instagram's Terms of Service apply. Use responsibly and respect content creators' rights.
