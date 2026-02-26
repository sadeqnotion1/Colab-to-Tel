# Baseline Report (Initial Pass)

## Metadata
| Field | Value |
|---|---|
| Repo | Colab_Telegram_Leecher |
| Baseline Date | 2026-02-25 |
| Mode | Local shell baseline (no CI telemetry available) |
| Auditor | Codex + repository command outputs |
| Confidence | Medium (high for local/static metrics, low for delivery metrics) |

## Executive Snapshot
- Provisional weighted score: `31/100` (from `audit/scorecard.md`)
- Highest-risk domains: Correctness, Security, CI/CD reliability
- Key blockers to world-class posture:
- No CI pipeline or branch gating (`.github/` missing)
- Tracked secret-bearing file (`credentials.json`) in git index
- Test system is non-deterministic and does not run formal tests
- High lint error volume and major complexity hotspots

## Repository Inventory
| Metric | Value | Evidence |
|---|---:|---|
| Total commits | 167 | `git rev-list --count HEAD` |
| Commits in last 30 days | 13 | `git log --since=...` |
| Commits in last 90 days | 167 | `git log --since=...` |
| Contributors (all-time) | 9 | `git shortlog -sn --all` |
| Python files in `colab_leecher` | 57 | `rg --files -g "*.py" colab_leecher` |
| Python LOC in `colab_leecher` | 21,905 | line-count aggregation |
| Python files in `tests` | 12 | `rg --files -g "*.py" tests` |
| Python LOC in `tests` | 1,375 | line-count aggregation |
| Markdown docs under `docs/` | 42 | `Get-ChildItem docs -Recurse -Filter *.md` |
| Docs fresh in last 90 days | 42/42 (100%) | filesystem timestamps |

## Dependency Baseline
| Metric | Value | Evidence |
|---|---:|---|
| Requirements entries | 22 | `requirements.txt` |
| Strict-pinned (`==`) | 1 | regex on requirements |
| Minimum-pinned (`>=`) | 5 | regex on requirements |
| Unpinned | 16 | regex on requirements |
| Dependency integrity check | Pass | `python -m pip check` |

Interpretation:
- Environment compatibility is currently broad and non-reproducible due low pinning ratio.

## Quality Baseline
### Static Lint
- `ruff check colab_leecher tests --statistics`
- Total: `1184` issues
- Top categories:
- `E701`: 438
- `E702`: 307
- `F541`: 150
- `F401`: 108
- `E402`: 35
- `F841`: 35
- `F821`: 32
- `invalid-syntax`: 14

### Complexity and Maintainability
- `radon cc colab_leecher -s -a`
- 490 blocks analyzed
- Average complexity: `B (8.2898)`
- Multiple `F/E` functions in production paths, including:
- `colab_leecher/__main__.py:1194 handle_url` (`F`)
- `colab_leecher/__main__.py:1793 handle_options` (`F`)
- `colab_leecher/utility/task_manager.py:894 Do_Leech` (`F`)
- `colab_leecher/utility/helper.py:323 extract_filename_from_url` (`F`)
- `colab_leecher/utility/converters.py:1711 splitVideo` (`F`)

- Largest modules by LOC:
- `colab_leecher/__main__.py`: 3328
- `colab_leecher/utility/converters.py`: 2063
- `colab_leecher/utility/helper.py`: 1794
- `colab_leecher/utility/task_manager.py`: 1542

### Syntax Compatibility
- `python -m compileall -q colab_leecher` fails:
- `colab_leecher/colab/sabnzbd_setup.py` line 22 contains notebook shell syntax (`!apt-get ...`) invalid in Python module context.

### Test Reliability
- `python -m pytest --collect-only -q` failed during collection:
- Assertion error involving `D:/Projects/Colab_Telegram_Leecher/nul`
- No tests collected

- `python -m unittest discover -s tests -p "test*.py"`:
- Ran `0` tests
- Executed debug scripts with runtime side effects/output

Interpretation:
- The current test folder is not a deterministic verification suite.
- Debug/diagnostic scripts are mixed with test-discovery patterns.

## Security Baseline
| Check | Result | Evidence |
|---|---|---|
| Tracked credentials-like file | **Fail** | `git ls-files credentials.json` returned tracked file |
| Ignore rules for credentials/session | Present | `.gitignore` contains credentials/session patterns |
| Vulnerability scanner run | Blocked | `pip-audit` missing |
| SAST scanner run | Blocked | `bandit` missing |
| Secrets scanning gate | Missing | no pre-commit/CI scanner config detected |

Interpretation:
- Secret handling is currently high-risk because ignored files were previously committed and remain tracked.

## CI/CD and Tooling Baseline
| Area | Result | Evidence |
|---|---|---|
| CI workflow definitions | Missing | `.github/` absent |
| Tooling configs (`pyproject`, `pytest.ini`, `pre-commit`) | Missing | config search returned none |
| Branch-quality gate telemetry | Unknown | no pipeline data source |
| Release reliability metrics | Unknown | no centralized release logs in repo |

## High-Priority Findings
| Severity | Finding | Evidence | Immediate Action |
|---|---|---|---|
| P0 | No CI pipeline/gates | `.github/` missing | Add CI with required checks (lint, tests, compile, security) |
| P0 | `credentials.json` tracked in git | `git ls-files credentials.json` | Remove from index/history, rotate impacted credentials |
| P0 | Test architecture non-functional | pytest/unittest baseline | Separate debug scripts; build deterministic pytest suite |
| P0 | Syntax-invalid module in package path | `compileall` failure | Move notebook shell code outside importable module path |
| P1 | High maintainability risk from monolithic hotspots | radon complexity + large files | Prioritized refactor of top 5 hotspot functions/modules |
| P1 | Dependency reproducibility risk | 16/22 unpinned deps | Add lock strategy and pin policy with update cadence |

## Baseline Coverage Gaps
- CI metrics (M01/M02) unavailable until CI exists.
- Coverage and flake metrics (M03/M05) unavailable until valid tests exist.
- Vulnerability counts (M10/M12) unavailable until security tooling is installed.
- Deployment/incident metrics (M06-M09) unavailable until release + incident logs are standardized.

## Recommended Next 7 Days
1. Create CI workflow with mandatory checks for main.
2. Remove tracked credentials file and rotate secrets.
3. Restructure tests into executable unit/integration suites.
4. Isolate notebook-only shell code from Python package imports.
5. Add minimum static policy: `ruff`, `pytest`, `compileall`, and secret scanning gates.

## Remediation Update (Wave 1, 2026-02-25)
Completed:
- Added CI workflow with compile/unit-test/security-hook jobs (`.github/workflows/ci.yml`).
- Added deterministic `pytest` configuration and initial `tests/unit` suite (6 passing tests).
- Added pre-commit secret guardrails (`.pre-commit-config.yaml` + `scripts/security/block_sensitive_files.py`).
- Removed invalid notebook shell syntax from `colab_leecher/colab/sabnzbd_setup.py` (now compile-safe Python).
- Removed tracked `credentials.json` from git index (`git rm --cached credentials.json`) and added `credentials.json.example`.

Validation after remediation:
- `python -m compileall -q colab_leecher tests/unit` -> pass
- `pytest -q` -> 6 passed
- `python scripts/security/block_sensitive_files.py` -> pass
- `pre-commit run --all-files` -> pass

## Remediation Update (Wave 2, 2026-02-25)
Completed:
- Added integration scaffolding (`tests/integration/*`) with explicit opt-in marker and runner flag.
- Split CI into branch-protection-friendly required checks:
- `lint`
- `unit-tests (py3.12)`
- `integration-scaffold`
- `security-guardrails`
- Added branch-protection checklist document (`docs/development/BRANCH_PROTECTION_CHECKS.md`).

Validation after remediation:
- `pytest -q tests/integration -m integration --runintegration` -> pass
- `ruff check tests/unit tests/integration scripts/security` -> pass
