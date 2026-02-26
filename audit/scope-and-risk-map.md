# Scope and Risk Map

## Scope Inventory
| Component/Area | Type | Criticality (H/M/L) | Owner | In Scope (Y/N) | Notes |
|---|---|---|---|---|---|
| Bot orchestration (`colab_leecher/__main__.py`) | Application | H | SadeQ (acting) | Y | 3328-line entrypoint with high complexity hotspots |
| Download pipeline (`colab_leecher/downlader/*`) | Application | H | SadeQ (acting) | Y | 17 downloader modules; multiple F/E complexity functions |
| Upload pipeline (`colab_leecher/uploader/*`) | Application | H | SadeQ (acting) | Y | Telegram and GDrive upload critical path |
| Utility/state layer (`colab_leecher/utility/*`) | Application | H | SadeQ (acting) | Y | Shared state and extraction logic, large helper modules |
| Colab setup/cells (`colab_leecher/colab/*`) | Platform | M | SadeQ (acting) | Y | Includes notebook shell syntax not valid in Python runtime |
| Test harness (`tests/*`, root `test_*.py`) | Quality | H | SadeQ (acting) | Y | Current files are debug scripts, not deterministic test suite |
| Documentation (`docs/*`) | Process | M | SadeQ (acting) | Y | 42 markdown docs updated within 90 days |

## Out-of-Scope Register
| Item | Reason Excluded | Review Date |
|---|---|---|
| Historical runtime logs and session journals at repo root | Evidence-only artifacts, not active application source | 2026-03-15 |
| External SaaS internals (Telegram/Mega/Google APIs) | Managed by providers, only integration behavior audited | 2026-03-15 |

## Dependency Map
| Source Component | Dependency | Type (internal/external) | Failure Impact | Fallback/Recovery | Owner |
|---|---|---|---|---|---|
| Bot runtime | Telegram API via PyroFork | External | Bot cannot receive/send commands and uploads | Retry/backoff; service health command | SadeQ (acting) |
| GDrive uploader | Google Drive API/client | External | Mirror workflows fail | Switch to Telegram upload mode | SadeQ (acting) |
| Downloader manager | `aria2c` binary | External tool | HTTP/torrent download features degrade | Fallback to requests-based downloaders for some links | SadeQ (acting) |
| NZB downloader | SABnzbd + provider NNTP creds | External service | NZB tasks fail or stall | Native NZB fallback / provider failover | SadeQ (acting) |
| Mindvalley downloader | `yt-dlp` / `N_m3u8DL-RE` / ffmpeg | External toolchain | Stream downloads or merges fail | Alternate downloader path and retry | SadeQ (acting) |
| Local execution | Python package environment | External runtime | Import/runtime mismatches, nondeterministic behavior | Lock and pin dependencies; reproducible env | SadeQ (acting) |

## Risk Register
Risk score formula:
- `Risk Score = Likelihood (1-5) * Impact (1-5)`

| Risk ID | Risk Description | Likelihood | Impact | Score | Priority | Owner | Mitigation Plan | Trigger |
|---|---|---:|---:|---:|---|---|---|---|
| R01 | No CI pipeline or branch gates allows regressions into main | 5 | 5 | 25 | P0 | SadeQ (acting) | Implement GitHub Actions + required checks + protected branches | Any direct main change without checks |
| R02 | Secret material exposure risk (`credentials.json` tracked in git) | 5 | 5 | 25 | P0 | SadeQ (acting) | Remove tracked secret file, rotate credentials, add secret scanning | Any secret-like file tracked in git |
| R03 | Test harness is non-deterministic and executes debug scripts (0 real tests) | 5 | 4 | 20 | P0 | SadeQ (acting) | Split debug scripts from tests, create pytest suite, add coverage gate | `pytest` fails collection or collects 0 tests |
| R04 | Python syntax incompatibility in Colab setup modules (`!apt-get` in `.py`) | 4 | 4 | 16 | P0 | SadeQ (acting) | Isolate notebook-only code and exclude from runtime package checks | `compileall` syntax errors in main package |
| R05 | High-complexity hotspots reduce maintainability and raise defect risk | 4 | 4 | 16 | P1 | SadeQ (acting) | Decompose large functions/modules with staged refactor plan | New features touching F-grade complexity blocks |

## High-Risk Areas for Early Review
1. Authentication/credentials handling
2. `__main__.py`, `utility/helper.py`, `utility/converters.py` hotspot refactor boundaries
3. Test strategy redesign (unit/integration split, deterministic fixtures)
4. Dependency update and pinning strategy (`requirements.txt` mostly unpinned)
5. CI/release gate implementation and rollback safety

## Day 1 Acceptance Criteria
- In-scope boundary approved.
- Out-of-scope list approved.
- Top 5 risks have owners and mitigation plans.
- P0/P1 priorities agreed.
