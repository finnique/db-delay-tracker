# Progress Log

CLAUDE.md is the plan. This file is the record of what actually happened —
use it to catch up after a break instead of re-reading the whole chat.

## Phases (status at a glance)

The phase list comes from CLAUDE.md; this table adds where we are. Keep the
Status column current so this file alone answers "where am I and what's next".

| # | Phase | Status | Notes |
|---|---|---|---|
| 0 | Setup (repo, tooling, DB API access) | Done 2026-09-21 | |
| 1 | Explore API locally, save fixtures | Done 2026-09-21 to 10-03 | Fixtures in `tests/fixtures/`, spec in `docs/`, polling design decided. |
| 2 | Terraform: S3, IAM, SSM | Done 2026-10-03 | |
| 3 | Collector Lambda + schedule + CloudWatch alarm | **Running since 2026-10-04 ~10:00 UTC** | Open: day-1 check, deliberate test of the Errors alarm email. |
| 4 | Parser to Parquet + pytest tests + Glue/Athena | **Next** | Deadline pressure: DST change on 2026-10-25. |
| 5 | dbt models: staging, latest-state merge per stop, fact table, marts, tests | Not started | |
| 6 | GitHub Actions daily dbt build (OIDC), freshness + completeness checks | Not started | |
| 7 | Export marts + Streamlit dashboard | Not started | |
| 8 | README, diagrams, cost breakdown, known limitations | Not started | Limitations are collected in the Next session list. |

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
| `src/db_delay_tracker/keys.py` | `raw_key(endpoint, eva, fetched_at, plan_slice=None)` — pure function that builds the storage key from the UTC fetch time. Validates endpoint, slice and timezone-awareness. |
| `src/db_delay_tracker/storage.py` | `Storage` protocol (single method `put(key, data)`), `LocalStorage` (atomic temp-file + rename; test fake / offline) and `S3Storage` (`put_object`, injectable client, lazy `boto3` import). |
| `src/db_delay_tracker/collector.py` | `collect_once(client, storage, stations, endpoint, now, plan_slice=None)` — fetches one endpoint for every station, gzips, stores raw. One station failing does not stop the others; returns `CollectResult` per station. |
| `src/db_delay_tracker/handler.py` | Lambda entry point. `handler(event, context)` reads `{"endpoint": ...}`, gets DB credentials from SSM (cached across warm invocations), builds `S3Storage` from `BUCKET_NAME`, calls `run(...)`. `run` collects one endpoint (for `plan`: the current and next two Berlin-local hours via `plan_slices`) and raises `CollectionError` if any station failed. |
| `scripts/build_lambda.py` | Builds `build/lambda.zip` (gitignored): `db_delay_tracker/` plus the `lambda` dependency group (`requests`, `boto3`) as Linux arm64 wheels at the `uv.lock` versions. Reproducible zip. Run with `uv run scripts/build_lambda.py` before `terraform apply`. |
| `tests/test_keys.py`, `test_storage.py`, `test_collector.py`, `test_handler.py` | pytest suite (31 tests), including the DST-end repeated hour and DST-safe plan slices. Run with `uv run pytest`. |
| `scripts/explore_api.py` | Phase 1 exploration script. Pulls `/plan` + `/fchg` for all 8 stations and saves raw XML to `tests/fixtures/`. Run with `uv run scripts/explore_api.py`. |
| `scripts/explore_rchg.py` | Fetches `/rchg` twice (2 min apart) for München Hbf + Ismaning and saves `tests/fixtures/rchg_{eva}_{HHMMSS}.xml`. Run with `uv run scripts/explore_rchg.py`. |
| `scripts/compare.py` | First, rough rchg-vs-fchg comparison (the learning version). Superseded by `compare_chg.py`. |
| `scripts/compare_chg.py` | Compares rchg snapshots against fchg: size, subset, same-content, snapshot overlap, plus a unified diff of one differing stop. Run with `uv run scripts/compare_chg.py`. |
| `docs/Timetables-1.0.274.json` | Official OpenAPI spec for the Timetables API (downloaded from the DB marketplace after login). Source of truth for field meanings. |
| `infra/` | Terraform (Phases 2–3). `versions.tf` (provider pins, region), `main.tf` (S3 bucket + hardening), `ssm.tf` (2 SecureString params, placeholder values), `iam.tf` (collector Lambda role + log group), `variables.tf`, `outputs.tf`, `lambda.tf` (collector function, arm64, python3.13), `scheduler.tf` (3 EventBridge schedules + scheduler role), `alarms.tf` (SNS email topic, errors and silence alarms). `terraform.tfvars` (gitignored) holds `alert_email` and `schedules_enabled`. Run from `infra/` with `$env:AWS_PROFILE="terraform-admin"`. State is local and gitignored; `.terraform.lock.hcl` is committed. |
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

### 2026-10-01 — OpenAPI spec

- Saved the official spec (v1.0.274) to `docs/`. A third-party mirror of v1.0.213 was used briefly; diffed against the official file: identical content, so it was deleted.
- Decoded from the spec:
  - Event status `cs`/`ps`: `p` planned (also used when a cancellation is revoked), `a` added, `c` cancelled. Cancelled events also carry `clt` (cancellation time).
  - Message type `t`: `h` HIM, `q` quality change, `f` free text, `d` cause of delay, `i` IBIS, `u` unassigned IBIS, `r` disruption, `c` connection.
  - Stop `id` = `{daily trip id}-{YYMMdd}-{stop index}`; daily trip id can be negative; index > 100 means an added stop.
  - `ct` is "estimated *or actual*" time, so some changed times are actuals (still treat as forecasts by default).
  - `ppth` never includes the current station.
- Not documented in the spec: message `c` codes (incl. delay-cause codes), `dm`, `ec`, `cat`. Treat as opaque or infer from data.
- Fixtures already contain cancellations: 161 `cs="c"` events across the 8 stations (most at München Heimeranplatz and München Ost), 1 `cs="a"`.
- Message counts in fixtures: f 3426, d 3418, h 1655, c 432, q 355, r 12, i 5.

### 2026-10-02 — `/rchg` vs `/fchg`, cancelled stop

- Wrote `scripts/explore_rchg.py`: two `/rchg` passes 2 minutes apart for Hbf (8000261) and Ismaning (8003092), plus a fresh `/fchg` fetched afterwards. Filenames carry an `HHMMSS` timestamp (no `:`, which Windows forbids in filenames).
- Compared with `scripts/compare_chg.py` (results for Hbf; Ismaning had 0 and 1 stops in `rchg` vs 50 in `fchg`):
  - **Size:** `rchg` 17 and 10 stops vs 468 in `fchg` (~2–4%).
  - **Subset:** every `rchg` stop id also exists in `fchg`. `rchg` never adds stops.
  - **Window:** between the two snapshots only 5 of 17 stops stayed, 12 dropped out, 5 were new. `rchg` is a sliding window of roughly 2 minutes, not an accumulating feed.
  - **Content:** most `rchg` stops are identical to their `fchg` entry. The differing ones had only a `ct` changed by a minute (forecast revised; `fchg` was fetched 4–7 min after `rchg`). `rchg` stops are complete `<s>` elements (`ar`/`dp` + `<m>`), not fragments, so a newer one can replace the older version for that `id`.
- **Design implication (proposal, not yet decided):** poll `/rchg` every ~90–120 s (changes are lost if polled less often than the window), and `/fchg` every ~10–15 min as the full-state backstop. 8 stations at 2 min = ~4 calls/min, well under the 60/min limit.
- **Cancelled stop (München Ost, `fchg`):** `cs="c"` sits on the `<ar>`/`<dp>` event, not on `<s>`. The event still carries a stale `ct` (forecast from before the cancellation) and `clt` (cancellation time). **Delay calculation (`ct - pt`) must exclude `cs="c"` events.** Delay-cause `<m t="d">` messages can also be attached to cancelled events.
- Open: not yet checked whether the `<dp>` of that example stop is also cancelled, nor the matching stop in `plan_8000262_...xml`. One `<m>` had `ts` and `ts-tts` a week apart (`ts` is the 10-digit local format, `ts-tts` is `yy-MM-dd HH:mm:ss.fff`); don't assume the two are equivalent when writing the parser.
- Housekeeping: the 09-21 fixtures (`fchg_{eva}.xml`, `plan_*`) were deleted from the working tree to keep them out of the comparison; they are still in git. Restore with `git restore tests/fixtures/<file>` and do not commit the deletions.

### 2026-10-03 — Cancellation check, polling decision, Phase 2 (Terraform)

- **Cancellations (München Ost fixture, 32 cancelled stops):** 11 have both `<ar>` and `<dp>` cancelled, 10 arrival only, 11 departure only. Cancellation is per event, so the fact-table grain is (stop `id`, arrival/departure). Cancelled events keep a stale `ct` (2 min after `pt` in the example), so `cs="c"` must be excluded from delay. Plan entries are normal (`pt` on both events). In the cancelled example `ts` and `ts-tts` agree; the week-apart case was a `t="h"` construction message. Plan: use `ts-tts` as the message timestamp.
- **Polling design decided:** `/rchg` every 90 s, `/fchg` every 15 min, `/plan` hourly. About 5.3 calls/min for 8 stations (limit 60). Filenames carry `HHMMSS` so 90 s polls cannot collide; record a UTC fetch timestamp per response.
- **Overlap policy:** the collector stores everything raw and never dedupes. The parser keeps all versions in staged Parquet (one row per stop id, event, fetch time, endpoint). The latest-state merge happens in dbt (Phase 5), keyed on `ts-tts` + fetch time.
- **AWS access:** IAM Identity Center was rejected. Account instances do not support permission sets, and organization instances need AWS Organizations, which upgrades a free-plan account to paid and expires the credits. Used an IAM user `terraform-admin` (MFA on, access key in the `terraform-admin` CLI profile) instead. Account `891498120098`, region `eu-central-1`. Access-key CSV to be deleted. Known limitation for the README: SSO would be the production choice, and CLI keys do not enforce MFA.
- **Terraform applied (11 resources):** S3 bucket `db-delay-tracker-data-891498120098` (public access blocked, ACLs disabled, SSE-S3, TLS-only policy, multipart cleanup, no versioning), two SSM SecureString parameters (`/db-delay-tracker/db-client-id`, `/db-delay-tracker/db-api-key`, placeholder values with `ignore_changes`), collector role `db-delay-tracker-collector-role`, log group (14-day retention).
- **Collector role permissions:** `s3:PutObject` on `raw/*` only; `ssm:GetParameter` on the two parameter ARNs only (no `kms:Decrypt` needed with the AWS-managed `aws/ssm` key); `logs:CreateLogStream`/`PutLogEvents` on its own log group only; trust limited to `lambda.amazonaws.com`.
- **Verified:** public access block (all four settings true); real credentials in SSM (client id read back OK); ~$5/month budget alert created; access-key CSV deleted.
- **Key rotation:** the DB API client secret was pasted into the chat by mistake, so it was reset on the DB Marketplace (reset client secret; client id and subscription unchanged). New secret put into SSM (`--overwrite`) and `.env`, tested with a real call. Shell history lines containing `aws ssm put-parameter` removed from the PSReadLine history file. **Lesson: never paste secrets into a chat; for checks, share only non-secret output.**

### 2026-10-04 — Storage keys, storage interface, collector (start of Phase 3)

- **Decisions:**
  - Keys use the **UTC fetch time**, not German local time: local time repeats 02:00–03:00 when DST ends (2026-10-25), so two fetches could share a key. Layout is `raw/{endpoint}/station={eva}/date={YYYY-MM-DD}/{HHMMSS}.xml.gz`; `/plan` adds the requested hour slice: `{HHMMSS}_slice-{YYMMDDHH}.xml.gz` (the plan XML does not reliably say which slice was asked for).
  - **CLAUDE.md is out of date on this** (it says `{HHMM}`, no UTC, and "AWS account pending"). CLAUDE.md is untracked/local by design, so update it by hand.
  - `Storage` has only `put`, mirroring the collector role's single `s3:PutObject` on `raw/*`. The parser (Phase 4) will need a separate readable interface and its own role.
  - **No local polling loop.** A laptop collector has gaps (sleep, shutdown) that are permanent because the API keeps no history, and the only credentials on the machine are the over-powerful `terraform-admin` ones. `LocalStorage` stays as a test fake and for offline runs. Go straight to the Lambda.
  - Only HTTP 200 responses are stored (failures are logged and returned, never written). Empty `rchg` responses are stored. No dedupe, no retries yet.
- **Code:** `keys.py`, `storage.py`, `collector.py` plus tests (23 passing). Added `pytest` and `tzdata` as dev dependencies (`tzdata` because Windows has no timezone database for `ZoneInfo("Europe/Berlin")`). Committed as `4247622`.
- **Smoke test with the real API** (one `collect_once` into a scratchpad folder, not in the repo): `rchg`, `fchg`, `plan` for all 8 stations → 24 files, no errors, all gunzip and parse as `<timetable>`. `fchg` München Hbf: ~162 KB XML → ~20 KB gzipped. Estimate: ~4 KB per `rchg` pass and ~75 KB per `fchg` pass for all 8 stations, under 100 MB/day in total.
- **Notes:**
  - `client.py` returns `response.text` and the collector re-encodes it as UTF-8. Checked on a fixture: the XML declares UTF-8 and umlauts survive. Storing `response.content` would be more literally "untouched"; not changed because repo structure changes are proposed first.
  - The Lambda handler must choose which `/plan` hour slice(s) to fetch, in German local time. `collect_once` just fetches the slice it is given.
  - The two untracked `tests/fixtures/fchg_*_150240.xml` files are leftovers from the rchg comparison; undecided whether to commit or delete.
- **Practice later (to write myself):**
  - Delete `keys.py` and rewrite it until `tests/test_keys.py` passes (the tests are the spec; the original is in git).
  - Write `LocalStorage` from scratch (about 10 lines).

### 2026-10-04 (later) — Lambda handler, Terraform, go-live (Phase 3)

- **Handler** (`handler.py`, commit `b39f90d`): see the file map. `plan` is fetched hourly for the current hour plus the next two (`PLAN_HOUR_OFFSETS = (0, 1, 2)`): `fchg` only lists changed stops, so every hour needs its plan captured at least once, and the extra offsets mean one failed run leaves no gap. Offsets are added in UTC and then converted to Berlin time, because adding hours to a Berlin datetime does wall-clock arithmetic and breaks around DST.
- **Correction to the 2026-10-03 polling decision:** EventBridge Scheduler's `rate()` only accepts minutes, hours or days (checked in the docs), so 90 s is impossible. `rchg` now runs **every 1 minute** (window is ~2 min, so no gaps; about 9 calls/min in total against the limit of 60). `fchg` every 15 min, `plan` hourly.
- **Packaging:** `scripts/build_lambda.py` + a new `lambda` dependency group in `pyproject.toml` (so the zip does not ship `lxml`/`python-dotenv`). `boto3` is bundled on purpose: the Lambda docs recommend including the SDK in the package, not relying on the runtime-included version. Python 3.13 runtime, arm64 (all runtimes support both architectures; deprecation June 2029). Zip is 17 MB, reproducible, contains `aarch64-linux` binaries.
- **Terraform applied (10 resources):** the Lambda (timeout 90 s, 256 MB; ~105 MB used), the scheduler role, 3 schedules, SNS topic + email subscription, 2 alarms. Schedules were created disabled (`schedules_enabled = false`).
- **Scheduler role permissions:** trust only `scheduler.amazonaws.com` with an `aws:SourceAccount` condition (confused-deputy protection); the only permission is `lambda:InvokeFunction` on this one function. Separate from the collector role: that one is what the function may do, this one is what the clock may do. Retries are off (`maximum_retry_attempts = 0`): a late retry of a short-window poll would only duplicate the next scheduled call.
- **Alarms:** `Errors >= 3` in 15 min (the handler raises when any station fails; 3 ignores one-off API blips) and `Invocations < 10` in 15 min with missing data treated as breaching (a dead schedule produces no errors, so the first alarm would stay silent). Both notify the SNS topic; the silence alarm's actions are off while `schedules_enabled` is false. The alert email address is in the gitignored `terraform.tfvars` because the GitHub repo is public.
- **Manual test before enabling:** `aws lambda invoke` for `rchg` / `fchg` / `plan` → 8 / 8 / 24 files in S3, no errors in the logs. This also proved the collector role's permissions for real (SSM read + decrypt, `PutObject` on `raw/*`, logs). Warm calls took 0.7 s (`fchg`) and 1.3 s (`plan`).
- **Go-live:** email subscription confirmed, `terraform plan` reviewed (0 add, 4 change, 0 destroy: three schedules + the silence alarm's actions), then applied. Collection has been running unattended since **2026-10-04 ~10:00 UTC**. Checked the first minutes: `rchg` fires at :32 past every minute, 8 stored and 0 failed each time; `fchg` and `plan` fired once at 10:00:31.
- **Health check ~7 min after go-live (10:07 UTC):** `rchg` 64 files (8 stations × 8 runs), `fchg` 16, `plan` 48, exactly what the schedules should produce; Hbf `rchg` has one file per minute at :32 with no gaps. Lambda Errors 0, Throttles 0, no failures in the logs. The silence alarm was in `ALARM` right after go-live (its first 15-minute window had fewer than 10 invocations) and went to `OK` by 10:09 once the count reached 10; expect an ALARM + OK email pair after any redeploy. The Errors alarm has not fired yet, so its email path is still unproven.
- **Lessons / gotchas:**
  - Git Bash rewrites `/aws/...` arguments into Windows paths; set `MSYS_NO_PATHCONV=1` when passing log group names to the AWS CLI.
  - `terraform apply` needs a reviewed `terraform plan` first (the tooling blocked a blind apply, rightly); show the plan, then apply.
  - The Terraform registry docs page would not load, so the scheduler arguments were written from memory; `validate`, `plan` and `apply` accepted them.
- The two leftover `fchg_*_150240.xml` fixtures were committed along with everything else.

## Next session

- [x] Pull the official OpenAPI spec into `docs/` (done 2026-10-01).
- [x] Look at `/rchg` (recent changes) fixture and compare against `/fchg` (done 2026-10-02, see above).
- [x] Cancellations: confirmed as `cs="c"` on `<ar>`/`<dp>` (see 2026-10-01). Viewed one example stop 2026-10-02; still to check `<dp>` and the plan entry.
- [x] Restore the 09-21 fixtures: they are in git and in the tree, nothing to do.
- [x] Cancellation check and polling design (done 2026-10-03, see above).
- [x] Phase 2 Terraform applied (S3, IAM role, SSM).
- [x] Real DB credentials in SSM, bucket public access block verified, access-key CSV deleted, budget alert created (see the 2026-10-03 entry).
- [x] Storage interface, key builder and `collect_once` with tests, smoke-tested against the real API (done 2026-10-04).
- [x] Lambda handler (done 2026-10-04, see above).
- [x] Terraform for the Lambda, manual invoke, schedules enabled (done 2026-10-04, collecting since ~10:00 UTC).
- [x] Start collecting before the DST switch (2026-10-25): running. The UTC keys make the repeated 02:00–03:00 hour safe for storage; the parser must still handle the German-local `YYMMddHHmm` strings inside the XML, which stay ambiguous in that hour. Also check what the API returns for plan slice `...02` on that day.
- [ ] Check on the collector tomorrow (first full day, 2026-10-05): file counts per endpoint and day in S3, CloudWatch logs for failures, that the alarm emails arrive (try triggering one deliberately, e.g. a bad invoke payload, to see the Errors alarm path), and whether the API ever returns errors or rate-limit responses (no retries exist yet).
- [ ] Update CLAUDE.md by hand (untracked): UTC keys, `HHMMSS`, 1-minute `rchg`, AWS no longer pending.
- [ ] Phase 4: parser Lambda (raw XML → Parquet, UTC timestamps) with pytest tests against the fixtures; separate readable storage interface and its own least-privilege role (`GetObject`/`ListBucket` on `raw/`, `PutObject` on `staged/`). Decide how to handle the ambiguous local-time strings during the DST hour.
- [ ] Optional: store `response.content` instead of `response.text` in the client for byte-exact raw data; add one retry on transient API errors if the logs show them.
- [ ] Practice (own coding): rewrite `keys.py` against `tests/test_keys.py`; write `LocalStorage` from scratch.
- [ ] Known limitations for the README: IAM user instead of SSO (see 2026-10-03), `fchg`/`rchg` times are forecasts not measured actuals, no retries, polling gaps are unrecoverable, Terraform state is local.
