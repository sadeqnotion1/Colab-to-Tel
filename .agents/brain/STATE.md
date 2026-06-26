# STATE — where we are right now

> Single source of truth. If this disagrees with the real code, the **code wins** —
> tell me and I'll fix the brain. Repo: https://github.com/sadeqnotion1/Colab-to-Tel

**Status (one-liner):** Working Colab Telegram leech bot. M1 and M2 code-complete in `master`. Active focus: live verification of unified progress and centralized `BAR_STYLE` in Google Colab, followed by M3 pipeline decision (keep vs. remove `colab_leecher`).

## Status table

| Part | Status | Notes |
|---|---|---|
| Download (aria2c / yt-dlp) | ✅ | `colab_leecher/downlader/aria2.py`, `ytdl.py`. Working. |
| 7z archive + split | ✅ | `utility/converters.py` `archive()`. Fast store-mode and streaming archive updates implemented. |
| Telegram upload | ✅ | `uploader/telegram.py` `upload_file(path, display_name, task_ctx)`. Working. |
| Progress dashboard | ✅ | Unified under `ProgressManager` and `task_dashboard`. Duplicated `BAR_STYLE` centralized in `bar_style.py`. |
| Fast 7z + honest progress + streaming upload fix | ✅ | Merged and verified in `master` (commit `ca319ec`). |
| YTDL 403 & Runtime Fixes | ✅ | Fixed AssertionError in download + name lookup, upgraded bootstrap to v3.2, and resolved HTTP 403 CDN errors (commit `99b7a1f`). |
| Instagram Profile & Post Downloader Hook | ✅ | Added instagrapi profile/post hooks, session cookie self-healing, request_timeout=15 override, clips_metadata v2 patch, parallel-task progress, and pause-and-resume rate limit handler (commit `9b4f83b`). |
| `.agents/` brain | ✅ | This system (installed 2026-06-24). |
| Knowledge graph | ✅ | Seeded in `graph/graph.json` and regenerated using render_graph.py. |

> Legend: ✅ done · 🟦 in progress · ⚠️ known issue · ⬜ not started.

## Known issues / risks
- **3 progress systems fighting over one message** (`Issues/mimo.txt`, `Issues/01_progress_system_unification.md`). Root cause of the "ugly bar" + missing archive/upload progress.
- **Archiving is slow** — `-mx=1` compression on already-compressed torrent media, single-threaded.
- **Upload waits for ALL split volumes** before starting (fully sequential pipeline).
- **Open PR** "Remove legacy colab_leecher bot pipeline" (theSadeQ, 2026-06-13) proposes deleting the whole `colab_leecher/` package. Conflicts with the active improvement work — needs a maintainer decision (see DECISIONS.md D-OPEN).
- Runs in Colab and reads `credentials.json` — keep secrets out of logs/commits.
