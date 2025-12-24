#!/usr/bin/env python3
"""
Debug script to test /ig command handler
Run this in Colab to see detailed logs of what's happening
"""

import logging
import asyncio
from pyrogram import filters

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
log = logging.getLogger(__name__)

async def debug_ig_command():
    """Test the /ig command handler with detailed logging"""
    try:
        log.info("=" * 60)
        log.info("DEBUG: Starting /ig command test")
        log.info("=" * 60)

        # Import the bot
        from colab_leecher import colab_bot
        from colab_leecher.utility.variables import BOT
        from colab_leecher.utility.task_manager import task_starter

        log.info("✓ Imports successful")
        log.info(f"  - colab_bot: {colab_bot}")
        log.info(f"  - BOT: {BOT}")
        log.info(f"  - task_starter: {task_starter}")

        # Check bot connection
        if colab_bot.is_connected:
            log.info("✓ Bot is connected to Telegram")
        else:
            log.error("✗ Bot is NOT connected!")
            return

        # Simulate the /ig command handler
        log.info("\nSimulating /ig command handler:")
        log.info("-" * 40)

        # Step 1: Set mode
        log.info("Step 1: Setting mode to 'leech'")
        BOT.Mode.mode = "leech"
        log.info(f"  ✓ BOT.Mode.mode = {BOT.Mode.mode}")

        # Step 2: Set ytdl
        log.info("Step 2: Setting ytdl to False")
        BOT.Mode.ytdl = False
        log.info(f"  ✓ BOT.Mode.ytdl = {BOT.Mode.ytdl}")

        # Step 3: Set service_type
        log.info("Step 3: Setting service_type to 'instagram'")
        BOT.Options.service_type = "instagram"
        log.info(f"  ✓ BOT.Options.service_type = {BOT.Options.service_type}")

        # Step 4: Prepare message text
        log.info("Step 4: Preparing message text")
        text = (
            "<b>📸 Instagram Leech » Send Me LINK(s) 🔗</b>\n\n"
            "**Supported:**\n"
            "• Individual Posts/Reels/IGTV\n"
            "• **ENTIRE PROFILES** (batch download)\n\n"
            "**Examples:**\n"
            "<code>https://instagram.com/username/</code> (all posts)\n"
            "<code>https://instagram.com/p/xyz</code> (single post)\n"
            "<code>https://instagram.com/reel/abc</code> (reel)"
        )
        log.info(f"  ✓ Message text prepared ({len(text)} characters)")

        # Step 5: Check task_starter function
        log.info("Step 5: Checking task_starter function")
        log.info(f"  - task_starter callable: {callable(task_starter)}")
        log.info(f"  - task_starter module: {task_starter.__module__}")

        log.info("\n" + "=" * 60)
        log.info("DEBUG TEST COMPLETE")
        log.info("=" * 60)
        log.info("\nIf you see this message, the imports and setup are working.")
        log.info("The issue is likely in task_starter() not sending the message.")
        log.info("\nNext steps:")
        log.info("1. Check if task_starter has any try-except blocks catching errors")
        log.info("2. Check if MSG.status_msg is initialized properly")
        log.info("3. Look for any asyncio/await issues")

    except Exception as e:
        log.error(f"\n❌ ERROR OCCURRED: {e}", exc_info=True)
        log.error("\nFull traceback above ↑")

if __name__ == "__main__":
    print("\n🔍 Running /ig command debug test...\n")
    asyncio.run(debug_ig_command())
    print("\n✓ Debug test finished. Check logs above for details.\n")
