#!/usr/bin/env python3
"""
Dual-bot launcher — leecher bot + controller bot in ONE process/event loop.

Use this INSTEAD of `python -m colab_leecher` when you want the controller:

    python -m colab_leecher.run_with_controller

Why this is safe: colab_leecher/__main__.py guards its startup under
`if __name__ == "__main__":`, so importing it here only registers the
decorated handlers on colab_bot — it does not call run(). Never run this
launcher and `python -m colab_leecher` at the same time (same bot token,
two sessions).
"""
from __future__ import annotations

import asyncio
import importlib
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
log = logging.getLogger("run_with_controller")


def _autodetect_sabnzbd() -> None:
    """Same optional SABnzbd auto-detection the classic entry point performs."""
    try:
        from .downlader.sabnzbd_downloader import set_sabnzbd_config
        from .utility.sabnzbd_autodetect import (
            auto_configure_sabnzbd,
            create_notification_file,
        )

        sabnzbd_config = auto_configure_sabnzbd()
        if sabnzbd_config:
            set_sabnzbd_config(sabnzbd_config)
            create_notification_file(sabnzbd_config, url_type="local")
            log.info("✅ SABnzbd auto-configured successfully")
        else:
            log.info("SABnzbd not detected - will use custom NNTP downloader")
    except Exception as exc:
        log.warning("SABnzbd auto-detection failed: %s", exc)


def main() -> int:
    from colab_leecher import ConfigError, colab_bot, ensure_runtime_config

    try:
        ensure_runtime_config()
    except ConfigError as config_err:
        log.critical("Bot configuration error: %s", config_err)
        return 1

    # Register ALL leecher handlers (guarded __main__: registers only).
    importlib.import_module("colab_leecher.__main__")

    from colab_leecher.controller.control_bot import build_control_bot
    from colab_leecher.controller.queue_watcher import queue_watcher

    try:
        control_bot = build_control_bot()
    except ConfigError as config_err:
        log.critical("Controller configuration error: %s", config_err)
        log.critical(
            'Add "CONTROL_BOT_TOKEN" to credentials.json, or start the classic '
            "entry point instead: python -m colab_leecher"
        )
        return 1

    _autodetect_sabnzbd()

    from pyrogram import idle

    async def _serve() -> None:
        from colab_leecher.utility.task_context import TASK_QUEUE

        await colab_bot.start()
        log.info("✅ Leecher bot started.")
        await control_bot.start()
        log.info("✅ Controller bot started.")

        watcher = asyncio.create_task(
            queue_watcher(notify_client=control_bot), name="jobs-queue-watcher"
        )
        log.info("✅ jobs.txt queue watcher started.")
        log.info("🚀 Both bots up. Press Ctrl+C to stop.")

        await idle()  # handles SIGINT/SIGTERM

        log.info("Shutting down…")
        watcher.cancel()
        try:
            await watcher
        except (asyncio.CancelledError, Exception):
            pass
        try:
            await TASK_QUEUE.shutdown()
        except Exception as exc:
            log.warning("TASK_QUEUE shutdown issue: %s", exc)
        await control_bot.stop()
        await colab_bot.stop()
        log.info("Clean shutdown complete.")

    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(_serve())
    except KeyboardInterrupt:
        log.info("Stopped by user (Ctrl+C).")
    except Exception as run_err:
        log.critical("Launcher crashed during run: %s", run_err, exc_info=True)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
