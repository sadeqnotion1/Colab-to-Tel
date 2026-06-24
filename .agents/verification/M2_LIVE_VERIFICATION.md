# M2 — Live-Verification Runbook (Colab)

**Goal:** prove the unified progress system behaves as one writer end-to-end.
Across **download → archive → upload** there must be **one** in-place status
message and **one** summary/dashboard message — no flicker, no two paths fighting
over the same Telegram message — and the bar style must be honored consistently.

> Grounded in `master` (commit `378eb7f`): `helper.status_bar` delegates to
> `ProgressManager` (directly when `task_ctx is None`, else via
> `UnifiedProgressSystem`); `ProgressManager` is the single status writer
> (`_edit_status_message` -> `safe_edit`); `task_dashboard` is the single summary
> writer and subscribes to `ProgressManager`.

## Pre-flight (1 min)
- [ ] Pull `master` with the M2 BAR_STYLE kit applied.
- [ ] `python apply_m2_barstyle.py --repo . --check` -> prints `OK` for all three modules, exits `0`.
- [ ] `python -c "from colab_leecher.utility.bar_style import BAR_STYLE; print(BAR_STYLE)"` -> prints `gradient` (or your env value).

## Environment (set in the Colab cell before launching)
```bash
export ARCHIVE_COMPRESSION=store      # M1 decision (fast, no recompress)
export STREAM_ARCHIVE_UPLOAD=0        # run #1 sequential; flip to 1 for run #2
export BAR_STYLE=gradient             # default; run #3 uses an override
```

## Run 1 — sequential pipeline (the core check)
1. Start the bot and send **one small real task** (a single small file from any
   supported source) that goes through download -> archive -> upload.
2. Watch the Telegram **status message** through all three phases.

**Pass if:**
- [ ] The **same** status message is edited in place during download (%, speed, ETA advance) — not a new message per tick.
- [ ] Phase label switches: download engine -> `Archiver (7z)` -> `TG Upload`.
- [ ] Exactly **one** summary/dashboard message; updates in place (no duplicates).
- [ ] No flicker / rapid double-edits (throttle holds — edits every few seconds, not many per second).
- [ ] Final state shows a single clean completion message.

## Run 2 — streaming upload path
- [ ] Set `STREAM_ARCHIVE_UPLOAD=1`, repeat Run 1 with a file large enough to stream.
- [ ] Same pass criteria. Additionally: archive + upload overlap, but still **one** status writer (no two concurrent edit loops on the same message).

## Run 3 — bar-style override
- [ ] Set `BAR_STYLE=sleek` (also valid: `modern`, `compact`, `classic`), restart, run a small task.
- [ ] Bar visuals change **consistently** in both the status message and the summary dashboard (proves the single shared `BAR_STYLE` is honored everywhere).

## Edge checks
- [ ] **Cancel** mid-download -> status message resolves to a single cancellation edit (no orphaned/competing edits).
- [ ] **Error path** (bad link) -> one clean error edit on the status message.

## Expected non-issues (do NOT fail the run on these)
- One-off messages like `Download failed`, `Parsing torrent contents...`,
  `Files kept on disk` are status/error/result messages, not the progress
  renderer. They legitimately call `edit_text` directly and are **out of M2 scope**.

## On completion (per Delivery Standard 5.5)
- [ ] Capture a screen recording or 2–3 screenshots per run (download / archive / upload).
- [ ] If all green: in the brain, flip M2 from *code-complete* to **verified** in
      `STATE.md` and `ROADMAP.md`, append a dated `SESSION_LOG.md` entry, then commit.
- [ ] If any check fails: record the failing step here, do **not** mark verified, and report.

## Then: M3 — keep-vs-remove `colab_leecher` (open decision)
Next milestone after M2 verifies. A **maintainer decision** (D-OPEN), not a code
task yet. Before deciding, gather: is the legacy path still imported/reachable,
what breaks if removed, and whether any user-facing flow depends on it.
