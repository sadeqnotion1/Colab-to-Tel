# Release Gates (Week 3)

## Metadata
| Field | Value |
|---|---|
| Date | 2026-02-27 |
| Phase | Week 3: CI/CD and release hardening |
| Source workflow | `.github/workflows/ci.yml` |
| Branch rules reference | `docs/development/BRANCH_PROTECTION_CHECKS.md` |
| Runbook references | `docs/operations/RELEASE_RUNBOOK.md`, `docs/operations/ROLLBACK_RUNBOOK.md`, `docs/operations/INCIDENT_RUNBOOK.md` |

## Required Gates
| gate_id | check_name | type | enforcement | fail condition | artifact source |
|---|---|---|---|---|---|
| RG-001 | `lint` | Quality | Required in branch protection | Ruff violations or complexity budget regression | GitHub Actions job log |
| RG-002 | `unit-tests (py3.12)` | Correctness | Required in branch protection | Unit test or compile failure | GitHub Actions job log |
| RG-003 | `integration-scaffold` | Correctness | Required in branch protection | Integration scaffold failure | GitHub Actions job log |
| RG-004 | `security-guardrails` | Security | Required in branch protection | Sensitive-file or pre-commit hook failure | GitHub Actions job log |
| RG-005 | `dependency-audit-linux` | Dependency Security | Required in branch protection | Vulnerability found in strict mode (`--fail-on-vulns`) | `dependency-audit-linux-report` workflow artifact |

## R90-004 Gate Verification (Checklist)
- [ ] Branch protection requires `dependency-audit-linux` with RG-001 through RG-004.
  Blocked: GitHub branch-protection API is unavailable for this private repo plan (`HTTP 403`: "Upgrade to GitHub Pro or make this repository public to enable this feature.").
- [ ] Passing CI run URL at merge commit is recorded.
  Blocked: remote default branch currently does not expose `.github/workflows/ci.yml` (`gh run list --workflow ci.yml` returns `HTTP 404`).
- [x] Strict-mode dependency audit summary is reproducible locally (`audit/raw/local/dependency-audit-summary.json`) and CI is configured to upload `audit/raw/ci/*` artifacts even on failure.
- [ ] At least one blocked/failing strict-mode run URL is recorded (proof that merge is blocked on vulnerabilities).
  Blocked until `ci.yml` is available on remote default branch.

## R90-004 Local Reproduction Commands
Run from repository root.

```powershell
python -m pip install --upgrade pip
python -m pip install pytest pre-commit pip-audit pyyaml
@'
from pathlib import Path
import yaml

wf = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
required = {"lint", "unit-tests (py3.12)", "integration-scaffold", "security-guardrails", "dependency-audit-linux"}
jobs = {(job.get("name", key).replace("${{ matrix.python-version }}", "3.12")) for key, job in wf["jobs"].items()}
missing = required - jobs
print("Checks:", sorted(jobs))
assert not missing, f"Missing checks: {sorted(missing)}"
'@ | python -
python scripts/security/run_dependency_audit.py --requirements requirements.txt --report-dir audit/raw/local --fail-on-vulns
Get-Content audit/raw/local/dependency-audit-summary.json
python scripts/quality/check_complexity_budget.py --target colab_leecher --baseline audit/complexity-f-baseline.json
```

## R90-009 Operational Evidence (Checklist)
- [x] One rollback drill executed with UTC timestamps and elapsed minutes.
- [x] Rollback drill artifacts stored under `docs/operations/evidence/20260227-111424/`.
- [x] One incident tabletop executed with MTTR value and CFR impact field.
- [x] Tabletop artifacts stored under `docs/operations/evidence/20260227-111424/`.
- [x] Action items recorded with owner and due date for both exercises.

## Execution Evidence (2026-02-27)
- Branch-protection query attempt:
  - `gh api repos/theSadeQ/Colab-to-Tel/branches/master/protection`
  - Result: `HTTP 403` plan limitation (private-repo branch-protection API unavailable).
- CI run evidence query attempt:
  - `gh run list --repo theSadeQ/Colab-to-Tel --workflow ci.yml --limit 30`
  - Result: `HTTP 404` (`ci.yml` not found on remote default branch).
- Rollback drill evidence:
  - `docs/operations/evidence/20260227-111424/rollback-drill-evidence.md`
  - `docs/operations/evidence/20260227-111424/revert-preview.txt`
  - `docs/operations/evidence/20260227-111424/timestamps.txt`
- Incident tabletop evidence:
  - `docs/operations/evidence/20260227-111424/incident-tabletop-evidence.md`
  - `docs/operations/evidence/20260227-111424/tabletop-log.txt`
  - `docs/operations/evidence/20260227-111424/pytest-unit.txt`
  - `docs/operations/evidence/20260227-111424/sensitive-files.txt`
- Dependency audit rerun evidence (post-remediation):
  - Command: `python scripts/security/run_dependency_audit.py --requirements requirements.txt --report-dir audit/raw/local --fail-on-vulns`
  - Result: `mode=direct`, `vulnerability_total=0`, `packages_with_vulns=0`
  - Artifact: `audit/raw/local/dependency-audit-summary.json`
- Complexity guardrail evidence:
  - Command: `python scripts/quality/check_complexity_budget.py --target colab_leecher --baseline audit/complexity-f-baseline.json`
  - Result: pass (`no new/regressed F-grade blocks`)
  - Baseline artifact: `audit/complexity-f-baseline.json`

## R90-009 Evidence Templates
Use `docs/operations/EVIDENCE_LOG_TEMPLATES.md` and runbooks to produce:
- `release-evidence.md`
- `rollback-drill-evidence.md`
- `incident-tabletop-evidence.md`

## Metric Mapping (from `audit/metric-catalog.md`)
| metric | data source after gate hardening |
|---|---|
| M06 Lead Time for Change | PR merge timestamp + release evidence timestamp |
| M07 Deployment Frequency | Count of release evidence records per week |
| M08 Change Failure Rate | Rollback/incident-tagged releases / total releases |
| M09 MTTR | Incident `started_at_utc` vs `restore_time_utc` from tabletop/live records |

## Week 3 Exit Criteria
1. RG-001 through RG-005 are configured as required branch checks.
2. `dependency-audit-linux` uploads artifacts even when strict mode fails.
3. Release, rollback, and incident runbooks include reproducible commands.
4. R90-004 and R90-009 evidence checklists have concrete artifacts and owners.
