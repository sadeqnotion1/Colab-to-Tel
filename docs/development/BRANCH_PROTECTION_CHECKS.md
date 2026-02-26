# Branch Protection Checks

This document defines the required status checks for protected branches.

## Target Branches
- `main`
- `master` (if still active)

## Required Status Checks
Configure these checks as required in branch protection rules:

1. `lint`
2. `unit-tests (py3.12)`
3. `integration-scaffold`
4. `security-guardrails`

These check names map to jobs in:
- `.github/workflows/ci.yml`

## Recommended Branch Rules
Enable:
- Require a pull request before merging
- Require approvals (minimum 1)
- Dismiss stale approvals when new commits are pushed
- Require conversation resolution before merging
- Require status checks to pass before merging
- Require branches to be up to date before merging
- Restrict direct pushes to protected branches

## Operational Notes
- Integration tests are scaffolded and deterministic by default.
- Unit tests and integration tests are executed in separate jobs.
- Sensitive-file checks run both as a standalone script and through pre-commit hooks.
