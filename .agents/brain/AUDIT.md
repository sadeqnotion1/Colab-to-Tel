# AUDIT.md — Audit queue (code-grounded)

> Deep-audit pass. Each item now cites the **real code** in `sadeqnotion1/Colab-to-Tel`
> (function names, the exact template/flow, and the root cause), plus a concrete fix plan.
> File/line pointers are from a read-only GitHub read on 2026-06-24; **code wins** — re-confirm before editing.
>
> Status: 🔍 to-audit · 🧪 audited→ready-to-fix · ⚠️ partially-audited · ✅ done · ❄️ deferred
> Sources read this pass: `ytdl.py`, `manager.py`, `aliases.py`, `uploader/telegram.py`,
> `utility/ui_copy.py`, `utility/handler.py`, `utility/converters.py` (prior), and `utility/task_dashboard.py` (2026-06-24 follow-up read).

---

## A1 — yt-dlp naming: nonsense for no-title sites + date is a PREFIX  🧪 ready-to-fix
**Reported:** Non-rich sites produce garbage names; YouTube files **start** with the date instead of ending with it.
**Confirmed in `colab_leecher/downlader/ytdl.py` → `YouTubeDL()`:**
```python
base_template     = f"{down_path}/%(upload_date>%Y-%m-%d,unknown_date)s_%(title,id).120B.%(ext)s"
fallback_template = f"{down_path}/%(id).150B.%(ext)s"
thumb_template    = f"{thumbnail_ytdl}/%(id).150B.%(ext)s"
```
and the playlist branch reuses `"%(title,id).120B.%(ext)s"`.
**Root cause:**
1. **Date is prefixed**: `%(upload_date...)s_` → `2026-06-24_Title.mp4`. Sites without `upload_date` literally get `unknown_date_...`.
2. **No-title fallback is `id`**: `%(title,id)` → when no title, the bare video id is used (`dQw4w9WgXcQ.mp4`).
3. **`fallback_template` is pure `%(id)`** and is swapped in on retry → worst-case nonsense names.
**Fix plan:**
- Move date to a suffix and stop emitting `unknown_date`: `%(title,id)s [%(upload_date>%Y-%m-%d)s].%(ext)s` (drop the ` []` when no date).
- Richer no-title chain: `%(title,fulltitle,track,alt_title,uploader,id)s`.
- Apply the same template to single, playlist, and `fallback_template`.
**Effort:** S (template strings only). **Risk:** low (cosmetic, no pipeline change).

## A2 — NZBcloud forces manual `TITLE=`; no real-name auto-resolve  🧪 ready-to-fix
**Reported:** With an nzbcloud link there's no option to pick the file's real name.
**Confirmed:**
- `manager.py → nzbcloud_download(urls, filenames, task_ctx)` *requires* a parallel `filenames` list
  (`if len(urls) != len(filenames): cancelTask(...)`) and downloads via `aria2_Download(url, i+1, file_name)`.
- `ui_copy.py → build_nzbcloud_prompt()` hard-requires the format `TITLE=filename.mkv` + URL.
- Auto-resolution helpers exist but aren’t used here: `extract_filename_from_url`, `build_filename_option_prompt`,
  `build_manual_filenames_prompt` (used by other services). `converters.py` even prioritizes `TITLE=` names for archive naming.
**Root cause:** nzbcloud has **only** the manual `TITLE=` path; it never does a Content-Disposition / HEAD lookup,
  so the user must hand-type names. (The `play?token=...` URLs carry no name in the path.)
**Fix plan:**
- Add a name-resolution step for nzbcloud: HEAD request (reuse the `curl_cffi`/`cf_clearance` approach from
  root `nzb_pc_downloader.py`) → read `Content-Disposition: filename=` → offer it via `build_filename_option_prompt`
  (“Use detected name” vs “Type your own”), same UX other services already have.
**Effort:** M. **Risk:** medium (depends on nzbcloud returning a usable header behind Cloudflare).

## A3 — task_manager / Telegram dashboard logic  🧪 ready-to-fix (dashboard now audited)
**Reported:** task_manager Telegram UI logic isn’t the best.
**Confirmed in `colab_leecher/utility/task_dashboard.py → update_summary_dashboard()`:**
- **Two different bar renderers inside one dashboard:** page 0 (Global list) uses `_progress_bar()` → `ProgressBar.generate(pct, 10, "ascii")` wrapped in `[...]`; the detail pages use `ProgressBar.generate(pct, length=16, style=BAR_STYLE)` (gradient). So one task shows a 10-char ASCII bar on the list and a 16-char gradient bar on its own page — inconsistent by design.
- **`0% / Unknown` upload bug — exact branch:** in the upload view, `if ts <= 0 or ts < u_bytes:` it falls back to `current_file_size`; when that is `0` → `percentage = 0.0, total_str = "Unknown"`. That is exactly the “0% / Unknown” on split-part uploads (total_size isn’t known before each part starts).
- **Archiving bar stuck at 0% — exact branch:** the archiving view uses `task_ctx.transfer.get_percentage()`, and only if that’s `0.0` falls back to `files_processed/total_files`. If the archiver reports neither, it sits at 0% (precisely what the delivered `archive_progress.py` poller fixes).
- **Percentage computed differently per page:** page 0 uses `base = up or down; base/ts*100` with **no** current_file_size fallback, while the detail page has the cfs fallback → the same task can read 0% on the list but a real % on its detail page.
- **Throttle/debounce constants are scattered:** `should_update_summary()`, `min_forced_update_interval`, a 2.0s window in `force_update_summary`, and a `_ui_suspended_until` FloodWait guard — each owns its own timing, so edits can still race.
- **A 4th progress coordinator confirmed:** this file does `get_progress_manager().subscribe(try_update_summary)` at import. So on top of `Issues/mimo.txt`’s three (helper.py / progress_dispatcher.py / task_dashboard.py) there is also `progress_manager` feeding it — the dashboard is downstream of all of them.
- **Global thumbnail again (ties A5/A6):** dashboard thumb = `BOT.Setting.thumbnail` + `Paths.THMB_PATH` (global) → first task’s `hero_image` → `Paths.DEFAULT_HERO`; a multi-task dashboard can’t show a per-task thumb.
**Root cause:** there is no single status model — each stage (download/archive/upload) and each page recomputes %/total/bar independently, fed by 4 progress producers and gated by several independent timers.
**Fix plan:** (1) one `render_progress(task_ctx, page)` helper so list and detail agree; (2) one `BAR_STYLE` everywhere (drop the ascii/gradient split); (3) fix `Unknown` by setting `current_file_size` before each part upload; (4) collapse the 4 producers into the single ProgressManager source (the M2 unification milestone); (5) one debounce owner. Pairs with the delivered archive/upload-progress package.
**Effort:** L. **Risk:** high (this *is* the M2 progress-unification milestone). **Status:** fully audited — ready to schedule under M2.

## A4 — `/nimbaha` mode: force every output part <1GB (hard external limit)  🧪 ready-to-fix (design clear)
**Reported:** An upstream bot only accepts links if each file is <1GB; want a regular/aria-like mode that guarantees parts <1GB.
**Confirmed how splitting works today:**
- `uploader/telegram.py → upload_file()` “Safety Net”: `max_split_size_bytes = helper.get_max_split_size_mib()*1024*1024`;
  if a file exceeds it, calls `converters.sizeChecker(file_path, remove=True)` then uploads each part.
- `handler.py → Leech()` also force-splits dir files >limit via `sizeChecker`, and already detects `.001` and gathers
  `re.search(r'\.[0-9]{3}$', f)` parts.
**Root cause / insight:** the split threshold is **`get_max_split_size_mib()`** (sized to Telegram’s 2GB/4GB limit), not to the user’s 1GB rule.
**Fix plan:**
- Register `/nimbaha` in `aliases.py` (clone the `/leech` handler: `BOT.Mode.mode="leech"`, `service_type=None` for auto-detect).
- Add an override flag (e.g. `BOT.Options.force_split_mib = 990`) and make `helper.get_max_split_size_mib()` return
  `min(telegram_limit, force_split_mib)` when set → the existing sizeChecker pipeline then guarantees <1GB parts everywhere.
- Use 990MB (not 1000) for safety; document `-mx=0` (store) so splitting is fast.
**Effort:** M. **Risk:** low–medium (reuses existing splitter; just changes the threshold + adds a command).

## A5 — Multitasking clobber: global `BOT.Mode/Options/Setting` shared across tasks  🧪 ready-to-fix (root cause found)
**Reported:** Running a torrent then a yt-dlp download causes problems.
**Confirmed root cause:**
- Every command in `aliases.py` mutates **global singletons**: `BOT.Mode.mode`, `BOT.Mode.ytdl`, `BOT.Options.service_type`
  (from `utility/variables.BOT`).
- A per-task system exists and is *partly* wired: `TaskContext` carries isolated `paths/messages/error/transfer/bot/msg`,
  and `TASK_QUEUE` tracks multiple tasks (`handler.py`, `telegram.py` already branch on `task_ctx`).
- **But** read-side settings stay global: `upload_file()` reads `BOT.Options.stream_upload`, `BOT.Setting.thumbnail`,
  `BOT.Setting.prefix/suffix`, `Paths.THMB_PATH` even when `task_ctx` is passed.
**Why it breaks:** starting task B overwrites `BOT.Mode.*` / `BOT.Options.service_type` while task A is still running and
  still reads those globals → wrong mode/service/thumbnail/stream flag applied to A.
**Fix plan (pick one):**
- (a) **Isolate**: move `Mode/Options/Setting` into `TaskContext` and have intake snapshot them per task; or
- (b) **Serialize**: enforce a single active setup at intake (the code already has `build_task_in_progress_notice()` and a
  pending-task warning — make it authoritative until per-task isolation lands).
**Effort:** L (a) / S (b). **Risk:** high (a), low (b). **Recommend:** ship (b) as a guard now, schedule (a).

## A6 — Silent thumbnail failure (no user notice)  🧪 ready-to-fix
**Reported:** Maintainer uses a rotating per-post thumbnail playlist; if it fails the bot should say so.
**Confirmed in `uploader/telegram.py`:** thumbnail resolution is custom (`BOT.Setting.thumbnail` + `Paths.THMB_PATH`)
  → else `helper.get_video_thumbnail()` → else `Paths.DEFAULT_HERO`. Every failure path is **`log.warning` only** —
  nothing is surfaced to the user (e.g. “Thumbnail conversion failed … using default”).
**Note:** there is **no per-post playlist rotation** in this file — the bot uses a single `THMB_PATH`. So the user’s
  “playlist that changes per post” is an external concept that silently collapses to DEFAULT_HERO.
**Fix plan:** when a custom/playlist thumbnail can’t be applied (missing, convert fail, fallback to DEFAULT_HERO),
  send a one-line warning to the task chat. Optionally add real playlist-rotation support as a follow-up.
**Effort:** S (notice) / M (rotation). **Risk:** low.

## A7 — “Send links” prompt + command list don’t advertise full ability set  🧪 ready-to-fix
**Reported:** The reply for link-only sends doesn’t show everything the bot can do.
**Confirmed inconsistencies:**
- `ui_copy.build_link_prompt` advertises only `SUPPORTED_LINK_SOURCES = "Direct, Magnet, Telegram, Mega, Google Drive, Debrid, NZB, Bitso"` and a name/zip/unzip example — omits destination choice (GDrive vs Colab mirror), `/setname`, thumbnail, split, archive type.
- `build_ytdl_prompt()` is just `"Send link(s)\n https://link1.mp4"`.
- `build_start_welcome_text()` mentions only `/tupload /gdupload /drupload`.
- **Command-name drift:** `aliases.py` registers `/mirror /leech /ytdl /ig /nzbcloud /count /del /stats /status`, while
  `build_help_text()` lists `/tupload /gdupload /ytupload /igupload /tiktokbulk /drupload /mindvalley /nzb /settings ...`.
  The two surfaces disagree → real discoverability bug.
**Fix plan:** unify command names (alias both), enrich `build_link_prompt` with per-task options + a “what I can do” footer,
  and make `/start` + `/help` the single canonical capability list.
**Effort:** M. **Risk:** low.

## A8 — Forwarded media: no destination menu / no zip→extract→reupload  🧪 ready-to-fix (parts already exist)
**Reported:** Forwarded videos/files should offer GDrive / keep-in-Colab / (if zip) extract-in-Colab then upload contents.
**Confirmed building blocks already present:**
- `ui_copy.build_upload_destination_prompt()` already offers **Google Drive** vs **Local Mirror (`/content/Mirrored_Files`)**.
- `/drupload` leeches from a Colab folder path (`build_directory_path_prompt`).
- `handler.Unzip_Handler()` extracts `.rar/.zip/.7z/.tar/.gz/.001/.z01` (incl. multi-part RAR) into `temp_unzip_path`; `/extract` exists.
- `transfer_state.AWAITING_UPLOAD_DECISION` indicates an upload-decision state machine already exists.
- Forwarded Telegram media path: `manager.TelegramDownload` + `is_telegram`.
**Root cause:** the pieces aren’t wired to the **forward intake** — forwarding doesn’t pop a destination/unzip menu.
**Fix plan:** on forwarded media, show an action menu (Telegram · GDrive · Keep in Colab · Unzip→reupload) reusing
  `build_upload_destination_prompt` + `Unzip_Handler` + `Leech`; route zip → `Unzip_Handler` → `Leech(temp_unzip_path)`.
**Effort:** M–L. **Risk:** medium (intake routing).

## A9 — PC-env smoke tests for downloaders  🧪 ready-to-fix (precedent exists)
**Reported:** Some downloaders may be broken; a PC logic test would help (instagram.py, terabox.py, nzb…).
**Confirmed inventory (from `manager.py` imports + detectors):**
- Detectors: `is_google_drive, is_mega, is_terabox, is_doodstream, is_instagram, is_nzbcloud, is_ytdl_link, is_telegram, is_torrent, is_downloadly`.
- Services/handlers: `nzbcloud, Debrid, bitso, downloadly, ytdl, direct(auto)`; `TeraBoxDownloader`, `DoodStreamDownloader`,
  `instagram_download/instagram_profile_download`, `megadl`, `g_DownLoad`, `TelegramDownload`, `aria2_Download`,
  `sabnzbd_downloader`, `mindvalley`, `tiktok_bulk`.
- **Precedent:** root-level `nzb_pc_downloader.py` is already a standalone PC tester → the pattern works.
**Fix plan:** add `tools/smoke_downloaders.py` that, per source, runs **detect → metadata/HEAD only** (no Telegram, no full
  download) and prints pass/fail + reason (auth, impersonation, dead extractor). Start with instagram, terabox, nzbcloud, doodstream.
**Effort:** M. **Risk:** low (offline-safe, read-only).

## A10 — Catch-all (new findings surfaced during this audit)  🔍
- **Command-name drift** (A7) is its own bug worth a dedicated fix.
- **Per-task settings leak** (A5): `BOT.Setting.thumbnail/stream_upload/prefix/suffix` are global even with `task_ctx`.
- **Stub-page detection is HTTP-only**: `manager.http_download_logic` sniffs 10KB HTML error pages, but the aria2/nzbcloud
  path (`aria2_Download`) doesn’t get that protection → silent tiny-file “success” possible.
- **Deeply nested subtitle/429 retry ladder** in `ytdl.py` (4+ levels) — maintainability/refactor candidate.
- **3 competing progress systems** (`Issues/mimo.txt`) — ties to A3 + the delivered archive/upload-progress fix package.
- **Open PR** “Remove legacy colab_leecher bot pipeline” — needs maintainer decision (DECISIONS D-OPEN).
