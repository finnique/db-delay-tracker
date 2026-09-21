"""Munich-area stations to collect, discovered via /station/{exact-name}.

The /station/{pattern} endpoint does an exact/near-exact name lookup, not a
fuzzy search, so this list is hardcoded from confirmed real lookups rather
than resolved dynamically on every collector run.
"""

from __future__ import annotations

from typing import NamedTuple


class Station(NamedTuple):
    name: str
    eva: str
    ds100: str


MUNICH_AREA_STATIONS: tuple[Station, ...] = (
    Station("München Hbf", "8000261", "MH"),
    Station("München Ost", "8000262", "MOP"),
    Station("München-Pasing", "8004158", "MP"),
    Station("München Flughafen Terminal", "8004168", "MFHT"),
    Station("München-Trudering", "8004162", "MTR"),
    Station("München Heimeranplatz", "8005419", "MHP"),
    Station("Ismaning", "8003092", "MIS"),
    Station("Freising", "8002078", "MFR"),
)
