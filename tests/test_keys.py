from datetime import UTC, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from db_delay_tracker.keys import raw_key

BERLIN = ZoneInfo("Europe/Berlin")


def test_rchg_key_layout():
    t = datetime(2026, 10, 4, 14, 1, 30, tzinfo=UTC)
    assert raw_key("rchg", 8000261, t) == (
        "raw/rchg/station=8000261/date=2026-10-04/140130.xml.gz"
    )


def test_plan_key_includes_slice():
    t = datetime(2026, 10, 4, 14, 0, 0, tzinfo=UTC)
    assert raw_key("plan", "8000261", t, plan_slice="26100416") == (
        "raw/plan/station=8000261/date=2026-10-04/140000_slice-26100416.xml.gz"
    )


def test_local_time_is_converted_to_utc_including_date():
    # 01:30 in Berlin on 2026-10-04 (CEST, UTC+2) is 23:30 UTC the day before.
    t = datetime(2026, 10, 4, 1, 30, 0, tzinfo=BERLIN)
    assert raw_key("fchg", 8000261, t) == (
        "raw/fchg/station=8000261/date=2026-10-03/233000.xml.gz"
    )


def test_dst_end_repeated_hour_gives_distinct_keys():
    # 2026-10-25: clocks go back 03:00 CEST -> 02:00 CET, so 02:30 Berlin happens twice.
    first = datetime(2026, 10, 25, 2, 30, tzinfo=BERLIN, fold=0)  # CEST
    second = datetime(2026, 10, 25, 2, 30, tzinfo=BERLIN, fold=1)  # CET
    assert first.utcoffset() == timedelta(hours=2)
    assert second.utcoffset() == timedelta(hours=1)

    k1 = raw_key("rchg", 8000261, first)
    k2 = raw_key("rchg", 8000261, second)
    assert k1 != k2
    assert k1.endswith("date=2026-10-25/003000.xml.gz")
    assert k2.endswith("date=2026-10-25/013000.xml.gz")


def test_dst_start_skipped_hour_is_monotonic_in_utc():
    # 2026-03-29: 02:00 CET -> 03:00 CEST. Keys across the jump must still sort in time order.
    before = datetime(2026, 3, 29, 1, 59, 30, tzinfo=BERLIN)
    after = datetime(2026, 3, 29, 3, 0, 30, tzinfo=BERLIN)
    assert raw_key("rchg", 1, before) < raw_key("rchg", 1, after)


def test_non_utc_fixed_offset_is_accepted():
    t = datetime(2026, 10, 4, 14, 0, 0, tzinfo=timezone(timedelta(hours=-5)))
    assert raw_key("rchg", 1, t).endswith("date=2026-10-04/190000.xml.gz")


def test_naive_datetime_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        raw_key("rchg", 1, datetime(2026, 10, 4, 14, 0, 0))


def test_unknown_endpoint_is_rejected():
    with pytest.raises(ValueError, match="unknown endpoint"):
        raw_key("station", 1, datetime(2026, 10, 4, tzinfo=UTC))


def test_plan_requires_valid_slice():
    t = datetime(2026, 10, 4, tzinfo=UTC)
    with pytest.raises(ValueError, match="YYMMDDHH"):
        raw_key("plan", 1, t)
    with pytest.raises(ValueError, match="YYMMDDHH"):
        raw_key("plan", 1, t, plan_slice="2610041")


def test_slice_rejected_for_other_endpoints():
    with pytest.raises(ValueError, match="only valid for the plan"):
        raw_key("fchg", 1, datetime(2026, 10, 4, tzinfo=UTC), plan_slice="26100416")
