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

## Tables

Grain of every table includes the fetch (`fetched_at_utc`, `endpoint`,
`station_eva`), because every snapshot is kept.

### events: one row per stop id x event type (ar/dp) x fetched file

| Column | Source | Notes |
|---|---|---|
| endpoint, station_eva, fetched_at_utc | context | |
| stop_id | `<s id>` | join key between plan and changes |
| event_type | tag | `ar` or `dp` |
| pt_utc, pt_local_raw | `pt` | plan files only, else null |
| ct_utc, ct_local_raw | `ct` | change files only, else null |
| cs, ps | `cs`, `ps` | `p`/`a`/`c`; null if absent |
| clt_utc, clt_local_raw | `clt` | cancellation time |
| line, platform | `l`, `pp`/`cp` | |
| time_ambiguous | derived | true if any time fell in the repeated DST hour |

### messages: one row per `<m>` x fetched file

| Column | Source | Notes |
|---|---|---|
| endpoint, station_eva, fetched_at_utc, stop_id | context / `<s>` | |
| event_type | parent tag | null if the `<m>` sits directly under `<s>` |
| level | derived | `stop` or `event` |
| msg_id, type, code, category | `id`, `t`, `c`, `cat` | opaque, undocumented codes kept as-is |
| ts_utc, ts_local_raw | `ts-tts` | not `ts`: `ts` is minute precision |
| valid_from_utc, valid_to_utc | `from`, `to` | construction/disruption validity |

### trips: one row per stop id, from plan files only

stop_id, station_eva, fetched_at_utc, category (`tl@c`), number (`tl@n`),
operator (`tl@o`), trip type (`tl@t`), planned path (`ppth`, arrival side).

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
