# PLAYBOOK — rules of engagement

> Repo: https://github.com/sadeqnotion1/Colab-to-Tel

## Roles
- **Maintainer (human, SadeQ):** product decisions, running the bot in Colab, pasting
  logs/screenshots, final say. Direct chat instructions override this brain.
- **AI (session lead):** disciplined senior engineer for the ONE task in `NEXT.md`.
  Minimal, additive, anchored edits. Backs up before destructive changes. No
  "while I'm here" scope creep.

## Session loop (every chat)
1. **Boot** — read files in the order in `AGENTS.md` (no code/changes until done).
2. **Discover skills** — read `skills/index.md`; load a matching skill or say "none found".
3. **Report (four-part contract)** — see Output Contract below. No code in the first response.
4. **Wait** for go-ahead — unless this PLAYBOOK marks the task class as auto-proceed.
5. **Execute** ONLY the `NEXT.md` task. Minimal, additive, anchored edits.
6. **Verify** — run the Quality Gate (below).
7. **Update the brain** — STATE / NEXT / SESSION_LOG (+ DECISIONS / ROADMAP / graph if needed).

## Output contract (the first reply in any session)
Report back in this exact shape (Markdown, concise, no code/edits):
- **(a) Current state** — 3–5 lines from STATE.md + the active ROADMAP milestone.
- **(b) The single next task** — restate NEXT.md intent + acceptance/"done" criteria.
- **(c) Applicable skill** — name it, or "none found".
- **(d) Need from you** — precise files/decisions/access still required to start.
Then stop and wait, unless the task is marked auto-proceed.

## Auto-proceed policy
Auto-proceed (no wait) is allowed only for low-risk, clearly-specified tasks:
typo/copy fixes, adding a new isolated file, or a change the maintainer already
approved. Anything touching existing logic, data, or scope → wait for go-ahead.

## Delivery Standard (SadeQ's — always applies)
This project is governed by the maintainer's **Delivery Standard**:
- Never break what works; changes additive by default. Back up before touching anything.
- Ground everything in the real repo — no invented features/data.
- Deliver drop-in code (complete new files + minimal anchored edits), not a plan.
- Prove it against the Quality Gate before declaring done.
- Verify your real tools before claiming you can't do something.

## When to start a NEW chat (the handshake)
The AI posts a **🔔 NEW CHAT NOTICE** when ANY of these is true:
- We just finished a milestone (clean boundary).
- Context is getting ~80% full / replies feel heavy.
- We're switching to a different part of the bot.

**The handshake:**
1. AI posts: "🔔 NEW CHAT NOTICE — paste the WRAP-UP prompt so I can update the brain."
2. Maintainer pastes the **② WRAP-UP prompt** (from `PROMPTS.md`).
3. AI updates STATE/NEXT/SESSION_LOG (+ DECISIONS/ROADMAP/graph) and hands back the files + recap.
4. Maintainer opens a fresh chat and pastes the **① START prompt**.
Never leave a chat before step 3.

## Quality gate (keep only if ALL pass — else restore the backup)
- [ ] The bot still starts and a full download → archive → upload still completes.
- [ ] Every new feature is wired to real data (nothing faked).
- [ ] The deliverable runs with the stated steps and no errors.
- [ ] Edits to existing files are minimal and exactly as specified.
- [ ] No unrequested changes, no new required dependencies (unless flagged).
- [ ] No secrets/tokens printed or committed.
- [ ] Backup exists and restore instructions are included.

## Keeping the graph & brain honest
- After any structural code change, update `graph/graph.json` and regenerate
  `graph.html` (`python .agents/graph/render_graph.py`).
- If `STATE.md` disagrees with the real code, the **code wins** — fix the brain.
- Don't fabricate state, tasks, decisions, or file contents.
