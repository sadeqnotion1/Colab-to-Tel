# Governance and Cadence

## Operating Model
This document defines who decides, who executes, and how audit progress is tracked and escalated.

## Cadence
| Meeting | Frequency | Duration | Required Participants | Objective | Output |
|---|---|---:|---|---|---|
| Daily audit standup | Daily (Mon-Fri) | 15 min | SadeQ + workstream delegates | Track blockers and progress | Updated status board |
| Findings triage | Tue/Thu | 45 min | SadeQ, Security delegate, QA delegate, CI/CD delegate | Prioritize findings (P0/P1/P2) | Ranked findings list |
| Governance checkpoint | Weekly | 60 min | Engineering lead + owners | Approve decisions and escalations | Decision log updates |
| Roadmap review | Biweekly | 60 min | Engineering lead + owners | Track remediation execution | Roadmap adjustments |
| Retrospective | Monthly | 45 min | Core contributors | Improve audit process | Retro notes and actions |

## Decision Rights
| Decision Type | Decision Owner | Consulted | SLA |
|---|---|---|---|
| Scorecard changes | SadeQ (Engineering Lead) | Audit lead, Security, QA | 2 business days |
| Security risk acceptance | Security delegate (acting SadeQ) | Engineering Lead | 1 business day |
| CI gate exceptions | CI/CD delegate (or acting SadeQ) | Engineering Lead, QA | 1 business day |
| Scope change | SadeQ (Engineering Lead) | Audit lead | 2 business days |
| Roadmap priority conflict | SadeQ (Engineering Lead) | All workstream owners | 2 business days |

## Escalation Matrix
| Severity | Example | First Response | Escalation Path | Response SLA |
|---|---|---|---|---|
| Sev-1 | Active security exposure / production outage risk | Security or Ops owner | Engineering Lead -> Leadership | < 1 hour |
| Sev-2 | Major release risk / repeated CI failure | CI/CD or QA owner | Engineering Lead | < 4 hours |
| Sev-3 | Standard remediation delay | Workstream owner | Audit Lead | < 1 business day |

## Reporting Template
Use this structure in weekly updates:
1. Overall score trend (week over week)
2. P0/P1 finding status
3. Gate compliance status
4. Risks requiring leadership decision
5. Next-week commitments

## Definition of Done Gates
- All Day 1 artifacts approved.
- Baseline data published and traceable.
- Security and quality gates enforced in CI.
- 30/60/90 roadmap approved with named owners and due dates.

## Attendance and Accountability Rule
If an owner misses 2 consecutive required checkpoints, the workstream is escalated to Engineering Lead for reassignment.
