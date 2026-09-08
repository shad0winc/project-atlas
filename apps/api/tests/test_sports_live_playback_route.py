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
        self.live_source_calls = 0
        self.source_registry_calls = 0

    def list_live_sources(self):
        self.live_source_calls += 1
        return [
            {
                "id": "event-001",
                "name": "Atlas Test Channel",
                "provider": "thesportsdb",
                "provider_event_id": "event-001",
                "standalone": False,
                "atlas_channel_id": "sports-event-001",
                "resource_source_ids": [
                    "primary-account",
                    "secondary-account",
                ],
            }
        ]

    def get_source_registry(self):
        self.source_registry_calls += 1
        return {
            "providers": [],
            "sources": [
                {
                    "source_id": "primary-account",
                    "kind": "licensed_subscription",
                    "enabled": True,
                    "priority": 100,
                    "max_connections": 1,
                },
                {
                    "source_id": "secondary-account",
                    "kind": "official_free",
                    "enabled": True,
                    "priority": 50,
                    "max_connections": 2,
                },
            ],
        }

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
    def __init__(
        self,
        session_id: str,
        resource_lease_id: str | None = None,
    ) -> None:
        self.session_id = session_id
        self.resource_lease_id = (
            resource_lease_id
        )


class _FakeResourceLease:
    def __init__(
        self,
        lease_id: str = "resource-lease-test",
        source_id: str = "primary-account",
    ) -> None:
        self.lease_id = lease_id
        self.source_id = source_id


class FakeResourcePool:
    ttl_seconds = 90

    def __init__(self) -> None:
        self.acquire_calls: list[
            dict[str, object]
        ] = []
        self.release_calls: list[
            dict[str, str]
        ] = []
        self.heartbeat_calls: list[
            dict[str, str]
        ] = []
        self.acquire_error: Exception | None = None
        self.heartbeat_error: Exception | None = None
        self.release_error: Exception | None = None
        self.release_result = True

    def acquire(self, **kwargs):
        self.acquire_calls.append(
            dict(kwargs)
        )

        if self.acquire_error is not None:
            raise self.acquire_error

        return _FakeResourceLease()

    def heartbeat(
        self,
        *,
        lease_id: str,
        user_id: str,
    ):
        self.heartbeat_calls.append(
            {
                "lease_id": lease_id,
                "user_id": user_id,
            }
        )

        if self.heartbeat_error is not None:
            raise self.heartbeat_error

        return _FakeResourceLease(
            lease_id=lease_id
        )

    def release(
        self,
        *,
        lease_id: str,
        user_id: str,
    ) -> bool:
        self.release_calls.append(
            {
                "lease_id": lease_id,
                "user_id": user_id,
            }
        )

        if self.release_error is not None:
            raise self.release_error

        return self.release_result


class FakeLiveSessions:
    ttl_seconds = 90

    def __init__(self) -> None:
        self.admit_calls: list[dict[str, object]] = []
        self.heartbeat_calls: list[dict[str, str]] = []
        self.release_calls: list[dict[str, str]] = []
        self.release_record_calls: list[
            dict[str, str]
        ] = []
        self.block = False
        self.active = {"live-session-test"}
        self.resource_lease_id: str | None = None

    def admit(self, **kwargs):
        from atlas.sports_session_registry import SportsSessionLimitExceeded

        self.admit_calls.append(dict(kwargs))
        if self.block:
            raise SportsSessionLimitExceeded("Sports session limit reached.")
        self.active.add("live-session-test")
        return _FakeLiveRecord(
            "live-session-test",
            self.admit_calls[-1].get(
                "resource_lease_id"
            ),
        )

    def heartbeat(self, *, session_id: str, user_id: str):
        from atlas.sports_session_registry import SportsSessionNotFound, SportsSessionRecord

        self.heartbeat_calls.append(
            {"session_id": session_id, "user_id": user_id}
        )
        if session_id not in self.active:
            raise SportsSessionNotFound("missing")
        return SportsSessionRecord(
            session_id=session_id,
            user_id=user_id,
            target_id="sports-event-001",
            created_at=1.0,
            last_seen_at=2.0,
            resource_lease_id=self.resource_lease_id,
        )

    def release_record(
        self,
        *,
        session_id: str,
        user_id: str,
    ):
        from atlas.sports_session_registry import SportsSessionRecord

        self.release_record_calls.append(
            {
                "session_id": session_id,
                "user_id": user_id,
            }
        )

        if session_id not in self.active:
            return None

        self.active.remove(session_id)

        return SportsSessionRecord(
            session_id=session_id,
            user_id=user_id,
            target_id="sports-event-001",
            created_at=1.0,
            last_seen_at=2.0,
            resource_lease_id=self.resource_lease_id,
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
    resource_pool: FakeResourcePool


def build_harness() -> Harness:
    app = FastAPI()
    app.include_router(sports_playback.router, prefix="/api/v1")

    sports = FakeSports()
    playback = FakePlayback()
    capabilities = FakeCapabilities()
    policy = FakePolicy()
    live_sessions = FakeLiveSessions()
    resource_pool = FakeResourcePool()

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
        sports_playback.get_sports_session_registry
    ] = lambda: live_sessions
    app.dependency_overrides[
        sports_playback.get_sports_resource_pool
    ] = lambda: resource_pool

    return Harness(
        client=TestClient(app),
        sports=sports,
        playback=playback,
        capabilities=capabilities,
        policy=policy,
        live_sessions=live_sessions,
        resource_pool=resource_pool,
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
    assert harness.sports.live_source_calls == 1
    assert harness.sports.source_registry_calls == 1

    assert harness.resource_pool.acquire_calls == [
        {
            "user_id": USER.user_id,
            "target_id": "sports-event-001",
            "candidate_source_ids": (
                "primary-account",
                "secondary-account",
            ),
            "capacities": {
                "primary-account": 1,
                "secondary-account": 2,
            },
            "user_limit": 5,
        }
    ]

    assert harness.live_sessions.admit_calls == [
        {
            "user_id": USER.user_id,
            "target_id": "sports-event-001",
            "limit": 5,
            "resource_lease_id": (
                "resource-lease-test"
            ),
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
    assert harness.live_sessions.release_calls == [
        {
            "session_id": "live-session-test",
            "user_id": USER.user_id,
        }
    ]


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
    assert harness.playback.calls == []
    assert harness.capabilities.calls == []


def test_watch_live_capability_failure_releases_shared_session() -> None:
    harness = build_harness()

    def fail_capability(**kwargs):
        raise RuntimeError("capability failed")

    harness.capabilities.create_bootstrap = fail_capability  # type: ignore[method-assign]

    try:
        harness.client.get(
            "/api/v1/sports/live/sports-event-001/session"
        )
    except RuntimeError:
        pass

    assert harness.live_sessions.release_calls == [
        {
            "session_id": "live-session-test",
            "user_id": USER.user_id,
        }
    ]


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
    assert harness.live_sessions.release_record_calls == [
        {
            "session_id": "live-session-test",
            "user_id": USER.user_id,
        }
    ]
    assert harness.resource_pool.release_calls == []


def test_watch_live_missing_heartbeat_session_is_404() -> None:
    harness = build_harness()

    response = harness.client.post(
        "/api/v1/sports/live/sessions/missing/heartbeat"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "Live session was not found."


def test_watch_live_ranks_only_explicit_enabled_resource_accounts() -> None:
    harness = build_harness()

    harness.sports.list_live_sources = lambda: [
        {
            "id": "event-001",
            "name": "Atlas Test Channel",
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
            "standalone": False,
            "atlas_channel_id": "sports-event-001",
            "resource_source_ids": [
                "community",
                "disabled",
                "official",
                "licensed-late",
                "licensed-first",
                "unrelated-missing",
            ],
        }
    ]

    harness.sports.get_source_registry = lambda: {
        "providers": [],
        "sources": [
            {
                "source_id": "community",
                "kind": "community_public",
                "enabled": True,
                "priority": 1,
                "max_connections": 4,
            },
            {
                "source_id": "disabled",
                "kind": "licensed_subscription",
                "enabled": False,
                "priority": 0,
                "max_connections": 8,
            },
            {
                "source_id": "official",
                "kind": "official_free",
                "enabled": True,
                "priority": 1,
                "max_connections": 3,
            },
            {
                "source_id": "licensed-late",
                "kind": "licensed_subscription",
                "enabled": True,
                "priority": 200,
                "max_connections": 2,
            },
            {
                "source_id": "licensed-first",
                "kind": "licensed_subscription",
                "enabled": True,
                "priority": 100,
                "max_connections": 1,
            },
            {
                "source_id": "not-associated",
                "kind": "licensed_subscription",
                "enabled": True,
                "priority": 0,
                "max_connections": 99,
            },
        ],
    }

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 200

    call = harness.resource_pool.acquire_calls[0]

    assert call["candidate_source_ids"] == (
        "licensed-first",
        "licensed-late",
        "official",
        "community",
    )

    assert call["capacities"] == {
        "licensed-first": 1,
        "licensed-late": 2,
        "official": 3,
        "community": 4,
    }


def test_watch_live_missing_resource_association_fails_closed() -> None:
    harness = build_harness()

    harness.sports.list_live_sources = lambda: [
        {
            "id": "event-001",
            "name": "Atlas Test Channel",
            "provider": "thesportsdb",
            "provider_event_id": "event-001",
            "standalone": False,
            "atlas_channel_id": "sports-event-001",
            "resource_source_ids": [],
        }
    ]

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Sports resource admission is unavailable."
    )
    assert harness.resource_pool.acquire_calls == []
    assert harness.live_sessions.admit_calls == []
    assert harness.playback.calls == []


def test_watch_live_all_associated_sources_unavailable_is_409() -> None:
    harness = build_harness()

    harness.sports.get_source_registry = lambda: {
        "providers": [],
        "sources": [
            {
                "source_id": "primary-account",
                "kind": "licensed_subscription",
                "enabled": False,
                "priority": 100,
                "max_connections": 1,
            },
            {
                "source_id": "secondary-account",
                "kind": "official_free",
                "enabled": False,
                "priority": 50,
                "max_connections": 2,
            },
        ],
    }

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Sports upstream capacity is unavailable."
    )
    assert harness.resource_pool.acquire_calls == []
    assert harness.live_sessions.admit_calls == []


def test_watch_live_resource_capacity_exhausted_is_409() -> None:
    from atlas.sports_resource_pool import (
        SportsResourcePoolExhausted,
    )

    harness = build_harness()
    harness.resource_pool.acquire_error = (
        SportsResourcePoolExhausted(
            "private capacity detail"
        )
    )

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Sports upstream capacity is unavailable."
    )
    assert "private" not in response.text.lower()
    assert harness.live_sessions.admit_calls == []


def test_watch_live_resource_user_limit_is_existing_409_contract() -> None:
    from atlas.sports_resource_pool import (
        SportsResourceUserLimitExceeded,
    )

    harness = build_harness()
    harness.resource_pool.acquire_error = (
        SportsResourceUserLimitExceeded(
            "private user detail"
        )
    )

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Live session limit reached."
    )
    assert "private" not in response.text.lower()
    assert harness.live_sessions.admit_calls == []


def test_watch_live_session_admission_failure_releases_resource_lease() -> None:
    harness = build_harness()
    harness.live_sessions.block = True

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 409

    assert harness.resource_pool.release_calls == [
        {
            "lease_id": "resource-lease-test",
            "user_id": USER.user_id,
        }
    ]


def test_watch_live_playback_failure_releases_resource_lease() -> None:
    harness = build_harness()

    def unavailable(**kwargs):
        raise PlaybackNotFoundError(
            "not live"
        )

    harness.playback.resolve_live_session = unavailable

    response = harness.client.get(
        "/api/v1/sports/live/sports-event-001/session"
    )

    assert response.status_code == 404

    assert harness.resource_pool.release_calls == [
        {
            "lease_id": "resource-lease-test",
            "user_id": USER.user_id,
        }
    ]


def test_watch_live_capability_failure_releases_resource_lease() -> None:
    harness = build_harness()

    def fail_capability(**kwargs):
        raise RuntimeError(
            "capability failed"
        )

    harness.capabilities.create_bootstrap = (
        fail_capability
    )

    try:
        harness.client.get(
            "/api/v1/sports/live/sports-event-001/session"
        )
    except RuntimeError:
        pass

    assert harness.resource_pool.release_calls == [
        {
            "lease_id": "resource-lease-test",
            "user_id": USER.user_id,
        }
    ]


def test_watch_live_linked_heartbeat_refreshes_resource_lease() -> None:
    harness = build_harness()
    harness.live_sessions.resource_lease_id = (
        "resource-lease-test"
    )

    response = harness.client.post(
        "/api/v1/sports/live/sessions/live-session-test/heartbeat"
    )

    assert response.status_code == 200

    assert harness.resource_pool.heartbeat_calls == [
        {
            "lease_id": "resource-lease-test",
            "user_id": USER.user_id,
        }
    ]


def test_watch_live_unlinked_heartbeat_preserves_legacy_compatibility() -> None:
    harness = build_harness()

    response = harness.client.post(
        "/api/v1/sports/live/sessions/live-session-test/heartbeat"
    )

    assert response.status_code == 200
    assert harness.resource_pool.heartbeat_calls == []


def test_watch_live_missing_resource_lease_fails_closed_and_removes_session() -> None:
    from atlas.sports_resource_pool import (
        SportsResourceLeaseNotFound,
    )

    harness = build_harness()
    harness.live_sessions.resource_lease_id = (
        "resource-lease-test"
    )
    harness.resource_pool.heartbeat_error = (
        SportsResourceLeaseNotFound(
            "private missing lease"
        )
    )

    response = harness.client.post(
        "/api/v1/sports/live/sessions/live-session-test/heartbeat"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Live session resource lease is unavailable."
    )
    assert "private" not in response.text.lower()

    assert harness.live_sessions.release_calls == [
        {
            "session_id": "live-session-test",
            "user_id": USER.user_id,
        }
    ]

    assert (
        "live-session-test"
        not in harness.live_sessions.active
    )


def test_watch_live_resource_heartbeat_state_failure_fails_closed() -> None:
    from atlas.sports_resource_pool import (
        SportsResourcePoolStateError,
    )

    harness = build_harness()
    harness.live_sessions.resource_lease_id = (
        "resource-lease-test"
    )
    harness.resource_pool.heartbeat_error = (
        SportsResourcePoolStateError(
            "private pool state"
        )
    )

    response = harness.client.post(
        "/api/v1/sports/live/sessions/live-session-test/heartbeat"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Live session resource lease is unavailable."
    )
    assert "private" not in response.text.lower()

    assert (
        "live-session-test"
        not in harness.live_sessions.active
    )


def test_watch_live_linked_release_releases_resource_lease() -> None:
    harness = build_harness()
    harness.live_sessions.resource_lease_id = (
        "resource-lease-test"
    )

    response = harness.client.delete(
        "/api/v1/sports/live/sessions/live-session-test"
    )

    assert response.status_code == 204

    assert harness.live_sessions.release_record_calls == [
        {
            "session_id": "live-session-test",
            "user_id": USER.user_id,
        }
    ]

    assert harness.resource_pool.release_calls == [
        {
            "lease_id": "resource-lease-test",
            "user_id": USER.user_id,
        }
    ]


def test_watch_live_release_missing_resource_lease_still_completes() -> None:
    harness = build_harness()
    harness.live_sessions.resource_lease_id = (
        "resource-lease-test"
    )
    harness.resource_pool.release_result = False

    response = harness.client.delete(
        "/api/v1/sports/live/sessions/live-session-test"
    )

    assert response.status_code == 204


def test_watch_live_unlinked_release_preserves_legacy_compatibility() -> None:
    harness = build_harness()

    response = harness.client.delete(
        "/api/v1/sports/live/sessions/live-session-test"
    )

    assert response.status_code == 204
    assert harness.resource_pool.release_calls == []


def test_watch_live_resource_release_state_failure_is_503() -> None:
    from atlas.sports_resource_pool import (
        SportsResourcePoolStateError,
    )

    harness = build_harness()
    harness.live_sessions.resource_lease_id = (
        "resource-lease-test"
    )
    harness.resource_pool.release_error = (
        SportsResourcePoolStateError(
            "private pool state"
        )
    )

    response = harness.client.delete(
        "/api/v1/sports/live/sessions/live-session-test"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == (
        "Live session resource release is unavailable."
    )
    assert "private" not in response.text.lower()

    assert (
        "live-session-test"
        not in harness.live_sessions.active
    )


def test_watch_live_missing_release_session_remains_404_without_pool_call() -> None:
    harness = build_harness()
    harness.live_sessions.active.clear()
    harness.live_sessions.resource_lease_id = (
        "resource-lease-test"
    )

    response = harness.client.delete(
        "/api/v1/sports/live/sessions/live-session-test"
    )

    assert response.status_code == 404
    assert response.json()["detail"] == (
        "Live session was not found."
    )
    assert harness.resource_pool.release_calls == []
