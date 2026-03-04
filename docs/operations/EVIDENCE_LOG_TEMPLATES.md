# Operations Evidence Log Templates

Use these templates to produce checklist-ready evidence for R90-009.

## Directory Convention
Store all artifacts under:

`docs/operations/evidence/<yyyyMMdd-HHmmss>-<release|rollback|incident>/`

## Release Evidence Template
Create `release-evidence.md` in the release evidence directory.

| field | value |
|---|---|
| release_id | `YYYYMMDD-HHMM-<short_sha>` |
| merge_sha |  |
| ci_run_url |  |
| required_checks | lint, unit-tests (py3.12), integration-scaffold, security-guardrails, dependency-audit-linux |
| dependency_audit_summary | `<evidence_dir>/dependency-audit/dependency-audit-summary.json` |
| approval_pr_url |  |
| merged_at_utc |  |
| rollback_needed | yes/no |
| notes |  |

## Rollback Drill Evidence Template
Create `rollback-drill-evidence.md` in rollback evidence directory.

| field | value |
|---|---|
| incident_id | `INC-YYYYMMDD-<n>` |
| rollback_target_sha |  |
| decision_time_utc |  |
| restore_time_utc |  |
| elapsed_minutes |  |
| revert_preview_path | `<evidence_dir>/revert-preview.txt` |
| revert_diffstat_path | `<evidence_dir>/revert-diffstat.txt` |
| verification_links | CI run URL, PR URL |
| action_items | owner + due date |

## Incident Tabletop Evidence Template
Create `incident-tabletop-evidence.md` in incident evidence directory.

| field | value |
|---|---|
| incident_id | `INC-YYYYMMDD-TT<n>` |
| scenario |  |
| severity | Sev-1/Sev-2/Sev-3 |
| started_at_utc |  |
| restore_time_utc |  |
| mttr_minutes |  |
| cfr_impacted_release | yes/no |
| timeline_path | `<evidence_dir>/tabletop-log.txt` |
| action_items | owner + due date |

## Gate-to-Evidence Mapping
| gate | evidence requirement |
|---|---|
| R90-004 | Passing CI run with `dependency-audit-linux` required + strict-mode summary artifact |
| R90-009 | One rollback drill evidence record + one incident tabletop evidence record with MTTR/CFR fields |
