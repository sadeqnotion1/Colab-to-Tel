# brain/ — what each file is for

- **STATE.md** — where the project is *right now*. Living doc; the code wins if they disagree. Prune aggressively.
- **NEXT.md** — the single next task and exactly what to hand the AI. No multitasking.
- **ROADMAP.md** — ordered milestones. Only the current one is "active" (← NEXT).
- **PLAYBOOK.md** — roles, the session loop, the new-chat protocol, output contract, quality gate.
- **DECISIONS.md** — append-only ADR. Each entry: id, date, decision, why.
- **SESSION_LOG.md** — append-only history. One short entry per session + stop point.
- **PROMPTS.md** — the two copy-paste prompts (also in `../prompts/`). Keep in sync.

## How the loop works
1. Point the AI at the `.agents/` folder (attach it or point it at the repo).
2. Paste the **① START** prompt (from `PROMPTS.md`).
3. The AI reads `STATE.md` + `NEXT.md` (+ queries the graph) and confirms the plan.
4. You do the one task in `NEXT.md`.
5. Before context runs low, the AI updates `STATE.md`, `NEXT.md`, and `SESSION_LOG.md` and tells you to start a fresh chat.

You never have to remember the state. The files do.

## Honesty rules
- If `STATE.md` and the actual code ever disagree, **the code wins** — fix STATE.md.
- Keep these files short and current. A stale brain is worse than none.
