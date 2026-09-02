"""Behavioral contracts for the internal Atlas identity writer."""

from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


TOKEN = "identity-writer-contract-token"


def _load_writer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    users = tmp_path / "users"
    identity = tmp_path / "identity"

    monkeypatch.setenv(
        "ATLAS_USERS_DIR",
        str(users),
    )
    monkeypatch.setenv(
        "ATLAS_IDENTITY_DIR",
        str(identity),
    )
    monkeypatch.setenv(
        "ATLAS_IDENTITY_WRITER_TOKEN",
        TOKEN,
    )

    module = importlib.import_module(
        "atlas_api.identity_writer"
    )
    module = importlib.reload(module)

    return module, users, identity


def _client(module) -> TestClient:
    return TestClient(module.app)


def _auth() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
    }


def test_writer_health_does_not_require_service_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, _, _ = _load_writer(
        monkeypatch,
        tmp_path,
    )

    response = _client(module).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
    }


def test_writer_rejects_missing_service_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, _, _ = _load_writer(
        monkeypatch,
        tmp_path,
    )

    response = _client(module).patch(
        "/internal/v1/users/example",
        json={
            "status": "disabled",
        },
    )

    assert response.status_code == 401


def test_writer_rejects_invalid_service_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, _, _ = _load_writer(
        monkeypatch,
        tmp_path,
    )

    response = _client(module).patch(
        "/internal/v1/users/example",
        headers={
            "Authorization": "Bearer wrong-token",
        },
        json={
            "status": "disabled",
        },
    )

    assert response.status_code == 401


def test_writer_updates_existing_user(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, users, _ = _load_writer(
        monkeypatch,
        tmp_path,
    )

    from atlas.user_profiles import UserProfileStore

    store = UserProfileStore(users)
    profile = store.create_user(
        "writer-user",
    )

    response = _client(module).patch(
        f"/internal/v1/users/{profile['user_id']}",
        headers=_auth(),
        json={
            "status": "disabled",
        },
    )

    assert response.status_code == 200

    persisted = UserProfileStore(users).get_user(
        profile["user_id"]
    )

    assert persisted["status"] == "disabled"


def test_writer_creates_invitation_under_identity_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, users, identity = _load_writer(
        monkeypatch,
        tmp_path,
    )

    response = _client(module).post(
        "/internal/v1/invitations",
        headers=_auth(),
        json={
            "email": "invitee@example.test",
            "role": "user",
            "days": 7,
            "created_by": "administrator",
        },
    )

    assert response.status_code == 201

    result = response.json()

    assert result["token"]
    assert result["invitation"]["email"] == (
        "invitee@example.test"
    )

    assert (
        identity / "invitations"
    ).is_dir()

    assert not (
        users / "invitations"
    ).exists()


def test_writer_revokes_invitation(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, _, _ = _load_writer(
        monkeypatch,
        tmp_path,
    )

    client = _client(module)

    created = client.post(
        "/internal/v1/invitations",
        headers=_auth(),
        json={
            "email": "revoke@example.test",
            "role": "user",
            "days": 7,
            "created_by": "administrator",
        },
    )

    assert created.status_code == 201

    invite_id = created.json()["invitation"][
        "invite_id"
    ]

    revoked = client.post(
        (
            "/internal/v1/invitations/"
            f"{invite_id}/revoke"
        ),
        headers=_auth(),
        json={
            "revoked_by": "administrator",
        },
    )

    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"


def test_writer_does_not_publish_public_api_routes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module, _, _ = _load_writer(
        monkeypatch,
        tmp_path,
    )

    client = _client(module)

    for path in (
        "/api/v1/auth/login",
        "/api/v1/admin/users",
        "/api/v1/admin/invitations",
    ):
        assert client.get(path).status_code == 404


def test_writer_requires_token_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "ATLAS_IDENTITY_WRITER_TOKEN",
        raising=False,
    )

    module = importlib.import_module(
        "atlas_api.identity_writer"
    )

    with pytest.raises(
        RuntimeError,
        match="ATLAS_IDENTITY_WRITER_TOKEN",
    ):
        importlib.reload(module)

    os.environ.pop(
        "ATLAS_IDENTITY_WRITER_TOKEN",
        None,
    )
