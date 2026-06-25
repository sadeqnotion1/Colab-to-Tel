# NEXT — the handoff card
_This is the FIRST thing to act on in a new chat (after the START prompt).
The AI rewrites this at the end of every session._

> Repo: https://github.com/sadeqnotion1/Colab-to-Tel

## ➡️ The one next task
**Colab Live Verification of instagrapi post/profile downloading & M2 Unification.** Run the bot in Google Colab using the updated `setup_cell.txt` (which has the fresh US-VPN session JSON with request_timeout=15 injected) to verify that:
1. `instagrapi_settings.json` is successfully written on startup and successfully loaded.
2. The bot reads this session JSON and downloads profile and post links (e.g. `https://www.instagram.com/p/DZzndRyD82d/`) bypassing login limits (verified locally to resolve PK and fetch media info correctly).
3. Centralized `BAR_STYLE` and unified progress manager display correctly without duplicate status edits.
Then, resolve the M3 pipeline decision (keep vs. remove `colab_leecher` package).

## Start the next chat with this
> "Run the updated Colab setup cell containing the new US-VPN session settings, perform the live verification run of instagrapi downloading, and decide on the M3 pipeline keep/remove package status."

## What to paste / give me at the start
Pull these from the repo (or paste them):
1. Google Colab execution logs for the startup setup cell and a sample download run.
2. Maintainer's choice on keeping or removing the `colab_leecher/` package (M3 pipeline decision).

## Decisions I need from you for this task
- The open PR "Remove legacy colab_leecher bot pipeline" — are we keeping the `colab_leecher` package (with these improvements) or removing it in favor of a narrowed `ytdl.py` focus?

## Definition of done for this task
- An Instagram post/profile download->archive->upload run completes successfully in Google Colab using the session settings.
- The `colab_leecher` keep/remove decision is finalized and recorded in `DECISIONS.md`.
