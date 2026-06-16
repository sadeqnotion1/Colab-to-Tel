"""
Registers lightweight commands to reach feature parity without Docker:

- /mirror (/m)          -> same flow as your GDrive upload (prompt → mirror)
- /leech (/l)           -> same flow as your Telegram upload (prompt → leech)
- /ytdl  (/y)           -> same flow as your yt-dlp leech
- /ig (/instagram)      -> Instagram batch downloader (posts, reels, stories)
- /nzbcloud (/nzbc)     -> NZBcloud direct downloads (supports gist URLs)
- /count                -> size of Drive link
- /del|/delete          -> delete Drive link
- /stats                -> CPU/RAM/Disk (psutil)

These avoid importing existing handlers to prevent circular imports and
instead replicate the tiny "set mode + prompt" logic those handlers use.
"""

import logging
from pyrogram import filters

from . import colab_bot
from .utility.variables import BOT, _update_setup_session
from .utility.task_manager import task_starter
from .utility.helper import sizeUnit
from .utility.ui_copy import (
    build_instagram_prompt,
    build_link_prompt,
    build_nzbcloud_prompt,
    build_ytdl_prompt,
)
from .gdrive_utils import count_link, delete_link

log = logging.getLogger(__name__)


# ---- Aliases that mimic your existing prompts ----

@colab_bot.on_message(filters.command(["mirror", "m"]) & filters.private)
async def mirror_cmd(client, message):
    # mirror to Google Drive
    BOT.Mode.mode = "mirror"
    BOT.Mode.ytdl = False
    BOT.Options.service_type = None
    text = build_link_prompt("♻️ Mirror Task » Send link(s)")
    prompt_msg = await task_starter(message, text)
    if prompt_msg:
        try:
            await _update_setup_session(message.from_user.id, mode="mirror")
        except Exception as e:
            log.error(f"Failed to update setup session for mirror: {e}")


@colab_bot.on_message(filters.command(["leech", "l"]) & filters.private)
async def leech_cmd(client, message):
    # leech to Telegram
    BOT.Mode.mode = "leech"
    BOT.Mode.ytdl = False
    BOT.Options.service_type = None
    text = build_link_prompt("⚡ Leech Task » Send link(s)")
    prompt_msg = await task_starter(message, text)
    if prompt_msg:
        try:
            await _update_setup_session(message.from_user.id, mode="leech")
        except Exception as e:
            log.error(f"Failed to update setup session for leech: {e}")


@colab_bot.on_message(filters.command(["ytdl", "y"]) & filters.private)
async def ytdl_cmd(client, message):
    # yt-dlp flow
    BOT.Mode.mode = "leech"
    BOT.Mode.ytdl = True
    BOT.Options.service_type = "ytdl"
    text = build_ytdl_prompt()
    prompt_msg = await task_starter(message, text)
    if prompt_msg:
        try:
            await _update_setup_session(message.from_user.id, mode="leech", service_type="ytdl")
        except Exception as e:
            log.error(f"Failed to update setup session for ytdl: {e}")


@colab_bot.on_message(filters.command(["ig", "instagram"]) & filters.private)
async def instagram_cmd(client, message):
    # Instagram download flow
    log.info("🔍 DEBUG: /ig handler called")
    log.info(f"  - User: {message.from_user.id}")
    log.info(f"  - Chat: {message.chat.id}")

    try:
        log.info("  - Setting mode to 'leech'")
        BOT.Mode.mode = "leech"
        BOT.Mode.ytdl = False
        BOT.Options.service_type = "direct"  # Use 'direct' to trigger auto-detect (which detects Instagram)

        log.info("  - Preparing message text")
        text = build_instagram_prompt()

        log.info("  - Calling task_starter()")
        prompt_msg = await task_starter(message, text)
        if prompt_msg:
            try:
                await _update_setup_session(message.from_user.id, mode="leech", service_type="direct")
            except Exception as e:
                log.error(f"Failed to update setup session for instagram: {e}")
        log.info("  ✓ task_starter() completed")

    except Exception as e:
        log.error(f"  ❌ ERROR in /ig handler: {e}", exc_info=True)


@colab_bot.on_message(filters.command(["nzbcloud", "nzbc"]) & filters.private)
async def nzbcloud_cmd(client, message):
    # NZBcloud download flow
    log.info(f"🔍 /nzbcloud handler called from {message.from_user.id}")

    try:
        log.info("  - Setting mode to 'leech'")
        BOT.Mode.mode = "leech"
        BOT.Mode.ytdl = False
        BOT.Options.service_type = "nzbcloud"  # Set service type directly

        log.info("  - Preparing message text")
        text = build_nzbcloud_prompt()

        log.info("  - Calling task_starter()")
        prompt_msg = await task_starter(message, text)
        if prompt_msg:
            try:
                await _update_setup_session(message.from_user.id, mode="leech", service_type="nzbcloud")
                log.info("  ✓ Setup session initialized for NZBcloud")
            except Exception as e:
                log.error(f"Failed to update setup session for nzbcloud: {e}")
        log.info("  ✓ task_starter() completed")

    except Exception as e:
        log.error(f"  ❌ ERROR in /nzbcloud handler: {e}", exc_info=True)


@colab_bot.on_message(filters.command("count") & filters.private)
async def count_cmd(client, message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("Usage: /count <GDrive link>", quote=True)
        return
    link = args[1].strip()
    size = await count_link(link)
    if size < 0:
        await message.reply_text("Failed to fetch size. Check the link and try again.", quote=True)
    else:
        await message.reply_text(f"📦 Size: {sizeUnit(size)}", quote=True)


@colab_bot.on_message(filters.command(["del", "delete"]) & filters.private)
async def del_cmd(client, message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.reply_text("Usage: /del <GDrive link>", quote=True)
        return
    link = args[1].strip()
    ok = await delete_link(link)
    await message.reply_text("✅ Deleted from Drive." if ok else "❌ Failed to delete from Drive.", quote=True)


@colab_bot.on_message(filters.command("stats") & filters.private)
async def stats_cmd(client, message):
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        vm = psutil.virtual_memory()
        du = psutil.disk_usage("/")
        text = (
            "⚙️ <b>System Stats</b>\n\n"
            f"CPU: <code>{cpu:.1f}%</code>\n"
            f"RAM: <code>{sizeUnit(vm.used)}/{sizeUnit(vm.total)}</code>\n"
            f"Disk: <code>{sizeUnit(du.used)}/{sizeUnit(du.total)}</code>"
        )
        await message.reply_text(text, quote=True)
    except Exception:
        log.exception("Stats command failed")
        await message.reply_text("Failed to fetch system stats.", quote=True)


@colab_bot.on_message(filters.command("status") & filters.private)
async def status_cmd(client, message):
    # Force dashboard to bottom
    from .utility.task_dashboard import update_summary_dashboard
    from .utility.task_context import TASK_QUEUE
    
    tasks = await TASK_QUEUE.get_all_tasks()
    if not tasks:
        await message.reply_text("❌ No active tasks found.", quote=True)
        return
        
    await message.delete() # Delete user command
    await update_summary_dashboard(client, force=True, move_to_bottom=True)
