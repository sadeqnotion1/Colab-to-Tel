# Rollback Runbook

## Purpose
Restore service quickly and safely when a release introduces high-impact regressions.

Evidence template reference: `docs/operations/EVIDENCE_LOG_TEMPLATES.md`

## Trigger Conditions
- Sev-1 incident after release.
- Sev-2 incident with sustained user impact.
- Critical security or data-integrity defect introduced by latest merge.

## Roles
- Rollback lead: Release owner
- Technical approver: Engineering lead
- Communications owner: Ops owner

## Decision Window
- Sev-1: decide rollback within 15 minutes.
- Sev-2: decide rollback within 60 minutes.

## Evidence Directory
Use one folder per rollback event:

```powershell
$UtcStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$EvidenceDir = "docs/operations/evidence/$UtcStamp-rollback"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
```

## Preferred Rollback Method (Live)
Use a non-destructive revert commit on protected branch.

```powershell
$RollbackTarget = "<merge_commit_sha>"
git fetch origin
git checkout main
git pull --ff-only
git revert $RollbackTarget --no-edit
git push origin main
```

If policy requires rollback through PR:
```powershell
$ShortSha = (git rev-parse --short HEAD).Trim()
git checkout main
git pull --ff-only
git checkout -b "rollback/$ShortSha"
git revert $RollbackTarget --no-edit
git push origin "rollback/$ShortSha"
```
Open PR and merge after required checks pass.

## Rollback Drill Procedure (R90-009 Evidence)
Use this when running a controlled drill without pushing rollback changes.

```powershell
$RollbackTarget = "<merge_commit_sha>"
$DecisionUtc = (Get-Date).ToUniversalTime().ToString("o")
git fetch origin
git checkout main
git pull --ff-only
git revert --no-commit $RollbackTarget
git status --short 2>&1 | Tee-Object "$EvidenceDir/revert-preview.txt"
git diff --stat 2>&1 | Tee-Object "$EvidenceDir/revert-diffstat.txt"
git revert --abort
$RestoreUtc = (Get-Date).ToUniversalTime().ToString("o")
$ElapsedMinutes = [math]::Round((New-TimeSpan -Start ([datetime]$DecisionUtc) -End ([datetime]$RestoreUtc)).TotalMinutes, 2)
@"
decision_time_utc=$DecisionUtc
restore_time_utc=$RestoreUtc
elapsed_minutes=$ElapsedMinutes
"@ | Set-Content "$EvidenceDir/timestamps.txt"
```

## Post-Rollback Verification
1. Required checks pass on rollback commit.
2. Bot startup succeeds:
```powershell
python -m colab_leecher
```
3. Core smoke validation:
```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q tests/unit
python scripts/security/block_sensitive_files.py
```
4. Confirm incident symptoms no longer reproduce.

## Evidence to Capture
| field | value |
|---|---|
| incident_id |  |
| rollback_commit |  |
| trigger_release_sha |  |
| decision_time_utc |  |
| restore_time_utc |  |
| elapsed_minutes |  |
| revert_preview_path | `<evidence_dir>/revert-preview.txt` |
| revert_diffstat_path | `<evidence_dir>/revert-diffstat.txt` |
| verification_links | CI run URL, PR URL, incident URL |
| action_items | numbered list with owners + due dates |

## Drill Completion Checklist (R90-009)
- `decision_time_utc` and `restore_time_utc` recorded in UTC.
- Elapsed minutes calculated and documented.
- Revert preview and diffstat artifacts saved under `docs/operations/evidence/<utc-stamp>-rollback/`.
- At least one follow-up action item created with owner and due date.

## Follow-Up
1. Open root-cause issue within 24 hours.
2. Add regression test before re-release.
3. Update release notes and incident postmortem.
