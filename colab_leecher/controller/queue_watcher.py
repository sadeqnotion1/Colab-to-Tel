"""
Job-queue watcher — lets ANYTHING enqueue work for Colab-to-Tel without
touching Telegram: scripts, cron, or the Seedr2TG pipeline can simply append
magnet/direct links to `jobs.txt` at the repo root (one per line).

The watcher claims all pending lines every POLL_SECONDS, submits each line as
its own task via controller.headless, and puts lines back if the queue refuses
them (so they retry on the next cycle). Comment lines (#) are ignored.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

# <repo root>/jobs.txt  (this file lives at colab_leecher/controller/)
JOBS_FILE = Path(__file__).resolve().parents[2] / "jobs.txt"
POLL_SECONDS = 15

_HEADER = (
    "# Colab-to-Tel job queue\n"
    "# One magnet or direct link per line. Lines are consumed automatically.\n"
)


def _parse_jobs(text: str) -> List[str]:
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _put_back(jobs: List[str]) -> None:
    """Re-append refused jobs so they are retried on the next poll."""
    if not jobs:
        return
    with JOBS_FILE.open("a", encoding="utf-8") as fh:
        for job in jobs:
            fh.write(job + "\n")


async def queue_watcher(notify_client=None) -> None:
    """Run forever; cancel the task to stop. `notify_client` (the controller
    bot) is used to tell the OWNER when jobs are picked up or refused."""
    from .. import OWNER
    from .headless import TaskAdmissionError, submit_task

    async def _notify(text: str) -> None:
        if notify_client is None:
            return
        try:
            await notify_client.send_message(OWNER, text)
        except Exception as exc:
            log.warning("queue_watcher: could not notify owner: %s", exc)

    if not JOBS_FILE.exists():
        JOBS_FILE.write_text(_HEADER, encoding="utf-8")
        log.info("Created empty job queue at %s", JOBS_FILE)

    log.info("Queue watcher polling %s every %ss", JOBS_FILE, POLL_SECONDS)
    while True:
        try:
            jobs = _parse_jobs(JOBS_FILE.read_text(encoding="utf-8"))
            if jobs:
                # Claim all pending jobs by resetting the file first.
                JOBS_FILE.write_text(_HEADER, encoding="utf-8")
                for index, job in enumerate(jobs):
                    try:
                        ctx = await submit_task([job])
                    except TaskAdmissionError as exc:
                        # Queue is full/paused: put this + remaining back.
                        _put_back(jobs[index:])
                        log.info(
                            "queue_watcher: admission refused (%s); "
                            "%d job(s) returned to jobs.txt",
                            exc, len(jobs) - index,
                        )
                        await _notify(
                            f"⏳ jobs.txt: {len(jobs) - index} job(s) waiting — {exc}"
                        )
                        break
                    except Exception as exc:
                        log.exception("queue_watcher: job failed to submit")
                        await _notify(f"❌ jobs.txt job failed to submit: {exc}\n{job[:100]}")
                    else:
                        await _notify(
                            f"🤖 jobs.txt → task `{ctx.get_short_id()}`\n{job[:100]}"
                        )
        except asyncio.CancelledError:
            log.info("Queue watcher stopped.")
            raise
        except Exception:
            log.exception("queue_watcher: poll cycle failed (will retry)")
        await asyncio.sleep(POLL_SECONDS)
