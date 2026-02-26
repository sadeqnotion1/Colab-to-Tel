# Metric Catalog

## Purpose
Define objective metrics, formulas, owners, and data sources used for baseline and ongoing audit scoring.

## Metric Definitions
| ID | Metric | Definition | Formula | Source | Owner | Cadence | Baseline | Target |
|---|---|---|---|---|---|---|---|---|
| M01 | CI Pass Rate | Successful main-branch CI runs over total runs | successful_runs / total_runs * 100 | CI pipeline history | CI/CD Owner (unassigned) | Daily | UNKNOWN (no CI pipeline) | >= 98% |
| M02 | Build Time p95 | 95th percentile main build duration | p95(build_duration_minutes) | CI metrics | CI/CD Owner (unassigned) | Weekly | UNKNOWN (no CI pipeline) | <= 10 min |
| M03 | Unit Test Coverage | Line coverage for unit tests | covered_lines / total_lines * 100 | Coverage report | QA Owner (acting) | Weekly | UNKNOWN (no coverage report) | >= 85% |
| M04 | Integration Coverage | Critical-path integration test coverage | covered_critical_paths / total_critical_paths * 100 | Test suite map | QA Owner (acting) | Weekly | UNKNOWN (no integration suite inventory) | >= 80% |
| M05 | Flaky Test Rate | Tests that fail non-deterministically | flaky_tests / total_tests * 100 | CI retry logs | QA Owner (acting) | Weekly | UNKNOWN (no deterministic suite) | <= 2% |
| M06 | Lead Time for Change | Commit-to-production duration median | median(prod_deploy_time - merge_time) | VCS + deploy logs | Eng Lead | Weekly | UNKNOWN (deploy telemetry missing) | down 30% |
| M07 | Deployment Frequency | Production deployments per week | count(prod_deploys) | Release logs | CI/CD Owner (unassigned) | Weekly | UNKNOWN (release log not centralized) | up 25% |
| M08 | Change Failure Rate | Deployments causing incidents/rollback | failed_deploys / total_deploys * 100 | Incident + deploy logs | Ops Owner (unassigned) | Weekly | UNKNOWN (incident log not standardized) | <= 10% |
| M09 | MTTR | Mean time to restore after incident | avg(restore_time - incident_start) | Incident records | Ops Owner (unassigned) | Weekly | UNKNOWN (incident tracker missing) | <= 60 min |
| M10 | Open High/Critical Vulns | Unresolved high/critical vulnerabilities | count(open_high_critical) | SAST/SCA dashboards | Security Owner (acting) | Daily | UNKNOWN (`pip-audit`/`bandit` not installed) | 0 |
| M11 | Secret Exposure Count | Exposed secrets detected in repo/history | count(open_secret_findings) | Secrets scan + git tracking check | Security Owner (acting) | Daily | 0 currently tracked (rotation still required for previously exposed values) | 0 |
| M12 | Dependency Freshness | Dependencies behind latest secure versions | outdated_deps / total_deps * 100 | Dependency scanner | Security Owner (acting) | Weekly | UNKNOWN (`pip-audit` missing); 16/22 requirements unpinned | <= 10% |
| M13 | Perf Budget Violations | CI runs exceeding performance budget | violating_runs / total_perf_runs * 100 | Perf test reports | Performance Owner (unassigned) | Weekly | UNKNOWN (no perf suite/budget) | <= 2% |
| M14 | Doc Freshness | Key docs updated in last 90 days | fresh_docs / required_docs * 100 | Docs review log | Eng Manager (acting) | Monthly | 100% (42/42 docs) | >= 95% |

## Required Data Sources
- CI system run history and timing metrics.
- Test and coverage reports.
- Security scanners (SAST, SCA, secrets).
- Deployment logs and incident tracker.
- Dependency and SBOM tooling output.
- Documentation review checklist.

## Data Quality Rules
- Every metric must have a single source of truth.
- Manual data extraction must include extraction date/time and method.
- If data is missing, mark `UNKNOWN` (do not estimate silently).

## Day 1 Completion Checklist
- Owner assigned for each metric.
- Formula validated for each metric.
- Data source and access confirmed.
- Baseline extraction date scheduled.
- Target values approved by engineering leadership.

## Baseline Extraction Metadata
- Extraction date: 2026-02-25
- Extraction mode: Local repository and local shell commands only
- Notes:
- CI/CD and production delivery metrics are blocked by missing pipeline telemetry.
- Security vulnerability counts are blocked until scanner tooling is installed and run in CI.
