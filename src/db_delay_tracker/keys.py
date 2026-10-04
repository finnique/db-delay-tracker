"""Storage keys for raw API responses.

Layout:
    raw/{endpoint}/station={eva}/date={YYYY-MM-DD}/{HHMMSS}.xml.gz
    raw/plan/station={eva}/date={YYYY-MM-DD}/{HHMMSS}_slice-{YYMMDDHH}.xml.gz

Date and time are the UTC *fetch* time, never German local time: local time
repeats the 02:00-03:00 hour when DST ends, so two fetches could share a key.
/plan responses also carry the requested hour slice in the filename, because
the XML itself does not reliably say which slice was asked for.

Pure functions, no I/O.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

ENDPOINTS = ("plan", "fchg", "rchg")

_SLICE_RE = re.compile(r"\d{8}")


def raw_key(
    endpoint: str,
    eva: str | int,
    fetched_at: datetime,
    plan_slice: str | None = None,
) -> str:
    """Build the storage key for one raw response.

    fetched_at must be timezone-aware (any zone; it is converted to UTC).
    plan_slice is the requested hour as YYMMDDHH and is required for, and only
    allowed with, the "plan" endpoint.
    """
    if endpoint not in ENDPOINTS:
        raise ValueError(f"unknown endpoint {endpoint!r}, expected one of {ENDPOINTS}")
    if fetched_at.tzinfo is None:
        raise ValueError("fetched_at must be timezone-aware")

    if endpoint == "plan":
        if plan_slice is None or not _SLICE_RE.fullmatch(plan_slice):
            raise ValueError("plan needs plan_slice as YYMMDDHH, e.g. '26100416'")
    elif plan_slice is not None:
        raise ValueError(f"plan_slice is only valid for the plan endpoint, not {endpoint!r}")

    utc = fetched_at.astimezone(UTC)
    name = utc.strftime("%H%M%S")
    if plan_slice is not None:
        name += f"_slice-{plan_slice}"
    return f"raw/{endpoint}/station={eva}/date={utc:%Y-%m-%d}/{name}.xml.gz"
