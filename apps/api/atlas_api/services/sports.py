"""Authenticated application adapter for the existing Atlas Sports module."""

from __future__ import annotations

import importlib
import os
import sys
from contextlib import contextmanager
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

        if key:
            os.environ.setdefault(
                key,
                value,
            )


@contextmanager
def _sports_import_path():
    sports_src = Path(
        "/opt/project-atlas/modules/sports/src"
    ).resolve()

    if not sports_src.is_dir():
        raise RuntimeError(
            f"Sports source directory is unavailable: {sports_src}"
        )

    path_text = str(sports_src)
    inserted = path_text not in sys.path

    if inserted:
        sys.path.insert(0, path_text)

    try:
        yield
    finally:
        if inserted:
            try:
                sys.path.remove(path_text)
            except ValueError:
                pass


def build_default_sports_api_service(
) -> SportsAPIService:
    _load_sports_module_env()

    with _sports_import_path():
        subscriptions = importlib.import_module(
            "subscriptions"
        )

        provider_registry = importlib.import_module(
            "providers.registry"
        )

        providers = {
            provider.name: provider
            for provider in provider_registry.enabled_providers()
        }

    return SportsAPIService(
        providers=providers,
        create_subscription=subscriptions.create_subscription,
        load_subscriptions=subscriptions.load_subscriptions,
    )
