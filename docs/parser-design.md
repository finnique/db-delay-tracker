# Parser design (Phase 4)

Raw XML (S3 `raw/`) -> typed rows -> Parquet (S3 `staged/`). Nothing is
deduplicated here; the latest-state merge is dbt (Phase 5).

## Two layers

1. **Pure functions** (`src/db_delay_tracker/parser.py`): bytes + context in,
   rows out. No S3, no file paths, no clock. Tested against `tests/fixtures/`.
2. **Thin I/O layer** (later, Lambda): reads an object, gunzips, takes the
   UTC fetch time and station from the key, calls the pure functions, writes
   Parquet.

Context the pure functions need (not in the XML): `endpoint`, `station_eva`,
`fetched_at` (aware UTC datetime, from the key).

## Why three tables

Each table holds one kind of thing (one grain), and they join on `stop_id`.

- `events`: what happens at a stop (planned and forecast times, cancelled
  or not). The core of the delay calculation.
- `messages`: why it happens (causes, disruption notices). Zero to many per
  event, so a separate table keeps event rows and delay counts correct.
- `trips`: which train it is (category, number, operator, route). Same for
  arrival, departure and every snapshot, so stored once from `plan` only.

```
trips (1 row per stop_id)
   | stop_id
   v
events (stop_id x ar/dp x snapshot)  <--  messages (0..n per event or stop)
```

Types: `str` = string, `ts` = timestamp (UTC, microsecond), `bool`.
Every column except the keys and `endpoint`/`station_eva`/`fetched_at_utc`
is nullable.

## Shared columns (all three tables)

| Column | Type | Contains | Purpose |
|---|---|---|---|
| `endpoint` | str | `plan`, `fchg` or `rchg` | Which API call the row came from |
| `station_eva` | str | e.g. `8000262` | Station whose timetable it is; a stop id repeats along a trip |
| `fetched_at_utc` | ts | when we asked the API (from the key) | Orders the versions of the same stop |
| `stop_id` | str | `{trip id}-{YYMMdd}-{stop index}` | Join key between all tables |

## events: one row per stop id x event type x fetched file

| Column | Type | Source | Contains | Purpose |
|---|---|---|---|---|
| `event_type` | str | tag | `ar` or `dp` | Arrival and departure have separate times and status |
| `pt_utc` | ts | `pt` | planned time | Baseline for the delay; plan files only |
| `pt_local_raw` | str | `pt` | e.g. `2610101221` | Safety copy for re-parsing the DST hour |
| `ct_utc` | ts | `ct` | changed (forecast) time | `ct - pt` is the delay; change files only |
| `ct_local_raw` | str | `ct` | original string | Safety copy |
| `cs` | str | `cs` | changed status: `p`, `a`, `c` | Cancelled events are excluded from delay |
| `ps` | str | `ps` | planned status | What the event was in the plan |
| `clt_utc` | ts | `clt` | cancellation time | How early a cancellation was announced |
| `clt_local_raw` | str | `clt` | original string | Safety copy |
| `line` | str | `l` | e.g. `S5` | Compare lines |
| `platform` | str | `pp` / `cp` | planned or changed platform | Platform changes are a disruption signal |
| `time_ambiguous` | bool | derived | any time in the repeated DST hour | Marks rows whose UTC value is a best guess |

## messages: one row per `<m>` x fetched file

| Column | Type | Source | Contains | Purpose |
|---|---|---|---|---|
| `event_type` | str | parent tag | `ar`, `dp` or null | Event the message belongs to; null if directly under `<s>` |
| `level` | str | derived | `stop` or `event` | Makes the null case explicit |
| `msg_id` | str | `id` | e.g. `r74539117` | Spot the same message seen again in later snapshots |
| `type` | str | `t` | `d` cause, `h` HIM, `q` quality, `f` text, `r` disruption, `c` connection, `i`/`u` IBIS | Kind of message |
| `code` | str | `c` | e.g. `43` | Reason/quality code; undocumented, kept opaque |
| `category` | str | `cat` | e.g. `Störung` | Readable label, mostly on `h` |
| `ts_utc` | ts | `ts-tts` | when the message was issued | Ordering and recency (`ts-tts`, not `ts`: `ts` is minute precision) |
| `ts_local_raw` | str | `ts-tts` | original string | Safety copy |
| `valid_from_utc` | ts | `from` | start of validity | Whether a notice applied at a given delay |
| `valid_to_utc` | ts | `to` | end of validity | Same |

## trips: one row per stop id, from plan files only

| Column | Type | Source | Contains | Purpose |
|---|---|---|---|---|
| `category` | str | `tl@c` | `S`, `RE`, `ICE`, ... | Main grouping: train type |
| `number` | str | `tl@n` | e.g. `6598` | Identifies a specific service |
| `operator` | str | `tl@o` | e.g. `800725` | Operator code |
| `trip_type` | str | `tl@t` | `p` planned, `e` extra, `z` additional, `s` replacement | Regular vs special train |
| `planned_path` | str | `ppth` | earlier stops joined with `\|` | Route; never includes the current station |

## Time handling

- XML times are German local time (`YYMMddHHmm` and `yy-MM-dd HH:mm:ss.fff`).
- Convert to UTC; keep the raw local string next to every converted value.
- `local_to_utc(raw, fetched_at) -> (utc_datetime, ambiguous)`.
- Outside the repeated hour (02:00-02:59 on the day DST ends): one valid
  UTC instant, `ambiguous = False`.
- Inside it: two candidates (summer/CEST and winter/CET). Pick the one
  closest to `fetched_at`; `ambiguous = True`.
- Weak spot: plan slices are fetched up to 2 h ahead, so "closest" can pick
  wrong for `pt`. Flagged rows exist so this can be checked against the
  real data of 2026-10-25 and re-parsed from raw if needed.
- Spring-forward gap (02:00-02:59 does not exist): an input in the gap is a
  data error; raise, do not guess.

## Rules carried over

- Cancelled events (`cs="c"`) keep a stale `ct`; the parser stores them as
  they are, and the delay calculation (dbt) excludes them.
- Unknown attributes/elements are ignored, not errors; missing optional
  attributes become null.
- The parser must not assume 15-minute boundaries in file names.

## Open questions (resolve with real data)

- What does `plan` return for slice `...02` on 2026-10-25?
- Do `ts` and `ts-tts` ever disagree beyond seconds precision?
- `trip_type` and `tl@f` (filter flag) values beyond the ones seen so far.
