# DECISIONS — append-only architecture decision record (ADR)

> Append-only. Newest at the bottom. Each entry: id · date · decision · why.
> Never rewrite or delete past entries — supersede them with a new one.

---

### D1 — 2026-06-24 — Install the `.agents/` brain, authored clean
**Decision:** Bootstrap this repo with the CreateProject starter pack (`.agents/` brain + launcher), but author every brain file clean and grounded in the real Colab-to-Tel code.
**Why:** A prior instantiation (SMC-PSO) reported that some upstream template files carried obfuscated injected-instruction markers. We ignore those and write trusted, repo-grounded content instead.

### D2 — 2026-06-24 — 7z defaults to store mode, multithreaded, env-gated
**Decision:** `ARCHIVE_COMPRESSION` env flag selects `store` (`-mx=0`, default) / `fast` (`-mx=1`, old) / `normal` (`-mx=5`); add `-mmt=on`.
**Why:** Torrent media is already compressed, so `-mx=1` burned CPU for ~0% gain. Store + multithread turns archiving into near disk-speed "package + split". Reversible via the flag.

### D3 — 2026-06-24 — Stream archive→upload behind a flag
**Decision:** Overlap archiving and uploading via `streaming_archive.py`, gated by `STREAM_ARCHIVE_UPLOAD=1`; the proven sequential path stays as the default/fallback.
**Why:** 7z writes split volumes sequentially, so volume N is final once N+1 appears — we can upload it immediately instead of waiting for all volumes.

### D4 — 2026-06-24 — One bar style now, full unification later
**Decision:** Introduce a single `BAR_STYLE` constant used by all renderers as a quick fix; track collapsing the 3 progress systems into one as milestone M2.
**Why:** Minimal, low-risk fix for the "ugly/competing bars" now; the deeper refactor (per `Issues/mimo.txt`) deserves its own milestone.

### D-OPEN — 2026-06-24 — Unresolved: keep vs. remove `colab_leecher`
**Open decision (needs maintainer):** PR "Remove legacy colab_leecher bot pipeline" (theSadeQ, 2026-06-13) proposes deleting the package. All current improvement work assumes the pipeline **stays**. Resolve before M3.

### D5 — 2026-06-24 — Centralize BAR_STYLE under bar_style.py
**Decision:** Extract and centralize the `BAR_STYLE` configuration to a new helper module `colab_leecher/utility/bar_style.py` and replace all duplicate module-level declarations with direct imports.
**Why:** Completes the M2 code cleanup by eliminating the duplicated `BAR_STYLE` constant in `progress_manager.py`, `task_dashboard.py`, and `enhanced_status.py`, ensuring a single source of truth at import and runtime.

### D6 — 2026-06-25 — Hook instagrapi post downloader & support root instagrapi_settings.json
**Decision:** Hook `grapi_post_download` into `instagram_download` (single posts) in `instagram.py` as the preferred path. Search for `instagrapi_settings.json` in both the dynamic `Paths.WORK_PATH` and the repo root directory. Parse both flat keys and nested `INSTAGRAM` key mapping in `colab_leecher/__init__.py`.
**Why:** Unifies the instagrapi private API session for single post downloads as well as profile downloads. Reading settings from the repo root and supporting nested keys allows the setup cell to dynamically inject settings on startup.

### D7 — 2026-06-25 — Override default instagrapi request_timeout to 15s
**Decision:** Force `cl.request_timeout = 15` after Client initialization and after `cl.load_settings(...)` in `instagram_grapi.py` and diagnostic scripts.
**Why:** Instagrapi's default `request_timeout` is hardcoded to 1 second. While loading settings JSON directly, this value gets written/restored to 1 second, causing CDN media file downloads to fail with a ConnectTimeoutError. Explicitly overriding it to 15 seconds ensures stable media downloads.

### D8 — 2026-06-25 — Monkeypatch instagrapi media extractors to drop clips_metadata (v2)
**Decision:** Inject `_patch_instagrapi_extractors` helper to intercept private API and GQL extractors and set `clips_metadata` entirely to `None` in the raw dictionary.
**Why:** In the installed `instagrapi` version, `ClipsMetadata.original_sound_info` is defined as required and non-nullable. If missing, it fails with `Field required`. If present but `None`, it fails with `Input should be a valid dictionary`. Since we only need basic media attributes (like `pk`, `media_type`, and `product_type`) for downloading and never read `clips_metadata`, and `Media.clips_metadata` itself is Optional, setting the whole sub-object to `None` skips this fragile validation entirely. This provides a robust, future-proof fix.

### D9 — 2026-06-25 — Thread task_ctx to show live progress for Instagram downloads in parallel-task mode
**Decision:** Forward `task_ctx` through the download manager and the main `instagram` hook entry points into the `grapi` engine. Update `_render(task_ctx=None)` to edit `task_ctx.status_msg` and use the per-task inline keyboard, falling back to `MSG.status_msg` only if `task_ctx` is None.
**Why:** In parallel-task mode, the global `MSG.status_msg` remains `None`, so `_render()` was a permanent no-op and the Telegram download message remained frozen on `#STARTING_TASK`. Passing `task_ctx` fixes this so live progress updates are correctly rendered on a per-task basis.

### D10 — 2026-06-25 — Paginate and download Instagram media incrementally in _profile_worker
**Decision:** Replace the all-or-nothing listing call `cl.user_medias(user_id, amount=amount)` in `_profile_worker` with an incremental page-by-page loop using `cl.user_medias_paginated(user_id, amount=50, end_cursor=...)` and download items on each page immediately. Add a short delay (`3.0`s) between page requests to pace pagination.
**Why:** Accumulating the entire media list up front took several minutes and triggered Instagram's "Please wait a few minutes" rate limiting (HTTP 401). When a rate limit occurred, the entire list was discarded, failing the task with "nothing downloaded". Paging and downloading incrementally ensures that any fetched media is successfully processed/uploaded even if rate-limiting halts the listing early (partial success), and the download time naturally paces the API requests to prevent throttling.

### D11 — 2026-06-26 — Pause and resume on rate limits during profile listing
**Decision:** Upgrade `_profile_worker` to dynamically detect rate limit errors (like `PleaseWaitFewMinutes` / "wait a few minutes" / 429) during listing. On detection, sleep for a graded duration `_IG_RETRY_WAIT * retry_number` showing a live countdown, then retry the same pagination cursor up to `_IG_MAX_RETRIES` times (per page).
**Why:** Rate-limiting on the very first page or later pages caused tasks to end with "nothing downloaded". Pausing and retrying the same cursor prevents the task from aborting prematurely and gives the API request time to succeed, while keeping all files successfully fetched so far.

### D12 — 2026-06-26 — Convert impersonate string to ImpersonateTarget in ytdl.py
**Decision:** Modify `colab_leecher/downlader/ytdl.py` to instantiate `ImpersonateTarget` using `ImpersonateTarget.from_str()` for the `"impersonate"` option, falling back to the raw string if older yt-dlp is in use. Update `runtime_bootstrap.py` to version `3.2` to simulate this behavior exactly in its health checks.
**Why:** yt-dlp's library API asserts that the `impersonate` option is an instance of `ImpersonateTarget`, rather than a plain string. Passing `"chrome"` raised an `AssertionError` during constructor execution, which disabled impersonation silently and caused YouTube and other CDNs to return HTTP 403 Forbidden errors on all download fragments.

### D13 — 2026-06-26 — Convert impersonate string to ImpersonateTarget in get_YT_Name (v4.1)
**Decision:** Modify `_get_YT_Name_sync` inside `colab_leecher/downlader/ytdl.py` to instantiate `ImpersonateTarget` using `ImpersonateTarget.from_str()` for the `"impersonate"` option, falling back to the raw string if older yt-dlp is in use.
**Why:** The metadata/name lookup in `_get_YT_Name_sync` also constructs a `YoutubeDL` client instance. In v4, we only patched `_build_ydl_opts()` (the downloader itself), leaving `_get_YT_Name_sync()` to pass a raw string. This caused name lookups to raise `AssertionError` and fall back to no impersonation, triggering rate limits/HTTP 403 Forbidden errors on segment downloads. Patching this second site fully completes the fix.

