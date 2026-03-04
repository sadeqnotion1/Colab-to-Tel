# Multi-Terminal Checklist

Use this checklist to run roadmap jobs in parallel without branch collisions.

## 1) One-Time Setup (Worktree Mode)
Run from repository root:

```powershell
git fetch --all --prune

git worktree add -b job/t1-state-migration ..\wt\t1 HEAD
git worktree add -b job/t2-exception-hardening ..\wt\t2 HEAD
git worktree add -b job/t3-lint-wave1 ..\wt\t3 HEAD
git worktree add -b job/t4-ci-ops-evidence ..\wt\t4 HEAD
```

Each terminal should work in its own folder:
- `..\wt\t1`
- `..\wt\t2`
- `..\wt\t3`
- `..\wt\t4`

## 2) Job Ownership
- `T1` (`job/t1-state-migration`): `R90-005`
  - Files: `colab_leecher/__main__.py`, `colab_leecher/utility/reply_state.py`, `colab_leecher/utility/variables.py`, `colab_leecher/utility/handler.py`
- `T2` (`job/t2-exception-hardening`): `R90-006`
  - Files: `colab_leecher/scripts/utils/streaming_extract_function.py`, `colab_leecher/downlader/*.py`, `colab_leecher/utility/sabnzbd_*.py`
- `T3` (`job/t3-lint-wave1`): `R90-007`
  - Files: `colab_leecher/utility/*.py` except files owned by `T1`/`T2`
- `T4` (`job/t4-ci-ops-evidence`): `R90-004` + `R90-009`
  - Files: `.github/workflows/ci.yml`, `docs/development/*`, `docs/operations/*`, `audit/release-gates.md`

Rule: do not edit another terminal's owned files while that terminal is active.

## 3) Per-Terminal Start Commands
Run in each terminal's worktree folder:

```powershell
git status --short
python -m compileall -q colab_leecher
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest -q tests/unit
```

If security-relevant:

```powershell
bandit -q -r <touched-paths> -f json -o audit/raw/local/<report>.json
```

## 4) Commit Format
Use clear slice commits:

```powershell
git add -A
git commit -m "R90-00X: <slice summary>"
```

## 5) Merge Order
Merge in this order:
1. `T1` state migration
2. `T2` exception hardening
3. `T3` lint wave
4. `T4` CI/docs evidence

Recommended merge flow from main repo root:

```powershell
git switch main
git pull --ff-only

git merge --no-ff job/t1-state-migration
git merge --no-ff job/t2-exception-hardening
git merge --no-ff job/t3-lint-wave1
git merge --no-ff job/t4-ci-ops-evidence
```

If conflicts occur, stop and resolve only in the current merge step before continuing.

## 6) End-of-Day Sync
For each worktree terminal:

```powershell
git fetch origin
git rebase origin/main
python -m compileall -q colab_leecher
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'; pytest -q tests/unit
```

## 7) Cleanup (After Merge)
From main repo root:

```powershell
git worktree remove ..\wt\t1
git worktree remove ..\wt\t2
git worktree remove ..\wt\t3
git worktree remove ..\wt\t4
git worktree prune
```
