# Rollback Drill Evidence (20260227-111424)

| field | value |
|---|---|
| incident_id | INC-20260227-1 |
| rollback_target_sha | d47bab47f269b2a4238d63826d39b6399ab31653 |
| decision_time_utc | 2026-02-27T11:14:24.8512590Z |
| restore_time_utc | 2026-02-27T11:14:33.0394311Z |
| elapsed_minutes | 0.14 |
| revert_preview_path | docs/operations/evidence/20260227-111424/revert-preview.txt |
| revert_diffstat_path | docs/operations/evidence/20260227-111424/revert-diffstat.txt |
| verification_links | local drill (no remote PR/run URL) |
| action_items | 1) CI-CD owner/2026-03-05: validate rollback against latest merge SHA after push. |
| status | completed |
| notes | Dry-run revert executed in detached worktree at `origin/master`; recovery validation commands were re-run on active branch and captured in tabletop evidence artifacts. |
