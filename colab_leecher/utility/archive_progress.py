"""Honest archive progress for the Telegram dashboard.

Fix #2 of the "Fast 7z + Honest Progress + Streaming Upload" delivery.

Why this exists
---------------
7z's own ``-bsp1`` percent only feeds the single-status code path. In
parallel / dashboard mode (``task_dashboard.py``) the archiving bar is computed
from ``files_processed / total_files`` which is ``0 / 1`` for a single archive,
so the bar sits at 0% the whole time.

This module implements the "size the files on disk" trick: while 7z runs it
periodically sums the bytes already written to the ``<name>.7z.00N`` split
volumes and maps that fraction onto the dashboard counters the renderer already
uses. No renderer changes are required.

Additive + reversible: nothing here runs unless ``start_archive_progress()`` is
called from ``archive()``. If ``task_ctx`` is ``None`` (single-task / legacy
mode) every function is a safe no-op.
"""

import asyncio
import logging
import os
from os import path as ospath

log = logging.getLogger(__name__)


async def _poll(archive_out_path, total_size, task_ctx, stop_evt):
    """Background loop: translate on-disk archive size -> dashboard percent."""
    if not task_ctx or total_size <= 0:
        return
    try:
        # Drive the existing dashboard "archiving" branch.
        task_ctx.messages.current_action = "archiving"
        task_ctx.messages.total_files = 100  # treat counters as a 0..100 scale
        task_ctx.messages.files_processed = 0
        while not stop_evt.is_set():
            produced = 0
            i = 1
            # Sum split volumes .001 .. .00N
            while True:
                vol = "{0}.{1:03d}".format(archive_out_path, i)
                if ospath.exists(vol):
                    try:
                        produced += os.path.getsize(vol)
                    except OSError:
                        pass
                    i += 1
                else:
                    break
            # Non-split fallback (single .7z with no volumes yet)
            if produced == 0 and ospath.exists(archive_out_path):
                try:
                    produced = os.path.getsize(archive_out_path)
                except OSError:
                    produced = 0
            pct = max(0, min(99, int(produced / total_size * 100)))
            task_ctx.messages.files_processed = pct
            await asyncio.sleep(2.0)
    except asyncio.CancelledError:
        raise
    except Exception as e:  # never let progress reporting break archiving
        log.debug("archive progress poller stopped: %s", e)


def start_archive_progress(archive_out_path, total_size, task_ctx):
    """Start the poller. Returns ``(task, stop_event)``.

    Always pair with ``finish_archive_progress(...)`` in a ``finally:`` block.
    """
    stop_evt = asyncio.Event()
    task = asyncio.create_task(
        _poll(archive_out_path, total_size, task_ctx, stop_evt)
    )
    return task, stop_evt


async def finish_archive_progress(task, stop_evt, task_ctx):
    """Stop the poller and snap the dashboard bar to 100%."""
    if stop_evt is not None:
        stop_evt.set()
    if task is not None:
        try:
            await task
        except Exception:
            pass
    if task_ctx:
        try:
            task_ctx.messages.files_processed = task_ctx.messages.total_files
        except Exception:
            pass
