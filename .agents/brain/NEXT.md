# NEXT — the handoff card
_This is the FIRST thing to act on in a new chat (after the START prompt).
The AI rewrites this at the end of every session._

> Repo: https://github.com/sadeqnotion1/Colab-to-Tel

## ➡️ The one next task
**M1 — Integrate & verify "Fast 7z + Honest Progress + Streaming Upload".** Apply the
drop-in delivery (2 new files: `utility/archive_progress.py`, `utility/streaming_archive.py`
+ the anchored edits in its APPLY.md) onto one small test torrent. Confirm: 7z runs in
store mode faster, the archiving bar moves, each `.7z.00N` upload shows a real percent,
and — with `STREAM_ARCHIVE_UPLOAD=1` — the first volume uploads while later volumes are
still being written.

## Start the next chat with this
> "Integrate the Fast-7z/Honest-Progress/Streaming-Upload delivery into colab_leecher, one small torrent, verify all five fixes, keep the old behavior reachable by unsetting the env flags."

## What to paste / give me at the start
Pull these from the repo (or paste them):
1. `colab_leecher/utility/converters.py` — the real `archive()` body (subprocess creation + the `await proc.wait()` section) so the Fix #4/#5 anchors land exactly.
2. `colab_leecher/utility/task_dashboard.py` — the upload branch (for the `0% / Unknown` fix) and the `ProgressBar.generate(... style=...)` call.
3. `colab_leecher/utility/handler.py` — the leech upload loop (`items_to_process`) so streamed-and-removed parts are skipped.
4. The delivery package `Colab-to-Tel-archive-upload-fix.zip` (APPLY.md + the 2 new files).

## Decisions I need from you for this task
- Default `ARCHIVE_COMPRESSION` = `store` (fastest) or `fast` (old behavior)?
- Turn on `STREAM_ARCHIVE_UPLOAD=1` by default, or keep it opt-in for now?
- The open "remove colab_leecher" PR — are we keeping and improving the pipeline (this work assumes yes)?

## Definition of done for this task
- Bot still completes a normal download → archive → upload on a small torrent.
- 7z noticeably faster in store mode; archiving bar visibly moves (not stuck at 0%).
- Each split part upload shows a real percent (no `0% / Unknown`).
- With `STREAM_ARCHIVE_UPLOAD=1`, upload of part 1 starts before the last part is written; final file count matches the sequential run.
- Unsetting the env flags restores exact prior behavior. Verified live in Colab.
