# Deutsche Bahn Delay Tracker

A data engineering project that continuously collects real-time train data for
eight Munich-area stations from the Deutsche Bahn Timetables API, keeps the raw
history, models it into delay analytics, and (planned) publishes a public
dashboard.

The DB API has **no history**: whatever is not collected is lost. The point of
this project is to build the pipeline that keeps it.

## Status

| Phase | Status |
|---|---|
| Collector (Lambda + EventBridge Scheduler + CloudWatch alarms), Terraform | Running on AWS since 2026-10-04 |
| Parser: raw XML to Parquet (UTC timestamps) | In progress |
| Glue Catalog + Athena | Planned |
| dbt models (latest state per stop, delay fact table, marts) | Planned |
| Daily dbt build via GitHub Actions (OIDC) | Planned |
| Streamlit dashboard | Planned |

[PROGRESS.md](PROGRESS.md) is the detailed development log.

## Architecture

```
EventBridge Scheduler
   rchg every 1 min | fchg every 15 min | plan every 1 h
            |
            v
   Collector Lambda (Python, arm64)  --  credentials from SSM Parameter Store
            |  raw gzipped XML, never parsed or modified
            v
   S3  raw/{endpoint}/station={eva}/date={YYYY-MM-DD}/{HHMMSS}.xml.gz
            |
            v
   Parser Lambda (hourly)  ->  S3 staged/ (Parquet, UTC)       [in progress]
            |
            v
   Glue Data Catalog + Athena  ->  dbt (GitHub Actions, OIDC)  [planned]
            |
            v
   Exported marts  ->  Streamlit Community Cloud               [planned]
```

Design decisions:

- **The collector does not parse.** Raw responses are stored untouched, so any
  parser bug can be fixed and re-run over the full history.
- **Storage sits behind a small interface** (`LocalStorage` for tests and
  offline use, `S3Storage` in Lambda), so the same collector code runs in both.
- **Overlapping polls are kept.** `/rchg` is a sliding window of about two
  minutes, so it is polled every minute. Deduplication happens downstream
  (latest state per stop in dbt), not in the collector.
- **Least-privilege IAM.** The collector role can only `PutObject` under
  `raw/*`, read its two SSM parameters, and write to its own log group.
- **Infrastructure is Terraform** (`infra/`), region eu-central-1.
- **The dashboard holds no AWS credentials** and reads small exported mart
  files instead of querying Athena.

## Stations

München Hbf, München Ost, München-Pasing, München Flughafen Terminal,
München-Trudering, München Heimeranplatz, Ismaning, Freising.

## Data and time handling

- Source: DB Timetables API (`/plan`, `/fchg`, `/rchg`), XML responses.
- Times arrive as German local time (`YYMMddHHmm`) and are converted to UTC in
  the parser. The autumn DST change (repeated hour) is handled explicitly and
  covered by tests (`tests/test_timeparse.py`).
- Changed times (`ct`) are **forecasts, not measured actuals**, and cancelled
  events (`cs="c"`) are excluded from delay calculations.

## Repository layout

| Path | Contents |
|---|---|
| `src/db_delay_tracker/` | API client, station list, storage keys, storage backends, collector, Lambda handler, time parsing |
| `tests/` | pytest suite and real API responses used as fixtures |
| `infra/` | Terraform: S3, IAM, SSM, Lambda, schedules, alarms |
| `scripts/` | Lambda build script and API exploration scripts |
| `docs/` | DB OpenAPI spec and the parser design note |

## Running locally

Requires [uv](https://docs.astral.sh/uv/).

```
uv sync
uv run pytest
```

To call the API yourself, copy `.env.example` to `.env` and fill in
`DB_CLIENT_ID` and `DB_API_KEY` (free keys from the DB API Marketplace). The
`.env` file is gitignored.

Deploying the collector:

```
uv run scripts/build_lambda.py
cd infra && terraform apply
```

## Known limitations

- The collector uses an IAM user with CLI keys for Terraform; IAM Identity
  Center (SSO) would be the production choice.
- The free DB subscription is rate limited (60 calls/min); the collector uses
  roughly 8 stations x (1 + 1/15 + 1/60) calls per minute.
- Delays are based on forecast times, not measured actuals.
- The DB API occasionally resets connections on busy stations. A failed poll is
  not retried, so a gap is possible; the CloudWatch alarms report it.

## Attribution

Train data: DB InfraGO AG, Deutsche Bahn Timetables API, licensed under
[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
