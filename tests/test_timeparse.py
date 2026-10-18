from datetime import datetime, timezone

import pytest

from db_delay_tracker.timeparse import local_to_utc, fetched_at_from_key, BERLIN
from db_delay_tracker.keys import raw_key


def test_summer_time():
    fetched_at = datetime(2026, 10, 25, 0 ,35, tzinfo=timezone.utc)
    result = local_to_utc("2607151200", fetched_at)
    assert result == (
        datetime(2026, 7, 15, 10, 0, tzinfo=timezone.utc), False
        )

def test_winter_time():
    fetched_at = datetime(2026, 10, 25, 0 ,35, tzinfo=timezone.utc)
    result = local_to_utc("2601151200", fetched_at)
    assert result == (
        datetime(2026, 1, 15, 11, 0, tzinfo=timezone.utc), False
        )

def test_ambiguous_fetched_early():
    fetched_at = datetime(2026, 10, 25, 0 ,35, tzinfo=timezone.utc)
    result = local_to_utc("2610250230", fetched_at)
    assert result == (
        datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc), True
        )

def test_ambiguous_fetched_late():
    fetched_at = datetime(2026, 10, 25, 1 ,40, tzinfo=timezone.utc)
    result = local_to_utc("2610250230", fetched_at)
    assert result == (
        datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc), True
        )

def test_gap():
    fetched_at = datetime(2026, 10, 25, 0 ,35, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match = "invalid raw time - time does not exist"):
        local_to_utc("2603290230", fetched_at)

@pytest.mark.parametrize("raw", ["", "261025023", "26102502300", "abcdefghij", "26a0250230", "2613450230"])
def test_malformed(raw):
    fetched_at = datetime(2026, 10, 25, 0 ,35, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match = "invalid raw time - string does not match format"):
        local_to_utc(raw, fetched_at)

@pytest.mark.parametrize("raw, fetched_at, expected_utc, expected_ambiguous",
                         [
                             pytest.param(
                                 "2610250159",
                                 datetime(2026, 10, 25, 0, 35, tzinfo=timezone.utc), # fetched_at = any
                                 datetime(2026, 10, 24, 23, 59, tzinfo=timezone.utc), # expected UTC = 2026-10-24 23:59 UTC
                                 False,
                                 id="last-minute-before-repeated-hour"
                             ),
                             pytest.param(
                                 "2610250200",
                                 datetime(2026, 10, 25, 0, 10, tzinfo=timezone.utc), # fetched_at = 2026-10-25 00:10 UTC
                                 datetime(2026, 10, 25, 0, 0, tzinfo=timezone.utc), # expected_UTC = 2026-10-25 00:00 UTC
                                 True,
                                 id="repeated-hour-first-minute"
                             ),
                             pytest.param(
                                 "2610250259",
                                 datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc), # fetched_at = 2026-10-25 01:30 
                                 datetime(2026, 10, 25, 1, 59, tzinfo=timezone.utc), # expected_UTC = 2026-10-25 01:59
                                 True,
                                 id="repeated-hour-last-minute"
                             ),
                             pytest.param(
                                 "2610250300",
                                 datetime(2026, 10, 25, 0, 35, tzinfo=timezone.utc), # fetched_at = any
                                 datetime(2026, 10, 25, 2, 0, tzinfo=timezone.utc), # expected_UTC = 2026-10-25 02:00 UTC
                                 False,
                                 id="first-minute-after-repeated-hour"
                             ),
                             pytest.param(
                                 "2610250230",
                                 datetime(2026, 10, 25, 1, 0, tzinfo=timezone.utc), # fetched_at = 2026-10-25 01:00 UTC (exact tie)
                                 datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc), # expected_utc = 2026-10-25 01:30 UTC (winter wins)
                                 True,
                                 id="tie-winter-wins"
                             ),
                             pytest.param(
                                 "2603290159",
                                 datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc), # fetched_at = any
                                 datetime(2026, 3, 29, 0, 59, tzinfo=timezone.utc), # expected_utc = 2026-03-29 00:59 UTC
                                 False,
                                 id="last-minute-before-gap"
                             ),
                             pytest.param(
                                 "2603290300",
                                 datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc), # fetched_at = any
                                 datetime(2026, 3, 29, 1, 0, tzinfo=timezone.utc), # expected_utc = 2026-03-29 01:00 UTC
                                 False,
                                 id="first-minute-after-gap"
                             )
                         ])
def test_dst_boundaries(raw, fetched_at, expected_utc, expected_ambiguous):
    assert local_to_utc(raw, fetched_at) == (expected_utc, expected_ambiguous)

@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("2603290200", id="gap-first-minute"),
        pytest.param("2603290259", id="gap-last-minute")
    ]
)
def test_nonexistent_time_boundaries(raw):
    fetched_at = datetime(2026, 3, 29, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="invalid raw time - time does not exist"):
        local_to_utc(raw, fetched_at)

@pytest.mark.parametrize("key, expected_fetched_at",
                         [
                             pytest.param(
                                 "raw/fchg/station=8000262/date=2026-10-10/105914.xml.gz",
                                 datetime(2026, 10, 10, 10, 59, 14, tzinfo=timezone.utc),
                                 id="fchg-key"), 
                             pytest.param(
                                 "raw/rchg/station=8000262/date=2026-10-10/105914.xml.gz",
                                 datetime(2026, 10, 10, 10, 59, 14, tzinfo=timezone.utc),
                                 id="rchg-key"),
                             pytest.param(
                                 "raw/plan/station=8000262/date=2026-10-10/105914_slice-26101012.xml.gz",
                                 datetime(2026, 10, 10, 10, 59, 14, tzinfo=timezone.utc),
                                 id="plan-key")
                         ]
                         )
def test_fetched_at_from_key(key, expected_fetched_at):
    assert fetched_at_from_key(key) == expected_fetched_at

@pytest.mark.parametrize("endpoint, plan_slice",
                         [
                             pytest.param("fchg", None, id="round-trip-fchg"),
                             pytest.param("rchg", None, id="round-trip-rchg"),
                             pytest.param("plan", "26101012", id="round-trip-plan")
                         ]
                         )
def test_raw_key_round_trip(endpoint, plan_slice):
    """
    raw_key() and fetched_at_from_key() should agree on the same format
    turn time into a key and then turn that key back into a time, the result should match the original time
    
    """
    fetched_at = datetime(2026, 10, 10, 12, 30, 5, tzinfo=timezone.utc)
    key = raw_key(endpoint, 8000262, fetched_at, plan_slice)
    result = fetched_at_from_key(key)
    assert result == fetched_at
    assert result.tzinfo == timezone.utc

def test_repeated_hour_keys():
    first = datetime(2026, 10, 25, 2, 30, tzinfo=BERLIN, fold=0)
    second = datetime(2026, 10, 25, 2, 30, tzinfo=BERLIN, fold=1)

    first_key = raw_key("fchg", 8000262, first)
    second_key = raw_key("fchg", 8000262, second)

    assert first_key != second_key
    assert fetched_at_from_key(first_key) == datetime(2026, 10, 25, 0, 30, tzinfo=timezone.utc)
    assert fetched_at_from_key(second_key) == datetime(2026, 10, 25, 1, 30, tzinfo=timezone.utc)