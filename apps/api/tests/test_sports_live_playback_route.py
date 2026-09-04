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


class FakePolicy:
    def __init__(self, limit: int = 5) -> None:
        self.limit = limit
        self.calls: list[str] = []

    def effective_limit(self, user_id: str) -> int:
        self.calls.append(user_id)
        return self.limit


class _FakeLiveRecord:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id


class FakeLiveSessions:
    ttl_seconds = 90

    def __init__(self) -> None:
        self.admit_calls: list[dict[str, object]] = []
        self.heartbeat_calls: list[dict[str, str]] = []
        self.release_calls: list[dict[str, str]] = []
        self.block = False
        self.active = {"live-session-test"}

    def admit(self, **kwargs):
        from atlas_api.live_sessions import LiveSessionLimitExceeded

        self.admit_calls.append(dict(kwargs))
        if self.block:
            raise LiveSessionLimitExceeded("Live-session limit reached.")
        self.active.add("live-session-test")
        return _FakeLiveRecord("live-session-test")

    def heartbeat(self, *, session_id: str, user_id: str):
        from atlas_api.live_sessions import LiveSessionNotFound, LiveSessionRecord

        self.heartbeat_calls.append(
            {"session_id": session_id, "user_id": user_id}
        )
        if session_id not in self.active:
            raise LiveSessionNotFound("missing")
        return LiveSessionRecord(
            session_id=session_id,
            user_id=user_id,
            target_id="sports-event-001",
            created_at=1.0,
            last_seen_at=2.0,
        )

    def release(self, *, session_id: str, user_id: str) -> bool:
        self.release_calls.append(
            {"session_id": session_id, "user_id": user_id}
        )
        if session_id not in self.active:
            return False
        self.active.remove(session_id)
        return True


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
    policy: FakePolicy
    live_sessions: FakeLiveSessions


def build_harness() -> Harness:
    app = FastAPI()
    app.include_router(sports_playback.router, prefix="/api/v1")

    sports = FakeSports()
    playback = FakePlayback()
    capabilities = FakeCapabilities()
    policy = FakePolicy()
    live_sessions = FakeLiveSessions()

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
    app.dependency_overrides[
        sports_playback.get_live_session_policy_store
    ] = lambda: policy
    app.dependency_overrides[
        sports_playback.get_live_session_registry
    ] = lambda: live_sessions

    return Harness(
        client=TestClient(app),
        sports=sports,
        playback=playback,
        capabilities=capabilities,
        policy=policy,
        live_sessions=live_sessions,
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
    assert harness.policy.calls == [USER.user_id]
    assert harness.live_sessions.admit_calls == [
        {
            "user_id": USER.user_id,
            "target_id": "sports-event-001",
            "limit": 5,
        }
    ]
    assert response.headers["x-atlas-live-session-id"] == "live-session-test"
    assert response.headers["x-atlas-live-session-ttl"] == "90"


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



def test_watch_live_limit_reached_is_409_without_capability() -> None:
    harness = build_harness()
    harness.live_sessions.block = True

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Live session limit reached."
    assert harness.capabilities.calls == []


def test_watch_live_heartbeat_is_scoped_to_authenticated_user() -> None:
    harness = build_harness()

    response = harness.client.post(
        "/api/v1/sports/live/sessions/live-session-test/heartbeat"
    )

    assert response.status_code == 200
    assert response.json() == {
        "session_id": "live-session-test",
        "active": True,
        "ttl_seconds": 90,
    }
    assert harness.live_sessions.heartbeat_calls == [
        {
            "session_id": "live-session-test",
            "user_id": USER.user_id,
        }
    ]


def test_watch_live_release_is_scoped_to_authenticated_user() -> None:
    harness = build_harness()

    response = harness.client.delete(
        "/api/v1/sports/live/sessions/live-session-test"
    )

    assert response.status_code == 204
    assert harness.live_sessions.release_calls == [
        {
            "session_id": "live-session-test",
            "user_id": USER.user_id,
        }
    ]


def test_watch_live_missing_heartbeat_session_is_404() -> None:
    harness = build_harness()

    response = harness.client.post(
        "/api/v1/sports/live/sessions/missing/heartbeat"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Live session was not found."
