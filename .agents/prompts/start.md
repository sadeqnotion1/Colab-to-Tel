```
Project: Colab-to-Tel (Colab Leecher) — repo: https://github.com/sadeqnotion1/Colab-to-Tel
Context source: the .agents/ folder. Pull it from the repo above (path .agents/),
or use what I've attached/pasted. Never improvise project state — if a file isn't
on GitHub and isn't attached, ask me for it by name.

Before doing anything, read these (in order), then report back:
- .agents/AGENTS.md            (repo + graph orientation)
- .agents/brain/STATE.md       (where we are)
- .agents/brain/NEXT.md        (the one next task + what to give you)
- .agents/brain/ROADMAP.md     (current milestone only)
- .agents/brain/PLAYBOOK.md    (roles + session loop)
- .agents/brain/DECISIONS.md   (the "why" — skim latest)
- .agents/graph/graph.json     (query as needed; do NOT dump it)
- .agents/skills/index.md      (load a matching skill, or say "none found")

Report back in this exact shape (Markdown, concise, no code/edits):
- (a) Current state — 3-5 lines from STATE.md + active ROADMAP milestone.
- (b) The single next task — restate NEXT.md intent + acceptance/"done" criteria.
- (c) Applicable skill — name it, or "none found".
- (d) Need from you — precise files/decisions/access still required to start.

Then stop and wait for my go-ahead, unless PLAYBOOK.md marks the task auto-proceed.

Working rules: Follow PLAYBOOK.md and my Delivery Standard. Work on ONLY the task in
NEXT.md — no "while I'm here" changes. Query the graph, don't dump it. Keep edits
minimal, additive, anchored; back up before destructive changes; never print or
commit secrets (credentials.json).

New-chat protocol: When context gets ~80% full OR we finish the milestone, post a
line beginning exactly 🔔 NEW CHAT NOTICE, say why (context vs. milestone), and
wait for my wrap-up prompt before stopping.

This prompt is overridden by my direct chat instructions.
```
