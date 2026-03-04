# Manual Findings (Week 2-3 Deep Audit)

## Metadata
| Field | Value |
|---|---|
| Run date | 2026-02-26 |
| Scope | Architecture, correctness, security, performance, operability |
| Method | Parallel evidence collection across code, docs, and CI controls |
| Source artifacts | `audit/raw/radon-cc.txt`, `audit/findings-automated.csv`, repository source/docs |

## Prioritized Findings
| finding_id | severity | category | title | evidence | risk statement | owner | due_date | eta | recommended mitigation |
|---|---|---|---|---|---|---|---|---|---|
| MAN-001 | Critical | Security | Shell command construction with dynamic input in runtime path | `colab_leecher/utility/converters.py:180`, `colab_leecher/utility/converters.py:226`, `colab_leecher/utility/converters.py:238`, `colab_leecher/utility/converters.py:1840`, `colab_leecher/utility/converters.py:1861`, `colab_leecher/downlader/aria2.py:27`, `colab_leecher/downlader/aria2.py:29` | Dynamic values (passwords, paths, URLs) are interpolated into shell strings, increasing command-injection and quoting-break risk in production download/convert flows. | Security + Platform | 2026-03-05 | 1 week | Replace `shell=True`/`create_subprocess_shell` in production paths with argument-list execution wrappers (`subprocess.run([...])`, `create_subprocess_exec(...)`), with strict input validation and escaping policy tests. |
| MAN-002 | High | Architecture / Correctness | Multi-user collision risk remains in setup flow due global state coupling | `colab_leecher/__main__.py:755`, `colab_leecher/__main__.py:766`, `colab_leecher/__main__.py:798`, `colab_leecher/__main__.py:805`, `colab_leecher/__main__.py:2470`, `colab_leecher/__main__.py:2605`, `colab_leecher/__main__.py:2819` | Parallel task execution exists, but setup/reply flow still writes to global `BOT`/`MSG` state, allowing cross-user state contamination and wrong-task behavior under concurrent usage. | Engineering | 2026-03-12 | 2 weeks | Complete migration of setup/reply handlers to per-user/per-task state (`TaskContext`/registry), remove legacy `BOT.State` and `MSG.status_msg` writes from active flows, and add concurrency regression tests. |
| MAN-003 | High | Reliability / Testability | Import-time credential loading and hard process exits in package initializer | `colab_leecher/__init__.py:27`, `colab_leecher/__init__.py:30`, `colab_leecher/__init__.py:36`, `colab_leecher/__init__.py:39`, `colab_leecher/__init__.py:42`, `colab_leecher/__init__.py:57` | Import side effects force credentials at import time and call `SystemExit`, making modules hard to test, reuse, or safely import in tooling/CI contexts. | Platform | 2026-03-05 | 1 week | Move credential loading to explicit startup/config bootstrap; keep module imports side-effect free; return typed config errors instead of process exits during import. |
| MAN-004 | Medium | Operability | Release/rollback/incident runbook deliverables not yet present | `docs/development/WORLD_CLASS_REPO_AUDIT_PLAN.md:122`, `docs/development/WORLD_CLASS_REPO_AUDIT_PLAN.md:124`, `docs/development/WORLD_CLASS_REPO_AUDIT_PLAN.md:125`, `audit/metric-catalog.md:16`, `audit/metric-catalog.md:17`, `audit/release-gates.md` (missing) | Incident response and recovery actions are not codified in repo artifacts yet, so operational response remains person-dependent and non-repeatable. | Ops | 2026-03-06 | 1 week | Add release, rollback, and incident runbooks; publish `audit/release-gates.md`; run one rollback drill and capture timestamps to begin MTTR/CFR baselining. |
| MAN-005 | Medium | Maintainability / Performance | Core orchestration and helper hotspots remain above safe complexity thresholds | `audit/raw/radon-cc.txt` entries: `colab_leecher/__main__.py:1194` (F/124), `colab_leecher/__main__.py:1793` (F/89), `colab_leecher/utility/task_manager.py:894` (F/96), `colab_leecher/utility/task_dashboard.py:56` (F/97), `colab_leecher/utility/helper.py:1489` (E/33) | Very high cyclomatic complexity in control-path functions increases regression likelihood, slows reviews, and limits safe change velocity. | Engineering | 2026-03-19 | 3 weeks | Refactor top 5 hotspots first with characterization tests, split orchestration from transport/UI formatting, and add “no new F-grade functions” CI policy. |
| MAN-006 | Medium | Correctness / Observability | Broad exception suppression still hides actionable failures | `colab_leecher/__main__.py:1411`, `colab_leecher/downlader/aria2.py:525`, `colab_leecher/utility/sabnzbd_client.py:67` | Bare `except` and `except: pass` patterns suppress root causes, weakening incident triage and allowing silent functional degradation. | Engineering | 2026-03-10 | 10 days | Replace bare handlers with explicit exception classes, structured logs, and error counters; fail closed where task integrity would otherwise be uncertain. |

## Recommended Remediation Sequence
1. Close `MAN-001` and `MAN-003` first (security and startup reliability blockers).
2. Execute `MAN-002` migration slices to remove remaining global setup-state coupling.
3. In parallel, implement `MAN-004` runbooks and `audit/release-gates.md`.
4. Burn down `MAN-005` and `MAN-006` with a staged refactor plus exception-hardening track.

## Evidence Reproduction Commands
```powershell
rg -n "TODO: Refactor to use per-user state dict|BOT\.State|MSG\.status_msg" colab_leecher/__main__.py
rg -n "shell=True|create_subprocess_shell|Popen\(" colab_leecher
rg -n "^\s*except\s*:|SystemExit\(|with open\(credentials_path|credentials_path" colab_leecher
Get-Content audit/raw/radon-cc.txt
```

## Remediation Update (2026-02-26)
- `MAN-001` progress: runtime-path shell invocation removed from `colab_leecher/utility/converters.py` and `colab_leecher/downlader/aria2.py`; remaining `shell=True` usages are currently limited to Colab setup-cell tooling paths.
- `MAN-002` progress: extraction flows in `colab_leecher/__main__.py` now use per-request `TaskContext` status messages instead of shared `MSG.status_msg`.
- `MAN-002` progress: `/extract` setup waiting state is now user-scoped (`extract_waiting_prompts`) and no longer uses global `extract_request_msg`, reducing cross-user setup collisions.
- `MAN-002` progress: manual filename reply setup now uses per-user prompt state (`filename_reply_prompts`) instead of global `BOT.State.expecting_*_filenames` flags.
- `MAN-002` progress: setup source-input prompts are now tracked per user (`source_waiting_prompts`) across `/gdupload`, `/mindvalley`, and `/nzb` flows instead of shared `src_request_msg`.
- `MAN-002` progress: `/mindvalley` and `/nzb` waiting flags are now user-scoped (`mindvalley_waiting_users`, `nzb_waiting_users`) instead of shared `BOT.State.*_waiting` gating.
- `MAN-002` progress: archive-password retry prompts/contexts are now user-scoped (`utility/reply_state.py`) and `handle_reply` consumes per-user password state instead of shared `BOT.State.password_waiting/password_retry_context`.
- `MAN-002` progress: settings prefix/suffix reply prompts now use per-user state (`settings_reply_prompts`) with explicit `set-prefix`/`set-suffix` callback handling instead of legacy shared reply prompt coupling.
- `MAN-002` progress: legacy setup flow now uses per-user setup snapshots (`setup_sessions`) for source links, service choice, filename lists, and per-request option overrides; `service_`/`fn_` callbacks and filename replies no longer mutate shared `BOT.SOURCE`/`BOT.Options.filenames` during setup.
- `MAN-002` progress: shared waiting mirrors (`BOT.State.extract_waiting`, `BOT.State.mindvalley_waiting`, `BOT.State.nzb_waiting`, `BOT.State.password_waiting`) are no longer written by active runtime setup/reply paths.
- `MAN-002` blocker note (superseded on 2026-02-27): legacy launch orchestration previously depended on `BOT.State.started/task_going`; current remaining blocker is now limited to legacy no-`task_ctx` compatibility branches in `utility/handler.py`.
- `MAN-006` progress: silent `except: pass` handlers in `colab_leecher/__main__.py`, `aria2.py`, `converters.py`, `sabnzbd_client.py`, `downlader/nzb.py`, `downlader/instagram.py`, `downlader/sabnzbd_downloader.py`, `utility/sabnzbd_autodetect.py`, `utility/sabnzbd_setup.py`, `utility/helper.py`, and `utility/task_manager.py` were replaced with explicit exception handling/logging.
- Follow-up evidence: targeted Bandit rerun for touched runtime modules reports `SEVERITY.HIGH=0`, `SEVERITY.MEDIUM=0`, `SEVERITY.LOW=18`.
- Follow-up evidence (password-state slice): targeted Bandit rerun for `__main__.py`, `utility/converters.py`, and `utility/reply_state.py` reports `SEVERITY.HIGH=0`, `SEVERITY.MEDIUM=0`, `SEVERITY.LOW=9`.

## Remediation Update (2026-02-27)
- `R90-007` wave 1 (T3 scope) applied low-risk lint autofixes on `colab_leecher/utility/*.py` excluding T1/T2-owned files (`reply_state.py`, `variables.py`, `handler.py`, `sabnzbd_*.py`).
- Scoped utility lint baseline (`ruff check <T3-owned utility files> --statistics`): `E701=144`, `E702=90`, `F541=41`, `F401=20`, `F841=19`, `F821=8`, `F811=3`, `F823=2`, `E703=1` (`328` total).
- Scoped utility lint after wave 1: `E701=144`, `E702=90`, `F841=19`, `F821=8`, `F811=3`, `F823=2` (`266` total).
- Net reduction: `62` issues removed (`F401 20->0`, `F541 41->0`, `E703 1->0`) with no control-flow rewrite.
- Validation evidence: `python -m compileall -q colab_leecher` passed; `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest -q tests/unit` passed (`10 passed`); CI lint command `ruff check tests/unit tests/integration scripts/security` passed before and after.
- Deferred lint debt for next waves: `E701/E702` one-line compound statements (`234`), plus `F841/F821/F811/F823` (`32`) in T3-owned utility modules.
- `MAN-006` (T2 scope) progress: broad suppression was removed from `colab_leecher/downlader/ytdl.py`, `colab_leecher/utility/sabnzbd_client.py`, and `colab_leecher/downlader/mega.py` by replacing swallow handlers with typed exception branches and contextual logs.
- `MAN-006` (T2 scope) validation: `python -m compileall -q colab_leecher` passed; `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest -q tests/unit` passed (`10 passed, 1 warning`); `bandit -q -r colab_leecher/downlader/ytdl.py colab_leecher/downlader/mega.py colab_leecher/utility/sabnzbd_client.py -f json -o audit/raw/local/bandit-t2.json` completed with `SEVERITY.HIGH=0`, `SEVERITY.MEDIUM=1`, `SEVERITY.LOW=6`.
- `MAN-006` residual in T2 scan: no remaining `except ...: pass` / bare suppression patterns were detected in `colab_leecher/scripts/utils/streaming_extract_function.py`, `colab_leecher/downlader/*.py`, and `colab_leecher/utility/sabnzbd_*.py`.
- `MAN-002` progress: `handle_options` destination, filename, and cancel callback paths no longer read/write shared `BOT.State.started/task_going`; cancellation now resolves via `TaskContext` queue lookup or per-user setup session state.
- `MAN-002` progress: `/cancel` fallback in `__main__.py` no longer invokes legacy global cancellation; it now clears only per-user setup/reply waiting state when no active queued task is found.
- `MAN-002` progress: destination/setup mode handoff now uses per-user/session values (`selected_mode`, `active_mode`) in callback and URL intake paths instead of mutating `BOT.Mode.mode` in those setup steps.
- `MAN-002` remaining blocker: legacy compatibility branches in `colab_leecher/utility/handler.py` still reference global `BOT.State/BOT.TASK/BOT.SOURCE` when `task_ctx` is absent; migrated runtime paths no longer depend on this, but full removal still requires scheduler/handler contract cleanup.
