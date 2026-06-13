  I'm working on a Telegram bot (Colab_Telegram_Leecher) that downloads files and sends them to users. The bot currently has three critical UI/UX issues:

  1. **Thumbnail photos are not showing** - When sending video/media files, thumbnails should be displayed but they're not appearing
  2. **Cancel buttons are not working** - Interactive keyboard buttons (like cancel/stop download buttons) are either not showing up or not responding when clicked
  3. **Formatted text is not displaying properly** - Messages that should have bold, italic, code blocks, or other Telegram formatting are showing as plain text or broken

  **Current Project Structure:**
  - Bot framework: Python with Pyrogram/Telethon (please check which one is used)
  - Main entry point: colab_leecher/__main__.py
  - Download manager: colab_leecher/downlader/manager.py
  - Message handlers: colab_leecher/utility/handler.py
  - Helper functions: colab_leecher/utility/helper.py
  - Task management: colab_leecher/utility/task_*.py files

  **What I need you to do:**

  1. **Analyze the codebase** - Examine the message sending functions, button creation, and thumbnail handling code
  2. **Identify root causes** - Determine why:
     - Thumbnails aren't being attached to media messages
     - InlineKeyboardMarkup or ReplyKeyboardMarkup buttons aren't rendering/responding
     - Parse_mode (HTML/Markdown) isn't being applied correctly
  3. **Provide specific fixes** - Show me exactly what code changes are needed in which files
  4. **Check for common issues** like:
     - Missing parse_mode parameter in send_message calls
     - Incorrect thumbnail path or file object handling
     - Button callback handlers not registered
     - Async/await issues in button handlers
     - File permissions or path issues for thumbnails

  Please review the relevant files and provide a detailed fix with code examples.