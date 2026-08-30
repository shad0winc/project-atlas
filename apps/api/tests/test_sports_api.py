"""HTTP contract tests for the Atlas v1 Sports request journey."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.routes.v1.sports import (
    get_sports_api_service,
    require_sports_events_request,
    require_sports_read,
    router,
)
from atlas_api.services.sports import (
    SportsWriterBackedAPIService,
    SportsWriterTransportError,
)


USER = AuthenticatedUser(
    user_id="usr-atlas-001",
    username="atlas-user",
    display_name="Atlas Test User",
    provider="test",
)


class FakeSportsService:
    def __init__(self) -> None:
        self.create_calls: list[dict[str, str]] = []

    def list_events_for_user(
        self,
        *,
        user_id: str,
        provider_name: str,
        provider_event_ids: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        assert user_id == USER.user_id
        assert provider_name == "thesportsdb"

        return [
            {
                "provider": "thesportsdb",
                "provider_event_id": "event-001",
                "name": "Atlas United vs Atlas City",
                "sport": "Soccer",
                "league": "Atlas Test League",
                "start_at": "2026-08-17T20:00:00Z",
                "status": "scheduled",
                "requested": False,
            }
        ]

    def create_event_subscription(
        self,
        *,
        user_id: str,
        provider_name: str,
        provider_event_id: str,
    ) -> tuple[dict[str, Any], bool]:
        self.create_calls.append(
            {
                "user_id": user_id,
                "provider": provider_name,
                "provider_event_id": provider_event_id,
            }
        )

        return (
            {
                "subscription_id": "sub-atlas-001",
                "type": "event",
                "provider": provider_name,
                "id": provider_event_id,
                "name": "Atlas United vs Atlas City",
                "user": user_id,
                "enabled": True,
                "created_at": "2026-08-16T20:00:00+00:00",
            },
            True,
        )


def build_client(
    service: FakeSportsService,
) -> TestClient:
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")

    app.dependency_overrides[
        require_sports_read
    ] = lambda: USER

    app.dependency_overrides[
        require_sports_events_request
    ] = lambda: USER

    app.dependency_overrides[
        get_sports_api_service
    ] = lambda: service

    return TestClient(app)


def test_list_sports_events_is_authenticated_user_scoped() -> None:
    service = FakeSportsService()
    client = build_client(service)

    response = client.get(
        "/api/v1/sports/events",
        params={"provider": "thesportsdb"},
    )

    assert response.status_code == 200

    assert response.json() == {
        "events": [
            {
                "provider": "thesportsdb",
                "provider_event_id": "event-001",
                "name": "Atlas United vs Atlas City",
                "sport": "Soccer",
                "league": "Atlas Test League",
                "start_at": "2026-08-17T20:00:00Z",
                "status": "scheduled",
                "requested": False,
            }
        ]
    }


def test_create_sports_event_subscription_uses_authenticated_user() -> None:
    service = FakeSportsService()
    client = build_client(service)

    response = client.post(
        "/api/v1/sports/subscriptions",
        json={
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
        },
    )

    assert response.status_code == 201

    assert service.create_calls == [
        {
            "user_id": USER.user_id,
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
        }
    ]

    payload = response.json()

    assert payload["subscription_id"] == "sub-atlas-001"
    assert payload["provider_event_id"] == "event-001"
    assert payload["user_id"] == USER.user_id


def test_create_sports_event_subscription_rejects_caller_owned_identity() -> None:
    service = FakeSportsService()
    client = build_client(service)

    response = client.post(
        "/api/v1/sports/subscriptions",
        json={
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
            "user_id": "usr-attacker",
        },
    )

    assert response.status_code == 422
    assert service.create_calls == []


def test_duplicate_sports_event_subscription_returns_existing_state() -> None:
    service = FakeSportsService()

    def duplicate(
        *,
        user_id: str,
        provider_name: str,
        provider_event_id: str,
    ) -> tuple[dict[str, Any], bool]:
        service.create_calls.append(
            {
                "user_id": user_id,
                "provider": provider_name,
                "provider_event_id": provider_event_id,
            }
        )

        return (
            {
                "subscription_id": "sub-existing",
                "type": "event",
                "provider": provider_name,
                "id": provider_event_id,
                "name": "Atlas United vs Atlas City",
                "user": user_id,
                "enabled": True,
                "created_at": "2026-08-16T20:00:00+00:00",
            },
            False,
        )

    service.create_event_subscription = duplicate  # type: ignore[method-assign]

    client = build_client(service)

    response = client.post(
        "/api/v1/sports/subscriptions",
        json={
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
        },
    )

    assert response.status_code == 200
    assert response.json()["subscription_id"] == "sub-existing"


def test_list_sports_events_maps_private_transport_failure_to_503() -> None:
    service = FakeSportsService()

    def unavailable(
        *,
        user_id: str,
        provider_name: str,
        provider_event_ids: tuple[str, ...] | None = None,
    ) -> list[dict[str, Any]]:
        raise SportsWriterTransportError(
            "Private Sports service is unavailable."
        )

    service.list_events_for_user = unavailable  # type: ignore[method-assign]
    client = build_client(service)

    response = client.get(
        "/api/v1/sports/events",
        params={"provider": "thesportsdb"},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Private Sports service is unavailable."
    }


def test_create_sports_subscription_maps_private_transport_failure_to_503() -> None:
    service = FakeSportsService()

    def unavailable(
        *,
        user_id: str,
        provider_name: str,
        provider_event_id: str,
    ) -> tuple[dict[str, Any], bool]:
        raise SportsWriterTransportError(
            "Private Sports service is unavailable."
        )

    service.create_event_subscription = unavailable  # type: ignore[method-assign]
    client = build_client(service)

    response = client.post(
        "/api/v1/sports/subscriptions",
        json={
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
        },
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "Private Sports service is unavailable."
    }


def test_sports_route_permission_contract_is_frozen() -> None:
    from atlas_api.routes.v1 import sports

    assert sports.SPORTS_READ_PERMISSION == "sports.read"
    assert (
        sports.SPORTS_EVENTS_REQUEST_PERMISSION
        == "sports.events.request"
    )


def test_sports_writer_adapter_maps_dropped_connection_to_transport_error(
    monkeypatch,
) -> None:
    import http.client

    import pytest

    service = SportsWriterBackedAPIService(
        base_url="http://sports-writer:8003",
        token="test-token",
        timeout_seconds=1.0,
    )

    def dropped_connection(*args, **kwargs):
        raise http.client.RemoteDisconnected(
            "Remote end closed connection without response"
        )

    monkeypatch.setattr(
        "atlas_api.services.sports.urllib.request.urlopen",
        dropped_connection,
    )

    with pytest.raises(
        SportsWriterTransportError,
        match="Private Sports service is unavailable",
    ):
        service.list_events_for_user(
            user_id="usr-test",
            provider_name="thesportsdb",
        )
