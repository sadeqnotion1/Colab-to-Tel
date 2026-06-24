"""Overlap 7z archiving with Telegram upload (no waiting for all splits).

Fix #5 of the "Fast 7z + Honest Progress + Streaming Upload" delivery.

Why this exists
---------------
Today the pipeline is fully sequential: ``archive()`` writes EVERY ``.7z.00N``
volume, and only then does the leech loop in ``handler.py`` start uploading
them. For a tens-of-GB torrent that means a long dead wait with nothing going
to Telegram.

Because 7z writes split volumes **sequentially**, volume ``N`` is final the
moment volume ``N+1`` begins to exist. This watcher uploads each completed
volume as soon as the next one appears (then deletes it to bound disk usage),
and uploads the final volume after 7z exits. Compression of later volumes
overlaps with the upload of earlier ones.

Additive + reversible: only used when ``STREAM_ARCHIVE_UPLOAD=1``. The proven
sequential path stays intact as the default / fallback.

Wiring
------
Call ``stream_archive_upload(archive_out_path, proc_task, task_ctx)`` where:
  * ``archive_out_path`` is the base archive path (volumes are this + ".001"...)
  * ``proc_task``        is an ``asyncio`` awaitable for the running 7z process
                         e.g. ``asyncio.create_task(proc.wait())``
  * ``task_ctx``         is the active TaskContext (may be ``None``)
Returns ``True`` only if every produced volume uploaded successfully.

NOTE: ``upload_file`` is called positionally as
``upload_file(path, display_name, task_ctx)`` to match the repo's existing
positional call sites (see ``uploader/telegram.py`` safety-net and
``downlader/aria2.py``).
"""

import asyncio
import logging
import os
from os import path as ospath

from natsort import natsorted

log = logging.getLogger(__name__)


async def stream_archive_upload(archive_out_path, proc_task, task_ctx):
    """Upload .7z.00N volumes as they complete while 7z is still running."""
    from ..uploader.telegram import upload_file

    uploaded = set()
    idx = 1
    ok = True

    def part(i):
        return "{0}.{1:03d}".format(archive_out_path, i)

    async def push(i):
        nonlocal ok
        p = part(i)
        if p in uploaded or not ospath.exists(p):
            return
        # Feed Fix #3 so the per-part upload bar shows a real percent.
        if task_ctx is not None and getattr(task_ctx, "transfer", None) is not None:
            try:
                task_ctx.transfer.current_file_size = os.path.getsize(p)
            except OSError:
                pass
        log.info("[stream] uploading %s", ospath.basename(p))
        if not await upload_file(p, ospath.basename(p), task_ctx):
            ok = False
            return
        uploaded.add(p)
        # Free disk as soon as the part is safely uploaded.
        try:
            os.remove(p)
        except OSError:
            pass

    # --- While 7z runs: volume N is final once volume N+1 exists. ---
    while not proc_task.done():
        if ospath.exists(part(idx + 1)):
            await push(idx)
            idx += 1
        else:
            await asyncio.sleep(1.0)

    # Let 7z finish writing the final (in-progress) volume.
    try:
        await proc_task
    except Exception as e:
        log.warning("[stream] 7z process await failed: %s", e)

    # --- Flush any remaining volumes in natural order (incl. the last one). ---
    dname = ospath.dirname(archive_out_path)
    base = ospath.basename(archive_out_path)
    try:
        remaining = natsorted(
            f for f in os.listdir(dname)
            if f.startswith(base + ".") and f[-3:].isdigit()
        )
    except OSError:
        remaining = []
    for f in remaining:
        try:
            await push(int(f[-3:]))
        except ValueError:
            continue

    return ok
