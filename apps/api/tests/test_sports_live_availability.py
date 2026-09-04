from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.routes.v1 import sports_playback
from atlas_api.services.sports import (
    SportsWriterBackedAPIService,
    SportsWriterTransportError,
)


USER = AuthenticatedUser(
    user_id="usr-live-availability",
    username="live-user",
    display_name="Live User",
    provider="test",
)


class FakeSports:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result
        self.calls: list[tuple[str, str]] = []

    def get_live_availability(
        self,
        *,
        provider_name: str,
        provider_event_id: str,
    ) -> dict[str, object]:
        self.calls.append((provider_name, provider_event_id))
        return dict(self.result)


def build_client(sports: FakeSports) -> TestClient:
    app = FastAPI()
    app.include_router(sports_playback.router, prefix="/api/v1")
    app.dependency_overrides[
        sports_playback.require_sports_read
    ] = lambda: USER
    app.dependency_overrides[
        sports_playback.get_sports_api_service
    ] = lambda: sports
    return TestClient(app)


def test_public_live_availability_returns_safe_bound_channel() -> None:
    sports = FakeSports(
        {
            "available": True,
            "atlas_channel_id": "sports-live-source-001",
        }
    )
    client = build_client(sports)

    response = client.get(
        "/api/v1/sports/live/availability",
        params={
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "available": True,
        "atlas_channel_id": "sports-live-source-001",
    }
    assert sports.calls == [("thesportsdb", "event-001")]


def test_public_live_availability_can_fail_closed() -> None:
    sports = FakeSports(
        {
            "available": False,
            "atlas_channel_id": None,
        }
    )
    client = build_client(sports)

    response = client.get(
        "/api/v1/sports/live/availability",
        params={
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "atlas_channel_id": None,
    }


def test_writer_adapter_uses_event_identity_and_validates_safe_shape(
    monkeypatch,
) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://sports-writer:8003",
        token="test-token",
        timeout_seconds=1.0,
    )
    calls: list[tuple[str, str]] = []

    def request(method: str, path: str, payload=None):
        calls.append((method, path))
        return {
            "availability": {
                "available": True,
                "atlas_channel_id": "sports-live-source-001",
            }
        }

    monkeypatch.setattr(service, "_request", request)

    result = service.get_live_availability(
        provider_name="thesportsdb",
        provider_event_id="event-001",
    )

    assert result == {
        "available": True,
        "atlas_channel_id": "sports-live-source-001",
    }
    assert calls == [
        (
            "GET",
            "/internal/v1/live/availability"
            "?provider=thesportsdb&provider_event_id=event-001",
        )
    ]


def test_writer_adapter_rejects_false_state_that_exposes_channel(
    monkeypatch,
) -> None:
    service = SportsWriterBackedAPIService(
        base_url="http://sports-writer:8003",
        token="test-token",
        timeout_seconds=1.0,
    )
    monkeypatch.setattr(
        service,
        "_request",
        lambda *args, **kwargs: {
            "availability": {
                "available": False,
                "atlas_channel_id": "must-not-escape",
            }
        },
    )

    try:
        service.get_live_availability(
            provider_name="thesportsdb",
            provider_event_id="event-001",
        )
    except SportsWriterTransportError:
        pass
    else:
        raise AssertionError("unsafe false availability must fail closed")
