# 🚀 Colab Telegram Leecher - Start Here!

**Welcome!** This guide will help you get started with the latest features.

---

## 🎉 What's New

### 1. ⚡ Parallel Task Support (NEW!)
**Run multiple downloads/uploads simultaneously!**

- ✅ `/tupload` - Multiple file uploads at once
- ✅ `/ytupload` - Multiple YouTube downloads at once
- ✅ `/igupload` - Multiple Instagram downloads at once
- ✅ `/drupload` - Multiple directory uploads at once
- ✅ `/gdupload` - Multiple GDrive uploads at once

**Quick Start:**
```
/tupload
http://file1.zip

/tupload  ← Start another immediately!
http://file2.zip

Both download at the same time! 🎉
```

📖 **Full Guide:** [docs/features/parallel-tasks/PARALLEL_UPLOAD_QUICK_START.md](docs/features/parallel-tasks/PARALLEL_UPLOAD_QUICK_START.md)

---

### 2. 🎨 Enhanced UI Components
**Beautiful new progress displays and menus!**

- ✅ Modern progress bars
- ✅ Clean status messages
- ✅ Professional menus
- ✅ Multiple styles (modern, compact, classic)

📖 **Full Guide:** [docs/features/ui-upgrade/UI_COMPONENTS_GUIDE.md](docs/features/ui-upgrade/UI_COMPONENTS_GUIDE.md)

---

## 🚀 Quick Start

### First Time Setup
1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configure credentials:**
   - Copy `credentials.json.example` to `credentials.json`
   - Fill in your bot token and API credentials

3. **Run the bot:**
   ```bash
   python -m colab_leecher
   ```

---

## 📚 Documentation

### For Users
- **[Parallel Upload Guide](docs/features/parallel-tasks/PARALLEL_UPLOAD_QUICK_START.md)** - How to use parallel uploads
- **[UI Components Guide](docs/features/ui-upgrade/UI_COMPONENTS_GUIDE.md)** - UI features and customization
- **[Main README](README.md)** - Project overview

### For Developers
- **[Architecture](docs/development/ARCHITECTURE.md)** - System architecture
- **[Contributing](docs/development/CONTRIBUTING.md)** - How to contribute
- **[Parallel Tasks Implementation](docs/features/parallel-tasks/TODAYS_ACCOMPLISHMENTS.md)** - Technical details

---

## ⚡ Parallel Tasks - Quick Examples

### Example 1: Multiple File Downloads
```
/tupload
http://file1.zip

/tupload
http://file2.zip

/tupload
http://file3.zip

All 3 download simultaneously! ✅
```

### Example 2: Mix Different Services
```
/tupload
http://direct-download.zip

/ytupload
https://youtube.com/watch?v=abc

/igupload
https://instagram.com/p/xyz

All run at the same time! ✅
```

### Example 3: Track Multiple Tasks
The bot shows a dashboard:
```
📊 ACTIVE TASKS (3)
━━━━━━━━━━━━━━━━━━

🔹 Task abc123 (/tupload)
   └─ file1.zip (45% - 3.2 MB/s)

🔹 Task def456 (/ytupload)
   └─ YouTube Video (67% - 1.8 MB/s)

🔹 Task ghi789 (/igupload)
   └─ Instagram Post (23% - 2.1 MB/s)
```

---

## 🎯 Key Features

### Parallel Execution
- ✅ Run unlimited tasks simultaneously
- ✅ Each task has unique ID
- ✅ Individual progress tracking
- ✅ Independent cancellation
- ✅ Error isolation (one fails, others continue)

### Enhanced UI
- ✅ Beautiful progress bars
- ✅ Clean status updates
- ✅ Professional menus
- ✅ Customizable styles

### Reliability
- ✅ Auto-retry on failures
- ✅ Resume support (where available)
- ✅ Comprehensive error handling
- ✅ Detailed logging

---

## 📖 Learn More

### Parallel Tasks
- **[Quick Start](docs/features/parallel-tasks/PARALLEL_UPLOAD_QUICK_START.md)** - User guide
- **[Parallel vs Queue](docs/features/parallel-tasks/PARALLEL_VS_QUEUE_EXPLAINED.md)** - How it works
- **[All Commands Guide](docs/features/parallel-tasks/ALL_COMMANDS_PARALLEL_COMPLETE.md)** - Complete reference
- **[Implementation Summary](docs/features/parallel-tasks/TODAYS_ACCOMPLISHMENTS.md)** - Technical details

### UI Components
- **[UI Guide](docs/features/ui-upgrade/UI_COMPONENTS_GUIDE.md)** - Complete reference
- **[Quick Examples](docs/features/ui-upgrade/QUICK_EXAMPLES.py)** - Code snippets
- **[Migration Guide](docs/features/ui-upgrade/MIGRATION_EXAMPLES.md)** - Upgrade existing code

### Development
- **[Architecture](docs/development/ARCHITECTURE.md)** - System design
- **[Contributing](docs/development/CONTRIBUTING.md)** - How to contribute
- **[Roadmap](docs/ROADMAP.md)** - Future plans

---

## 🆘 Troubleshooting

### "ModuleNotFoundError"
**Fix:** Install dependencies
```bash
pip install -r requirements.txt
```

### "Already working!" message still appears
**Fix:** Make sure you're using the new parallel commands:
- Use: `/tupload` ✅
- Not: Old blocking commands ❌

### Bot not responding
**Fix:** Check logs for errors
```bash
python -m colab_leecher
# Watch the console output
```

### Need Help?
- Check **[docs/](docs/)** folder
- Review bot logs
- Open GitHub issue

---

## 🎊 Enjoy!

**Start using parallel uploads today!**

```bash
# Run the bot
python -m colab_leecher

# In Telegram
/tupload
<your link>

/tupload  # Start another!
<another link>

# Both run simultaneously! 🎉
```

---

**Questions?** Check the [documentation](docs/) or open an issue!

**Happy leeching!** 🚀
