# Audit Scorecard (0-5)

## Scoring Scale
- `0`: Critical failure, unmanaged risk, no repeatable control.
- `1`: Ad hoc control exists but ineffective.
- `2`: Partial implementation, inconsistent enforcement.
- `3`: Reliable baseline, repeatable in normal conditions.
- `4`: Strong controls, measured and enforced by gates.
- `5`: Best-in-class, continuously improved with trend evidence.

## Category Weights
| Category | Weight (%) |
|---|---|
| Architecture | 15 |
| Correctness | 15 |
| Security | 20 |
| Performance | 10 |
| Developer Experience | 10 |
| CI/CD and Release Reliability | 15 |
| Observability and Incident Readiness | 10 |
| Documentation and Governance | 5 |

Total = 100%

## Rubric by Category
| Category | 0-1 Signal | 3 Signal | 5 Signal | Required Evidence | Owner |
|---|---|---|---|---|---|
| Architecture | Unclear boundaries, high coupling | Clear module boundaries, known contracts | Explicit boundaries, low coupling, ADR-backed decisions | Architecture doc + module map + ADR links | Tech Lead |
| Correctness | Low or unreliable tests | Stable unit/integration baseline | High confidence tests with low flake and contract coverage | CI test reports + flake trend + defect leakage | QA Lead |
| Security | Critical exposures unresolved | Core controls in place and monitored | Preventive + detective controls with zero critical backlog | SAST/SCA/secrets/SBOM reports + closure SLA | Security Owner |
| Performance | No budget/monitoring | Basic p95 tracking and regression checks | Enforced budgets + trend improvement | Perf benchmarks + CI budget gate | Performance Owner |
| Developer Experience | Slow/friction-heavy dev flow | Standardized local setup and checks | Fast feedback loops and high contributor throughput | Setup timing + survey + PR lead time | DevEx Owner |
| CI/CD and Release Reliability | Frequent breakage/manual steps | Stable automated pipeline with rollback | Predictable releases with strong gates and fast MTTR | Pipeline history + release logs + rollback drills | CI/CD Owner |
| Observability and Incident Readiness | Weak logs/alerts/runbooks | Actionable telemetry and basic runbooks | Full SLI/SLO + practiced incident response | Alerts, dashboards, runbooks, postmortems | Ops Owner |
| Documentation and Governance | Stale or missing docs | Core docs present and reviewed | Living docs tied to change process and ownership | Doc freshness report + review rubric + ADR usage | Eng Manager |

## Scoring Worksheet
| Category | Weight | Baseline Score (Day 1) | Target Score (Week 4) | Weighted Baseline | Weighted Target | Evidence Link | Status |
|---|---:|---:|---:|---:|---:|---|---|
| Architecture | 15 | 2 | 4 | 6.0 | 12.0 | `audit/baseline.md` (Complexity + hotspot size) | At risk |
| Correctness | 15 | 1 | 4 | 3.0 | 12.0 | `audit/baseline.md` (pytest/unittest outcomes) | Critical |
| Security | 20 | 1 | 4 | 4.0 | 16.0 | `audit/baseline.md` (tracked `credentials.json`, missing scanners) | Critical |
| Performance | 10 | 2 | 4 | 4.0 | 8.0 | `audit/baseline.md` (no perf budget or gate) | At risk |
| Developer Experience | 10 | 2 | 4 | 4.0 | 8.0 | `audit/baseline.md` (1184 ruff issues, missing tooling config) | At risk |
| CI/CD and Release Reliability | 15 | 1 | 4 | 3.0 | 12.0 | `audit/baseline.md` (`.github/` missing) | Critical |
| Observability and Incident Readiness | 10 | 2 | 4 | 4.0 | 8.0 | `audit/baseline.md` (logging exists, no SLI/SLO/runbook gate) | At risk |
| Documentation and Governance | 5 | 3 | 4 | 3.0 | 4.0 | `audit/baseline.md` (42/42 docs fresh, governance not enforced) | Needs improvement |
| Total | 100 |  |  | 31.0 | 80.0 |  |  |

Formula:
- `Weighted Score = (Category Score / 5) * Weight`

## Evidence Rules
- Evidence must be timestamped and reproducible.
- Evidence source must be linked (CI run, scan report, benchmark output, issue ID).
- Subjective statements without evidence do not affect score.

## Day 1 Sign-Off Checklist
- Scoring categories approved.
- Weighting approved.
- Category owners assigned.
- Evidence standards agreed.
- Tie-break rule confirmed: lower score prevails when evidence conflicts.

## Baseline Interpretation
- Current weighted score is `31/100` (Day 1 provisional baseline).
- Highest-risk categories: Correctness, Security, CI/CD Reliability.
- Week 4 target baseline is `80/100`; residual gap requires CI introduction, test reform, and security controls first.
