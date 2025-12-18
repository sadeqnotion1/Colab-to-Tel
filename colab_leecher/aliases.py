"""
Registers lightweight commands to reach feature parity without Docker:

- /mirror (/m)       -> same flow as your GDrive upload (prompt → mirror)
- /leech (/l)        -> same flow as your Telegram upload (prompt → leech)
- /ytdl  (/y)        -> same flow as your yt-dlp leech
- /ig (/instagram)   -> Instagram batch downloader (posts, reels, stories)
- /count             -> size of Drive link
- /del|/delete       -> delete Drive link
- /stats             -> CPU/RAM/Disk (psutil)

These avoid importing existing handlers to prevent circular imports and
instead replicate the tiny "set mode + prompt" logic those handlers use.
"""

import logging
from pyrogram import filters

from . import colab_bot
from .utility.variables import BOT
from .utility.task_manager import task_starter
from .utility.helper import sizeUnit
from .gdrive_utils import count_link, delete_link

log = logging.getLogger(__name__)


# ---- Aliases that mimic your existing prompts ----

@colab_bot.on_message(filters.command(["mirror", "m"]) & filters.private)
async def mirror_cmd(client, message):
    # mirror to Google Drive
    BOT.Mode.mode = "mirror"
    BOT.Mode.ytdl = False
    BOT.Options.service_type = None
    text = (
        "<b>♻️ Mirror Task » Send Me THEM LINK(s) 🔗</b>\n\n"
        "(Direct, Magnet, TG, Mega, GDrive, Debrid, NZB, bitso)\n\n"
        "<code>https//link1.xyz\n[name.ext]\n{zip_pw}\n(unzip_pw)</code>"
    )
    await task_starter(message, text)


@colab_bot.on_message(filters.command(["leech", "l"]) & filters.private)
async def leech_cmd(client, message):
    # leech to Telegram
    BOT.Mode.mode = "leech"
    BOT.Mode.ytdl = False
    BOT.Options.service_type = None
    text = (
        "<b>⚡ Leech Task » Send Me THEM LINK(s) 🔗</b>\n\n"
        "(Direct, Magnet, TG, Mega, GDrive, Debrid, NZB, bitso)\n\n"
        "<code>https//link1.xyz\n[name.ext]\n{zip_pw}\n(unzip_pw)</code>"
    )
    await task_starter(message, text)


@colab_bot.on_message(filters.command(["ytdl", "y"]) & filters.private)
async def ytdl_cmd(client, message):
    # yt-dlp flow
    BOT.Mode.mode = "leech"
    BOT.Mode.ytdl = True
    BOT.Options.service_type = "ytdl"
    text = (
        "<b>🏮 YTDL Leech » Send Me LINK(s) 🔗</b>\n\n"
        "<code>https//link1.mp4</code>"
    )
    await task_starter(message, text)


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
        BOT.Options.service_type = "instagram"

        log.info("  - Preparing message text")
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

        log.info("  - Calling task_starter()")
        await task_starter(message, text)
        log.info("  ✓ task_starter() completed")

    except Exception as e:
        log.error(f"  ❌ ERROR in /ig handler: {e}", exc_info=True)


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