#!/usr/bin/env python3

from __future__ import annotations

import copy
import hashlib
import fcntl
import json
import math
import stat
import tempfile
from contextlib import contextmanager
from contextvars import ContextVar
from providers.shared_request_cache import SharedRequestCache, SharedRequestDeferred
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


_BACKGROUND_FETCH = ContextVar("sports_background_fetch", default=False)
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
_RATE_LIMIT_MAX_SECONDS = 300  # Maximum retry hint, not the persisted deadline.
_SHARED_REQUEST_LIMIT = 20
_SHARED_REQUEST_WINDOW_SECONDS = 60
# Controller-only partial refreshes are private process memory, separate from
# the normal response cache. No incomplete snapshot is returned to consumers.
_REFRESH_LOCK = threading.Lock()
_REFRESH_PROGRESS: OrderedDict[tuple, dict[str, Any]] = OrderedDict()
# Complete normalized snapshots are separate from partial work and normal cache.
_REFRESH_COMPLETE: OrderedDict[tuple, dict[str, Any]] = OrderedDict()
_REFRESH_MAX_AGE_SECONDS = 900
_REFRESH_MAX_PLANS = 8
_REFRESH_MAX_REQUESTS = 128
_REFRESH_MAX_BYTES = 4 * 1024 * 1024
_REFRESH_COMPLETE_MAX_BYTES = 4 * 1024 * 1024
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
                seconds = math.ceil(
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

    # Preserve the provider's full Retry-After. Client retry hints may be
    # shorter, but they must never shorten the shared upstream exclusion.
    return max(1, seconds)


def _load_shared_budget() -> dict[str, Any]:
    try:
        descriptor = os.open(
            _PROVIDER_BUDGET_FILE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
        )
    except FileNotFoundError:
        return {"provider": "thesportsdb", "retry_until_epoch": 0.0,
                "request_epochs": []}
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
            raise RuntimeError("Sports provider budget is not a regular file")
        if details.st_size > 16384:
            raise RuntimeError("Sports provider budget is too large")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            raw = handle.read(16385)
        if len(raw) > 16384:
            raise RuntimeError("Sports provider budget is too large")
    finally:
        os.close(descriptor)
    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate budget field")
            result[key] = value
        return result

    try:
        payload = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, UnicodeError):
        raise RuntimeError("Sports provider budget is invalid") from None
    if not isinstance(payload, dict) or payload.get("provider") != "thesportsdb":
        raise RuntimeError("Sports provider budget is invalid")
    deadline = payload.get("retry_until_epoch")
    epochs = payload.get("request_epochs", [])
    if (type(deadline) not in (int, float) or not math.isfinite(deadline)
            or deadline < 0 or not isinstance(epochs, list)
            or len(epochs) > _SHARED_REQUEST_LIMIT
            or any(type(stamp) not in (int, float) or not math.isfinite(stamp)
                   or stamp < 0 for stamp in epochs)):
        raise RuntimeError("Sports provider budget is invalid")
    # Legacy cooldown-only documents retain their deadline and start with no
    # recorded admissions. Every new upstream request is charged durably.
    return {"provider": "thesportsdb", "retry_until_epoch": deadline,
            "request_epochs": epochs}


def _load_shared_rate_limit_until() -> float:
    return float(_load_shared_budget()["retry_until_epoch"])


@contextmanager
def _shared_budget_lock():
    _PROVIDER_BUDGET_FILE.parent.mkdir(parents=True, exist_ok=True)
    lock_file = _PROVIDER_BUDGET_FILE.with_name(
        f"{_PROVIDER_BUDGET_FILE.name}.lock"
    )
    descriptor = os.open(
        lock_file, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o644
    )
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
            raise RuntimeError("Sports provider budget lock is invalid")
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        linked = lock_file.lstat()
        if (linked.st_dev, linked.st_ino) != (details.st_dev, details.st_ino):
            raise RuntimeError("Sports provider budget lock changed")
        yield
    finally:
        os.close(descriptor)


def _save_shared_budget(payload: dict[str, Any]) -> None:
    descriptor, name = tempfile.mkstemp(
        prefix=_PROVIDER_BUDGET_FILE.name + ".tmp.",
        dir=_PROVIDER_BUDGET_FILE.parent,
    )
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(_PROVIDER_BUDGET_FILE)
        parent = os.open(_PROVIDER_BUDGET_FILE.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    finally:
        temporary.unlink(missing_ok=True)


def _write_shared_rate_limit_until(retry_until_epoch: float) -> None:
    deadline = float(retry_until_epoch)
    if not math.isfinite(deadline) or deadline < 0:
        raise RuntimeError("Sports provider cooldown is invalid")
    with _shared_budget_lock():
        payload = _load_shared_budget()
        payload["retry_until_epoch"] = max(payload["retry_until_epoch"], deadline)
        _save_shared_budget(payload)


def _reserve_shared_request() -> None:
    # The reservation commits before HTTP. Failed requests and a process death
    # after reservation remain charged; no quota is refunded on uncertainty.
    with _shared_budget_lock():
        payload = _load_shared_budget()
        now = time.time()
        if not math.isfinite(now) or now < 0:
            raise RuntimeError("Sports provider clock is invalid")
        deadline = payload["retry_until_epoch"]
        if deadline > now:
            raise SportsProviderRateLimitError(
                min(_RATE_LIMIT_MAX_SECONDS, max(1, math.ceil(deadline - now)))
            )
        epochs = [stamp for stamp in payload["request_epochs"]
                  if stamp > now - _SHARED_REQUEST_WINDOW_SECONDS]
        if len(epochs) >= _SHARED_REQUEST_LIMIT:
            wait = min(epochs) + _SHARED_REQUEST_WINDOW_SECONDS - now
            raise SportsProviderRateLimitError(
                min(_RATE_LIMIT_MAX_SECONDS, max(1, math.ceil(wait)))
            )
        payload["request_epochs"] = epochs + [now]
        _save_shared_budget(payload)


def _shared_retry_after_seconds(now_epoch: float | None = None) -> int:
    now = time.time() if now_epoch is None else float(now_epoch)
    retry_until = _load_shared_rate_limit_until()
    if retry_until <= now:
        return 0
    return max(1, min(math.ceil(retry_until - now), _RATE_LIMIT_MAX_SECONDS))


def _reset_request_budget_for_tests() -> None:
    global _RATE_LIMIT_UNTIL
    with _CACHE_LOCK:
        _RESPONSE_CACHE.clear()
        _RATE_LIMIT_UNTIL = 0.0
    with _REFRESH_LOCK:
        _REFRESH_PROGRESS.clear()
        _REFRESH_COMPLETE.clear()


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

    def request_json(self, endpoint: str, parameters: dict[str, str]) -> dict[str, Any]:
        enabled = os.getenv("SPORTS_SHARED_METADATA_CACHE_ENABLED", "0")
        if enabled not in {"0", "1"}:
            raise RuntimeError("Invalid shared metadata cache activation")
        if enabled == "0":
            return self._request_json_local(endpoint, parameters)
        cache = SharedRequestCache(
            _PROVIDER_BUDGET_FILE.parent / "provider-request-coordination",
            self.api_key, clock=lambda: time.time(),
        )
        key = _cache_key(endpoint, parameters)
        def fetch():
            # A memory hit must not be persisted under a new observation time.
            with _CACHE_LOCK:
                _RESPONSE_CACHE.pop(key, None)
            return self._request_json_local(endpoint, parameters)
        try:
            reply = cache.get_or_fetch(endpoint, parameters,
                ttl=_cache_ttl_seconds(endpoint), background=_BACKGROUND_FETCH.get(), fetch=fetch)
        except SharedRequestDeferred as error:
            raise SportsProviderRateLimitError(error.retry_after_seconds) from None
        age = time.time() - reply.observed_at
        if not math.isfinite(age) or age < 0 or age >= _cache_ttl_seconds(endpoint):
            raise RuntimeError("Shared metadata age is invalid")
        with _CACHE_LOCK:
            _RESPONSE_CACHE[key] = (
                time.monotonic() + _cache_ttl_seconds(endpoint) - age,
                copy.deepcopy(reply.payload),
            )
            _RESPONSE_CACHE.move_to_end(key)
            while len(_RESPONSE_CACHE) > _CACHE_MAX_ENTRIES:
                _RESPONSE_CACHE.popitem(last=False)
        return copy.deepcopy(reply.payload)

    def _request_json_local(
        self,
        endpoint: str,
        parameters: dict[str, str],
    ) -> dict[str, Any]:
        global _RATE_LIMIT_UNTIL

        key = _cache_key(endpoint, parameters)
        now = time.monotonic()

        with _CACHE_LOCK:
            cached = _RESPONSE_CACHE.get(key)
            if cached is not None:
                expires_at, payload = cached
                if expires_at > now:
                    _RESPONSE_CACHE.move_to_end(key)
                    return copy.deepcopy(payload)
                del _RESPONSE_CACHE[key]
            if _RATE_LIMIT_UNTIL > now:
                raise SportsProviderRateLimitError(
                    max(1, math.ceil(_RATE_LIMIT_UNTIL - now))
                )

        shared_retry_after = _shared_retry_after_seconds()
        if shared_retry_after > 0:
            raise SportsProviderRateLimitError(shared_retry_after)

        _reserve_shared_request()
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

    @staticmethod
    def _complete_storage_bytes(games, responses, observations) -> int:
        # Include retained provider payloads as well as normalized games in the
        # existing total serialized-payload bound. No response may hide here.
        value = [games, [[key, payload, observations[key]]
                         for key, payload in responses.items()]]
        return len(json.dumps(value, separators=(",", ":"), allow_nan=False).encode())

    def _renew_complete_snapshot(self, complete, arguments):
        """Renew the oldest observations first, retaining full plan coverage.

        A cooldown can interrupt renewal, but never normalization: reconstruct
        all planned requests from retained responses without additional HTTP.
        The completion timestamp advances only after every response has a new
        observation since the preceding full renewal.
        """
        responses = copy.deepcopy(complete["responses"])
        observations = dict(complete["observations"])
        changed = False
        deferred = None
        for key in sorted(responses, key=lambda item: (observations[item], item)):
            endpoint, parameters = key
            before = time.monotonic()
            age = before - observations[key]
            if not math.isfinite(age) or age < 0:
                raise RuntimeError("Sports rolling refresh clock is invalid")
            if age < _cache_ttl_seconds(endpoint):
                continue
            try:
                payload = self.request_json(endpoint, dict(parameters))
            except SportsProviderRateLimitError as error:
                deferred = error
                break
            if not isinstance(payload, dict):
                raise RuntimeError("Sports refresh response must be an object")
            observed = before
            with _CACHE_LOCK:
                cached = _RESPONSE_CACHE.get(key)
                if cached is not None:
                    cached_observed = cached[0] - _cache_ttl_seconds(endpoint)
                    if not math.isfinite(cached_observed) or cached_observed > time.monotonic():
                        raise RuntimeError("Sports refresh cache clock is invalid")
                    observed = min(observed, cached_observed)
            if observed < observations[key]:
                raise RuntimeError("Sports rolling refresh observation regressed")
            if observed > observations[key]:
                responses[key] = copy.deepcopy(payload)
                observations[key] = observed
                changed = True
            if self._complete_storage_bytes(complete["games"], responses, observations) > _REFRESH_COMPLETE_MAX_BYTES:
                raise RuntimeError("Sports rolling refresh memory bound exceeded")

        current = time.monotonic()
        oldest = min(observations.values(), default=complete["oldest"])
        epoch = time.time()
        if (not math.isfinite(current) or not 0 <= current - oldest <= _REFRESH_MAX_AGE_SECONDS
                or current < complete["completed_monotonic"]
                or not math.isfinite(epoch) or epoch < complete["completed_epoch"]):
            raise RuntimeError("Sports rolling refresh observations expired or clock invalid")
        if changed:
            used = set()
            def retained(endpoint, parameters):
                key = _cache_key(endpoint, parameters)
                if key not in responses:
                    raise RuntimeError("Sports rolling refresh plan coverage changed")
                used.add(key)
                return copy.deepcopy(responses[key])
            clone = copy.copy(self)
            clone.request_json = retained
            games = clone.fetch_games(**arguments)
            if used != set(responses):
                raise RuntimeError("Sports rolling refresh plan coverage changed")
            size = self._complete_storage_bytes(games, responses, observations)
            if size > _REFRESH_COMPLETE_MAX_BYTES:
                raise RuntimeError("Sports rolling refresh memory bound exceeded")
            current, epoch = time.monotonic(), time.time()
            if (not math.isfinite(current) or not 0 <= current - oldest <= _REFRESH_MAX_AGE_SECONDS
                    or current < complete["completed_monotonic"]
                    or not math.isfinite(epoch) or epoch < complete["completed_epoch"]):
                raise RuntimeError("Sports rolling refresh observations expired or clock invalid")
            renewed = bool(observations) and all(
                observed > complete["completed_monotonic"] for observed in observations.values())
            if renewed:
                complete["completed_monotonic"] = current
                complete["completed_epoch"] = epoch
                complete["completed_at"] = datetime.fromtimestamp(epoch, timezone.utc).isoformat()
            # Until full renewal, at least one original observation remains at
            # or before the unchanged completion time. Age changes reflect real
            # replaced responses, never a renewed timestamp on a cache hit.
            age_at_completion = complete["completed_monotonic"] - oldest
            if age_at_completion < 0:
                raise RuntimeError("Sports rolling refresh completion age is invalid")
            complete.update(games=copy.deepcopy(games), responses=responses,
                observations=observations, oldest=oldest, bytes=size)
            complete["metadata"]["oldest_response_age_seconds"] = round(age_at_completion, 3)
        self.last_refresh_snapshot = copy.deepcopy(complete["metadata"])
        self.last_refresh_completed_at = complete["completed_at"]
        if deferred is not None:
            self.last_refresh_deferred = {
                "reason": "rate-limit", "retry_after_seconds": deferred.retry_after_seconds,
            }
        return copy.deepcopy(complete["games"])

    def _tracked_plan_handoff(self, identity, arguments):
        """Reuse observations across tracked-ID changes within one strict scope.

        Credentials, day, horizon and explicit event/team/league targets must
        match. Reusing a response does not assert coverage of a missing request.
        """
        scope = identity[:3] + identity[4:]
        donors = [value for key, value in _REFRESH_COMPLETE.items()
                  if key != identity and key[:3] + key[4:] == scope
                  and "responses" in value]
        if not donors:
            return None, None
        planned = set()
        def plan_request(endpoint, parameters):
            planned.add(_cache_key(endpoint, parameters))
            if len(planned) > _REFRESH_MAX_REQUESTS:
                raise RuntimeError("Sports refresh request bound exceeded")
            return {}
        planner = copy.copy(self)
        planner.request_json = plan_request
        planner.fetch_games(**arguments)
        if not planned:
            return None, None
        responses, observations = {}, {}
        for donor in donors:
            for key in planned & donor["responses"].keys():
                observed = donor["observations"][key]
                if key not in observations or observed > observations[key]:
                    responses[key] = copy.deepcopy(donor["responses"][key])
                    observations[key] = observed
        current = time.monotonic()
        if (not math.isfinite(current) or any(
                not math.isfinite(value) or not 0 <= current - value <= _REFRESH_MAX_AGE_SECONDS
                for value in observations.values())):
            raise RuntimeError("Sports tracked-plan handoff observations expired or clock invalid")
        size = sum(len(json.dumps(value, separators=(",", ":")).encode())
                   for value in responses.values())
        if size > _REFRESH_MAX_BYTES:
            raise RuntimeError("Sports refresh memory bound exceeded")
        entry = {"oldest": min(observations.values(), default=current),
                 "responses": responses, "observations": observations, "bytes": size}
        if set(responses) != planned:
            # New requests remain missing. Ordinary cold completion must obtain
            # them through shared admission before this identity can be healthy.
            return entry, None
        used = set()
        def retained(endpoint, parameters):
            key = _cache_key(endpoint, parameters)
            if key not in responses:
                raise RuntimeError("Sports tracked-plan handoff coverage changed")
            used.add(key)
            return copy.deepcopy(responses[key])
        normalizer = copy.copy(self)
        normalizer.request_json = retained
        games = normalizer.fetch_games(**arguments)
        if used != planned:
            raise RuntimeError("Sports tracked-plan handoff coverage changed")
        current, epoch = time.monotonic(), time.time()
        oldest = entry["oldest"]
        if (not math.isfinite(current) or not 0 <= current - oldest <= _REFRESH_MAX_AGE_SECONDS
                or not math.isfinite(epoch) or any(
                    current < donor["completed_monotonic"] or epoch < donor["completed_epoch"]
                    for donor in donors)):
            raise RuntimeError("Sports tracked-plan handoff observations expired or clock invalid")
        anchor = min(donors, key=lambda donor: donor["completed_monotonic"])
        # Keep a conservative existing completion marker until all required
        # observations are newer than it. Never change response timestamps.
        renewed = all(value > anchor["completed_monotonic"] for value in observations.values())
        completed_monotonic = current if renewed else anchor["completed_monotonic"]
        completed_epoch = epoch if renewed else anchor["completed_epoch"]
        completed_at = (datetime.fromtimestamp(epoch, timezone.utc).isoformat()
                        if renewed else anchor["completed_at"])
        size = self._complete_storage_bytes(games, responses, observations)
        if size > _REFRESH_COMPLETE_MAX_BYTES:
            raise RuntimeError("Sports tracked-plan handoff memory bound exceeded")
        complete = {"oldest": oldest, "completed_monotonic": completed_monotonic,
                    "completed_epoch": completed_epoch, "completed_at": completed_at,
                    "responses": responses, "observations": observations,
                    "games": copy.deepcopy(games), "bytes": size,
                    "metadata": {"version": 1, "maximum_age_seconds": _REFRESH_MAX_AGE_SECONDS,
                        "completed_request_count": len(planned),
                        "oldest_response_age_seconds": round(completed_monotonic - oldest, 3)}}
        return None, complete

    def fetch_games_resumable(self, *args, **kwargs):
        token = _BACKGROUND_FETCH.set(True)
        try:
            return self._fetch_games_resumable(*args, **kwargs)
        finally:
            _BACKGROUND_FETCH.reset(token)

    def _fetch_games_resumable(
        self,
        tracked_event_ids: list[str] | None = None,
        event_ids: list[str] | None = None,
        team_ids: list[str] | None = None,
        league_ids: list[str] | None = None,
        date_value: str | None = None,
        days_ahead: int | None = None,
    ) -> list[dict[str, Any]]:
        """Complete a bounded controller snapshot across rate-limit deferrals.

        Checkpoints survive new provider instances in this process, not process
        death. Interactive fetch_games and response-cache TTLs are unchanged.
        """
        self.last_refresh_snapshot = None
        self.last_refresh_completed_at = None
        self.last_refresh_deferred = None
        date_value = (
            datetime.now(timezone.utc).date().isoformat()
            if date_value is None
            else datetime.fromisoformat(date_value).date().isoformat()
        )
        arguments = {
            "tracked_event_ids": sorted(set(tracked_event_ids or [])),
            "event_ids": sorted(set(event_ids or [])),
            "team_ids": sorted(set(team_ids or [])),
            "league_ids": sorted(set(league_ids or [])),
            "date_value": date_value,
            "days_ahead": days_ahead,
        }
        identity = (
            hashlib.sha256(self.api_key.encode()).digest(),
            date_value,
            self.discovery_days_ahead if days_ahead is None else days_ahead,
            *(tuple(arguments[name]) for name in (
                "tracked_event_ids", "event_ids", "team_ids", "league_ids"
            )),
        )
        # Serializing this opt-in path prevents concurrent callers from mutating
        # a shared checkpoint. Ordinary interactive requests do not take this lock.
        with _REFRESH_LOCK:
            now = time.monotonic()
            if not math.isfinite(now):
                _REFRESH_PROGRESS.clear()
                _REFRESH_COMPLETE.clear()
                raise RuntimeError("Sports refresh clock is invalid")
            for key, complete in list(_REFRESH_COMPLETE.items()):
                if (not 0 <= now - complete["oldest"] <= _REFRESH_MAX_AGE_SECONDS
                        or now < complete["completed_monotonic"]
                        or not math.isfinite(time.time())
                        or time.time() < complete["completed_epoch"]):
                    del _REFRESH_COMPLETE[key]
            for key, entry in list(_REFRESH_PROGRESS.items()):
                if not 0 <= now - entry["oldest"] <= _REFRESH_MAX_AGE_SECONDS:
                    del _REFRESH_PROGRESS[key]
            while sum(item["bytes"] for item in _REFRESH_COMPLETE.values()) > _REFRESH_COMPLETE_MAX_BYTES:
                _REFRESH_COMPLETE.popitem(last=False)
            if identity not in _REFRESH_COMPLETE and identity not in _REFRESH_PROGRESS:
                entry, adopted = self._tracked_plan_handoff(identity, arguments)
                if entry is not None:
                    _REFRESH_PROGRESS[identity] = entry
                if adopted is not None:
                    _REFRESH_COMPLETE[identity] = adopted
                    while (len(_REFRESH_COMPLETE) > _REFRESH_MAX_PLANS
                           or sum(item["bytes"] for item in _REFRESH_COMPLETE.values()) > _REFRESH_COMPLETE_MAX_BYTES):
                        _REFRESH_COMPLETE.popitem(last=False)
            complete = _REFRESH_COMPLETE.get(identity)
            if complete is not None and "responses" in complete:
                try:
                    result = self._renew_complete_snapshot(complete, arguments)
                    _REFRESH_COMPLETE.move_to_end(identity)
                    while sum(item["bytes"] for item in _REFRESH_COMPLETE.values()) > _REFRESH_COMPLETE_MAX_BYTES:
                        _REFRESH_COMPLETE.popitem(last=False)
                    return result
                except BaseException:
                    _REFRESH_PROGRESS.pop(identity, None)
                    _REFRESH_COMPLETE.pop(identity, None)
                    raise
            if identity not in _REFRESH_PROGRESS:
                _REFRESH_PROGRESS[identity] = {
                    "oldest": now, "responses": {}, "observations": {}, "bytes": 0,
                }
            _REFRESH_PROGRESS.move_to_end(identity)
            while len(_REFRESH_PROGRESS) > _REFRESH_MAX_PLANS:
                _REFRESH_PROGRESS.popitem(last=False)
            entry = _REFRESH_PROGRESS[identity]

            def require_current() -> None:
                age = time.monotonic() - entry["oldest"]
                if not math.isfinite(age) or not 0 <= age <= _REFRESH_MAX_AGE_SECONDS:
                    raise RuntimeError("Sports refresh checkpoint expired")

            used = set()
            def request(endpoint: str, parameters: dict[str, str]) -> dict[str, Any]:
                require_current()
                key = _cache_key(endpoint, parameters)
                used.add(key)
                if key in entry["responses"]:
                    return copy.deepcopy(entry["responses"][key])
                if len(entry["responses"]) >= _REFRESH_MAX_REQUESTS:
                    raise RuntimeError("Sports refresh request bound exceeded")
                before = time.monotonic()
                payload = self.request_json(endpoint, parameters)
                if not isinstance(payload, dict):
                    raise RuntimeError("Sports refresh response must be an object")
                # Normal cache reuse can predate checkpoint creation. Charge its
                # original observation age, so retries cannot refresh its timestamp.
                observed = before
                with _CACHE_LOCK:
                    cached = _RESPONSE_CACHE.get(key)
                    if cached is not None:
                        cached_observed = cached[0] - _cache_ttl_seconds(endpoint)
                        if not math.isfinite(cached_observed) or cached_observed > time.monotonic():
                            raise RuntimeError("Sports refresh cache clock is invalid")
                        observed = min(observed, cached_observed)
                entry["oldest"] = min(entry["oldest"], observed)
                require_current()
                size = len(json.dumps(payload, separators=(",", ":")).encode())
                if entry["bytes"] + size > _REFRESH_MAX_BYTES:
                    raise RuntimeError("Sports refresh memory bound exceeded")
                entry["responses"][key] = copy.deepcopy(payload)
                entry["observations"][key] = observed
                entry["bytes"] += size
                return payload

            # A private clone routes just this snapshot through checkpointed
            # requests. Never replace the original instance's request method.
            clone = copy.copy(self)
            clone.request_json = request
            try:
                result = clone.fetch_games(**arguments)
                require_current()
                if used != set(entry["responses"]):
                    raise RuntimeError("Sports refresh plan coverage changed")
            except SportsProviderRateLimitError as error:
                # Only a complete, same-identity snapshot can cover a deferral.
                # Keep collecting the next snapshot; never publish partial work.
                complete = _REFRESH_COMPLETE.get(identity)
                current = time.monotonic()
                if complete is not None and (
                    math.isfinite(current)
                    and 0 <= current - complete["oldest"] <= _REFRESH_MAX_AGE_SECONDS
                    and current >= complete["completed_monotonic"]
                    and math.isfinite(time.time())
                    and time.time() >= complete["completed_epoch"]
                ):
                    self.last_refresh_snapshot = copy.deepcopy(complete["metadata"])
                    self.last_refresh_completed_at = complete["completed_at"]
                    self.last_refresh_deferred = {
                        "reason": "rate-limit",
                        "retry_after_seconds": error.retry_after_seconds,
                    }
                    _REFRESH_COMPLETE.move_to_end(identity)
                    return copy.deepcopy(complete["games"])
                _REFRESH_COMPLETE.pop(identity, None)
                raise
            except BaseException:
                _REFRESH_PROGRESS.pop(identity, None)
                _REFRESH_COMPLETE.pop(identity, None)
                raise
            else:
                self.last_refresh_snapshot = {
                    "version": 1,
                    "oldest_response_age_seconds": round(
                        max(0.0, time.monotonic() - entry["oldest"]), 3,
                    ),
                    "maximum_age_seconds": _REFRESH_MAX_AGE_SECONDS,
                    "completed_request_count": len(entry["responses"]),
                }
                _REFRESH_PROGRESS.pop(identity, None)
                _REFRESH_COMPLETE.pop(identity, None)
                completed_epoch = time.time()
                if not math.isfinite(completed_epoch):
                    raise RuntimeError("Sports refresh completion clock is invalid")
                self.last_refresh_completed_at = datetime.fromtimestamp(
                    completed_epoch, timezone.utc,
                ).isoformat()
                size = self._complete_storage_bytes(result, entry["responses"], entry["observations"])
                if size <= _REFRESH_COMPLETE_MAX_BYTES:
                    _REFRESH_COMPLETE[identity] = {
                        "oldest": entry["oldest"], "completed_monotonic": time.monotonic(),
                        "completed_epoch": completed_epoch,
                        "completed_at": self.last_refresh_completed_at,
                        "metadata": copy.deepcopy(self.last_refresh_snapshot),
                        "games": copy.deepcopy(result), "bytes": size,
                        "responses": copy.deepcopy(entry["responses"]),
                        "observations": dict(entry["observations"]),
                    }
                    while (len(_REFRESH_COMPLETE) > _REFRESH_MAX_PLANS
                           or sum(item["bytes"] for item in _REFRESH_COMPLETE.values()) > _REFRESH_COMPLETE_MAX_BYTES):
                        _REFRESH_COMPLETE.popitem(last=False)
                return result

    def fetch_games(
        self,
        tracked_event_ids: list[str] | None = None,
        event_ids: list[str] | None = None,
        team_ids: list[str] | None = None,
        league_ids: list[str] | None = None,
        date_value: str | None = None,
        days_ahead: int | None = None,
    ) -> list[dict[str, Any]]:
        # Interactive schedules can request seven days without changing the
        # background discovery horizon or bypassing the shared request budget.
        if days_ahead is not None and (
            type(days_ahead) is not int or not 0 <= days_ahead <= 7
        ):
            raise ValueError("Schedule horizon must be between zero and seven days")
        discovery_days = self.discovery_days_ahead if days_ahead is None else days_ahead

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
            # A game may move out of the next-events list as it starts.
            # Recent events contribute only provider-reported live games.
            recent_response = self.request_json("eventslast.php", {"id": team_id})
            recent = recent_response.get("results") or recent_response.get("events") or []
            live_recent = [
                event for event in recent
                if isinstance(event, dict) and self.normalize_status(event) == "live"
            ]
            for event in [*self.fetch_team_events(team_id), *live_recent]:
                event_id = str(
                    event.get(
                        "idEvent",
                        "",
                    )
                ).strip()

                if event_id:
                    events_by_id[event_id] = event

        for day_offset in range(
            discovery_days + 1
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
            "q1", "q2", "q3", "q4", "ht", "ot",
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
