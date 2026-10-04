from datetime import UTC, datetime

import pytest

from db_delay_tracker.handler import CollectionError, plan_slices, run
from db_delay_tracker.stations import MUNICH_AREA_STATIONS
from db_delay_tracker.storage import LocalStorage

NOW = datetime(2026, 10, 4, 14, 1, 30, tzinfo=UTC)  # 16:01 in Berlin (CEST)
XML = "<timetable/>"


class FakeClient:
    def __init__(self, fail_for=()):
        self.fail_for = set(fail_for)
        self.plan_calls = []

    def _ok(self, eva):
        if eva in self.fail_for:
            raise RuntimeError("boom")
        return XML

    def recent_changes(self, eva):
        return self._ok(eva)

    def full_changes(self, eva):
        return self._ok(eva)

    def plan(self, eva, yymmdd, hh):
        self.plan_calls.append((eva, yymmdd, hh))
        return self._ok(eva)


def test_plan_slices_use_berlin_local_hours():
    assert plan_slices(NOW) == ["26100416", "26100417", "26100418"]


def test_plan_slices_cross_midnight_in_local_time():
    late = datetime(2026, 10, 4, 21, 30, tzinfo=UTC)  # 23:30 Berlin
    assert plan_slices(late) == ["26100423", "26100500", "26100501"]


def test_plan_slices_dst_end_does_not_skip_or_repeat_an_hour():
    # 2026-10-25: 01:00 UTC is 02:00 CET (second 02:00); 00:30 UTC is 02:30 CEST (first).
    start = datetime(2026, 10, 25, 0, 30, tzinfo=UTC)
    assert plan_slices(start) == ["26102502", "26102503"]  # 02 appears once, not twice


def test_plan_slices_dst_start_skips_the_missing_hour():
    # 2026-03-29: 01:30 UTC is 03:30 CEST; 02:00 local never exists.
    start = datetime(2026, 3, 29, 0, 30, tzinfo=UTC)  # 01:30 CET
    assert plan_slices(start) == ["26032901", "26032903", "26032904"]


def test_run_rchg_stores_one_file_per_station(tmp_path):
    results = run("rchg", FakeClient(), LocalStorage(tmp_path), NOW)
    assert len(results) == len(MUNICH_AREA_STATIONS)
    assert len(list(tmp_path.rglob("*.xml.gz"))) == len(MUNICH_AREA_STATIONS)


def test_run_plan_fetches_every_slice_for_every_station(tmp_path):
    client = FakeClient()
    results = run("plan", client, LocalStorage(tmp_path), NOW)
    assert len(results) == 3 * len(MUNICH_AREA_STATIONS)
    hours = {hh for _, _, hh in client.plan_calls}
    assert hours == {"16", "17", "18"}


def test_run_raises_when_a_station_fails_but_still_stores_the_rest(tmp_path):
    client = FakeClient(fail_for={"8000261"})
    with pytest.raises(CollectionError, match=r"1/8 failed.*8000261"):
        run("fchg", client, LocalStorage(tmp_path), NOW)
    assert len(list(tmp_path.rglob("*.xml.gz"))) == len(MUNICH_AREA_STATIONS) - 1


def test_run_rejects_unknown_endpoint(tmp_path):
    with pytest.raises(ValueError, match="unknown endpoint"):
        run("station", FakeClient(), LocalStorage(tmp_path), NOW)
