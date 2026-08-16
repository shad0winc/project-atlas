"""Contract tests for the authenticated Sports application boundary."""

from __future__ import annotations

from typing import Any

import pytest

from atlas_api.services.sports import (
    SportsAPIService,
    SportsEventNotFoundError,
)


class FakeSportsProvider:
    name = "thesportsdb"

    def __init__(self) -> None:
        self.fetch_event_calls: list[str] = []
        self.fetch_games_calls = 0

    def fetch_games(
        self,
    ) -> list[dict[str, Any]]:
        self.fetch_games_calls += 1

        return [
            {
                "provider": self.name,
                "provider_event_id": "event-001",
                "name": "Atlas United vs Atlas City",
                "sport": "Soccer",
                "league": "Atlas Test League",
                "start_at": "2026-08-17T20:00:00Z",
                "status": "scheduled",
            },
            {
                "provider": self.name,
                "provider_event_id": "event-002",
                "name": "Atlas Rovers vs Atlas Athletic",
                "sport": "Soccer",
                "league": "Atlas Test League",
                "start_at": "2026-08-18T20:00:00Z",
                "status": "scheduled",
            },
        ]

    def fetch_event(
        self,
        event_id: str,
    ) -> dict[str, Any] | None:
        self.fetch_event_calls.append(event_id)

        if event_id == "missing-event":
            return None

        return {
            "idEvent": event_id,
            "strEvent": "Atlas United vs Atlas City",
            "strSport": "Soccer",
            "strLeague": "Atlas Test League",
            "strTimestamp": "2026-08-17T20:00:00Z",
            "strStatus": "Not Started",
        }

    def normalize_event(
        self,
        event: dict[str, Any],
    ) -> dict[str, Any]:
        return {
            "provider": self.name,
            "provider_event_id": str(event["idEvent"]),
            "name": str(event["strEvent"]),
            "sport": str(event["strSport"]),
            "league": str(event["strLeague"]),
            "start_at": str(event["strTimestamp"]),
            "status": "scheduled",
        }


def test_create_event_subscription_derives_server_owned_fields() -> None:
    provider = FakeSportsProvider()
    captured: list[tuple[str, str, str, str, str]] = []

    def create_subscription(
        subscription_type: str,
        provider_name: str,
        event_id: str,
        name: str,
        user_id: str,
    ) -> tuple[dict[str, Any], bool]:
        captured.append(
            (
                subscription_type,
                provider_name,
                event_id,
                name,
                user_id,
            )
        )

        return (
            {
                "subscription_id": "sub-atlas-001",
                "type": subscription_type,
                "provider": provider_name,
                "id": event_id,
                "name": name,
                "user": user_id,
                "enabled": True,
                "created_at": "2026-08-16T20:00:00+00:00",
            },
            True,
        )

    service = SportsAPIService(
        providers={"thesportsdb": provider},
        create_subscription=create_subscription,
        load_subscriptions=lambda: [],
    )

    result, created = service.create_event_subscription(
        user_id="usr-atlas-001",
        provider_name="thesportsdb",
        provider_event_id="event-001",
    )

    assert created is True
    assert provider.fetch_event_calls == ["event-001"]

    assert captured == [
        (
            "event",
            "thesportsdb",
            "event-001",
            "Atlas United vs Atlas City",
            "usr-atlas-001",
        )
    ]

    assert result["subscription_id"] == "sub-atlas-001"
    assert result["provider"] == "thesportsdb"
    assert result["id"] == "event-001"
    assert result["user"] == "usr-atlas-001"


def test_create_event_subscription_preserves_duplicate_result() -> None:
    provider = FakeSportsProvider()

    existing = {
        "subscription_id": "sub-existing",
        "type": "event",
        "provider": "thesportsdb",
        "id": "event-001",
        "name": "Atlas United vs Atlas City",
        "user": "usr-atlas-001",
        "enabled": True,
        "created_at": "2026-08-16T20:00:00+00:00",
    }

    service = SportsAPIService(
        providers={"thesportsdb": provider},
        create_subscription=lambda *args: (existing, False),
        load_subscriptions=lambda: [existing],
    )

    result, created = service.create_event_subscription(
        user_id="usr-atlas-001",
        provider_name="thesportsdb",
        provider_event_id="event-001",
    )

    assert created is False
    assert result == existing


def test_create_event_subscription_rejects_missing_provider_event() -> None:
    provider = FakeSportsProvider()

    service = SportsAPIService(
        providers={"thesportsdb": provider},
        create_subscription=lambda *args: pytest.fail(
            "Missing provider event must not create a subscription."
        ),
        load_subscriptions=lambda: [],
    )

    with pytest.raises(
        SportsEventNotFoundError,
        match="Sports event was not found",
    ):
        service.create_event_subscription(
            user_id="usr-atlas-001",
            provider_name="thesportsdb",
            provider_event_id="missing-event",
        )


def test_list_events_marks_only_same_user_provider_event_as_requested() -> None:
    provider = FakeSportsProvider()

    subscriptions = [
        {
            "subscription_id": "sub-own",
            "type": "event",
            "provider": "thesportsdb",
            "id": "event-001",
            "name": "Atlas United vs Atlas City",
            "user": "usr-atlas-001",
            "enabled": True,
            "created_at": "2026-08-16T20:00:00+00:00",
        },
        {
            "subscription_id": "sub-other-user",
            "type": "event",
            "provider": "thesportsdb",
            "id": "event-002",
            "name": "Other Event",
            "user": "usr-other",
            "enabled": True,
            "created_at": "2026-08-16T20:00:00+00:00",
        },
    ]

    service = SportsAPIService(
        providers={"thesportsdb": provider},
        create_subscription=lambda *args: pytest.fail(
            "Read operation must not create subscriptions."
        ),
        load_subscriptions=lambda: subscriptions,
    )

    events = service.list_events_for_user(
        user_id="usr-atlas-001",
        provider_name="thesportsdb",
        provider_event_ids=("event-001", "event-002"),
    )

    assert [event["provider_event_id"] for event in events] == [
        "event-001",
        "event-002",
    ]

    assert events[0]["requested"] is True
    assert events[1]["requested"] is False


def test_sports_module_env_loader_sets_only_missing_values(
    tmp_path,
    monkeypatch,
) -> None:
    from atlas_api.services.sports import (
        _load_sports_module_env,
    )

    env_file = tmp_path / ".env"

    env_file.write_text(
        "\n".join(
            (
                "# Sports fixture",
                "SPORTS_TEST_NEW=value-from-file",
                "SPORTS_TEST_EXISTING=value-from-file",
                "",
            )
        ),
        encoding="utf-8",
    )

    monkeypatch.delenv(
        "SPORTS_TEST_NEW",
        raising=False,
    )

    monkeypatch.setenv(
        "SPORTS_TEST_EXISTING",
        "value-from-process",
    )

    _load_sports_module_env(env_file)

    assert (
        __import__("os").environ[
            "SPORTS_TEST_NEW"
        ]
        == "value-from-file"
    )

    assert (
        __import__("os").environ[
            "SPORTS_TEST_EXISTING"
        ]
        == "value-from-process"
    )


def test_list_events_without_ids_uses_provider_discovery() -> None:
    provider = FakeSportsProvider()

    subscriptions = [
        {
            "subscription_id": "sub-own",
            "type": "event",
            "provider": "thesportsdb",
            "id": "event-001",
            "name": "Atlas United vs Atlas City",
            "user": "usr-atlas-001",
            "enabled": True,
            "created_at": "2026-08-16T20:00:00+00:00",
        },
    ]

    service = SportsAPIService(
        providers={"thesportsdb": provider},
        create_subscription=lambda *args: pytest.fail(
            "Discovery must not create subscriptions."
        ),
        load_subscriptions=lambda: subscriptions,
    )

    events = service.list_events_for_user(
        user_id="usr-atlas-001",
        provider_name="thesportsdb",
    )

    assert provider.fetch_games_calls == 1
    assert provider.fetch_event_calls == []

    assert [
        event["provider_event_id"]
        for event in events
    ] == [
        "event-001",
        "event-002",
    ]

    assert events[0]["requested"] is True
    assert events[1]["requested"] is False


def test_list_events_with_ids_does_not_run_broad_discovery() -> None:
    provider = FakeSportsProvider()

    service = SportsAPIService(
        providers={"thesportsdb": provider},
        create_subscription=lambda *args: pytest.fail(
            "Read operation must not create subscriptions."
        ),
        load_subscriptions=lambda: [],
    )

    events = service.list_events_for_user(
        user_id="usr-atlas-001",
        provider_name="thesportsdb",
        provider_event_ids=("event-001",),
    )

    assert provider.fetch_games_calls == 0
    assert provider.fetch_event_calls == [
        "event-001",
    ]

    assert len(events) == 1
    assert (
        events[0]["provider_event_id"]
        == "event-001"
    )
