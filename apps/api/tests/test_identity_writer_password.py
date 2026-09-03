"""Private identity-writer password mutation contracts."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from atlas.user_profiles import UserProfileStore


TOKEN = "identity-writer-password-token"
JELLYFIN_ID = "0123456789abcdef0123456789abcdef"


def _load_writer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setenv(
        "ATLAS_USERS_DIR",
        str(tmp_path / "users"),
    )
    monkeypatch.setenv(
        "ATLAS_IDENTITY_DIR",
        str(tmp_path / "identity"),
    )
    monkeypatch.setenv(
        "ATLAS_IDENTITY_WRITER_TOKEN",
        TOKEN,
    )
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_URL",
        "http://jellyfin.test",
    )
    monkeypatch.setenv(
        "ATLAS_JELLYFIN_API_KEY",
        "test-api-key",
    )

    module = importlib.import_module(
        "atlas_api.identity_writer"
    )
    module = importlib.reload(module)

    return module


def _auth() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
    }


class RecordingJellyfin:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def set_password(
        self,
        user_id: str,
        password: str,
    ) -> None:
        self.calls.append(
            (user_id, password)
        )


def test_password_route_resolves_linked_jellyfin_id(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    profiles = UserProfileStore(
        tmp_path / "users"
    )

    target = profiles.create_user(
        "target",
        display_name="Target User",
        email="target@example.test",
        jellyfin_user_id=JELLYFIN_ID,
    )

    jellyfin = RecordingJellyfin()

    monkeypatch.setattr(
        module,
        "_jellyfin_identity_client",
        lambda: jellyfin,
    )

    secret = "private-password-value"

    response = TestClient(module.app).post(
        (
            "/internal/v1/users/"
            f"{target['user_id']}/password"
        ),
        headers=_auth(),
        json={
            "new_password": secret,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "password-set",
    }

    assert jellyfin.calls == [
        (
            JELLYFIN_ID,
            secret,
        )
    ]

    assert secret not in response.text


def test_password_route_rejects_unlinked_user(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    profiles = UserProfileStore(
        tmp_path / "users"
    )

    target = profiles.create_user(
        "unlinked",
        display_name="Unlinked User",
        email="unlinked@example.test",
    )

    jellyfin = RecordingJellyfin()

    monkeypatch.setattr(
        module,
        "_jellyfin_identity_client",
        lambda: jellyfin,
    )

    response = TestClient(module.app).post(
        (
            "/internal/v1/users/"
            f"{target['user_id']}/password"
        ),
        headers=_auth(),
        json={
            "new_password": "must-not-be-forwarded",
        },
    )

    assert response.status_code == 409
    assert jellyfin.calls == []


def test_password_route_requires_service_authentication(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    response = TestClient(module.app).post(
        "/internal/v1/users/usr_missing/password",
        json={
            "new_password": "must-not-run",
        },
    )

    assert response.status_code == 401
