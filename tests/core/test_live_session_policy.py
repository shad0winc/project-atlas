from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.live_session_policy import (
    DEFAULT_LIVE_SESSION_LIMIT,
    LiveSessionPolicyError,
    LiveSessionPolicyStore,
    default_live_session_policy_store,
)


def test_policy_initializes_default_five_and_persists_overrides(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-session-policy.json"
    store = LiveSessionPolicyStore(path)

    store.initialize()

    assert store.snapshot() == {
        "version": 1,
        "default_limit": 5,
        "overrides": {},
    }
    assert store.effective_limit("usr-a") == 5

    store.set_override("usr-a", 2)
    assert store.effective_limit("usr-a") == 2
    assert store.effective_limit("usr-b") == 5

    store.set_default_limit(7)
    assert store.effective_limit("usr-a") == 2
    assert store.effective_limit("usr-b") == 7

    assert store.clear_override("usr-a") is True
    assert store.effective_limit("usr-a") == 7
    assert store.clear_override("usr-a") is False

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {
        "version": 1,
        "default_limit": 7,
        "overrides": {},
    }
    assert DEFAULT_LIVE_SESSION_LIMIT == 5


def test_policy_rejects_invalid_or_corrupt_state(tmp_path: Path) -> None:
    path = tmp_path / "live-session-policy.json"
    store = LiveSessionPolicyStore(path)
    store.initialize()

    with pytest.raises(LiveSessionPolicyError):
        store.set_default_limit(0)

    with pytest.raises(LiveSessionPolicyError):
        store.set_override("usr-a", -1)

    path.write_text(
        '{"version":1,"default_limit":5,"overrides":{"usr-a":0}}',
        encoding="utf-8",
    )

    with pytest.raises(LiveSessionPolicyError):
        store.snapshot()


def test_default_policy_lives_inside_existing_users_recovery_surface(
    monkeypatch,
    tmp_path: Path,
) -> None:
    users = tmp_path / "users"
    monkeypatch.setenv("ATLAS_USERS_DIR", str(users))
    monkeypatch.delenv("ATLAS_LIVE_SESSION_POLICY_PATH", raising=False)

    store = default_live_session_policy_store()

    assert store.path == users / "live-session-policy.json"


def test_missing_policy_is_read_only_default_without_creating_file(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-session-policy.json"
    store = LiveSessionPolicyStore(path)

    assert not path.exists()
    assert store.snapshot() == {
        "version": 1,
        "default_limit": 5,
        "overrides": {},
    }
    assert store.effective_limit("usr-a") == 5
    assert not path.exists()


def test_mutation_can_create_policy_from_implicit_default(
    tmp_path: Path,
) -> None:
    path = tmp_path / "live-session-policy.json"
    store = LiveSessionPolicyStore(path)

    store.set_override("usr-a", 2)

    assert path.is_file()
    assert store.snapshot() == {
        "version": 1,
        "default_limit": 5,
        "overrides": {"usr-a": 2},
    }
