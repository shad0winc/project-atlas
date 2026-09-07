from pathlib import Path

import pytest

from atlas.sports_session_registry import (
    SportsSessionLimitExceeded,
    SportsSessionNotFound,
    SportsSessionRegistry,
    SportsSessionStateError,
)


class Clock:
    def __init__(self) -> None:
        self.value = 1000.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class SessionIds:
    def __init__(self) -> None:
        self.value = 0

    def __call__(self) -> str:
        self.value += 1
        return f"sports-session-{self.value}"


def registry(
    path: Path,
    *,
    clock: Clock,
    ids: SessionIds,
) -> SportsSessionRegistry:
    return SportsSessionRegistry(
        path,
        ttl_seconds=90,
        clock=clock,
        session_id_factory=ids,
    )


def test_admits_up_to_user_limit(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()

    store = registry(
        tmp_path / "sessions.json",
        clock=clock,
        ids=ids,
    )

    first = store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=2,
    )

    second = store.admit(
        user_id="usr-one",
        target_id="game-two",
        limit=2,
    )

    assert first.session_id == "sports-session-1"
    assert second.session_id == "sports-session-2"
    assert store.active_count_for_user(
        "usr-one"
    ) == 2


def test_user_limit_is_enforced_across_instances(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()
    path = tmp_path / "sessions.json"

    first = registry(
        path,
        clock=clock,
        ids=ids,
    )

    second = registry(
        path,
        clock=clock,
        ids=ids,
    )

    first.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=1,
    )

    with pytest.raises(
        SportsSessionLimitExceeded,
        match="Sports session limit reached",
    ):
        second.admit(
            user_id="usr-one",
            target_id="game-two",
            limit=1,
        )


def test_different_users_do_not_share_limit(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()

    store = registry(
        tmp_path / "sessions.json",
        clock=clock,
        ids=ids,
    )

    store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=1,
    )

    store.admit(
        user_id="usr-two",
        target_id="game-two",
        limit=1,
    )

    assert store.active_count_for_user(
        "usr-one"
    ) == 1

    assert store.active_count_for_user(
        "usr-two"
    ) == 1


def test_release_restores_user_slot(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()

    store = registry(
        tmp_path / "sessions.json",
        clock=clock,
        ids=ids,
    )

    session = store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=1,
    )

    assert store.release(
        session_id=session.session_id,
        user_id="usr-one",
    )

    replacement = store.admit(
        user_id="usr-one",
        target_id="game-two",
        limit=1,
    )

    assert replacement.target_id == "game-two"


def test_release_is_scoped_to_owner(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()

    store = registry(
        tmp_path / "sessions.json",
        clock=clock,
        ids=ids,
    )

    session = store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=1,
    )

    assert (
        store.release(
            session_id=session.session_id,
            user_id="usr-two",
        )
        is False
    )

    assert store.active_count_for_user(
        "usr-one"
    ) == 1


def test_heartbeat_refreshes_owned_session(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()

    store = registry(
        tmp_path / "sessions.json",
        clock=clock,
        ids=ids,
    )

    session = store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=1,
    )

    clock.advance(60)

    refreshed = store.heartbeat(
        session_id=session.session_id,
        user_id="usr-one",
    )

    assert refreshed.last_seen_at == 1060.0

    clock.advance(60)

    assert store.active_count_for_user(
        "usr-one"
    ) == 1


def test_heartbeat_is_scoped_to_owner(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()

    store = registry(
        tmp_path / "sessions.json",
        clock=clock,
        ids=ids,
    )

    session = store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=1,
    )

    with pytest.raises(
        SportsSessionNotFound
    ):
        store.heartbeat(
            session_id=session.session_id,
            user_id="usr-two",
        )


def test_ttl_expiry_restores_user_slot(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()

    store = registry(
        tmp_path / "sessions.json",
        clock=clock,
        ids=ids,
    )

    store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=1,
    )

    clock.advance(90)

    replacement = store.admit(
        user_id="usr-one",
        target_id="game-two",
        limit=1,
    )

    assert replacement.target_id == "game-two"


def test_snapshot_is_safe_and_relative(
    tmp_path: Path,
) -> None:
    clock = Clock()
    ids = SessionIds()

    store = registry(
        tmp_path / "sessions.json",
        clock=clock,
        ids=ids,
    )

    session = store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=2,
    )

    clock.advance(12)

    snapshots = store.snapshot_active()

    assert len(snapshots) == 1

    snapshot = snapshots[0]

    assert snapshot.session_id == session.session_id
    assert snapshot.user_id == "usr-one"
    assert snapshot.target_id == "game-one"
    assert snapshot.age_seconds == 12
    assert snapshot.heartbeat_age_seconds == 12


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        0,
        -1,
        1.5,
        "2",
        None,
    ],
)
def test_rejects_invalid_limit(
    tmp_path: Path,
    value,
) -> None:
    store = SportsSessionRegistry(
        tmp_path / "sessions.json"
    )

    with pytest.raises(ValueError):
        store.admit(
            user_id="usr-one",
            target_id="game-one",
            limit=value,
        )


def test_state_file_is_mode_0600(
    tmp_path: Path,
) -> None:
    store = SportsSessionRegistry(
        tmp_path / "sessions.json"
    )

    store.admit(
        user_id="usr-one",
        target_id="game-one",
        limit=1,
    )

    assert (
        store.path.stat().st_mode
        & 0o777
    ) == 0o600


def test_invalid_state_fails_closed(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sessions.json"

    path.write_text(
        '{"version":1,"sessions":{"bad":{}}}\n',
        encoding="utf-8",
    )

    store = SportsSessionRegistry(path)

    with pytest.raises(
        SportsSessionStateError
    ):
        store.snapshot_active()
