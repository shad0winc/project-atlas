#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from providers.base import SportsProvider


class TheSportsDBProvider(SportsProvider):
    name = "thesportsdb"

    def __init__(self) -> None:
        self.api_key = os.getenv(
            "SPORTS_THESPORTSDB_API_KEY",
            "",
        ).strip()

        self.discovery_days_ahead = int(
            os.getenv(
                "SPORTS_DISCOVERY_DAYS_AHEAD",
                "1",
            )
        )

        self.league_ids = [
            value.strip()
            for value in os.getenv(
                "SPORTS_THESPORTSDB_LEAGUE_IDS",
                "",
            ).split(",")
            if value.strip()
        ]

        self.timeout = int(
            os.getenv(
                "SPORTS_PROVIDER_TIMEOUT_SECONDS",
                "15",
            )
        )

    def enabled(self) -> bool:
        return bool(
            self.api_key
            and self.league_ids
        )

    def request_json(
        self,
        endpoint: str,
        parameters: dict[str, str],
    ) -> dict[str, Any]:
        query = urllib.parse.urlencode(parameters)

        url = (
            "https://www.thesportsdb.com/"
            f"api/v1/json/{self.api_key}/"
            f"{endpoint}?{query}"
        )

        request = urllib.request.Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Project-Atlas-Sports/0.1"
                ),
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                return json.load(response)

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(
                f"TheSportsDB request failed: {exc}"
            ) from exc

    def fetch_day_events(
        self,
        date_value: str,
        league_id: str,
    ) -> list[dict[str, Any]]:
        response = self.request_json(
            "eventsday.php",
            {
                "d": date_value,
                "l": league_id,
            },
        )

        return response.get("events") or []

    def fetch_team_events(
        self,
        team_id: str,
    ) -> list[dict[str, Any]]:
        response = self.request_json(
            "eventsnext.php",
            {
                "id": team_id,
            },
        )

        return response.get("events") or []

    def fetch_event(
        self,
        event_id: str,
    ) -> dict[str, Any] | None:
        response = self.request_json(
            "lookupevent.php",
            {
                "id": event_id,
            },
        )

        events = response.get("events") or []

        if not events:
            return None

        return events[0]

    def fetch_games(
        self,
        tracked_event_ids: list[str] | None = None,
        event_ids: list[str] | None = None,
        team_ids: list[str] | None = None,
        league_ids: list[str] | None = None,
        date_value: str | None = None,
    ) -> list[dict[str, Any]]:
        if date_value is None:
            start_date = datetime.now(
                timezone.utc
            ).date()
        else:
            start_date = datetime.fromisoformat(
                date_value
            ).date()

        events_by_id: dict[
            str,
            dict[str, Any],
        ] = {}

        for team_id in team_ids or []:
            for event in self.fetch_team_events(
                team_id
            ):
                event_id = str(
                    event.get(
                        "idEvent",
                        "",
                    )
                ).strip()

                if event_id:
                    events_by_id[event_id] = event

        for day_offset in range(
            self.discovery_days_ahead + 1
        ):
            discovery_date = (
                start_date
                + timedelta(days=day_offset)
            ).isoformat()

            for league_id in league_ids or []:
                for event in self.fetch_day_events(
                    discovery_date,
                    league_id,
                ):
                    event_id = str(
                        event.get(
                            "idEvent",
                            "",
                        )
                    ).strip()

                    if event_id:
                        events_by_id[event_id] = event

        refresh_event_ids = set(
            tracked_event_ids or []
        )

        refresh_event_ids.update(
            event_ids or []
        )

        for event_id in refresh_event_ids:
            event = self.fetch_event(
                event_id
            )

            if event is not None:
                events_by_id[event_id] = event

        return [
            self.normalize_event(event)
            for event in events_by_id.values()
        ]

    def normalize_event(
        self,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        event_id = str(
            event.get("idEvent", "")
        ).strip()

        if not event_id:
            raise ValueError(
                "TheSportsDB event missing idEvent"
            )

        name = (
            event.get("strEvent")
            or event.get("strFilename")
            or event_id
        )

        start_at = self.event_start_timestamp(
            event
        )

        return {
            "id": f"thesportsdb-{event_id}",
            "provider": self.name,
            "provider_event_id": event_id,
            "provider_league_id": str(
                event.get(
                    "idLeague",
                    "",
                )
            ),
            "name": str(name),
            "sport": event.get("strSport"),
            "league": event.get("strLeague"),
            "home_team": event.get("strHomeTeam"),
            "away_team": event.get("strAwayTeam"),
            "home_team_id": str(
                event.get(
                    "idHomeTeam",
                    "",
                )
            ),
            "away_team_id": str(
                event.get(
                    "idAwayTeam",
                    "",
                )
            ),
            "start_at": start_at,
            "status": self.normalize_status(event),
            "duration_minutes": 240,
            "stream_url": "",
        }

    def normalize_status(
        self,
        event: dict[str, Any],
    ) -> str:
        status = str(
            event.get("strStatus") or ""
        ).strip().lower()

        if status in {
            "match finished",
            "finished",
            "final",
            "ft",
        }:
            return "final"

        if status in {
            "live",
            "in progress",
            "in_progress",
        }:
            return "live"

        return "scheduled"

    def event_start_timestamp(
        self,
        event: dict[str, Any],
    ) -> str | None:
        timestamp = event.get("strTimestamp")

        if timestamp:
            try:
                parsed = datetime.fromisoformat(
                    str(timestamp).replace(
                        "Z",
                        "+00:00",
                    )
                )

                if parsed.tzinfo is None:
                    parsed = parsed.replace(
                        tzinfo=timezone.utc
                    )

                return parsed.astimezone(
                    timezone.utc
                ).isoformat()

            except ValueError:
                pass

        date_value = event.get("dateEvent")
        time_value = event.get("strTime")

        if not date_value:
            return None

        combined = (
            f"{date_value}T"
            f"{time_value or '00:00:00'}"
        )

        try:
            parsed = datetime.fromisoformat(
                combined
            ).replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

        return parsed.isoformat()
