"""
Controller bot — a SECOND Telegram bot (own BotFather token) running in the
same process/event loop as the leecher bot.

Why in-process: Telegram bots cannot see or message other bots, so the
controller drives the engine as a library (controller.headless), not over
Telegram. Both bots share TASK_QUEUE, so /status, /cancel, /pause see
everything — including tasks started via the leecher's own UI.

Credentials: add "CONTROL_BOT_TOKEN" to credentials.json (API_ID/API_HASH are
reused from the existing config).
"""
from __future__ import annotations

import logging

from pyrogram import Client, filters
from pyrogram.types import Message

log = logging.getLogger(__name__)

HELP_TEXT = (
    "**Colab-to-Tel Controller**\n\n"
    "`/auto <link> [link…]` — start a leech task (magnet / direct URL)\n"
    "`/zip <link> [link…]` — same, but compress before upload\n"
    "`/status` — active tasks with progress\n"
    "`/cancel <task_id>` — cancel a task (8-char id from /status)\n"
    "`/pause` — stop admitting new tasks\n"
    "`/resume` — resume admitting tasks\n"
    "`/health` — system health summary\n\n"
    "Fully automatic mode: append links to `jobs.txt` in the repo root — "
    "the queue watcher picks them up within ~15s."
)


def build_control_bot() -> Client:
    """Create the controller Client and register its handlers."""
    from .. import API_HASH, API_ID, ConfigError, credentials, ensure_runtime_config

    ensure_runtime_config()
    token = credentials.get("CONTROL_BOT_TOKEN")
    if not token:
        raise ConfigError(
            "CONTROL_BOT_TOKEN is missing from credentials.json. "
            "Create a second bot with @BotFather and add its token "
            '("CONTROL_BOT_TOKEN": "123456:ABC-...").'
        )

    app = Client(
        "control_bot",
        api_id=int(API_ID),
        api_hash=str(API_HASH),
        bot_token=str(token),
        workers=4,
    )
    _register_handlers(app)
    return app


def _extract_links(message: Message) -> list:
    parts = (message.text or "").split(None, 1)
    if len(parts) < 2:
        return []
    return [
        tok
        for tok in parts[1].split()
        if tok.lower().startswith(("magnet:", "http://", "https://"))
    ]


def _register_handlers(app: Client) -> None:
    from .. import OWNER
    from ..utility.handler import cancelTask
    from ..utility.helper import sizeUnit
    from ..utility.task_context import TASK_QUEUE
    from .headless import TaskAdmissionError, submit_task

    owner_only = filters.private & filters.user(OWNER)

    @app.on_message(filters.command(["start", "help"]) & owner_only)
    async def _help(client, message):
        await message.reply_text(HELP_TEXT)

    async def _launch(message: Message, mode_type: str) -> None:
        links = _extract_links(message)
        if not links:
            await message.reply_text(
                "Usage: `/auto <magnet or direct URL> [more links…]`"
            )
            return
        try:
            ctx = await submit_task(links, mode_type=mode_type)
        except TaskAdmissionError as exc:
            await message.reply_text(f"⛔ Not started: {exc}")
            return
        except Exception as exc:
            log.exception("Controller failed to submit task")
            await message.reply_text(f"❌ Failed to start task: {exc}")
            return
        await message.reply_text(
            f"🚀 Task `{ctx.get_short_id()}` started — {len(links)} link(s), "
            f"type `{mode_type}`.\nUse /status to follow it."
        )

    @app.on_message(filters.command("auto") & owner_only)
    async def _auto(client, message):
        await _launch(message, "normal")

    @app.on_message(filters.command("zip") & owner_only)
    async def _zip(client, message):
        await _launch(message, "zip")

    @app.on_message(filters.command("status") & owner_only)
    async def _status(client, message):
        tasks = await TASK_QUEUE.get_all_tasks()
        if not tasks:
            await message.reply_text("💤 No active tasks.")
            return
        lines = []
        for ctx in tasks.values():
            if ctx.is_cancelled:
                state = "🚫 cancelled"
            elif ctx.is_completed:
                state = "✅ done"
            else:
                state = "▶️ running"
            name = ctx.messages.download_name or (
                ctx.source_urls[0][:48] if ctx.source_urls else "?"
            )
            try:
                progress = f"{ctx.transfer.get_percentage():.1f}% @ {sizeUnit(ctx.transfer.get_speed())}/s"
            except Exception:
                progress = "n/a"
            lines.append(f"`{ctx.get_short_id()}` {state} — {name}\n{progress}")
        await message.reply_text("\n\n".join(lines))

    @app.on_message(filters.command("cancel") & owner_only)
    async def _cancel(client, message):
        parts = (message.text or "").split()
        if len(parts) != 2:
            await message.reply_text("Usage: `/cancel <task_id>` (see /status)")
            return
        short_id = parts[1].strip()
        tasks = await TASK_QUEUE.get_all_tasks()
        ctx = next(
            (c for c in tasks.values() if c.get_short_id() == short_id), None
        )
        if ctx is None:
            await message.reply_text(f"🤷 No active task `{short_id}`.")
            return
        await cancelTask("Cancelled via controller bot", task_ctx=ctx)
        await message.reply_text(f"🛑 Cancellation requested for `{short_id}`.")

    @app.on_message(filters.command("pause") & owner_only)
    async def _pause(client, message):
        TASK_QUEUE.paused = True
        await message.reply_text(
            "⏸ Queue paused — new tasks will be refused until /resume. "
            "Running tasks continue."
        )

    @app.on_message(filters.command("resume") & owner_only)
    async def _resume(client, message):
        TASK_QUEUE.paused = False
        await message.reply_text("▶️ Queue resumed — new tasks are admitted again.")

    @app.on_message(filters.command("health") & owner_only)
    async def _health(client, message):
        await message.reply_text(TASK_QUEUE.get_health_summary())
