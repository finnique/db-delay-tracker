"""One collection pass: fetch an endpoint for every station and store it raw.

The collector never parses the XML. It gzips the response text and writes it
under the key from keys.raw_key. The client, the storage and the clock are
passed in, so the same function runs in tests, locally and inside Lambda.
"""

from __future__ import annotations

import gzip
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from db_delay_tracker.keys import raw_key
from db_delay_tracker.stations import Station
from db_delay_tracker.storage import Storage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CollectResult:
    eva: str
    key: str | None  # set when the response was stored
    error: str | None  # set when fetching or storing failed


def _fetch(client, endpoint: str, eva: str, plan_slice: str | None) -> str:
    if endpoint == "rchg":
        return client.recent_changes(eva)
    if endpoint == "fchg":
        return client.full_changes(eva)
    if endpoint == "plan":
        # plan_slice is YYMMDDHH; the API wants the date and the hour separately.
        return client.plan(eva, plan_slice[:6], plan_slice[6:])
    raise ValueError(f"unknown endpoint {endpoint!r}")


def collect_once(
    client,
    storage: Storage,
    stations: Sequence[Station],
    endpoint: str,
    now: datetime,
    plan_slice: str | None = None,
) -> list[CollectResult]:
    """Fetch `endpoint` for every station and store each response raw.

    `now` (timezone-aware) is the fetch time that ends up in the keys.
    One station failing never stops the others; failures are returned in the
    results and logged, and nothing is written for them. Only successful
    responses are stored, so raw/ never contains error pages.
    """
    results = []
    for station in stations:
        try:
            # Build the key first: it validates endpoint, slice and `now`
            # before we spend an API call.
            key = raw_key(endpoint, station.eva, now, plan_slice)
            xml = _fetch(client, endpoint, station.eva, plan_slice)
            # mtime=0 keeps the gzip header free of the current time, so the
            # same XML always compresses to the same bytes.
            storage.put(key, gzip.compress(xml.encode("utf-8"), mtime=0))
            results.append(CollectResult(station.eva, key, None))
        except Exception as exc:
            logger.exception("collect %s failed for %s (%s)", endpoint, station.eva, station.name)
            results.append(CollectResult(station.eva, None, f"{type(exc).__name__}: {exc}"))
    return results
