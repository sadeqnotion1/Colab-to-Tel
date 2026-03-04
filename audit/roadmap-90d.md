# 90-Day Remediation Roadmap

## Metadata
| Field | Value |
|---|---|
| Created | 2026-02-26 |
| Horizon start | 2026-02-26 |
| Horizon end | 2026-05-27 |
| Inputs | `audit/findings-automated.csv`, `audit/findings-manual.md`, `audit/release-gates.md`, `audit/scorecard.md` |
| Baseline score | 31/100 |
| Week 4 target | 80/100 |

## Prioritization Model
- Severity weights: Critical=5, High=4, Medium=3, Low=2
- Effort weights: Small=1, Medium=2, Large=3
- Priority index = Severity x Impact confidence / Effort
- Execution rule: prioritize unblockers for security, correctness, and release gates first.

## Parallel Execution Lanes
| Lane | Focus | Owner | Runs in parallel with |
|---|---|---|---|
| A | Security stabilization | Security + Platform | B, C |
| B | Runtime correctness and architecture | Engineering | A, C |
| C | CI/CD and operability hardening | CI/CD + Ops | A, B |
| D | Maintainability and performance | Engineering | A, C |
| E | Governance and metrics instrumentation | Eng Lead + Ops | A, B, C, D |

## 30/60/90 Milestones
| Milestone | Date | Required outcomes |
|---|---|---|
| Day 30 | 2026-03-28 | All critical dependency CVEs remediated; `dependency-audit-linux` in strict mode and required; shell command hardening phase 1 complete; import-time credential side effects removed. |
| Day 60 | 2026-04-27 | Global state collision risks removed from active setup flows; exception hardening complete in critical paths; rollback drill executed and documented; lint debt reduced by >= 50% from current baseline. |
| Day 90 | 2026-05-27 | Top complexity hotspots refactored; dependency pinning and SBOM policy stable; release/incident metrics flowing weekly (M06-M09); weighted score >= 80 and no category below 3. |

## Prioritized Backlog (P0/P1/P2)
| roadmap_id | priority | source findings | objective | owner | start | target | effort | dependencies | done criteria |
|---|---|---|---|---|---|---|---|---|---|
| R90-001 | P0 | AUTO-004, AUTO-005, AUTO-006, AUTO-007, AUTO-008, AUTO-009, AUTO-010 | Patch all open critical/high dependency CVEs and re-baseline audit outputs | Security | 2026-02-26 | 2026-03-05 | Medium | none | `pip-audit` report shows zero critical/high vulns for production deps |
| R90-002 | P0 | MAN-001, AUTO-002 | Remove dynamic `shell=True`/`create_subprocess_shell` usage from production runtime paths | Security + Platform | 2026-02-26 | 2026-03-12 | Large | R90-001 partial | No exploitable dynamic shell construction in runtime path; Bandit B602 high findings closed or justified |
| R90-003 | P0 | MAN-003 | Refactor credentials loading out of import path and remove import-time `SystemExit` behavior | Platform | 2026-02-26 | 2026-03-05 | Medium | none | Importing package no longer reads credentials or exits process |
| R90-004 | P0 | AUTO-011, RG-005 | Promote dependency audit from report-only to strict required gate | CI/CD | 2026-03-01 | 2026-03-12 | Small | R90-001 | CI fails on dependency vulnerabilities; branch protection marks gate required; strict-mode audit artifact is always uploaded |
| R90-005 | P1 | MAN-002 | Complete per-user/per-task state migration for setup/reply flows | Engineering | 2026-03-01 | 2026-04-10 | Large | R90-003 | No active setup path writes to shared `BOT.State`/`MSG.status_msg` for user-isolated flows |
| R90-006 | P1 | MAN-006 | Replace bare `except` and suppression in critical flows with typed handling and logs | Engineering | 2026-03-01 | 2026-03-31 | Medium | none | No bare handlers in critical control paths; incident triage logs include root cause fields |
| R90-007 | P1 | AUTO-001 | Burn down lint debt in staged waves (top rule classes first) | Platform + Engineering | 2026-03-05 | 2026-04-27 | Large | none | Lint issue count reduced by >= 50%; no new priority rule regressions |
| R90-008 | P1 | AUTO-012, MAN-005 | Refactor top 5 complexity hotspots and add "no new F-grade" policy | Engineering | 2026-03-10 | 2026-05-10 | Large | R90-005 partial | Top 5 hotspots reduced below E; policy documented and enforced in CI |
| R90-009 | P1 | MAN-004, RG controls | Execute one rollback drill and one incident tabletop; capture MTTR/CFR evidence | Ops + CI/CD | 2026-03-12 | 2026-04-05 | Small | R90-004 | Rollback + tabletop artifacts recorded with UTC timestamps, MTTR/CFR fields, and action items |
| R90-010 | P2 | AUTO-013, AUTO-014 | Adopt pinned dependency strategy with repeatable lock update cadence | Platform | 2026-03-15 | 2026-05-20 | Medium | R90-001 | Requirements pinned with update policy; SBOM warnings reduced to accepted threshold |
| R90-011 | P2 | AUTO-015 | Resolve unknown license metadata and document compliance disposition | Compliance | 2026-03-15 | 2026-04-30 | Small | none | License review record completed for unknown packages |
| R90-012 | P2 | Scorecard perf/coverage gaps | Add performance budget baseline and expand correctness evidence (coverage/integration map) | QA + Performance | 2026-03-20 | 2026-05-27 | Medium | R90-007 | M03/M04/M13 have repeatable measurement and weekly trend report |

## Dependency Map (Critical Path)
1. R90-001 -> R90-004
2. R90-003 -> R90-005
3. R90-005 + R90-006 -> R90-008
4. R90-004 -> R90-009
5. R90-001 -> R90-010

## Execution Update (2026-02-26)
- R90-003 in progress: import-time hard exits were removed and replaced with explicit runtime configuration guards in `colab_leecher/__init__.py`.
- R90-004 in progress: CI dependency-audit gate is set to strict mode (`--fail-on-vulns`) and corresponding branch-protection documentation is updated.
- R90-002 in progress: runtime-path shell invocation patterns were removed from `converters.py` and `aria2.py` (remaining `shell=True` usage is currently in Colab setup-cell scripts).
- R90-005 partial: extraction command flows in `__main__.py` now use per-request `TaskContext` status messages; `/extract` path-wait prompts are tracked per user (`extract_waiting_prompts`); manual filename reply setup now uses per-user prompt state (`filename_reply_prompts`) instead of global `expecting_*` flags; setup source-input prompts now use per-user tracking (`source_waiting_prompts`) instead of shared `src_request_msg`; `/mindvalley` + `/nzb` waiting gates are user-scoped (`mindvalley_waiting_users`, `nzb_waiting_users`); archive-password retry reply state is user-scoped (`utility/reply_state.py`) instead of shared `BOT.State.password_*`; and settings prefix/suffix reply prompts are now user-scoped (`settings_reply_prompts`) with explicit callback flow support.
- R90-005 partial: legacy setup handoff now stores per-user setup snapshots (`setup_sessions`) for source links, service selection, filename lists, and per-request option overrides; `handle_url`, `service_`/`fn_` callbacks, and filename reply handling now consume/update that snapshot instead of mutating shared setup globals.
- R90-005 partial: active setup/reply waiting helpers no longer mirror state into shared `BOT.State.*_waiting` flags; password reply state now remains fully isolated in `utility/reply_state.py`.
- R90-005 blocker resolved (2026-02-27): `cancelTask`/`SendLogs` now require `task_ctx`, and `taskScheduler` enforces `task_ctx` input. `utility/handler.py` no longer uses legacy `BOT.State/BOT.TASK/BOT.SOURCE` fallback reads/writes in active cancellation/completion paths.
- R90-006 partial: silent exception suppression in critical touched modules was replaced with explicit logging across runtime, NZB, SABnzbd, and helper/task management paths.
- R90-006 evidence: targeted post-remediation Bandit run over touched modules is at `SEVERITY.HIGH=0`, `SEVERITY.MEDIUM=0`, `SEVERITY.LOW=18`.

## Execution Update (2026-02-27)
- R90-007 wave 1 executed on `job/t3-lint-wave1` in T3-owned utility modules only (excluding T1/T2-owned files).
- Rule-class reduction from scoped utility baseline (`ruff --statistics`):
  - `F401`: `20 -> 0`
  - `F541`: `41 -> 0`
  - `E703`: `1 -> 0`
  - Total: `328 -> 266` (`-62`, 18.9% reduction for scoped files).
- CI lint command from workflow (`ruff check tests/unit tests/integration scripts/security`) remained green before and after.
- Required local gates passed: `python -m compileall -q colab_leecher` and `$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest -q tests/unit` (`10 passed`).
- R90-006 (T2 exception-hardening slice) replaced suppression handlers in `colab_leecher/downlader/ytdl.py`, `colab_leecher/utility/sabnzbd_client.py`, and `colab_leecher/downlader/mega.py` with typed handling and contextual logs.
- R90-006 (T2 evidence): `bandit -q -r colab_leecher/downlader/ytdl.py colab_leecher/downlader/mega.py colab_leecher/utility/sabnzbd_client.py -f json -o audit/raw/local/bandit-t2.json` reports `SEVERITY.HIGH=0`, `SEVERITY.MEDIUM=1`, `SEVERITY.LOW=6` (medium/low findings are pre-existing `mega.py` subprocess/tmp-directory checks).
- R90-006 (T2 scope check): no remaining suppression patterns (`except ...: pass` or bare suppressive handlers) were found across `colab_leecher/scripts/utils/streaming_extract_function.py`, `colab_leecher/downlader/*.py`, and `colab_leecher/utility/sabnzbd_*.py`.
- R90-007 wave 2 executed (utility scope): targeted classes `E701/E702/F841/F821/F811/F823` reduced from `301 -> 0` using staged formatter + manual remediation (`autopep8` passes plus focused fixes in `converters.py`, `task_manager.py`, `helper.py`, `handler.py`, `task_dashboard.py`, `enhanced_status.py`).
- R90-007 wave 2 verification: `ruff check colab_leecher/utility --select E701,E702,F841,F821,F811,F823 --statistics` is clean; `python -m compileall -q colab_leecher` and `pytest -q tests/unit` remain passing.
- R90-004 (T4) update: dependency-audit workflow now keeps summary/artifact steps under `if: always()` so strict-mode failures still publish evidence (`audit/raw/ci/*`).
- R90-004 (T4) update: branch-protection guide now includes runnable workflow/path verification commands and strict local gate commands.
- R90-009 (T4) update: release/rollback/incident runbooks now include reproducible evidence-capture command packs under `docs/operations/evidence/<utc-stamp>-*`.
- R90-009 (T4) update: operations evidence templates added at `docs/operations/EVIDENCE_LOG_TEMPLATES.md` and linked from release gates.
- R90-009 (T4) execution evidence: rollback drill + incident tabletop were executed and captured at `docs/operations/evidence/20260227-111424/` (including UTC timeline, MTTR, CFR, and action items).
- R90-004 (T4) external verification blocker: GitHub branch-protection API returned `HTTP 403` for this private repository plan, and workflow-run query for `ci.yml` returned `HTTP 404` on remote default branch.
- R90-005 (T1) update: active callback setup/cancel/runtime paths in `__main__.py` no longer gate on `BOT.State.started/task_going`; cancellation now resolves through `TaskContext` queue lookup plus per-user setup session state.
- R90-005 (T1) update: `/cancel` no-task fallback now clears per-user setup/reply state only and does not call legacy global `cancelTask(...)`.
- R90-005 (T1) update: destination and URL intake setup flow now uses session-local mode handoff (`selected_mode`/`active_mode`) instead of mutating shared mode state in those steps.
- R90-001 completed (2026-02-27): production dependency pins were updated in `requirements.txt` (`aiohttp`, `requests`, `Pillow`, `pyrofork`, `yt_dlp`, `pymongo`), `asyncio` was removed, and `uvloop` is now platform-gated (`platform_system != "Windows"`).
- R90-001 evidence (2026-02-27): `python scripts/security/run_dependency_audit.py --requirements requirements.txt --report-dir audit/raw/local --fail-on-vulns` returns `mode=direct`, `vulnerability_total=0`, `packages_with_vulns=0` (`audit/raw/local/dependency-audit-summary.json`).
- R90-002 completed scope (runtime path): `bandit -q -r colab_leecher/utility colab_leecher/downlader colab_leecher/scripts/utils -f json -o audit/raw/local/bandit-runtime-postfix.json` now reports `SEVERITY.HIGH=0`, `SEVERITY.MEDIUM=0`, and `B602=0` (no dynamic-shell injection pattern in active runtime path).
- R90-002 hardening follow-up: medium findings `B108` were removed by replacing hardcoded temp paths with secure temp APIs in `downlader/mega.py` and `scripts/utils/streaming_extract_function.py`; trusted local token deserialization in `downlader/gdrive.py` is explicitly annotated and constrained.
- R90-006 progress (2026-02-27): remaining bare-except debt (`E722`) was reduced to zero across `colab_leecher` (`ruff check colab_leecher --select E722 --statistics` is clean).
- R90-008 policy slice (2026-02-27): complexity baseline guard was introduced via `scripts/quality/check_complexity_budget.py` with baseline `audit/complexity-f-baseline.json`, and CI now enforces "no new/regressed F-grade blocks" under the `lint` gate.

## R90-004 / R90-009 Completion Snapshot (2026-02-27)
- R90-004 completed scope in this branch:
  - [x] strict dependency gate enabled in CI
  - [x] branch-protection required checks documented with runnable verification commands
  - [x] strict dependency-audit artifact retention documented and implemented
  - [ ] production branch-protection screenshot/export captured from GitHub settings (blocked by private-repo plan/API access limits in current environment)
  - [ ] passing + failing run URLs attached to release evidence log (blocked until `ci.yml` exists on remote default branch)
- R90-009 completed scope in this branch:
  - [x] rollback drill procedure documented with timestamp/evidence commands
  - [x] incident tabletop procedure documented with MTTR/CFR capture
  - [x] evidence templates added for release, rollback, and tabletop records
  - [x] one rollback drill executed and recorded (`docs/operations/evidence/20260227-111424/rollback-drill-evidence.md`)
  - [x] one incident tabletop executed and recorded (`docs/operations/evidence/20260227-111424/incident-tabletop-evidence.md`)

## Execution Cadence
- Weekly Monday: backlog re-prioritization and owner commitments.
- Weekly Wednesday: risk review (security, incident readiness, blocked dependencies).
- Weekly Friday: metric review against M01-M14 and score impact update.

## Multi-Terminal Execution Model (Updated 2026-02-27)
Use this split so you can run concurrent terminals with low merge conflicts.

### Coordination Rules
1. One terminal = one branch = one roadmap slice.
2. Do not edit files owned by another active terminal.
3. Rebase and merge in order: T1 -> T2 -> T3 -> T4.
4. Each terminal must pass local checks before merge: `python -m compileall -q colab_leecher` and `pytest -q tests/unit`.

### Terminal Job Packs
| Terminal | Branch name | Roadmap focus | File ownership (exclusive while active) | Done criteria |
|---|---|---|---|---|
| T1 | `job/t1-state-migration` | R90-005 | `colab_leecher/__main__.py`, `colab_leecher/utility/reply_state.py`, `colab_leecher/utility/variables.py`, `colab_leecher/utility/handler.py` | Remaining shared setup/reply state removed or isolated with per-user maps; no new regressions in unit tests |
| T2 | `job/t2-exception-hardening` | R90-006 | `colab_leecher/scripts/utils/streaming_extract_function.py`, `colab_leecher/downlader/*.py`, `colab_leecher/utility/sabnzbd_*.py` | No bare `except` in targeted modules; failures logged with actionable context |
| T3 | `job/t3-lint-wave1` | R90-007 | `colab_leecher/utility/*.py` (except files owned by T1/T2), lint configs, targeted tests | Priority lint classes reduced for selected modules; no behavior change failures |
| T4 | `job/t4-ci-ops-evidence` | R90-004 + R90-009 | `.github/workflows/ci.yml`, `docs/development/*`, `docs/operations/*`, `audit/release-gates.md`, `audit/roadmap-90d.md`, `audit/README.md` | CI gate docs + rollback/incident evidence updated and internally reproducible |

### Quick Start Commands (Per Terminal)
1. `git switch -c <branch-name>`
2. `python -m compileall -q colab_leecher`
3. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1; pytest -q tests/unit`
4. If security-related: `bandit -q -r <touched-paths> -f json -o audit/raw/local/<report>.json`
5. `git add -A && git commit -m "<roadmap-id>: <slice summary>"`

### Merge Queue
1. Merge `T1` first (state isolation is a dependency for R90-008).
2. Merge `T2` second (exception hardening on top of latest state flow).
3. Merge `T3` third (lint fixes after behavior stabilization).
4. Merge `T4` last (docs/CI evidence usually rebases cleanly).

## Score Improvement Targets
| Category | Baseline | Day 30 target | Day 60 target | Day 90 target |
|---|---:|---:|---:|---:|
| Architecture | 2 | 2.5 | 3.5 | 4 |
| Correctness | 1 | 2.5 | 3.5 | 4 |
| Security | 1 | 3.5 | 4 | 4 |
| Performance | 2 | 2 | 3 | 4 |
| Developer Experience | 2 | 2.5 | 3.5 | 4 |
| CI/CD and Release Reliability | 1 | 3 | 3.5 | 4 |
| Observability and Incident Readiness | 2 | 3 | 3.5 | 4 |
| Documentation and Governance | 3 | 3.5 | 4 | 4 |

## Risk Register for Roadmap Delivery
| Risk | Impact | Mitigation |
|---|---|---|
| Dependency upgrades break runtime behavior | High | Use canary branch + targeted integration checks before merge |
| Large refactors stall due coupling | High | Slice by command flow; enforce characterization tests before edits |
| Gate strictness slows delivery initially | Medium | Stage enforcement with 1-week stabilization windows and clear owner SLAs |
| Owner bandwidth contention | Medium | Enforce WIP limits per lane and publish weekly blocked-item list |

## Weekly Reporting Template
| Week ending | Completed items | In-flight items | Blockers | Score delta | Next week commitments |
|---|---|---|---|---|---|
| YYYY-MM-DD |  |  |  |  |  |
