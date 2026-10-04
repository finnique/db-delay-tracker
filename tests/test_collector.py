import gzip
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from db_delay_tracker.collector import collect_once
from db_delay_tracker.stations import Station
from db_delay_tracker.storage import LocalStorage

NOW = datetime(2026, 10, 4, 14, 1, 30, tzinfo=UTC)
HBF = Station("München Hbf", "8000261", "MH")
OST = Station("München Ost", "8000262", "MOP")
XML = "<timetable station='München Hbf'><s id='1'/></timetable>"


class FakeClient:
    def __init__(self, fail_for=()):
        self.fail_for = set(fail_for)
        self.calls = []

    def _respond(self, name, eva, *args):
        self.calls.append((name, eva, *args))
        if eva in self.fail_for:
            raise RuntimeError("boom")
        return XML

    def recent_changes(self, eva):
        return self._respond("rchg", eva)

    def full_changes(self, eva):
        return self._respond("fchg", eva)

    def plan(self, eva, yymmdd, hh):
        return self._respond("plan", eva, yymmdd, hh)


def test_stores_gzipped_raw_xml_under_key(tmp_path):
    results = collect_once(FakeClient(), LocalStorage(tmp_path), [HBF], "rchg", NOW)

    key = "raw/rchg/station=8000261/date=2026-10-04/140130.xml.gz"
    assert [(r.eva, r.key, r.error) for r in results] == [("8000261", key, None)]
    assert gzip.decompress((tmp_path / key).read_bytes()).decode("utf-8") == XML


def test_every_station_gets_its_own_file(tmp_path):
    results = collect_once(FakeClient(), LocalStorage(tmp_path), [HBF, OST], "fchg", NOW)

    assert all(r.error is None for r in results)
    assert len(list(tmp_path.rglob("*.xml.gz"))) == 2


def test_one_failing_station_does_not_stop_the_others(tmp_path):
    client = FakeClient(fail_for={"8000261"})
    results = collect_once(client, LocalStorage(tmp_path), [HBF, OST], "rchg", NOW)

    by_eva = {r.eva: r for r in results}
    assert by_eva["8000261"].key is None
    assert "RuntimeError: boom" in by_eva["8000261"].error
    assert by_eva["8000262"].error is None
    # nothing is written for the failed station
    assert [p.name for p in tmp_path.rglob("*.xml.gz")] == ["140130.xml.gz"]
    assert not list(tmp_path.glob("raw/rchg/station=8000261"))


def test_storage_failure_is_reported_not_raised():
    class BrokenStorage:
        def put(self, key, data):
            raise OSError("disk full")

    results = collect_once(FakeClient(), BrokenStorage(), [HBF], "rchg", NOW)
    assert results[0].key is None
    assert "OSError: disk full" in results[0].error


def test_plan_splits_slice_into_date_and_hour(tmp_path):
    client = FakeClient()
    results = collect_once(
        client, LocalStorage(tmp_path), [HBF], "plan", NOW, plan_slice="26100416"
    )

    assert client.calls == [("plan", "8000261", "261004", "16")]
    assert results[0].key == (
        "raw/plan/station=8000261/date=2026-10-04/140130_slice-26100416.xml.gz"
    )


def test_invalid_input_is_reported_before_any_api_call(tmp_path):
    client = FakeClient()
    results = collect_once(client, LocalStorage(tmp_path), [HBF], "plan", NOW)  # no slice

    assert client.calls == []
    assert "YYMMDDHH" in results[0].error


def test_dst_repeated_hour_does_not_overwrite(tmp_path):
    berlin = ZoneInfo("Europe/Berlin")
    first = datetime(2026, 10, 25, 2, 30, tzinfo=berlin, fold=0)
    second = datetime(2026, 10, 25, 2, 30, tzinfo=berlin, fold=1)
    storage = LocalStorage(tmp_path)

    collect_once(FakeClient(), storage, [HBF], "rchg", first)
    collect_once(FakeClient(), storage, [HBF], "rchg", second)

    assert len(list(tmp_path.rglob("*.xml.gz"))) == 2


def test_same_xml_compresses_to_same_bytes(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    collect_once(FakeClient(), LocalStorage(a), [HBF], "rchg", NOW)
    collect_once(FakeClient(), LocalStorage(b), [HBF], "rchg", datetime(2026, 10, 4, 14, 1, 30, tzinfo=UTC))
    fa = next(a.rglob("*.xml.gz")).read_bytes()
    fb = next(b.rglob("*.xml.gz")).read_bytes()
    assert fa == fb
