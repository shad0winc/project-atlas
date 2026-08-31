"""Authenticated application adapter for the existing Atlas Sports module."""

from __future__ import annotations

import http.client
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence


class SportsError(RuntimeError):
    """Base Sports API application error."""


class SportsProviderNotFoundError(SportsError):
    """Requested Sports provider is unavailable."""


class SportsEventNotFoundError(SportsError):
    """Requested Sports event does not exist."""


CreateSubscription = Callable[
    [str, str, str, str, str],
    tuple[dict[str, Any], bool],
]

LoadSubscriptions = Callable[
    [],
    list[dict[str, Any]],
]


class SportsAPIService:
    """Authenticated boundary over the existing Sports domain."""

    def __init__(
        self,
        *,
        providers: Mapping[str, Any],
        create_subscription: CreateSubscription,
        load_subscriptions: LoadSubscriptions,
    ) -> None:
        self._providers = {
            str(name).strip().lower(): provider
            for name, provider in providers.items()
        }

        self._create_subscription = create_subscription
        self._load_subscriptions = load_subscriptions

    def list_events_for_user(
        self,
        *,
        user_id: str,
        provider_name: str,
        provider_event_ids: Sequence[str] | None = None,
        team_ids: Sequence[str] | None = None,
        league_ids: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        provider = self._provider(provider_name)

        event_ids = tuple(
            str(event_id).strip()
            for event_id in (provider_event_ids or ())
            if str(event_id).strip()
        )

        subscriptions = self._load_subscriptions()

        requested_ids = {
            str(subscription.get("id", "")).strip()
            for subscription in subscriptions
            if (
                str(subscription.get("type", "")).strip().lower()
                == "event"
                and str(subscription.get("provider", "")).strip().lower()
                == provider.name
                and str(subscription.get("user", "")).strip()
                == user_id
                and bool(subscription.get("enabled", True))
            )
        }

        events: list[dict[str, Any]] = []

        if event_ids:
            provider_events: list[dict[str, Any]] = []

            for event_id in event_ids:
                raw_event = provider.fetch_event(event_id)

                if raw_event is None:
                    continue

                provider_events.append(
                    dict(
                        provider.normalize_event(
                            raw_event
                        )
                    )
                )
        else:
            provider_events = [
                dict(event)
                for event in provider.fetch_games()
            ]

        for normalized in provider_events:
            normalized_event_id = str(
                normalized.get(
                    "provider_event_id",
                    "",
                )
            ).strip()

            if not normalized_event_id:
                continue

            normalized["requested"] = (
                normalized_event_id in requested_ids
            )

            events.append(normalized)

        return events

    def create_event_subscription(
        self,
        *,
        user_id: str,
        provider_name: str,
        provider_event_id: str,
    ) -> tuple[dict[str, Any], bool]:
        provider = self._provider(provider_name)

        event_id = provider_event_id.strip()

        raw_event = provider.fetch_event(event_id)

        if raw_event is None:
            raise SportsEventNotFoundError(
                "Sports event was not found."
            )

        normalized = provider.normalize_event(raw_event)

        name = str(
            normalized.get("name", "")
        ).strip()

        if not name:
            raise SportsError(
                "Sports provider returned an event without a name."
            )

        return self._create_subscription(
            "event",
            provider.name,
            event_id,
            name,
            user_id,
        )

    def _provider(
        self,
        provider_name: str,
    ) -> Any:
        normalized = provider_name.strip().lower()

        provider = self._providers.get(normalized)

        if provider is None:
            raise SportsProviderNotFoundError(
                f"Sports provider is unavailable: {normalized}"
            )

        return provider


def _load_sports_module_env(
    env_file: Path = Path(
        "/opt/project-atlas/modules/sports/.env"
    ),
) -> None:
    """Load Sports module environment without overriding process values."""

    if not env_file.exists():
        return

    for raw_line in env_file.read_text(
        encoding="utf-8",
    ).splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split(
            "=",
            1,
        )

        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if not key:
            continue

        os.environ.setdefault(
            key,
            value,
        )


class SportsProviderRateLimitError(SportsError):
    def __init__(
        self,
        message: str,
        retry_after_seconds: int,
    ) -> None:
        self.retry_after_seconds = max(
            1,
            min(int(retry_after_seconds), 300),
        )
        super().__init__(message)


class SportsWriterTransportError(SportsError):
    """Private Sports service could not satisfy an API request."""


class SportsWriterBackedAPIService:
    """Authenticated API adapter backed by the private Sports service."""

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        normalized_url = base_url.strip().rstrip("/")
        normalized_token = token.strip()
        if not normalized_url:
            raise RuntimeError("ATLAS_SPORTS_WRITER_URL is required")
        if not normalized_token:
            raise RuntimeError("ATLAS_SPORTS_WRITER_TOKEN is required")
        self._base_url = normalized_url
        self._token = normalized_token
        self._timeout_seconds = timeout_seconds

    def list_events_for_user(
        self,
        *,
        user_id: str,
        provider_name: str,
        provider_event_ids: Sequence[str] | None = None,
        team_ids: Sequence[str] | None = None,
        league_ids: Sequence[str] | None = None,
    ) -> list[dict[str, Any]]:
        query_items: list[tuple[str, str]] = [
            ("user_id", user_id),
            ("provider", provider_name),
        ]
        for event_id in provider_event_ids or ():
            normalized = str(event_id).strip()
            if normalized:
                query_items.append(("event_id", normalized))
        for team_id in team_ids or ():
            normalized = str(team_id).strip()
            if normalized:
                query_items.append(("team_id", normalized))
        for league_id in league_ids or ():
            normalized = str(league_id).strip()
            if normalized:
                query_items.append(("league_id", normalized))
        payload = self._request(
            "GET",
            "/internal/v1/events?" + urllib.parse.urlencode(query_items),
        )
        events = payload.get("events", [])
        if not isinstance(events, list):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid events payload."
            )
        return [dict(event) for event in events if isinstance(event, dict)]

    def create_event_subscription(
        self,
        *,
        user_id: str,
        provider_name: str,
        provider_event_id: str,
    ) -> tuple[dict[str, Any], bool]:
        payload = self._request(
            "POST",
            "/internal/v1/events/request",
            {
                "user_id": user_id,
                "provider": provider_name,
                "provider_event_id": provider_event_id,
            },
        )
        subscription = payload.get("subscription")
        created = payload.get("created")
        if not isinstance(subscription, dict) or not isinstance(created, bool):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid subscription payload."
            )
        return dict(subscription), created

    def search_teams(self, *, provider_name: str, query: str) -> list[dict[str, Any]]:
        payload = self._request("GET", "/internal/v1/search/teams?" + urllib.parse.urlencode({"provider": provider_name, "query": query}))
        items = payload.get("teams", [])
        if not isinstance(items, list):
            raise SportsWriterTransportError("Private Sports service returned an invalid team search payload.")
        return [dict(item) for item in items if isinstance(item, dict)]

    def search_leagues(self, *, provider_name: str, query: str) -> list[dict[str, Any]]:
        payload = self._request("GET", "/internal/v1/search/leagues?" + urllib.parse.urlencode({"provider": provider_name, "query": query}))
        items = payload.get("leagues", [])
        if not isinstance(items, list):
            raise SportsWriterTransportError("Private Sports service returned an invalid league search payload.")
        return [dict(item) for item in items if isinstance(item, dict)]

    def list_subscriptions_for_user(self, *, user_id: str) -> list[dict[str, Any]]:
        payload = self._request("GET", "/internal/v1/subscriptions?" + urllib.parse.urlencode({"user_id": user_id}))
        items = payload.get("subscriptions", [])
        if not isinstance(items, list):
            raise SportsWriterTransportError("Private Sports service returned an invalid subscriptions payload.")
        return [dict(item) for item in items if isinstance(item, dict)]

    def create_follow_subscription(self, *, user_id: str, provider_name: str, subscription_type: str, provider_id: str) -> tuple[dict[str, Any], bool]:
        payload = self._request("POST", "/internal/v1/subscriptions", {"user_id": user_id, "provider": provider_name, "type": subscription_type, "provider_id": provider_id})
        subscription = payload.get("subscription")
        created = payload.get("created")
        if not isinstance(subscription, dict) or not isinstance(created, bool):
            raise SportsWriterTransportError("Private Sports service returned an invalid subscription payload.")
        return dict(subscription), created

    def remove_follow_subscription(self, *, user_id: str, subscription_id: str) -> bool:
        payload = self._request("DELETE", "/internal/v1/subscriptions/" + urllib.parse.quote(subscription_id, safe="") + "?" + urllib.parse.urlencode({"user_id": user_id}))
        removed = payload.get("removed")
        if not isinstance(removed, bool):
            raise SportsWriterTransportError("Private Sports service returned an invalid removal payload.")
        return removed

    def _request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        body: bytes | None = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._token}",
        }
        if payload is not None:
            body = json.dumps(dict(payload), separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=body,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                raw = response.read()
        except urllib.error.HTTPError as exc:
            error_payload: dict[str, Any] = {}
            try:
                decoded = json.loads(exc.read().decode("utf-8"))
                if isinstance(decoded, dict):
                    error_payload = decoded
            except (UnicodeDecodeError, json.JSONDecodeError):
                pass
            code = str(error_payload.get("code", "")).strip()
            message = str(
                error_payload.get(
                    "error",
                    "Private Sports service request failed.",
                )
            ).strip()
            if code == "provider_not_found":
                raise SportsProviderNotFoundError(message) from exc
            if code == "event_not_found":
                raise SportsEventNotFoundError(message) from exc
            if code == "sports_provider_rate_limited":
                retry_after_raw = error_payload.get(
                    "retry_after_seconds",
                    exc.headers.get("Retry-After", "60"),
                )
                try:
                    retry_after = int(retry_after_raw)
                except (TypeError, ValueError):
                    retry_after = 60
                raise SportsProviderRateLimitError(
                    message
                    or "Sports provider is temporarily rate limited.",
                    retry_after,
                ) from exc
            raise SportsWriterTransportError(message) from exc
        except (
            urllib.error.URLError,
            TimeoutError,
            ConnectionError,
            http.client.HTTPException,
        ) as exc:
            raise SportsWriterTransportError(
                "Private Sports service is unavailable."
            ) from exc

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SportsWriterTransportError(
                "Private Sports service returned invalid JSON."
            ) from exc
        if not isinstance(decoded, dict):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid response."
            )
        return decoded


def build_default_sports_api_service() -> SportsWriterBackedAPIService:
    return SportsWriterBackedAPIService(
        base_url=os.getenv(
            "ATLAS_SPORTS_WRITER_URL",
            "http://sports-writer:8003",
        ),
        token=os.getenv(
            "ATLAS_SPORTS_WRITER_TOKEN",
            "",
        ),
    )
