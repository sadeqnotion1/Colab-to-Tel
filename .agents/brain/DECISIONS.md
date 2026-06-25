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

