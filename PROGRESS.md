# Progress Log

CLAUDE.md is the plan. This file is the record of what actually happened —
use it to catch up after a break instead of re-reading the whole chat.

## Repository map

| Path | What it is |
|---|---|
| `CLAUDE.md` | Project plan/spec: purpose, architecture, phases, rules. Read this first. |
| `PROGRESS.md` | This file — session log and file map, updated as we go. |
| `pyproject.toml` | Project metadata + dependencies, managed by `uv`. |
| `uv.lock` | Exact pinned dependency versions/hashes. Committed for reproducibility. |
| `.python-version` | Pins the Python version (3.13) `uv` uses for this project. |
| `.gitignore` | Excludes `.venv/`, `.env`, `raw/`, `staged/`, caches, editor files. |
| `.env.example` | Template for `.env` — shows which env vars are needed (`DB_CLIENT_ID`, `DB_API_KEY`), no real values. |
| `.env` | Real DB API credentials. Gitignored, never commit. |
| `src/db_delay_tracker/client.py` | `DBTimetablesClient` — thin wrapper around the DB Timetables API (auth headers, base URL, `/station`, `/plan`, `/fchg`, `/rchg` methods). Returns raw XML text, does not parse. Reused by future collector code. |
| `src/db_delay_tracker/stations.py` | Hardcoded list of the 8 Munich-area stations we track (name, EVA number, ds100 code), confirmed via real `/station/{exact-name}` lookups. |
| `scripts/explore_api.py` | Phase 1 exploration script. Pulls `/plan` + `/fchg` for all 8 stations and saves raw XML to `tests/fixtures/`. Run with `uv run scripts/explore_api.py`. |
| `tests/fixtures/` | Real raw XML responses saved for later parser development/testing. `plan_{eva}_{yymmdd}{hh}.xml` (static schedule) and `fchg_{eva}.xml` (changes/delays) per station. |

## Session log

### 2026-09-21 — Phase 0 (setup) and Phase 1 (API exploration)

**Phase 0 — repo, tooling, DB API access**
- Installed `uv`, ran `uv init` (created `pyproject.toml`, `src/` layout, `git init`'d the repo on branch `main`).
- Added `.gitignore` and `.env.example`.
- Added dependencies: `requests`, `lxml`, later `python-dotenv`.
- First commit pushed to `github.com/finnique/db-delay-tracker` — accidentally included `CLAUDE.md` (not meant to be public). Fixed by squashing all history into a single fresh commit (`git checkout --orphan` + force-push) since there was nothing else worth preserving yet. **Lesson: add `.gitignore` entries *before* the first commit, not after** — untracking a file later doesn't remove it from already-pushed history.
- Registered a DB API Marketplace account and application, got `DB-Client-Id`/`DB-Api-Key`.
- Hit a 403 Forbidden on first calls — cause was not having *subscribed the application* to the Timetables API product specifically (creating an app and subscribing to a product are separate steps in DB's marketplace). Fixed by subscribing to the free plan (60 calls/min) from the product catalog page.

**Phase 1 — explore the API, save fixtures**
- Built `DBTimetablesClient` (`src/db_delay_tracker/client.py`): auth headers, base URL, thin methods for `/station`, `/plan`, `/fchg`, `/rchg`. No parsing — returns raw XML text, matching the "collector doesn't parse" architecture rule.
- Explored `/station/{pattern}` manually via PowerShell (`Invoke-WebRequest`/`Invoke-RestMethod`). **Key finding: this endpoint is an exact/near-exact name lookup, not a fuzzy search.** A bare prefix like `"Frankfurt"` doesn't return all Frankfurt stations — it appears to seek the nearest entry in sorted order (ASCII sort puts `"Frankfurt "` before `"Frankfurt("`, which explains the odd single result we first got). `*` wildcard did not work as hoped. Reliable approach: query the exact official DB station name (URL-escaped via `[uri]::EscapeDataString` to handle umlauts correctly).
- Looked up and confirmed 8 Munich-area stations by exact name, hardcoded into `src/db_delay_tracker/stations.py` rather than re-discovering them on every run:
  - München Hbf (8000261), München Ost (8000262), München-Pasing (8004158),
    München Flughafen Terminal (8004168), München-Trudering (8004162),
    München Heimeranplatz (8005419), Ismaning (8003092), Freising (8002078).
- Ran `scripts/explore_api.py` to pull `/plan` + `/fchg` for all 8 stations → 16 raw XML fixtures saved in `tests/fixtures/` (sizes ranged ~4.5KB to ~350KB, biggest at München Hbf, matching CLAUDE.md's expectation that big hubs have large `fchg` feeds).
- Read real fixture content and identified the core data model:
  - `id` attribute is the join key between `plan.xml` and `fchg.xml` for the same stop.
  - `pt` (planned time, in plan) vs `ct` (changed/forecast time, in fchg) — delay = `ct - pt`.
  - Each `<ar>`/`<dp>` in `fchg` can carry multiple `<m>` (message) elements, each with its own `ts-tts` — confirms the "late-arriving duplicate updates" problem from CLAUDE.md: polling repeatedly will re-see the same stop `id` with an evolving message set, so storage/merge must be idempotent, not append-only.
  - Message type codes (`t="d"`, `t="h"`, etc.) aren't self-evident from the XML — need the OpenAPI spec doc to decode them (not yet pulled locally).
- Considered and rejected using the third-party `deutsche-bahn-api` PyPI package: it parses responses for you, which conflicts with the "collector stores raw XML untouched" architecture rule, and using it would remove the point of this project (learning to handle the raw API's messiness).
- Added a pointer from `CLAUDE.md` to this file so the plan and the record are easy to find from either side.
- Committed everything: client, stations list, exploration script, fixtures, this log (`1c30ca5 add log, explore_api`). `CLAUDE.md` itself stays untracked/local by design (see the history-scrub note above).

## Next session

- [ ] Pull the official OpenAPI spec (`Timetables-*.json`) into `docs/` per CLAUDE.md, to decode message type codes (`t="d"`, `t="h"`, ...) properly instead of guessing.
- [ ] Look at `/rchg` (recent changes) fixture to compare against `/fchg` — understand what's different about the "last ~2 min" feed.
- [ ] Find/inspect a cancellation example in the saved fixtures (haven't confirmed what a cancelled stop looks like in the XML yet).
- [ ] Decide phase 1 "done" criteria are met, then start Phase 2: Terraform for S3, IAM, SSM.
- [ ] Explicitly plan for DST switch handling (late October) per CLAUDE.md rules — not yet addressed.
