from __future__ import annotations

import pytest

from atlas_api.live_sessions import (
    LiveSessionLimitExceeded,
    LiveSessionNotFound,
    LiveSessionRegistry,
)


def test_per_user_limit_and_user_isolation() -> None:
    ids = iter(("a1", "a2", "a3", "b1"))
    registry = LiveSessionRegistry(
        ttl_seconds=90,
        clock=lambda: 1.0,
        session_id_factory=lambda: next(ids),
    )

    registry.admit(user_id="usr-a", target_id="same-event", limit=3)
    registry.admit(user_id="usr-a", target_id="same-event", limit=3)
    registry.admit(user_id="usr-a", target_id="same-event", limit=3)

    with pytest.raises(LiveSessionLimitExceeded):
        registry.admit(user_id="usr-a", target_id="same-event", limit=3)

    registry.admit(user_id="usr-b", target_id="same-event", limit=3)

    assert registry.active_count_for_user("usr-a") == 3
    assert registry.active_count_for_user("usr-b") == 1


def test_lowered_limit_does_not_kill_existing_sessions() -> None:
    ids = iter(("s1", "s2", "s3"))
    registry = LiveSessionRegistry(
        ttl_seconds=90,
        clock=lambda: 1.0,
        session_id_factory=lambda: next(ids),
    )

    registry.admit(user_id="usr-a", target_id="event", limit=5)
    registry.admit(user_id="usr-a", target_id="event", limit=5)

    assert registry.active_count_for_user("usr-a") == 2

    with pytest.raises(LiveSessionLimitExceeded):
        registry.admit(user_id="usr-a", target_id="event", limit=2)

    assert registry.active_count_for_user("usr-a") == 2


def test_heartbeat_extends_lifetime_and_stale_sessions_expire() -> None:
    now = [0.0]
    registry = LiveSessionRegistry(
        ttl_seconds=90,
        clock=lambda: now[0],
        session_id_factory=lambda: "session-1",
    )

    registry.admit(user_id="usr-a", target_id="event", limit=1)

    now[0] = 60.0
    registry.heartbeat(session_id="session-1", user_id="usr-a")

    now[0] = 120.0
    assert registry.active_count_for_user("usr-a") == 1

    now[0] = 151.0
    assert registry.active_count_for_user("usr-a") == 0

    with pytest.raises(LiveSessionNotFound):
        registry.heartbeat(session_id="session-1", user_id="usr-a")


def test_session_ownership_prevents_cross_user_heartbeat_or_release() -> None:
    registry = LiveSessionRegistry(
        ttl_seconds=90,
        clock=lambda: 1.0,
        session_id_factory=lambda: "session-1",
    )

    registry.admit(user_id="usr-a", target_id="event", limit=5)

    with pytest.raises(LiveSessionNotFound):
        registry.heartbeat(session_id="session-1", user_id="usr-b")

    assert registry.release(session_id="session-1", user_id="usr-b") is False
    assert registry.active_count_for_user("usr-a") == 1

    assert registry.release(session_id="session-1", user_id="usr-a") is True
    assert registry.active_count_for_user("usr-a") == 0


def test_snapshot_active_returns_relative_safe_state_and_prunes_stale() -> None:
    now = [100.0]
    ids = iter(("session-b", "session-a"))
    registry = LiveSessionRegistry(
        ttl_seconds=90,
        clock=lambda: now[0],
        session_id_factory=lambda: next(ids),
    )

    registry.admit(user_id="usr-b", target_id="event-b", limit=5)
    now[0] = 110.0
    registry.admit(user_id="usr-a", target_id="event-a", limit=5)
    now[0] = 125.0
    registry.heartbeat(session_id="session-b", user_id="usr-b")
    now[0] = 140.0

    snapshot = registry.snapshot_active()

    assert [(item.user_id, item.session_id) for item in snapshot] == [
        ("usr-a", "session-a"),
        ("usr-b", "session-b"),
    ]

    first, second = snapshot
    assert first.target_id == "event-a"
    assert first.age_seconds == 30
    assert first.heartbeat_age_seconds == 30
    assert second.target_id == "event-b"
    assert second.age_seconds == 40
    assert second.heartbeat_age_seconds == 15

    assert not hasattr(first, "created_at")
    assert not hasattr(first, "last_seen_at")

    now[0] = 231.0
    assert registry.snapshot_active() == ()
