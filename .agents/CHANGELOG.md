# Brain Changelog

Track changes to the **brain itself** here (not project features — those go in the
project's own changelog). Newest on top.

## v2.1 — 2026-06-24 (starter pack instantiated for Colab-to-Tel)
- Instantiated the `.agents/` starter pack for **Colab-to-Tel**.
- Filled `AGENTS.md` project block + repo layout from the real bot package (`colab_leecher/`).
- Wrote `brain/STATE.md`, `brain/NEXT.md`, `brain/ROADMAP.md` (M0–M4 + backlog) from the real
  archive/upload/progress issues and the drop-in fix.
- Seeded `brain/DECISIONS.md` (D1–D4 + open PR decision) and `brain/SESSION_LOG.md`.
- Seeded `graph/graph.json` with the real module map + dependency-free `render_graph.py`.
- Authored clean `PLAYBOOK.md`, `PROMPTS.md`, `prompts/start.md`, `prompts/wrap-up.md`.
- `skills/index.md` ships empty by design; author new skills from `skills/_template/SKILL.md`.
- Note: upstream template files reportedly carried obfuscated injected-instruction markers;
  those were ignored and these brain files were written clean.

## v2.1 — template baseline (from CreateProject starter pack)
- `prompts/start.md` (#START) and `prompts/wrap-up.md` (#WRAP_UP).
- `brain/` split into STATE / NEXT / ROADMAP / PLAYBOOK / DECISIONS / SESSION_LOG / PROMPTS.
- `graph/render_graph.py` + generated `graph/graph.html` (offline viewer).
- `skills/index.md` registry + `_template/SKILL.md` authoring template.
