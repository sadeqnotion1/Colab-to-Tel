# Release Runbook

## Purpose
Define the standard release workflow for protected branches with reproducible quality gates and release evidence capture.

## Scope
- Branches: `main`, `master` (if active)
- Pipeline source: `.github/workflows/ci.yml`
- Required checks are defined in `docs/development/BRANCH_PROTECTION_CHECKS.md`
- Evidence templates are defined in `docs/operations/EVIDENCE_LOG_TEMPLATES.md`

## Roles
- Release owner: CI/CD owner
- Approver: Engineering lead
- Incident fallback owner: Ops owner

## Preconditions
1. No open `Critical` findings without explicit waiver.
2. Branch protection is enabled with required checks:
   - `lint`
   - `unit-tests (py3.12)`
   - `integration-scaffold`
   - `security-guardrails`
   - `dependency-audit-linux` (required after strict mode enablement)
3. Release candidate is merge-ready via pull request (no direct push).
4. Evidence folder is prepared under `docs/operations/evidence/` for this release.

## Release Procedure
1. Prepare release variables and evidence directory:
```powershell
$ReleaseBranch = "main"
$UtcStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$EvidenceDir = "docs/operations/evidence/$UtcStamp-release"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
```

2. Sync branch and install tooling:
```powershell
git fetch origin
git checkout $ReleaseBranch
git pull --ff-only
python -m pip install --upgrade pip
python -m pip install pytest pre-commit pip-audit
```

3. Run local gates and capture outputs:
```powershell
python -m compileall -q colab_leecher tests/unit tests/integration 2>&1 | Tee-Object "$EvidenceDir/compileall.txt"
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q tests/unit 2>&1 | Tee-Object "$EvidenceDir/pytest-unit.txt"
pytest -q tests/integration -m integration --runintegration 2>&1 | Tee-Object "$EvidenceDir/pytest-integration.txt"
python scripts/security/block_sensitive_files.py 2>&1 | Tee-Object "$EvidenceDir/sensitive-files.txt"
pre-commit run --all-files 2>&1 | Tee-Object "$EvidenceDir/pre-commit.txt"
python scripts/security/run_dependency_audit.py --requirements requirements.txt --report-dir "$EvidenceDir/dependency-audit" --fail-on-vulns
Get-Content "$EvidenceDir/dependency-audit/dependency-audit-summary.json"
```

4. Open or refresh pull request to protected branch.
5. Verify all required checks are green in GitHub Actions.
6. Verify no unresolved review threads and at least one approval.
7. Merge pull request.
8. Record release entry in release log template (below).
9. Monitor first 30 minutes for regressions (errors, failed jobs, user-facing failures).

## Release Log Template
Create or append entries in your team release log using this schema:

| field | value |
|---|---|
| release_id | YYYYMMDD-HHMM-<short_sha> |
| merge_sha |  |
| merged_by |  |
| merged_at_utc |  |
| ci_run_url |  |
| checks_passed | lint, unit-tests, integration-scaffold, security-guardrails, dependency-audit-linux |
| evidence_dir | `docs/operations/evidence/<utc-stamp>-release` |
| dependency_audit_summary | `<evidence_dir>/dependency-audit/dependency-audit-summary.json` |
| risk_notes |  |
| rollback_needed | yes/no |
| rollback_incident_id | n/a or `INC-YYYYMMDD-<n>` |

## Exit Criteria
- Merge completed.
- All required checks passed at merge commit.
- Release log entry completed.
- Evidence directory exists with captured local gate outputs and dependency audit summary.
- No Sev-1/Sev-2 incident opened within the 30-minute stabilization window.

## If Release Fails
Immediately execute `docs/operations/ROLLBACK_RUNBOOK.md`.
