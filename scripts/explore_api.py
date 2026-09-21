"""Phase 1 exploration: pull sample timetable + changes data for our Munich
stations and save raw XML as fixtures.

Run with: uv run scripts/explore_api.py

Saves raw XML responses to tests/fixtures/ so later phases (parsing, tests)
have real sample data to work against instead of guesses.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from dotenv import load_dotenv

from db_delay_tracker.client import DBTimetablesClient
from db_delay_tracker.stations import MUNICH_AREA_STATIONS

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def save_fixture(name: str, content: str) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / name
    path.write_text(content, encoding="utf-8")
    print(f"saved {path} ({len(content)} bytes)")


def main() -> None:
    load_dotenv()
    client = DBTimetablesClient()

    now = dt.datetime.now()
    yymmdd = now.strftime("%y%m%d")
    hh = now.strftime("%H")

    for station in MUNICH_AREA_STATIONS:
        print(f"\n=== {station.name} (eva={station.eva}) ===")

        print(f"Fetching plan for {yymmdd} {hh}:00...")
        plan_xml = client.plan(station.eva, yymmdd, hh)
        save_fixture(f"plan_{station.eva}_{yymmdd}{hh}.xml", plan_xml)

        print("Fetching full changes (fchg)...")
        fchg_xml = client.full_changes(station.eva)
        save_fixture(f"fchg_{station.eva}.xml", fchg_xml)

    print("\nDone. Inspect tests/fixtures/ to see the raw shapes.")


if __name__ == "__main__":
    main()
