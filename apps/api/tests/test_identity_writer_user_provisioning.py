"""Private identity-writer Atlas/Jellyfin provisioning contracts."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from atlas_api.services.user_provisioning import (
    UserProvisioningCompensationError,
    UserProvisioningConflictError,
    UserProvisioningError,
)


TOKEN = "identity-writer-provisioning-token"


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

    module = importlib.import_module(
        "atlas_api.identity_writer"
    )
    module = importlib.reload(module)

    return module


def _client(module) -> TestClient:
    return TestClient(module.app)


def _auth() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {TOKEN}",
    }


def _payload() -> dict[str, Any]:
    return {
        "username": "michael",
        "email": "michael@example.com",
        "password": "initial-password",
        "roles": ["user"],
        "display_name": "Michael",
        "first_name": "Michael",
        "last_name": "Atlas",
    }


class FakeProvisioningService:
    def __init__(
        self,
        *,
        result: dict[str, Any] | None = None,
        error: Exception | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def provision_user(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.calls.append(dict(kwargs))

        if self.error is not None:
            raise self.error

        assert self.result is not None
        return dict(self.result)


def _result() -> dict[str, Any]:
    return {
        "user_id": "atlas-user-1",
        "username": "michael",
        "display_name": "Michael",
        "first_name": "Michael",
        "last_name": "Atlas",
        "email": "michael@example.com",
        "roles": ("user",),
        "status": "active",
        "jellyfin_user_id": "jellyfin-user-1",
    }


def test_create_requires_private_writer_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    response = _client(module).post(
        "/internal/v1/users",
        json=_payload(),
    )

    assert response.status_code == 401


def test_create_rejects_invalid_private_writer_token(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    response = _client(module).post(
        "/internal/v1/users",
        headers={
            "Authorization": "Bearer wrong-token",
        },
        json=_payload(),
    )

    assert response.status_code == 401


def test_create_delegates_to_provisioning_service_and_sanitizes_response(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    fake = FakeProvisioningService(
        result=_result(),
    )

    monkeypatch.setattr(
        module,
        "_user_provisioning_service",
        lambda: fake,
    )

    response = _client(module).post(
        "/internal/v1/users",
        headers=_auth(),
        json=_payload(),
    )

    assert response.status_code == 201

    assert fake.calls == [
        {
            "username": "michael",
            "email": "michael@example.com",
            "password": "initial-password",
            "roles": ["user"],
            "display_name": "Michael",
            "first_name": "Michael",
            "last_name": "Atlas",
        }
    ]

    body = response.json()

    assert body == {
        "user_id": "atlas-user-1",
        "username": "michael",
        "display_name": "Michael",
        "first_name": "Michael",
        "last_name": "Atlas",
        "email": "michael@example.com",
        "roles": ["user"],
        "status": "active",
        "jellyfin_user_id": "jellyfin-user-1",
    }

    assert "password" not in body
    assert "initial-password" not in response.text


def test_create_conflict_maps_to_409(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    fake = FakeProvisioningService(
        error=UserProvisioningConflictError(
            "Email already exists.",
            status_code=409,
        )
    )

    monkeypatch.setattr(
        module,
        "_user_provisioning_service",
        lambda: fake,
    )

    response = _client(module).post(
        "/internal/v1/users",
        headers=_auth(),
        json=_payload(),
    )

    assert response.status_code == 409
    assert response.json() == {
        "detail": "Email already exists.",
    }


def test_create_provisioning_failure_preserves_safe_status(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    fake = FakeProvisioningService(
        error=UserProvisioningError(
            "Jellyfin user creation failed.",
            status_code=502,
        )
    )

    monkeypatch.setattr(
        module,
        "_user_provisioning_service",
        lambda: fake,
    )

    response = _client(module).post(
        "/internal/v1/users",
        headers=_auth(),
        json=_payload(),
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Jellyfin user creation failed.",
    }

    assert "initial-password" not in response.text


def test_compensation_failure_hides_orphan_identifier(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    fake = FakeProvisioningService(
        error=UserProvisioningCompensationError(
            "rollback failed",
            jellyfin_user_id="secret-orphan-id",
        )
    )

    monkeypatch.setattr(
        module,
        "_user_provisioning_service",
        lambda: fake,
    )

    response = _client(module).post(
        "/internal/v1/users",
        headers=_auth(),
        json=_payload(),
    )

    assert response.status_code == 500

    assert response.json() == {
        "detail": (
            "User provisioning failed and requires "
            "administrator recovery."
        )
    }

    assert "secret-orphan-id" not in response.text
    assert "initial-password" not in response.text


@pytest.mark.parametrize(
    "field",
    [
        "email",
        "password",
        "username",
        "roles",
    ],
)
def test_create_requires_provisioning_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    field: str,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    payload = _payload()
    payload.pop(field)

    response = _client(module).post(
        "/internal/v1/users",
        headers=_auth(),
        json=payload,
    )

    assert response.status_code == 422


def test_create_rejects_unknown_request_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_writer(
        monkeypatch,
        tmp_path,
    )

    payload = _payload()
    payload["admin"] = True

    response = _client(module).post(
        "/internal/v1/users",
        headers=_auth(),
        json=payload,
    )

    assert response.status_code == 422
