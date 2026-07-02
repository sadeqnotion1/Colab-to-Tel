"""
Controller package — Option A: two bots, one process.

- headless.py      submit tasks straight to the engine (no Telegram UI flow)
- control_bot.py   second Pyrogram bot (own BotFather token) that drives the workflow
- queue_watcher.py polls jobs.txt so anything (scripts, Seedr2TG, cron) can enqueue work

Entry point: python -m colab_leecher.run_with_controller
"""
