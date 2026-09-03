"""Security contracts for durable Atlas password-recovery state."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from atlas.identity import IdentityPaths
from atlas.password_recovery import (
    PasswordRecoveryError,
    PasswordRecoveryStore,
    hash_token,
)


def _store(
    tmp_path: Path,
    now: datetime,
) -> PasswordRecoveryStore:
    return PasswordRecoveryStore(
        IdentityPaths(tmp_path / "identity"),
        clock=lambda: now,
    )


def test_plaintext_token_is_not_persisted(
    tmp_path: Path,
) -> None:
    now = datetime(
        2026,
        9,
        3,
        12,
        0,
        tzinfo=timezone.utc,
    )
    store = _store(tmp_path, now)

    issue = store.create(user_id="user-1")

    persisted = (
        store.paths.password_recovery_registry.read_text()
        + issue.recovery["recovery_id"]
    )

    assert issue.token not in persisted
    assert issue.recovery["token_hash"] == hash_token(
        issue.token
    )


def test_new_issue_revokes_previous_user_token(
    tmp_path: Path,
) -> None:
    now = datetime(
        2026,
        9,
        3,
        12,
        0,
        tzinfo=timezone.utc,
    )
    store = _store(tmp_path, now)

    first = store.create(user_id="user-1")
    second = store.create(user_id="user-1")

    with pytest.raises(PasswordRecoveryError):
        store.verify_token(first.token)

    assert (
        store.verify_token(second.token)["recovery_id"]
        == second.recovery["recovery_id"]
    )


def test_completed_token_is_single_use(
    tmp_path: Path,
) -> None:
    now = datetime(
        2026,
        9,
        3,
        12,
        0,
        tzinfo=timezone.utc,
    )
    store = _store(tmp_path, now)

    issue = store.create(user_id="user-1")
    record = store.verify_token(issue.token)
    store.complete(record["recovery_id"])

    with pytest.raises(PasswordRecoveryError):
        store.verify_token(issue.token)


def test_expired_token_is_rejected(
    tmp_path: Path,
) -> None:
    current = [
        datetime(
            2026,
            9,
            3,
            12,
            0,
            tzinfo=timezone.utc,
        )
    ]

    store = PasswordRecoveryStore(
        IdentityPaths(tmp_path / "identity"),
        clock=lambda: current[0],
    )

    issue = store.create(
        user_id="user-1",
        expires_in=timedelta(minutes=5),
    )

    current[0] += timedelta(minutes=6)

    with pytest.raises(
        PasswordRecoveryError,
        match="expired",
    ):
        store.verify_token(issue.token)
