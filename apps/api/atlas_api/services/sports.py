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


class SportsSubscriptionNotFoundError(SportsError):
    """Requested Sports subscription does not exist for the user."""


class SportsRecordingTargetUnsupportedError(SportsError):
    """Recording intent is unsupported for the requested target."""


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


class SportsLiveTvBindingNotFoundError(LookupError):
    """Raised when an Atlas Sports channel has no exact Live TV binding."""


class SportsProviderAccountConflictError(
    SportsWriterTransportError
):
    """Provider-account mutation conflicts with current state."""


class SportsProviderAccountNotFoundError(
    SportsWriterTransportError
):
    """Provider account disappeared during a scoped mutation."""


class SportsProviderAccountInvalidError(
    SportsWriterTransportError
):
    """Provider-account lifecycle request is invalid."""


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

    def search_events(
        self,
        *,
        user_id: str,
        provider_name: str,
        query: str,
    ) -> list[dict[str, Any]]:
        payload = self._request(
            "GET",
            "/internal/v1/search/events?"
            + urllib.parse.urlencode(
                {
                    "user_id": user_id,
                    "provider": provider_name,
                    "query": query,
                }
            ),
        )
        items = payload.get("events", [])
        if not isinstance(items, list):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid event search payload."
            )
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

    def update_follow_recording(
        self,
        *,
        user_id: str,
        subscription_id: str,
        record: bool,
    ) -> dict[str, Any]:
        payload = self._request(
            "PATCH",
            "/internal/v1/subscriptions/"
            + urllib.parse.quote(subscription_id, safe="")
            + "/recording",
            {
                "user_id": user_id,
                "record": record,
            },
        )
        subscription = payload.get("subscription")
        if not isinstance(subscription, dict):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid subscription payload."
            )
        return dict(subscription)


    def get_live_availability(
        self,
        *,
        provider_name: str,
        provider_event_id: str,
    ) -> dict[str, object]:
        payload = self._request(
            "GET",
            "/internal/v1/live/availability?"
            + urllib.parse.urlencode(
                {
                    "provider": provider_name,
                    "provider_event_id": provider_event_id,
                }
            ),
        )
        availability = payload.get("availability")
        if not isinstance(availability, dict):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid "
                "Live availability payload."
            )

        available = availability.get("available")
        atlas_channel_id = availability.get("atlas_channel_id")
        if not isinstance(available, bool):
            raise SportsWriterTransportError(
                "Private Sports service returned invalid "
                "Live availability state."
            )
        if available:
            atlas_id = str(atlas_channel_id or "").strip()
            if not atlas_id:
                raise SportsWriterTransportError(
                    "Private Sports service returned incomplete "
                    "Live availability state."
                )
            return {
                "available": True,
                "atlas_channel_id": atlas_id,
            }

        if atlas_channel_id is not None:
            raise SportsWriterTransportError(
                "Private Sports service returned unsafe "
                "Live availability state."
            )

        return {
            "available": False,
            "atlas_channel_id": None,
        }

    def list_live_sources(
        self,
    ) -> list[dict[str, Any]]:
        """Return credential-safe authorized LiveSource metadata."""

        payload = self._request(
            "GET",
            "/internal/v1/live-sources",
        )

        raw_sources = payload.get(
            "live_sources"
        )

        if not isinstance(raw_sources, list):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid "
                "LiveSource payload."
            )

        allowed_fields = {
            "id",
            "name",
            "provider",
            "provider_event_id",
            "standalone",
            "atlas_channel_id",
            "resource_source_ids",
        }

        normalized: list[
            dict[str, Any]
        ] = []

        for raw in raw_sources:
            if (
                not isinstance(raw, dict)
                or not set(raw).issubset(
                    allowed_fields
                )
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned an unsafe "
                    "LiveSource entry."
                )

            source_id = raw.get("id")
            name = raw.get("name")
            provider = raw.get("provider")
            provider_event_id = raw.get(
                "provider_event_id"
            )
            standalone = raw.get(
                "standalone"
            )
            atlas_channel_id = raw.get(
                "atlas_channel_id"
            )

            if (
                not isinstance(source_id, str)
                or not source_id.strip()
                or not isinstance(name, str)
                or not name.strip()
                or not isinstance(standalone, bool)
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned an invalid "
                    "LiveSource entry."
                )

            if (
                provider is not None
                and (
                    not isinstance(provider, str)
                    or not provider.strip()
                )
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned an invalid "
                    "LiveSource provider."
                )

            if (
                provider_event_id is not None
                and (
                    not isinstance(
                        provider_event_id,
                        str,
                    )
                    or not provider_event_id.strip()
                )
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned an invalid "
                    "LiveSource provider event."
                )

            raw_resource_source_ids = raw.get(
                "resource_source_ids",
                [],
            )

            if (
                atlas_channel_id is not None
                and (
                    not isinstance(
                        atlas_channel_id,
                        str,
                    )
                    or not atlas_channel_id.strip()
                )
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned invalid "
                    "LiveSource channel metadata."
                )

            if not isinstance(
                raw_resource_source_ids,
                list,
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned invalid "
                    "LiveSource resource metadata."
                )

            resource_source_ids: list[str] = []
            seen_resource_source_ids: set[str] = set()

            for raw_resource_source_id in (
                raw_resource_source_ids
            ):
                if (
                    not isinstance(
                        raw_resource_source_id,
                        str,
                    )
                    or not raw_resource_source_id.strip()
                ):
                    raise SportsWriterTransportError(
                        "Private Sports service returned invalid "
                        "LiveSource resource metadata."
                    )

                resource_source_id = (
                    raw_resource_source_id.strip()
                )

                if (
                    resource_source_id
                    in seen_resource_source_ids
                ):
                    raise SportsWriterTransportError(
                        "Private Sports service returned duplicate "
                        "LiveSource resource metadata."
                    )

                seen_resource_source_ids.add(
                    resource_source_id
                )
                resource_source_ids.append(
                    resource_source_id
                )

            if (
                resource_source_ids
                and atlas_channel_id is None
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned incomplete "
                    "resource-managed LiveSource metadata."
                )

            normalized.append(
                {
                    "id": source_id.strip(),
                    "name": name.strip(),
                    "provider": (
                        provider.strip()
                        if isinstance(provider, str)
                        else None
                    ),
                    "provider_event_id": (
                        provider_event_id.strip()
                        if isinstance(
                            provider_event_id,
                            str,
                        )
                        else None
                    ),
                    "standalone": standalone,
                    "atlas_channel_id": (
                        atlas_channel_id.strip()
                        if isinstance(
                            atlas_channel_id,
                            str,
                        )
                        else None
                    ),
                    "resource_source_ids": (
                        resource_source_ids
                    ),
                }
            )

        return normalized

    def get_live_tv_binding(
        self,
        *,
        atlas_channel_id: str,
    ) -> dict[str, str]:
        payload = self._request(
            "GET",
            "/internal/v1/live-tv/bindings?"
            + urllib.parse.urlencode(
                {"atlas_channel_id": atlas_channel_id}
            ),
        )
        binding = payload.get("binding")
        if not isinstance(binding, dict):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid "
                "Live TV binding payload."
            )
        atlas_id = str(
            binding.get("atlas_channel_id", "")
        ).strip()
        jellyfin_id = str(
            binding.get("jellyfin_item_id", "")
        ).strip()
        if not atlas_id or not jellyfin_id:
            raise SportsWriterTransportError(
                "Private Sports service returned an incomplete "
                "Live TV binding."
            )
        if atlas_id != atlas_channel_id.strip():
            raise SportsWriterTransportError(
                "Private Sports service returned a mismatched "
                "Live TV binding."
            )
        return {
            "atlas_channel_id": atlas_id,
            "jellyfin_item_id": jellyfin_id,
        }

    def list_live_tv_bindings(
        self,
    ) -> list[dict[str, str]]:
        payload = self._request(
            "GET",
            "/internal/v1/live-tv/bindings",
        )
        bindings = payload.get("bindings")
        if not isinstance(bindings, list):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid "
                "Live TV bindings payload."
            )

        result: list[dict[str, str]] = []
        for binding in bindings:
            if not isinstance(binding, dict):
                raise SportsWriterTransportError(
                    "Private Sports service returned an invalid "
                    "Live TV binding entry."
                )
            atlas_id = str(
                binding.get("atlas_channel_id", "")
            ).strip()
            jellyfin_id = str(
                binding.get("jellyfin_item_id", "")
            ).strip()
            if not atlas_id or not jellyfin_id:
                raise SportsWriterTransportError(
                    "Private Sports service returned an incomplete "
                    "Live TV binding entry."
                )
            result.append(
                {
                    "atlas_channel_id": atlas_id,
                    "jellyfin_item_id": jellyfin_id,
                }
            )
        return result

    def set_live_tv_binding(
        self,
        *,
        atlas_channel_id: str,
        jellyfin_item_id: str,
    ) -> dict[str, str]:
        payload = self._request(
            "POST",
            "/internal/v1/live-tv/bindings",
            {
                "atlas_channel_id": atlas_channel_id,
                "jellyfin_item_id": jellyfin_item_id,
            },
        )
        binding = payload.get("binding")
        if not isinstance(binding, dict):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid "
                "Live TV binding payload."
            )
        atlas_id = str(
            binding.get("atlas_channel_id", "")
        ).strip()
        jellyfin_id = str(
            binding.get("jellyfin_item_id", "")
        ).strip()
        if not atlas_id or not jellyfin_id:
            raise SportsWriterTransportError(
                "Private Sports service returned an incomplete "
                "Live TV binding."
            )
        return {
            "atlas_channel_id": atlas_id,
            "jellyfin_item_id": jellyfin_id,
        }

    def remove_live_tv_binding(
        self,
        *,
        atlas_channel_id: str,
    ) -> bool:
        payload = self._request(
            "DELETE",
            "/internal/v1/live-tv/bindings/"
            + urllib.parse.quote(
                atlas_channel_id,
                safe="",
            ),
        )
        removed = payload.get("removed")
        if not isinstance(removed, bool):
            raise SportsWriterTransportError(
                "Private Sports service returned an invalid "
                "Live TV binding removal payload."
            )
        return removed

    @staticmethod
    def _safe_source_registry_payload(
        payload: Mapping[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        """Validate the credential-safe source registry boundary."""

        providers = payload.get("providers")
        sources = payload.get("sources")

        if not isinstance(providers, list):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an invalid providers payload."
            )

        if not isinstance(sources, list):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an invalid sources payload."
            )

        safe_providers: list[
            dict[str, Any]
        ] = []

        safe_sources: list[
            dict[str, Any]
        ] = []

        forbidden = {
            "password",
            "username",
            "server_url",
            "url",
            "token",
            "api_key",
            "apikey",
            "secret",
        }

        def assert_safe(
            value: object,
        ) -> None:
            if isinstance(value, dict):
                for raw_key, child in value.items():
                    key = (
                        str(raw_key)
                        .strip()
                        .lower()
                    )

                    if key in forbidden:
                        raise SportsWriterTransportError(
                            "Private Sports service returned "
                            "credential-bearing source metadata."
                        )

                    assert_safe(child)

            elif isinstance(value, list):
                for child in value:
                    assert_safe(child)

        for provider in providers:
            if not isinstance(
                provider,
                dict,
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned "
                    "an invalid provider entry."
                )

            assert_safe(provider)

            safe_providers.append(
                dict(provider)
            )

        for source in sources:
            if not isinstance(
                source,
                dict,
            ):
                raise SportsWriterTransportError(
                    "Private Sports service returned "
                    "an invalid source entry."
                )

            assert_safe(source)

            safe_sources.append(
                dict(source)
            )

        return {
            "providers": safe_providers,
            "sources": safe_sources,
        }

    def get_source_registry(
        self,
    ) -> dict[str, list[dict[str, Any]]]:
        """Return credential-safe Sports provider/account metadata."""

        return self._safe_source_registry_payload(
            self._request(
                "GET",
                "/internal/v1/sources",
            )
        )

    def update_provider_display_name(
        self,
        *,
        provider_id: str,
        display_name: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """Rename one provider without changing stable identity."""

        normalized_provider_id = (
            provider_id.strip()
        )

        if not normalized_provider_id:
            raise ValueError(
                "provider_id is required"
            )

        normalized_display_name = (
            display_name.strip()
        )

        if not normalized_display_name:
            raise ValueError(
                "provider display name is required"
            )

        payload = self._request(
            "PATCH",
            "/internal/v1/providers/"
            + urllib.parse.quote(
                normalized_provider_id,
                safe="",
            ),
            {
                "provider_display_name": (
                    normalized_display_name
                ),
            },
        )

        return self._safe_source_registry_payload(
            payload
        )

    def update_source_metadata(
        self,
        *,
        source_id: str,
        fields: Mapping[str, Any],
    ) -> dict[str, list[dict[str, Any]]]:
        """Update only safe editable account metadata."""

        normalized_source_id = (
            source_id.strip()
        )

        if not normalized_source_id:
            raise ValueError(
                "source_id is required"
            )

        allowed = {
            "account_display_name",
            "enabled",
            "max_connections",
        }

        unsupported = (
            set(fields)
            - allowed
        )

        if unsupported:
            raise ValueError(
                "unsupported Sports source "
                "metadata fields"
            )

        if not fields:
            raise ValueError(
                "at least one Sports source "
                "metadata field is required"
            )

        payload = self._request(
            "PATCH",
            "/internal/v1/sources/"
            + urllib.parse.quote(
                normalized_source_id,
                safe="",
            ),
            dict(fields),
        )

        return self._safe_source_registry_payload(
            payload
        )

    def create_provider_account(
        self,
        *,
        source_id: str,
        provider_id: str,
        provider_display_name: str,
        account_display_name: str,
        server_url: str,
        username: str,
        password: str,
        max_connections: int,
        priority: int = 100,
    ) -> dict[str, list[dict[str, Any]]]:
        """Create one disabled provider account transactionally."""

        normalized_source_id = source_id.strip()
        normalized_provider_id = provider_id.strip()
        normalized_provider_display_name = (
            provider_display_name.strip()
        )
        normalized_account_display_name = (
            account_display_name.strip()
        )
        normalized_server_url = server_url.strip()
        normalized_username = username.strip()

        required = (
            normalized_source_id,
            normalized_provider_id,
            normalized_provider_display_name,
            normalized_account_display_name,
            normalized_server_url,
            normalized_username,
        )

        if not all(required):
            raise ValueError(
                "Provider account identity and "
                "connection fields are required."
            )

        if (
            not isinstance(password, str)
            or password == ""
        ):
            raise ValueError(
                "Provider account password is required."
            )

        if (
            isinstance(max_connections, bool)
            or not isinstance(max_connections, int)
            or max_connections <= 0
        ):
            raise ValueError(
                "Provider account capacity must "
                "be a positive integer."
            )

        if (
            isinstance(priority, bool)
            or not isinstance(priority, int)
            or priority < 0
        ):
            raise ValueError(
                "Provider account priority must "
                "be a non-negative integer."
            )

        payload = self._request(
            "POST",
            "/internal/v1/provider-accounts",
            {
                "source_id": normalized_source_id,
                "provider_id": normalized_provider_id,
                "provider_display_name": (
                    normalized_provider_display_name
                ),
                "account_display_name": (
                    normalized_account_display_name
                ),
                "server_url": normalized_server_url,
                "username": normalized_username,
                "password": password,
                "max_connections": max_connections,
                "priority": priority,
            },
        )

        source = payload.get("source")
        account = payload.get("account")

        if not isinstance(source, dict):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an invalid created source."
            )

        if not isinstance(account, dict):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an invalid created account."
            )

        # Reuse the existing recursive credential
        # boundary rather than maintaining a second
        # secret-key allow/deny implementation.
        safe_source = (
            self._safe_source_registry_payload(
                {
                    "providers": [],
                    "sources": [
                        source,
                    ],
                }
            )["sources"][0]
        )

        if (
            str(
                safe_source.get(
                    "source_id",
                    "",
                )
            ).strip()
            != normalized_source_id
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "the wrong created source."
            )

        if (
            str(
                safe_source.get(
                    "provider_id",
                    "",
                )
            ).strip()
            != normalized_provider_id
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "the wrong created provider."
            )

        if safe_source.get("enabled") is not False:
            raise SportsWriterTransportError(
                "New provider account was not "
                "created disabled."
            )

        allowed_account_fields = {
            "account_id",
            "name",
            "account_type",
            "enabled",
            "configured_max_connections",
            "credentials_configured",
        }

        if set(account) != allowed_account_fields:
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an unsafe created account."
            )

        if account.get("account_type") != "XC":
            raise SportsWriterTransportError(
                "Private Sports service created "
                "an unexpected account type."
            )

        if not isinstance(
            account.get(
                "credentials_configured"
            ),
            bool,
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "invalid created credential state."
            )

        # Do not return the private creation payload:
        # source metadata includes backend_reference.
        # Refresh through the established safe registry
        # adapter instead.
        return self.get_source_registry()

    def remove_provider_account(
        self,
        *,
        source_id: str,
    ) -> bool:
        """Remove one already-disabled provider account."""

        normalized_source_id = source_id.strip()

        if not normalized_source_id:
            raise ValueError(
                "source_id is required"
            )

        payload = self._request(
            "DELETE",
            "/internal/v1/provider-accounts/"
            + urllib.parse.quote(
                normalized_source_id,
                safe="",
            ),
        )

        if set(payload) != {
            "removed",
            "source_id",
        }:
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an unsafe provider-account "
                "removal response."
            )

        if payload.get("removed") is not True:
            raise SportsWriterTransportError(
                "Private Sports service did not "
                "confirm provider-account removal."
            )

        if (
            str(
                payload.get(
                    "source_id",
                    "",
                )
            ).strip()
            != normalized_source_id
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "the wrong removed source."
            )

        return True

    def update_dispatcharr_credentials(
        self,
        *,
        source_id: str,
        server_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> dict[str, Any]:
        """Update only allowlisted provider authentication fields."""

        normalized_source_id = (
            source_id.strip()
        )

        if not normalized_source_id:
            raise ValueError(
                "source_id is required"
            )

        body: dict[str, Any] = {}

        if server_url is not None:
            body[
                "server_url"
            ] = server_url

        if username is not None:
            body[
                "username"
            ] = username

        if password is not None:
            body[
                "password"
            ] = password

        if not body:
            raise ValueError(
                "At least one connection "
                "field is required"
            )

        payload = self._request(
            "PATCH",
            "/internal/v1/sources/"
            + urllib.parse.quote(
                normalized_source_id,
                safe="",
            )
            + "/credentials",
            body,
        )

        account = payload.get(
            "account"
        )

        if not isinstance(
            account,
            dict,
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an invalid Dispatcharr account."
            )

        allowed = {
            "account_id",
            "name",
            "account_type",
            "enabled",
            "configured_max_connections",
            "credentials_configured",
        }

        if set(account) != allowed:
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an unsafe Dispatcharr account."
            )

        if not isinstance(
            account.get(
                "credentials_configured"
            ),
            bool,
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "invalid credential status."
            )

        return dict(account)

    def get_dispatcharr_account(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        """Return only secret-safe Dispatcharr account state."""

        normalized_source_id = (
            source_id.strip()
        )

        if not normalized_source_id:
            raise ValueError(
                "source_id is required"
            )

        payload = self._request(
            "GET",
            "/internal/v1/sources/"
            + urllib.parse.quote(
                normalized_source_id,
                safe="",
            )
            + "/dispatcharr-account",
        )

        account = payload.get(
            "account"
        )

        if not isinstance(
            account,
            dict,
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an invalid Dispatcharr account."
            )

        allowed = {
            "account_id",
            "name",
            "account_type",
            "enabled",
            "configured_max_connections",
            "credentials_configured",
        }

        if set(account) != allowed:
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an unsafe Dispatcharr account."
            )

        if not isinstance(
            account.get(
                "credentials_configured"
            ),
            bool,
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "invalid credential status."
            )

        return dict(account)

    def test_dispatcharr_connection(
        self,
        *,
        source_id: str,
    ) -> dict[str, Any]:
        """Run one secret-safe provider authentication probe."""

        normalized_source_id = (
            source_id.strip()
        )

        if not normalized_source_id:
            raise ValueError(
                "source_id is required"
            )

        payload = self._request(
            "POST",
            "/internal/v1/sources/"
            + urllib.parse.quote(
                normalized_source_id,
                safe="",
            )
            + "/test-connection",
            {},
        )

        connection = payload.get(
            "connection"
        )

        if not isinstance(
            connection,
            dict,
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an invalid connection test."
            )

        allowed = {
            "ok",
            "status",
            "expires_at",
            "provider_max_connections",
            "active_connections",
        }

        if set(connection) != allowed:
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "an unsafe connection test."
            )

        if not isinstance(
            connection.get("ok"),
            bool,
        ):
            raise SportsWriterTransportError(
                "Private Sports service returned "
                "invalid connection-test status."
            )

        return dict(connection)

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
            if code in {
                "sports_source_exists",
                "sports_provider_account_enabled",
                "sports_provider_account_playback_dependency",
            }:
                raise SportsProviderAccountConflictError(
                    message
                ) from exc
            if code == "sports_source_not_found":
                raise SportsProviderAccountNotFoundError(
                    message
                ) from exc
            if code == "sports_provider_account_invalid":
                raise SportsProviderAccountInvalidError(
                    message
                ) from exc
            if code == "sports_live_tv_binding_not_found":
                raise SportsLiveTvBindingNotFoundError(message) from exc
            if code == "provider_not_found":
                raise SportsProviderNotFoundError(message) from exc
            if code == "event_not_found":
                raise SportsEventNotFoundError(message) from exc
            if code == "sports_subscription_not_found":
                raise SportsSubscriptionNotFoundError(message) from exc
            if code == "sports_recording_target_unsupported":
                raise SportsRecordingTargetUnsupportedError(message) from exc
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
