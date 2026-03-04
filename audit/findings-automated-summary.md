# Automated Findings Summary (Week 2)

## Run Date
- 2026-02-26

## Deliverables
- `audit/findings-automated.csv`
- Raw outputs under `audit/raw/`

## Headline Results
- Lint issues: 1171 (`ruff`)
- SAST findings: 30 high, 9 medium, 83 low (`bandit`)
- Dependency vulnerabilities: 14 across 6 packages (`pip-audit`, pinned subset)
- Complexity hotspots: 22 F-grade and 8 E-grade blocks (`radon`)
- SBOM warnings: 21 unpinned components (`cyclonedx-py`)
- License metadata gaps: 1 package with unknown license (`pymegatools`)

## Notable Critical Items
1. `aiohttp 3.13.1` with 8 CVEs (fix at `3.13.3`)
2. `pyrofork 2.2.11` path traversal CVE (fix at `2.3.69`)
3. Overall dependency security posture: 14 known CVEs in active dependencies

## Caveats
- Direct `pip-audit -r requirements.txt` failed on Windows host due `uvloop` build incompatibility.
- Mitigation used: generated pinned requirements from installed project dependencies and audited via `--no-deps`.
- 5 requirements are missing from current host environment and need Linux CI validation:
  - `asyncio`, `opencv-python`, `tgcrypto`, `uvloop`, `sabyenc`

## Immediate Priorities
1. Patch vulnerable dependencies (Critical/High first).
2. Run the new Linux CI dependency-audit job and review artifacts from `dependency-audit-linux-report`.
3. Start staged lint and complexity reduction plan for hotspot modules.

## Control Update (2026-02-26)
- Added Linux CI dependency audit control:
  - Workflow job: `dependency-audit-linux`
  - Runner script: `scripts/security/run_dependency_audit.py`
  - Artifact output: `audit/raw/ci/*` (uploaded by CI)
- Mode is strict (`--fail-on-vulns`) and should be configured as a required branch protection check.
- Ongoing action: keep dependency vulnerability backlog at zero for Critical/High findings.
