from __future__ import annotations

from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.testclient import TestClient

from atlas.media import (
    PlaybackActionKind,
    PlaybackSession,
    PlaybackSourceType,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.routes.v1 import sports_playback
from atlas_api.services.playback import PlaybackNotFoundError
from atlas_api.services.sports import (
    SportsLiveTvBindingNotFoundError,
    SportsWriterTransportError,
)


USER = AuthenticatedUser(
    user_id="usr-atlas-live",
    username="atlas-live",
    display_name="Atlas Live",
    provider="test",
)


class FakeProfiles:
    def get_user(self, user_id: str) -> dict[str, str]:
        assert user_id == USER.user_id
        return {
            "user_id": USER.user_id,
            "jellyfin_user_id": "jf-user-live",
        }


class FakeSports:
    def __init__(self) -> None:
        self.binding_calls: list[str] = []

    def get_live_tv_binding(
        self,
        *,
        atlas_channel_id: str,
    ) -> dict[str, str]:
        self.binding_calls.append(atlas_channel_id)
        return {
            "atlas_channel_id": atlas_channel_id,
            "jellyfin_item_id": "jf-channel-exact",
        }


class FakePlayback:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def resolve_live_session(self, **kwargs) -> PlaybackSession:
        self.calls.append(dict(kwargs))
        return PlaybackSession(
            available=True,
            action=PlaybackActionKind.WATCH_LIVE,
            label="Watch Live",
            backend="jellyfin",
            source_type=PlaybackSourceType.LIVE,
            provider="jellyfin",
            requested_target_id="jf-channel-exact",
            playable_target_id="jf-channel-exact",
            title="Atlas Test Channel",
            media_type="video",
            duration_ticks=None,
            can_seek=False,
            stream_path="/Videos/jf-channel-exact/master.m3u8",
            audio_tracks=(),
            subtitle_tracks=(),
            previous_target_id=None,
            next_target_id=None,
        )


class FakeCapabilities:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def create_bootstrap(
        self,
        *,
        user_id: str,
        playable_target_id: str,
        stream_path: str,
    ) -> str:
        self.calls.append(
            {
                "user_id": user_id,
                "playable_target_id": playable_target_id,
                "stream_path": stream_path,
            }
        )
        return "capability-test-token"


@dataclass
class Harness:
    client: TestClient
    sports: FakeSports
    playback: FakePlayback
    capabilities: FakeCapabilities


def build_harness() -> Harness:
    app = FastAPI()
    app.include_router(sports_playback.router, prefix="/api/v1")

    sports = FakeSports()
    playback = FakePlayback()
    capabilities = FakeCapabilities()

    app.dependency_overrides[
        sports_playback.require_sports_read
    ] = lambda: USER
    app.dependency_overrides[
        sports_playback.get_sports_api_service
    ] = lambda: sports
    app.dependency_overrides[
        sports_playback.get_user_profile_store
    ] = lambda: FakeProfiles()
    app.dependency_overrides[
        sports_playback.get_playback_service
    ] = lambda: playback
    app.dependency_overrides[
        sports_playback.get_playback_capability_service
    ] = lambda: capabilities

    return Harness(
        client=TestClient(app),
        sports=sports,
        playback=playback,
        capabilities=capabilities,
    )


def test_watch_live_uses_exact_binding_and_authenticated_identity() -> None:
    harness = build_harness()

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 200
    assert harness.sports.binding_calls == ["sports-event-001"]
    assert harness.playback.calls == [
        {
            "provider": "jellyfin",
            "item_id": "jf-channel-exact",
            "jellyfin_user_id": "jf-user-live",
            "subtitle_stream_index": None,
        }
    ]
    assert harness.capabilities.calls == [
        {
            "user_id": USER.user_id,
            "playable_target_id": "jf-channel-exact",
            "stream_path": "/Videos/jf-channel-exact/master.m3u8",
        }
    ]

    payload = response.json()
    assert payload["action"] == "watch_live"
    assert payload["source_type"] == "live"
    assert payload["playable_target_id"] == "jf-channel-exact"
    assert payload["playback_capability"] == "capability-test-token"


def test_watch_live_missing_binding_is_404() -> None:
    harness = build_harness()

    def missing(*, atlas_channel_id: str):
        raise SportsLiveTvBindingNotFoundError(
            f"missing: {atlas_channel_id}"
        )

    harness.sports.get_live_tv_binding = missing  # type: ignore[method-assign]

    response = harness.client.get(
        "/api/v1/sports/live/sports-missing/session"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Sports live channel is not available."
    )
    assert harness.playback.calls == []


def test_watch_live_bound_non_live_or_missing_jellyfin_item_is_404() -> None:
    harness = build_harness()

    def unavailable(**kwargs):
        raise PlaybackNotFoundError("not live")

    harness.playback.resolve_live_session = unavailable  # type: ignore[method-assign]

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Sports live channel is not available."
    )


def test_watch_live_writer_failure_is_503_without_private_detail() -> None:
    harness = build_harness()

    def unavailable(*, atlas_channel_id: str):
        raise SportsWriterTransportError(
            "private writer secret diagnostic"
        )

    harness.sports.get_live_tv_binding = unavailable  # type: ignore[method-assign]

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Sports live channel resolution is unavailable."
    )
    assert "secret" not in response.text.lower()


def test_watch_live_supports_explicit_subtitle_selection() -> None:
    harness = build_harness()

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session",
        params={"subtitle": "4"},
    )

    assert response.status_code == 200
    assert harness.playback.calls[0]["subtitle_stream_index"] == 4
