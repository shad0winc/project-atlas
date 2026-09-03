#!/usr/bin/env python3

from __future__ import annotations

import copy
import fcntl
import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import OrderedDict
from email.utils import parsedate_to_datetime
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from pathlib import Path
from typing import Any

from providers.base import SportsProvider


class SportsProviderRateLimitError(RuntimeError):
    provider_rate_limited = True

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__(
            "Sports provider is temporarily rate limited."
        )


_CACHE_LOCK = threading.Lock()
_RESPONSE_CACHE: OrderedDict[
    tuple[str, tuple[tuple[str, str], ...]],
    tuple[float, dict[str, Any]],
] = OrderedDict()
_RATE_LIMIT_UNTIL = 0.0

_CACHE_MAX_ENTRIES = 512
_SEARCH_CACHE_TTL_SECONDS = 60
_DISCOVERY_CACHE_TTL_SECONDS = 300
_RATE_LIMIT_FALLBACK_SECONDS = 60
_RATE_LIMIT_MAX_SECONDS = 300
_PROVIDER_BUDGET_FILE = Path(
    os.getenv(
        "SPORTS_PROVIDER_REQUEST_BUDGET_FILE",
        "/mnt/storage/configs/sportyfin/state/provider-request-budget.json",
    )
)


def _cache_ttl_seconds(endpoint: str) -> int:
    if endpoint in {
        "searchteams.php",
        "search_all_teams.php",
        "searchevents.php",
    }:
        return _SEARCH_CACHE_TTL_SECONDS
    return _DISCOVERY_CACHE_TTL_SECONDS


def _cache_key(
    endpoint: str,
    parameters: dict[str, str],
) -> tuple[str, tuple[tuple[str, str], ...]]:
    return (
        endpoint,
        tuple(
            sorted(
                (str(key), str(value))
                for key, value in parameters.items()
            )
        ),
    )


def _retry_after_seconds(error: urllib.error.HTTPError) -> int:
    raw = ""
    if error.headers is not None:
        raw = str(error.headers.get("Retry-After", "")).strip()

    seconds: int | None = None

    if raw:
        try:
            seconds = int(raw)
        except ValueError:
            try:
                parsed = parsedate_to_datetime(raw)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                seconds = int(
                    max(
                        1,
                        (
                            parsed
                            - datetime.now(timezone.utc)
                        ).total_seconds(),
                    )
                )
            except (TypeError, ValueError, OverflowError):
                seconds = None

    if seconds is None:
        seconds = _RATE_LIMIT_FALLBACK_SECONDS

    return max(
        1,
        min(seconds, _RATE_LIMIT_MAX_SECONDS),
    )


def _load_shared_rate_limit_until() -> float:
    try:
        with _PROVIDER_BUDGET_FILE.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return 0.0

    if not isinstance(payload, dict):
        return 0.0

    try:
        retry_until = float(payload.get("retry_until_epoch", 0.0))
    except (TypeError, ValueError):
        return 0.0

    return max(0.0, retry_until)


def _write_shared_rate_limit_until(retry_until_epoch: float) -> None:
    _PROVIDER_BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)

    lock_file = _PROVIDER_BUDGET_FILE.with_name(
        f"{_PROVIDER_BUDGET_FILE.name}.lock"
    )

    with lock_file.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)

        current = _load_shared_rate_limit_until()
        retry_until = max(current, float(retry_until_epoch))

        temporary = _PROVIDER_BUDGET_FILE.with_name(
            f"{_PROVIDER_BUDGET_FILE.name}.tmp.{os.getpid()}"
        )
        try:
            with temporary.open("w", encoding="utf-8") as handle:
                json.dump(
                    {
                        "provider": "thesportsdb",
                        "retry_until_epoch": retry_until,
                    },
                    handle,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                handle.write("\n")
            temporary.replace(_PROVIDER_BUDGET_FILE)
        finally:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _shared_retry_after_seconds(now_epoch: float | None = None) -> int:
    now = time.time() if now_epoch is None else float(now_epoch)
    retry_until = _load_shared_rate_limit_until()

    if retry_until <= now:
        return 0

    return max(
        1,
        min(
            int(retry_until - now),
            _RATE_LIMIT_MAX_SECONDS,
        ),
    )


def _reset_request_budget_for_tests() -> None:
    global _RATE_LIMIT_UNTIL
    with _CACHE_LOCK:
        _RESPONSE_CACHE.clear()
        _RATE_LIMIT_UNTIL = 0.0


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
        )

    def request_json(
        self,
        endpoint: str,
        parameters: dict[str, str],
    ) -> dict[str, Any]:
        global _RATE_LIMIT_UNTIL

        key = _cache_key(endpoint, parameters)
        now = time.monotonic()

        shared_retry_after = _shared_retry_after_seconds()
        if shared_retry_after > 0:
            raise SportsProviderRateLimitError(shared_retry_after)

        with _CACHE_LOCK:
            if _RATE_LIMIT_UNTIL > now:
                raise SportsProviderRateLimitError(
                    max(1, int(_RATE_LIMIT_UNTIL - now))
                )

            cached = _RESPONSE_CACHE.get(key)
            if cached is not None:
                expires_at, payload = cached
                if expires_at > now:
                    _RESPONSE_CACHE.move_to_end(key)
                    return copy.deepcopy(payload)
                del _RESPONSE_CACHE[key]

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
                "User-Agent": "Project-Atlas-Sports/0.1",
            },
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                payload = json.load(response)

        except urllib.error.HTTPError as exc:
            if exc.code == HTTPStatus.TOO_MANY_REQUESTS:
                retry_after = _retry_after_seconds(exc)
                with _CACHE_LOCK:
                    _RATE_LIMIT_UNTIL = max(
                        _RATE_LIMIT_UNTIL,
                        time.monotonic() + retry_after,
                    )
                _write_shared_rate_limit_until(
                    time.time() + retry_after
                )
                raise SportsProviderRateLimitError(
                    retry_after
                ) from exc

            raise RuntimeError(
                f"TheSportsDB request failed: HTTP {exc.code}"
            ) from exc

        except (
            urllib.error.URLError,
            TimeoutError,
            json.JSONDecodeError,
        ) as exc:
            raise RuntimeError(
                "TheSportsDB request failed."
            ) from exc

        ttl_seconds = _cache_ttl_seconds(endpoint)
        with _CACHE_LOCK:
            _RESPONSE_CACHE[key] = (
                time.monotonic() + ttl_seconds,
                copy.deepcopy(payload),
            )
            _RESPONSE_CACHE.move_to_end(key)
            while len(_RESPONSE_CACHE) > _CACHE_MAX_ENTRIES:
                _RESPONSE_CACHE.popitem(last=False)

        return payload

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

    def search_teams(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        response = self.request_json(
            "searchteams.php",
            {
                "t": query,
            },
        )

        teams = response.get("teams") or []

        results: list[dict[str, Any]] = []

        for team in teams:
            team_id = str(
                team.get(
                    "idTeam",
                    "",
                )
            ).strip()

            if not team_id:
                continue

            results.append(
                {
                    "provider": self.name,
                    "id": team_id,
                    "name": str(
                        team.get(
                            "strTeam",
                            team_id,
                        )
                    ),
                    "sport": team.get(
                        "strSport"
                    ),
                    "league": team.get(
                        "strLeague"
                    ),
                    "country": team.get(
                        "strCountry"
                    ),
                }
            )

        return results

    def search_leagues(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        normalized_query = query.strip()

        if not normalized_query:
            return []

        response = self.request_json(
            "search_all_teams.php",
            {
                "l": normalized_query,
            },
        )

        teams = response.get("teams") or []
        results_by_id: dict[str, dict[str, Any]] = {}

        for team in teams:
            if not isinstance(team, dict):
                continue

            league_id = str(
                team.get("idLeague") or ""
            ).strip()
            name = str(
                team.get("strLeague") or ""
            ).strip()

            if not league_id or not name:
                continue

            results_by_id.setdefault(
                league_id,
                {
                    "provider": self.name,
                    "id": league_id,
                    "name": name,
                    "sport": team.get("strSport"),
                    "country": team.get("strCountry"),
                },
            )

        return list(results_by_id.values())

    def search_events(
        self,
        query: str,
    ) -> list[dict[str, Any]]:
        normalized_query = query.strip()

        if not normalized_query:
            return []

        events_by_id: dict[str, dict[str, Any]] = {}

        direct = self.request_json(
            "searchevents.php",
            {
                "e": normalized_query,
            },
        )

        direct_events = (
            direct.get("event")
            or direct.get("events")
            or []
        )
        if isinstance(direct_events, dict):
            direct_events = [direct_events]

        for raw_event in direct_events:
            if not isinstance(raw_event, dict):
                continue
            normalized = self.normalize_event(raw_event)
            if self._is_current_or_future_search_event(normalized):
                events_by_id[normalized["provider_event_id"]] = normalized

        for team in self.search_teams(normalized_query):
            team_id = str(team.get("id") or "").strip()
            if not team_id:
                continue
            for raw_event in self.fetch_team_events(team_id):
                if not isinstance(raw_event, dict):
                    continue
                normalized = self.normalize_event(raw_event)
                if self._is_current_or_future_search_event(normalized):
                    events_by_id[normalized["provider_event_id"]] = normalized

        for league in self.search_leagues(normalized_query):
            league_id = str(league.get("id") or "").strip()
            if not league_id:
                continue
            for normalized in self.fetch_games(
                league_ids=[league_id],
            ):
                if self._is_current_or_future_search_event(normalized):
                    events_by_id[normalized["provider_event_id"]] = normalized

        return list(events_by_id.values())

    def _is_current_or_future_search_event(
        self,
        event: dict[str, Any],
    ) -> bool:
        status = str(event.get("status") or "").strip().casefold()
        if status == "live":
            return True

        start_at = event.get("start_at")
        if not isinstance(start_at, str) or not start_at.strip():
            return False

        try:
            start = datetime.fromisoformat(
                start_at.replace("Z", "+00:00")
            )
        except ValueError:
            return False

        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)

        return start >= datetime.now(timezone.utc)

    def upcoming_team_games(
        self,
        team_id: str,
    ) -> list[dict[str, Any]]:
        return [
            self.normalize_event(event)
            for event in self.fetch_team_events(
                team_id
            )
        ]

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

    def fetch_team(
        self,
        team_id: str,
    ) -> dict[str, Any] | None:
        response = self.request_json(
            "lookupteam.php",
            {
                "id": team_id,
            },
        )

        teams = response.get("teams") or []

        if not teams:
            return None

        return teams[0]

    def fetch_league(
        self,
        league_id: str,
    ) -> dict[str, Any] | None:
        response = self.request_json(
            "lookupleague.php",
            {
                "id": league_id,
            },
        )

        leagues = response.get("leagues") or []

        if not leagues:
            return None

        return leagues[0]

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
