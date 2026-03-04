# Incident Response Runbook

## Purpose
Standardize incident handling, escalation, and recovery evidence for production-impact events.

Evidence template reference: `docs/operations/EVIDENCE_LOG_TEMPLATES.md`

## Severity Levels
- Sev-1: Full outage, data loss risk, or critical security impact.
- Sev-2: Major feature unavailable or severe degradation.
- Sev-3: Limited impact with workaround available.

## Response Targets
- Sev-1: acknowledge in 15 minutes.
- Sev-2: acknowledge in 60 minutes.
- Sev-3: acknowledge in 4 hours.

## Initial Triage Checklist
1. Create incident ID: `INC-YYYYMMDD-<n>`.
2. Record detection timestamp (UTC).
3. Identify blast radius:
   - Which commands/features fail
   - Which users/flows are affected
4. Assign incident commander.
5. Decide containment action:
   - Disable feature path
   - Pause releases
   - Rollback (see rollback runbook)

## Evidence Directory
Use one folder per incident or tabletop:

```powershell
$UtcStamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$EvidenceDir = "docs/operations/evidence/$UtcStamp-incident"
New-Item -ItemType Directory -Force -Path $EvidenceDir | Out-Null
```

## Containment and Recovery
1. Reproduce quickly on latest commit.
2. Collect logs and failed job links.
3. Execute one of:
   - Hotfix PR + required checks
   - Rollback to last known good commit
4. Validate recovery with smoke checks:
```powershell
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q tests/unit
python scripts/security/block_sensitive_files.py
```
5. Confirm recovery timestamp (UTC).

## Incident Tabletop Procedure (R90-009 Evidence)
Use this to run a no-impact tabletop and capture MTTR/CFR evidence.

```powershell
$IncidentId = "INC-$((Get-Date).ToUniversalTime().ToString('yyyyMMdd'))-TT1"
$StartUtc = (Get-Date).ToUniversalTime().ToString("o")
@"
incident_id=$IncidentId
scenario=Dependency audit gate blocks urgent release
started_at_utc=$StartUtc
severity=Sev-2
incident_commander=<name>
"@ | Set-Content "$EvidenceDir/tabletop-log.txt"

$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
pytest -q tests/unit 2>&1 | Tee-Object "$EvidenceDir/pytest-unit.txt"
python scripts/security/block_sensitive_files.py 2>&1 | Tee-Object "$EvidenceDir/sensitive-files.txt"

$RestoreUtc = (Get-Date).ToUniversalTime().ToString("o")
$MttrMinutes = [math]::Round((New-TimeSpan -Start ([datetime]$StartUtc) -End ([datetime]$RestoreUtc)).TotalMinutes, 2)
@"
restore_time_utc=$RestoreUtc
mttr_minutes=$MttrMinutes
cfr_impacted_release=yes_or_no
action_items=1) <owner>/<date>: <action>
"@ | Add-Content "$EvidenceDir/tabletop-log.txt"
```

## Communication Template
Use this exact format in incident channel/ticket:

| field | value |
|---|---|
| incident_id |  |
| severity | Sev-1/Sev-2/Sev-3 |
| started_at_utc |  |
| detected_by |  |
| affected_surface |  |
| mitigation_in_progress |  |
| eta_next_update |  |

## Incident Closure Criteria
1. User impact ended and verified.
2. Recovery action documented (hotfix or rollback).
3. Timeline completed with UTC timestamps.
4. Owner assigned for postmortem and prevention action.

## Postmortem Minimum Fields
| field | value |
|---|---|
| incident_id |  |
| root_cause |  |
| contributing_factors |  |
| customer_impact |  |
| time_to_detect_min |  |
| time_to_restore_min |  |
| corrective_actions |  |
| preventive_actions |  |

## Tabletop Completion Checklist (R90-009)
- Scenario, owner, and severity recorded in `tabletop-log.txt`.
- UTC start and restore timestamps captured.
- MTTR (minutes) calculated and recorded.
- CFR impact (`yes`/`no`) recorded for the simulated release decision.
- At least one preventive action item is assigned with owner and due date.
