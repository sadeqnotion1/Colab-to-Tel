# ROADMAP — ordered build plan

Build in order. Each milestone is small enough to finish in roughly one chat.
Don't start the next one until the current one's acceptance criteria pass.

> Repo: https://github.com/sadeqnotion1/Colab-to-Tel
> Every item maps to real Colab-to-Tel code — nothing invented.
> Mark the active milestone with **← NEXT**. Keep finished ones ✅ with a one-liner.

---

## ✅ M0 — Scaffold & brain
- `.agents/` brain installed from the CreateProject starter pack and filled for this repo (2026-06-24).

## 🟦 M1 — Fast 7z + honest progress + streaming upload  ← NEXT
- Integrate the drop-in fix: `utility/archive_progress.py` + `utility/streaming_archive.py` + anchored edits.
- Acceptance: faster store-mode 7z; archiving bar moves; per-part upload shows real %; `STREAM_ARCHIVE_UPLOAD=1` overlaps archive+upload; env-flag rollback intact.

## ⬜ M2 — Progress-system unification
- Collapse the 3 competing renderers (`helper.py` `status_bar`, `progress_dispatcher.py`, `task_dashboard.py`) into one source of truth.
- Reference: `Issues/mimo.txt`, `Issues/01_progress_system_unification.md`.
- Acceptance: a single renderer + one `BAR_STYLE`; download/archive/upload all use it; no duplicate/competing edits to the same Telegram message.

## ⬜ M3 — Pipeline decision: keep vs. remove `colab_leecher`
- Resolve the open PR "Remove legacy colab_leecher bot pipeline". Decide whether the bot stays (and these improvements land) or the repo narrows to `ytdl.py`.
- Acceptance: PR merged or closed with a recorded decision in DECISIONS.md.

## ⬜ M4 — Polish
- Robust error/empty-state handling around archive/upload; cleaner Colab setup cell; doc refresh.

## Backlog / maybe-later
- Parallel/concurrent uploads of independent split sets.
- Resume/retry on Telegram flood-wait.
- Configurable split size from the setup cell.

## 🔎 Audit queue (code-grounded) — deep pass 2026-06-24

Status: 🧪 ready-to-fix · ⚠️ partial · 🔍 to-audit

- [ ] **A1** 🧪 yt-dlp template: date as suffix (not `unknown_date_` prefix) + better no-title fallback — `ytdl.py YouTubeDL()` (effort S)
- [ ] **A2** 🧪 NZBcloud real-name auto-resolve (HEAD/Content-Disposition) vs forced `TITLE=` — `manager.nzbcloud_download`, `build_nzbcloud_prompt` (M)
- [ ] **A3** ⚠️ task dashboard logic — audited copy/queue; `task_dashboard.py` + progress unification pending (rate-limited) (L)
- [ ] **A4** 🧪 `/nimbaha` mode: add cmd + `force_split_mib=990` so `get_max_split_size_mib()` guarantees <1GB parts — `aliases.py`, `telegram.upload_file`, `handler.Leech` (M)
- [ ] **A5** 🧪 multitasking clobber: global `BOT.Mode/Options/Setting` shared across tasks — isolate into `TaskContext` or serialize intake (L/S)
- [ ] **A6** 🧪 notify on thumbnail failure (currently `log.warning` only → silent DEFAULT_HERO) — `uploader/telegram.py` (S)
- [ ] **A7** 🧪 enrich link prompt + fix command-name drift (`/leech` vs `/tupload`) — `ui_copy.py`, `aliases.py` (M)
- [ ] **A8** 🧪 forwarded media menu: GDrive / Colab / unzip→reupload (parts exist: `build_upload_destination_prompt`, `Unzip_Handler`, `Leech`) (M/L)
- [ ] **A9** 🧪 PC smoke tests for downloaders (detect→metadata only) — precedent: root `nzb_pc_downloader.py` (M)
- [ ] **A10** 🔍 catch-all: command drift, per-task settings leak, aria2 stub-detection gap, nested ytdl retry ladder, progress unification, open PR


