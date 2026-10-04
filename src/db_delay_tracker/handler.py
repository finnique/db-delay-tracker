"""AWS Lambda entry point for the collector.

EventBridge Scheduler invokes the function with {"endpoint": "rchg" | "fchg" | "plan"}.
All the real work is in collector.collect_once; this module only wires it up:
credentials from SSM, S3Storage for the bucket, the clock, and the /plan slices.

Environment variables (set by Terraform):
    BUCKET_NAME   S3 bucket for the raw files
    SSM_PREFIX    parameter prefix, default "/db-delay-tracker"
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from db_delay_tracker.client import DBTimetablesClient
from db_delay_tracker.collector import CollectResult, collect_once
from db_delay_tracker.keys import ENDPOINTS
from db_delay_tracker.stations import MUNICH_AREA_STATIONS
from db_delay_tracker.storage import S3Storage, Storage

logging.getLogger().setLevel(logging.INFO)  # Lambda's root logger defaults to WARNING
logger = logging.getLogger(__name__)

BERLIN = ZoneInfo("Europe/Berlin")

# /plan is fetched hourly for the current hour and the next two. fchg only lists
# stops that changed, so every hour needs its plan at least once before it
# happens; the extra offsets mean one failed run does not leave a gap.
PLAN_HOUR_OFFSETS = (0, 1, 2)


class CollectionError(Exception):
    """Raised when at least one station failed, so the invocation shows as failed."""


def plan_slices(now: datetime, offsets: tuple[int, ...] = PLAN_HOUR_OFFSETS) -> list[str]:
    """YYMMDDHH slices (German local time) for `now` plus each hour offset.

    The offset is added in UTC and only then converted to Berlin time. Adding it
    to a Berlin datetime would do wall-clock arithmetic and go wrong around DST.
    """
    now_utc = now.astimezone(UTC)
    slices = []
    for hours in offsets:
        local = (now_utc + timedelta(hours=hours)).astimezone(BERLIN)
        s = local.strftime("%y%m%d%H")
        if s not in slices:  # the repeated 02:00 hour on DST end maps twice to one slice
            slices.append(s)
    return slices


def run(endpoint: str, client, storage: Storage, now: datetime) -> list[CollectResult]:
    """Collect one endpoint for all stations; raise CollectionError if any failed."""
    if endpoint not in ENDPOINTS:
        raise ValueError(f"unknown endpoint {endpoint!r}, expected one of {ENDPOINTS}")

    if endpoint == "plan":
        results = []
        for plan_slice in plan_slices(now):
            results += collect_once(
                client, storage, MUNICH_AREA_STATIONS, endpoint, now, plan_slice=plan_slice
            )
    else:
        results = collect_once(client, storage, MUNICH_AREA_STATIONS, endpoint, now)

    failed = [r for r in results if r.error]
    logger.info("%s: %d stored, %d failed", endpoint, len(results) - len(failed), len(failed))
    if failed:
        # Everything that succeeded is already stored; raising only makes the
        # failure visible (Lambda Errors metric -> CloudWatch alarm).
        details = "; ".join(f"{r.eva}: {r.error}" for r in failed)
        raise CollectionError(f"{endpoint}: {len(failed)}/{len(results)} failed ({details})")
    return results


def _load_client() -> DBTimetablesClient:
    import boto3

    prefix = os.environ.get("SSM_PREFIX", "/db-delay-tracker")
    ssm = boto3.client("ssm")

    def get(name: str) -> str:
        return ssm.get_parameter(Name=f"{prefix}/{name}", WithDecryption=True)["Parameter"]["Value"]

    return DBTimetablesClient(client_id=get("db-client-id"), api_key=get("db-api-key"))


# Kept at module level: Lambda reuses a warm container between invocations, so
# credentials are read from SSM once instead of on every 90-second call.
_client: DBTimetablesClient | None = None


def handler(event, context):
    global _client
    endpoint = event["endpoint"]
    if _client is None:
        _client = _load_client()
    storage = S3Storage(os.environ["BUCKET_NAME"])
    results = run(endpoint, _client, storage, datetime.now(UTC))
    return {"endpoint": endpoint, "stored": len(results)}
