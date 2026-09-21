"""Thin client for the DB Timetables API.

Auth is two headers (DB-Client-Id, DB-Api-Key), read from the environment.
Responses are XML text; this client does not parse them, only fetches raw
bytes/text, so the same client works for exploration, fixture-saving, and
the future collector Lambda (which stores raw XML untouched).
"""

from __future__ import annotations

import os

import requests

BASE_URL = "https://apis.deutschebahn.com/db-api-marketplace/apis/timetables/v1"


class DBTimetablesClient:
    def __init__(self, client_id: str | None = None, api_key: str | None = None) -> None:
        self.client_id = client_id or os.environ["DB_CLIENT_ID"]
        self.api_key = api_key or os.environ["DB_API_KEY"]
        self._session = requests.Session()
        self._session.headers.update(
            {
                "DB-Client-Id": self.client_id,
                "DB-Api-Key": self.api_key,
                "Accept": "application/xml",
            }
        )

    def _get(self, path: str) -> str:
        response = self._session.get(f"{BASE_URL}{path}", timeout=10)
        response.raise_for_status()
        return response.text

    def station(self, pattern: str) -> str:
        """Look up stations by name pattern. Returns raw XML with EVA numbers."""
        return self._get(f"/station/{pattern}")

    def plan(self, eva: str, yymmdd: str, hh: str) -> str:
        """Static timetable for one station/hour slice. No delay info."""
        return self._get(f"/plan/{eva}/{yymmdd}/{hh}")

    def full_changes(self, eva: str) -> str:
        """All known changes (delays, cancellations) for the current day."""
        return self._get(f"/fchg/{eva}")

    def recent_changes(self, eva: str) -> str:
        """Changes from roughly the last 2 minutes."""
        return self._get(f"/rchg/{eva}")
