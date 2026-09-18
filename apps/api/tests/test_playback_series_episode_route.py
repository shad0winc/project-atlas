"""Route contracts for safe Theater series episode navigation."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import clear_dependency_caches
from atlas_api.routes.v1 import playback


USER = AuthenticatedUser(
    user_id="usr-episode-navigation",
    username="episode-navigation",
    display_name="Episode Navigation",
    provider="test",
)


class FakePlayback:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def list_library_series_episodes(
        self,
        *,
        provider: str,
        item_id: str,
    ) -> tuple[dict[str, object], ...]:
        self.calls.append(
            {
                "provider": provider,
                "item_id": item_id,
            }
        )

        return (
            {
                "id": "episode-s01e01",
                "title": "Pilot",
                "series_name": "Example Series",
                "season_number": 1,
                "episode_number": 1,
            },
            {
                "id": "episode-s02e03",
                "title": "Return",
                "series_name": "Example Series",
                "season_number": 2,
                "episode_number": 3,
            },
        )


def build_client() -> tuple[TestClient, FakePlayback]:
    app = FastAPI()
    app.include_router(
        playback.router,
        prefix="/api/v1",
    )

    service = FakePlayback()

    app.dependency_overrides[
        playback.require_playback_read
    ] = lambda: USER

    app.dependency_overrides[
        playback.get_playback_service
    ] = lambda: service

    return TestClient(app), service


def test_series_episode_route_returns_safe_ordered_identities() -> None:
    client, service = build_client()

    response = client.get(
        "/api/v1/media/playback/jellyfin/series-1/episodes"
    )

    assert response.status_code == 200

    assert service.calls == [
        {
            "provider": "jellyfin",
            "item_id": "series-1",
        }
    ]

    assert response.json() == {
        "provider": "jellyfin",
        "series_id": "series-1",
        "episodes": [
            {
                "id": "episode-s01e01",
                "title": "Pilot",
                "series_name": "Example Series",
                "season_number": 1,
                "episode_number": 1,
            },
            {
                "id": "episode-s02e03",
                "title": "Return",
                "series_name": "Example Series",
                "season_number": 2,
                "episode_number": 3,
            },
        ],
    }


def test_series_episode_route_requires_media_read(
    tmp_path,
    monkeypatch,
) -> None:
    audit_path = tmp_path / "events.jsonl"
    audit_path.write_text("", encoding="utf-8")
    audit_path.chmod(0o660)

    monkeypatch.setenv(
        "ATLAS_JWT_SECRET",
        "atlas-playback-episode-test-secret-0123456789abcdef",
    )
    monkeypatch.setenv(
        "ATLAS_SECURITY_AUDIT_PATH",
        str(audit_path),
    )

    clear_dependency_caches()

    try:
        app = FastAPI()
        app.include_router(
            playback.router,
            prefix="/api/v1",
        )

        client = TestClient(app)

        response = client.get(
            "/api/v1/media/playback/jellyfin/series-1/episodes"
        )

        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
    finally:
        clear_dependency_caches()
