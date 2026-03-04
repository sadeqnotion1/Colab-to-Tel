# Branch Protection Checks

This document defines required branch-protection checks for R90-004 (strict dependency gate).

## Target Branches
- `main`
- `master` (if still active)

## Required Status Checks
Configure these checks as required:

1. `lint`
2. `unit-tests (py3.12)`
3. `integration-scaffold`
4. `security-guardrails`
5. `dependency-audit-linux`

Source of truth: `.github/workflows/ci.yml`

## Local Verification Commands
Run from repository root.

1. Install local tooling:

```powershell
python -m pip install --upgrade pip
python -m pip install pytest pre-commit pip-audit pyyaml
```

2. Validate workflow YAML parses and required check names are present:

```powershell
@'
from pathlib import Path
import yaml

wf = yaml.safe_load(Path(".github/workflows/ci.yml").read_text(encoding="utf-8"))
required = {"lint", "unit-tests (py3.12)", "integration-scaffold", "security-guardrails", "dependency-audit-linux"}
jobs = {(job.get("name", key).replace("${{ matrix.python-version }}", "3.12")) for key, job in wf["jobs"].items()}
missing = required - jobs
print("Workflow:", wf.get("name"))
print("Checks:", sorted(jobs))
assert not missing, f"Missing required checks: {sorted(missing)}"
print("OK: all required checks found.")
'@ | python -
```

3. Validate referenced script and test paths:

```powershell
@'
from pathlib import Path

refs = [
    "scripts/security/block_sensitive_files.py",
    "scripts/security/run_dependency_audit.py",
    "tests/unit",
    "tests/integration",
    "requirements.txt",
]
missing = [p for p in refs if not Path(p).exists()]
print("Missing:", missing)
assert not missing, f"Missing referenced paths: {missing}"
print("OK: all referenced paths exist.")
'@ | python -
```

4. Run gate commands locally:

```powershell
python -m compileall -q colab_leecher tests/unit tests/integration
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q tests/unit
pytest -q tests/integration -m integration --runintegration
python scripts/security/block_sensitive_files.py
pre-commit run --all-files
python scripts/security/run_dependency_audit.py --requirements requirements.txt --report-dir audit/raw/local --fail-on-vulns
```

`run_dependency_audit.py` returns non-zero when vulnerabilities are found in strict mode. That is expected gate behavior.

## Branch Rule Settings
Enable these repository rules:

- Require a pull request before merging
- Require approvals (minimum 1)
- Dismiss stale approvals when new commits are pushed
- Require conversation resolution before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Restrict direct pushes to protected branches

## Evidence Checklist
- Screenshot or exported settings proving all 5 checks are required.
- URL to a passing PR where all required checks are green.
- URL to a failing PR/run where `dependency-audit-linux` blocks merge when vulnerabilities exist.
