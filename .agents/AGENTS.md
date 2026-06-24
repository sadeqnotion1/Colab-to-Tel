# AGENTS.md — Repo & Graph Orientation

> Read this **first** in every session. It tells you what the repo is, where the
> brain lives, and how to load context in the right order. Do not write code or
> propose changes until you have completed the boot sequence below.

## Project

- **Name:** Colab-to-Tel ("Colab Leecher")
- **Repo:** https://github.com/sadeqnotion1/Colab-to-Tel  ·  branch `master`
- **One-line purpose:** A Google Colab–hosted Telegram leech bot: download (aria2c / yt-dlp) → 7z archive + split → upload to Telegram, with a live progress dashboard.
- **Primary stack:** Python 3 · asyncio · Telegram client (`colab_leecher/uploader/telegram.py`) · aria2c + yt-dlp downloaders · 7z (p7zip) archiving · runs inside Google Colab.

> Stack note: confirm the exact Telegram library and entry point against the code — if the brain ever disagrees with the code, **the code wins** (fix the brain).

## Boot sequence (in order, every session)

1. `brain/STATE.md`     → where we are
2. `brain/NEXT.md`      → the ONE next task + what to hand you
3. `brain/ROADMAP.md`   → the **current milestone only**
4. `brain/AUDIT.md`     → the audit queue / backlog of issues
5. `brain/PLAYBOOK.md`  → roles + session loop + protocols
6. `brain/DECISIONS.md` → skim the latest decisions (the "why")
7. `graph/graph.json`   → **query as needed; never dump it in full**
8. `skills/index.md`    → discover skills; load one if it matches NEXT.md

## Prompts

- `prompts/start.md`   → the #START kickoff prompt.
- `prompts/wrap-up.md` → the #WRAP_UP closing prompt.

## Repo layout (high level)

> Keep this in sync with the actual tree.

```text
Colab-to-Tel/
├── colab_leecher/
│   ├── downlader/        # aria2.py, ... (note: 'downlader' spelling is real)
│   ├── uploader/         # telegram.py  -> upload_file(path, display_name, task_ctx)
│   └── utility/          # converters.py (7z archive), handler.py (Zip_Handler + leech loop),
│                         # task_manager.py, task_dashboard.py, helper.py,
│                         # progress_manager.py, enhanced_status.py, ui_copy.py, variables.py
├── Issues/               # mimo.txt, 01_progress_system_unification.md
├── notebooks/
├── ytdl.py               # yt-dlp entry (kept)
├── requirements.txt
├── credentials.json.example
├── .agents/              # this brain
├── launcher/             # ui_theme.py + demo + integration example
├── run.sh / run.bat
└── README.md
```

> Reality check: there is an **open PR** "Remove legacy colab_leecher bot pipeline" (theSadeQ, 2026-06-13) that proposes deleting `colab_leecher/` and keeping `ytdl.py` + `LICENCE`. See STATE.md / DECISIONS.md — do not act on it without the maintainer's call.

## Graph orientation

- The knowledge graph (`graph/graph.json`) maps modules, files, functions, and their
  relationships. Use it to answer "what calls what" / "where does X live" **without**
  reading the whole codebase.
- **Query, don't dump.** Pull only the nodes/edges you need.
- Regenerate the visual `graph/graph.html` with `python .agents/graph/render_graph.py`.

## Hard rules (summary — full rules in PLAYBOOK.md)

- Work on **only** the task in `NEXT.md`. No "while I'm here" changes.
- Don't fabricate state, tasks, decisions, or file contents.
- Keep edits minimal, additive, anchored. Back up before destructive changes.
- This bot runs in **Google Colab** and touches secrets (`credentials.json`) — never print or commit tokens.
- A direct chat instruction from the maintainer overrides this brain.
