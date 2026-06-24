# STATE — where we are right now

> Single source of truth. If this disagrees with the real code, the **code wins** —
> tell me and I'll fix the brain. Repo: https://github.com/sadeqnotion1/Colab-to-Tel

**Status (one-liner):** Working Colab Telegram leech bot. `.agents/` brain just installed from the CreateProject starter pack. Active focus: integrate + verify the delivered **"Fast 7z + Honest Progress + Streaming Upload"** fix, then unify the competing progress systems.

## Status table

| Part | Status | Notes |
|---|---|---|
| Download (aria2c / yt-dlp) | ✅ | `colab_leecher/downlader/aria2.py`, `ytdl.py`. Working. |
| 7z archive + split | ✅ | `utility/converters.py` `archive()`. Works but **slow** (`-mx=1`, no `-mmt`). |
| Telegram upload | ✅ | `uploader/telegram.py` `upload_file(path, display_name, task_ctx)`. Working. |
| Progress dashboard | ⚠️ | 3 competing renderers (`helper.py`, `progress_dispatcher.py`, `task_dashboard.py`) per `Issues/mimo.txt`; archiving bar stuck at 0%, split-upload bar shows `0% / Unknown`, mixed styles. |
| Fast 7z + honest progress + streaming upload fix | 🟦 | Drop-in package authored (2 new files + anchored edits, env-gated). **Not yet integrated/verified** in the repo. |
| `.agents/` brain | ✅ | This system (installed 2026-06-24). |
| Knowledge graph | 🟦 | Seeded in `graph/graph.json` from known modules; refine as code is read. |

> Legend: ✅ done · 🟦 in progress · ⚠️ known issue · ⬜ not started.

## Known issues / risks
- **3 progress systems fighting over one message** (`Issues/mimo.txt`, `Issues/01_progress_system_unification.md`). Root cause of the "ugly bar" + missing archive/upload progress.
- **Archiving is slow** — `-mx=1` compression on already-compressed torrent media, single-threaded.
- **Upload waits for ALL split volumes** before starting (fully sequential pipeline).
- **Open PR** "Remove legacy colab_leecher bot pipeline" (theSadeQ, 2026-06-13) proposes deleting the whole `colab_leecher/` package. Conflicts with the active improvement work — needs a maintainer decision (see DECISIONS.md D-OPEN).
- Runs in Colab and reads `credentials.json` — keep secrets out of logs/commits.
