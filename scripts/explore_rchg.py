"""Phase 1 exploration: pull /rchg data for our Munich
stations and save raw XML as fixtures.


Saves raw XML responses to tests/fixtures/ so later phases (parsing, tests)
have real sample data to work against instead of guesses.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
import time

from dotenv import load_dotenv

from db_delay_tracker.client import DBTimetablesClient
from db_delay_tracker.stations import MUNICH_AREA_STATIONS

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def save_fixture(name: str, content: str) -> None:
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    path = FIXTURES_DIR / name
    path.write_text(content, encoding="utf-8")
    print(f"saved {path} ({len(content)} bytes)")


PASSES = 1
SLEEP_SECONDS = 120
TARGET_EVAS = {"8000261", "8003092"}  # München Hbf and Ismaning
stations = [s for s in MUNICH_AREA_STATIONS if s.eva in TARGET_EVAS]
assert len(stations) == len(TARGET_EVAS), "unknown EVA in TARGET_EVAS"


def main() -> None:
    load_dotenv()
    client = DBTimetablesClient()

    for pass_num in range(PASSES):

        now = dt.datetime.now()
        timestamp = now.strftime("%H%M%S")

        for station in stations:
            print(f"\n=== {station.name} (eva={station.eva}) ===")

            # print("Fetching recent changes (rchg)...")
            # rchg_xml = client.recent_changes(station.eva)
            # save_fixture(f"rchg_{station.eva}_{timestamp}.xml", rchg_xml)

            print("Fetching full changes (fchg)...")
            fchg_xml = client.full_changes(station.eva)
            save_fixture(f"fchg_{station.eva}_{timestamp}.xml", fchg_xml)

        # if pass_num < PASSES - 1:
        #     print(f"Sleeping {SLEEP_SECONDS}s...")
        #     time.sleep(SLEEP_SECONDS)


    print("\nDone. Inspect tests/fixtures/ to see the raw shapes.")


if __name__ == "__main__":
    main()
