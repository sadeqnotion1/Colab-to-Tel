# Day 1 Decisions Log

## Session Metadata
| Field | Value |
|---|---|
| Date | 2026-02-25 |
| Facilitator | SadeQ (acting Audit Lead) |
| Note Taker | Codex (assistant-generated draft) |
| Participants | SadeQ (Engineering/Security/QA acting roles) |

## Decision Log
| Decision ID | Time | Category | Decision | Rationale | Options Considered | Owner | Review Date | Status |
|---|---|---|---|---|---|---|---|---|
| D-001 | 14:00 | Scope | Include Colab setup scripts in audit scope | Setup scripts directly affect runtime stability and install path | Exclude notebook-only code | SadeQ | 2026-03-15 | Approved |
| D-002 | 14:20 | Metrics | Mark unavailable delivery/security metrics as `UNKNOWN` until CI tooling exists | Prevents fake precision and keeps baseline evidence-based | Estimate from local runs | SadeQ | 2026-03-01 | Approved |
| D-003 | 14:45 | Governance | Use acting single-owner model until delegates are assigned | Enables immediate execution without waiting for staffing | Pause until all roles staffed | SadeQ | 2026-03-01 | Approved |
| D-004 | 15:10 | Security | Treat tracked `credentials.json` as P0 remediation item | Secret exposure is highest impact and easiest immediate control | Defer to Week 2 | SadeQ | 2026-02-26 | Approved |
| D-005 | 15:30 | Correctness | Separate debug scripts from executable test suite before any coverage target | Current tests execute side effects and do not produce confidence | Keep mixed debug/test layout | SadeQ | 2026-03-03 | Approved |

## Open Questions
| Question ID | Question | Owner | Due Date | Blocking (Y/N) | Status |
|---|---|---|---|---|---|
| Q-001 | Which CI platform and branch protection policy will be the source of truth? | SadeQ | 2026-03-01 | Y | Open |
| Q-002 | Which minimal test matrix is required for merge gating (py versions, platforms)? | SadeQ | 2026-03-03 | Y | Open |
| Q-003 | Which secret scanner will be enforced pre-commit and in CI? | SadeQ | 2026-03-01 | Y | Open |
| Q-004 | Do we keep Colab shell-command files in package path or move to notebook assets? | SadeQ | 2026-03-03 | N | Open |

## Action Items
| Action ID | Task | Owner | Priority (P0/P1/P2) | Due Date | Status | Evidence Link |
|---|---|---|---|---|---|---|
| A-001 | Finalize scorecard weighting and approve provisional baseline 31/100 | SadeQ | P0 | 2026-02-26 | Open | `audit/scorecard.md` |
| A-002 | Implement CI pipeline and required checks (lint, test, security, compile) | SadeQ | P0 | 2026-03-06 | Completed (initial) | `.github/workflows/ci.yml` |
| A-003 | Remove tracked `credentials.json` from repo history/path and rotate credentials | SadeQ | P0 | 2026-02-26 | In Progress | `git rm --cached credentials.json` |
| A-004 | Split debug scripts from tests; create deterministic `pytest` suite | SadeQ | P0 | 2026-03-06 | Completed (initial) | `pytest.ini`, `tests/unit/*`, `tests/debug/README.md` |
| A-005 | Publish governance cadence to contributors | SadeQ | P1 | 2026-02-27 | Open | `audit/governance-cadence.md` |
| A-006 | Rotate all credentials that were present in historical/local `credentials.json` | SadeQ | P0 | 2026-02-26 | Open | Security runbook / provider consoles |

## Sign-Off Checklist
- Charter approved by Engineering Lead.
- Scorecard categories and weights approved.
- Metric owners assigned.
- Scope boundary approved.
- Escalation model approved.
- No unresolved blocker for Day 2 baseline.

## Sign-Off
| Name | Role | Decision | Date |
|---|---|---|---|
| SadeQ | Engineering Lead | Pending | 2026-02-25 |
| SadeQ (or delegate) | Security Owner | Pending | 2026-02-25 |
| SadeQ (or delegate) | QA Owner | Pending | 2026-02-25 |
