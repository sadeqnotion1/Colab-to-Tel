# Contributing to Telegram-Leecher

Thank you for your interest in contributing to Telegram-Leecher! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Development Setup](#development-setup)
3. [Code Standards](#code-standards)
4. [Adding New Features](#adding-new-features)
5. [Testing](#testing)
6. [Submitting Changes](#submitting-changes)
7. [Code Review Process](#code-review-process)

---

## Getting Started

### Prerequisites

- Python 3.8+
- Git
- Telegram account and API credentials
- Basic understanding of async/await in Python
- Familiarity with Pyrogram library

### Fork and Clone

```bash
# Fork the repository on GitHub first, then:
git clone https://github.com/YOUR_USERNAME/Telegram-Leecher.git
cd Telegram-Leecher
```

---

## Development Setup

### Local Development

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install additional tools:**
   ```bash
   # For Mindvalley support
   bash install_mindvalley_deps.sh

   # For local testing
   apt-get install ffmpeg aria2  # Linux
   brew install ffmpeg aria2      # macOS
   ```

3. **Configure credentials:**
   ```bash
   cp credentials.json.example credentials.json
   # Edit credentials.json with your API credentials
   ```

4. **Run the bot:**
   ```bash
   python run_bot_local.py
   ```

### Google Colab Development

1. Upload `colab/setup_cell.py` to a Colab notebook
2. Fill in credentials in the form
3. Run the cell to install and start the bot
4. Test your changes in Colab environment

---

## Code Standards

### Python Style Guide

We follow PEP 8 with some modifications:

- **Indentation**: 4 spaces (no tabs)
- **Line length**: 100 characters (120 for long URLs/strings)
- **Naming conventions**:
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_CASE` for constants

### Async/Await

Always use async functions for I/O operations:

```python
# ✅ Good
async def download_file(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.read()

# ❌ Bad
def download_file(url):
    response = requests.get(url)  # Blocking I/O
    return response.content
```

### Logging

Use the logging module, not print():

```python
import logging
log = logging.getLogger(__name__)

# ✅ Good
log.info("Download started")
log.error(f"Failed to download: {e}")

# ❌ Bad
print("Download started")
```

### Error Handling

Always handle exceptions gracefully:

```python
# ✅ Good
try:
    result = await download()
except DownloadError as e:
    log.error(f"Download failed: {e}")
    await update_progress_bar(0, "❌ Download failed")
    return False, None

# ❌ Bad
result = await download()  # Unhandled exception will crash bot
```

---

## Adding New Features

### Adding a New Downloader

Follow the standard downloader pattern:

1. **Create downloader file:**
   ```bash
   touch colab_leecher/downlader/myservice.py
   ```

2. **Implement downloader class:**
   ```python
   from colab_leecher.downlader.base import BaseDownloader

   class MyServiceDownloader(BaseDownloader):
       """Download files from MyService"""

       def __init__(self, client, message, task_ctx=None):
           super().__init__(client, message, task_ctx)
           self.service_name = "MyService"

       async def download(self, url, output_dir=None):
           """Main download method"""
           output_dir = output_dir or self.download_dir

           # Start progress tracking
           self.start_progress_tracking(stream_type="file")

           try:
               await self.update_progress_bar(0, "Starting download...")

               # Your download logic here
               # Use self.update_progress_bar() for progress updates

               await self.update_progress_bar(100, "Complete ✅")
               return True, output_path

           except Exception as e:
               log.error(f"Download failed: {e}")
               await self.update_progress_bar(self.current_percentage, "❌ Failed")
               return False, None
   ```

3. **Add URL detection:**

   In `colab_leecher/utility/helper.py`:
   ```python
   def is_myservice(url):
       """Check if URL is from MyService"""
       return "myservice.com" in url.lower()
   ```

4. **Add to manager.py:**

   In `colab_leecher/downlader/manager.py`:
   ```python
   from colab_leecher.utility.helper import is_myservice
   from colab_leecher.downlader.myservice import MyServiceDownloader

   # Add to routing logic
   if is_myservice(url):
       downloader = MyServiceDownloader(client, message, task_ctx)
       return await downloader.download(url)
   ```

5. **Add command handler:**

   In `colab_leecher/__main__.py`:
   ```python
   @colab_bot.on_message(filters.command("myservice"))
   async def myservice_command(client, message):
       """Handle /myservice command"""
       BOT.Mode.mode = "leech"
       BOT.Options.service_type = "myservice"

       text = "<b>📥 MyService Download » Send Me LINK(s) 🔗</b>"
       await task_starter(message, text)
   ```

6. **Update documentation:**
   - Add to `README.md` features list
   - Create `docs/features/MYSERVICE_GUIDE.md` if complex
   - Update `ARCHITECTURE.md` with any architectural changes

### Progress Bar Implementation

**CRITICAL**: All downloaders MUST maintain progress bar format throughout the download/upload cycle. See [CLAUDE.md](CLAUDE.md) for detailed requirements.

**Key Rules:**
1. Use `send_photo()` for initial status message (with thumbnail)
2. Update progress ONLY via `update_progress_bar()` or `status_bar()`
3. NEVER break format with intermediate text messages
4. Show completion as `100%` with checkmark and file size
5. Display errors in progress bar format at current percentage

**Example:**
```python
# ✅ CORRECT - Maintains progress bar format
await self.update_progress_bar(0, "Starting...")
await self.update_progress_bar(33.3, "Downloading...")
await self.update_progress_bar(66.7, "Downloading...")
await self.update_progress_bar(100, "Complete ✅ 250.5 MiB")

# ❌ WRONG - Breaks progress bar format
await message.reply_text("Starting download...")  # Don't do this!
await simple_message_update("Downloading...")     # Don't do this!
```

---

## Testing

### Unit Tests

Create tests in `tests/`:

```python
# tests/test_myservice.py
import pytest
from colab_leecher.downlader.myservice import MyServiceDownloader

@pytest.mark.asyncio
async def test_myservice_download():
    """Test MyService downloader"""
    # Your test here
    pass
```

Run tests:
```bash
pytest tests/
```

### Debug Scripts

Create debug scripts in `tests/debug/`:

```python
# tests/debug/debug_myservice.py
#!/usr/bin/env python3
"""Debug MyService downloader"""

async def test_myservice():
    # Debug code here
    pass

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_myservice())
```

### Manual Testing Checklist

Before submitting:

- [ ] Test download with valid URL
- [ ] Test with invalid URL (error handling)
- [ ] Test progress bar updates correctly
- [ ] Test thumbnail displays throughout
- [ ] Test completion shows 100% with file size
- [ ] Test error displays in progress bar format
- [ ] Test in both Colab and local environments
- [ ] Test with leech mode (Telegram upload)
- [ ] Test with mirror mode (GDrive upload)

---

## Submitting Changes

### Commit Guidelines

**Commit Message Format:**
```
Type: Brief description (50 chars max)

Detailed explanation if needed. Wrap at 72 characters.

- Bullet points for multiple changes
- Reference issues: Fixes #123
```

**Types:**
- `Feature:` New functionality
- `Fix:` Bug fix
- `Refactor:` Code reorganization without behavior change
- `Docs:` Documentation only
- `Test:` Adding or updating tests
- `Cleanup:` Removing obsolete code

**Examples:**
```
Feature: Add MyService downloader

Implements download support for MyService URLs with:
- URL detection in helper.py
- MyServiceDownloader class with progress tracking
- Command handler /myservice

Fixes #123
```

```
Fix: Mindvalley thumbnail not persisting

Changed status updates to use edit_caption() instead of
edit_text() to preserve thumbnail throughout download.
```

### Pull Request Process

1. **Create feature branch:**
   ```bash
   git checkout -b feature/myservice-downloader
   ```

2. **Make changes and commit:**
   ```bash
   git add .
   git commit -m "Feature: Add MyService downloader"
   ```

3. **Push to your fork:**
   ```bash
   git push origin feature/myservice-downloader
   ```

4. **Create Pull Request on GitHub:**
   - Clear title describing the change
   - Description with:
     - What was changed
     - Why it was changed
     - How to test it
   - Screenshots/GIFs if UI changes
   - Link to related issues

5. **Address review comments:**
   - Make requested changes
   - Push additional commits
   - Respond to reviewer questions

---

## Code Review Process

### What We Look For

**Functionality:**
- ✅ Feature works as described
- ✅ Edge cases handled
- ✅ Errors handled gracefully

**Code Quality:**
- ✅ Follows code standards
- ✅ No code duplication
- ✅ Clear variable/function names
- ✅ Appropriate use of async/await

**Documentation:**
- ✅ Docstrings for public functions/classes
- ✅ Comments for complex logic
- ✅ README/docs updated if needed

**Progress Bar Compliance:**
- ✅ Uses `BaseDownloader` if applicable
- ✅ Maintains progress bar format throughout
- ✅ Shows thumbnail consistently
- ✅ Follows standard progress bar pattern

### Review Timeline

- Initial review: Within 3-5 days
- Follow-up reviews: Within 2-3 days
- Merging: After approval from maintainer

---

## Development Tips

### Debugging

**Enable debug logging:**
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

**Use debug scripts:**
```bash
python tests/debug/instagram_debug.py --all
```

**Colab debugging:**
```python
# In Colab cell
!python tests/debug/debug_bot_startup.py
```

### Common Pitfalls

**1. Global State Issues**

❌ **Wrong:**
```python
# Multiple tasks will conflict!
MSG.status_msg = await client.send_message(...)
```

✅ **Right:**
```python
# Use task context for multi-task support
if task_ctx:
    task_ctx.status_msg = await client.send_message(...)
else:
    MSG.status_msg = await client.send_message(...)
```

**2. Breaking Progress Bar Format**

❌ **Wrong:**
```python
await message.reply_text("Download complete!")  # Breaks format!
```

✅ **Right:**
```python
await self.update_progress_bar(100, "Complete ✅ 250.5 MiB")  # Maintains format
```

**3. Blocking I/O**

❌ **Wrong:**
```python
with open(file, 'rb') as f:  # Blocks event loop!
    data = f.read()
```

✅ **Right:**
```python
async with aiofiles.open(file, 'rb') as f:
    data = await f.read()
```

---

## Getting Help

- **GitHub Issues**: Ask questions or report bugs
- **Discussions**: General discussions and feature requests
- **Documentation**: Check [ARCHITECTURE.md](ARCHITECTURE.md) and [CLAUDE.md](CLAUDE.md)

---

## License

By contributing, you agree that your contributions will be licensed under the GPL-3.0 License.

---

**Happy Contributing! 🎉**

For more information:
- [Architecture Overview](ARCHITECTURE.md)
- [Development Guidelines (Claude Code)](CLAUDE.md)
- [Project Roadmap](../ROADMAP.md)
