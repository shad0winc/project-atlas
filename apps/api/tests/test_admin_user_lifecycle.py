"""PR107 administrator user-lifecycle contracts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from atlas.user_profiles import UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_current_user,
    get_identity_writer_client,
    get_security_audit_writer,
    get_user_profile_store,
)
from atlas_api.main import create_app


class RecordingWriter:
    def __init__(self) -> None:
        self.creates: list[dict[str, Any]] = []
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.passwords: list[tuple[str, str]] = []

    def create_user(self, **kwargs: Any) -> dict[str, Any]:
        self.creates.append(dict(kwargs))

        return {
            "user_id": "created-user",
            "username": kwargs["username"],
            "display_name": kwargs["display_name"],
            "first_name": kwargs.get("first_name"),
            "last_name": kwargs.get("last_name"),
            "email": str(kwargs["email"]).lower(),
            "discord_account": kwargs.get("discord_account"),
            "email_notifications_enabled": kwargs.get(
                "email_notifications_enabled",
                False,
            ),
            "discord_notifications_enabled": kwargs.get(
                "discord_notifications_enabled",
                False,
            ),
            "roles": list(kwargs["roles"]),
            "status": "active",
            "jellyfin_user_id": "jf-created",
        }

    def update_user(
        self,
        identifier: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        self.updates.append(
            (identifier, dict(updates))
        )

        return {
            "user_id": identifier,
            "username": "target",
            "display_name": updates.get(
                "display_name",
                "Target User",
            ),
            "first_name": updates.get("first_name"),
            "last_name": updates.get("last_name"),
            "email": updates.get(
                "email",
                "target@example.test",
            ),
            "discord_account": updates.get(
                "discord_account"
            ),
            "email_notifications_enabled": updates.get(
                "email_notifications_enabled",
                False,
            ),
            "discord_notifications_enabled": updates.get(
                "discord_notifications_enabled",
                False,
            ),
            "roles": ["member"],
            "status": "active",
            "jellyfin_user_id": "jf-target",
        }

    def set_user_password(
        self,
        identifier: str,
        new_password: str,
    ) -> dict[str, str]:
        self.passwords.append(
            (identifier, new_password)
        )

        return {
            "status": "password-set",
        }


class RecordingAudit:
    def __init__(self) -> None:
        self.events: list[
            tuple[str, dict[str, Any] | None]
        ] = []

    def publish(
        self,
        event_name: str,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self.events.append(
            (
                event_name,
                dict(payload)
                if payload is not None
                else None,
            )
        )


def _authenticated(
    profile: dict[str, Any],
) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=str(profile["user_id"]),
        username=str(profile["username"]),
        display_name=str(profile["display_name"]),
        roles=tuple(profile["roles"]),
        provider="atlas",
        metadata={},
    )


def _fixture(
    tmp_path: Path,
) -> tuple[
    TestClient,
    UserProfileStore,
    RecordingWriter,
    RecordingAudit,
    dict[str, Any],
]:
    profiles = UserProfileStore(
        tmp_path / "users"
    )

    admin = profiles.create_user(
        "atlas-admin",
        display_name="Atlas Admin",
        email="admin@example.test",
        roles=("global_admin",),
    )

    writer = RecordingWriter()
    audit = RecordingAudit()

    app = create_app()

    app.dependency_overrides[
        get_user_profile_store
    ] = lambda: profiles

    app.dependency_overrides[
        get_current_user
    ] = lambda: _authenticated(admin)

    app.dependency_overrides[
        get_identity_writer_client
    ] = lambda: writer

    app.dependency_overrides[
        get_security_audit_writer
    ] = lambda: audit

    return (
        TestClient(app),
        profiles,
        writer,
        audit,
        admin,
    )


def _create_payload() -> dict[str, Any]:
    return {
        "username": "new-user",
        "display_name": "New User",
        "email": "new@example.test",
        "password": "initial-password",
        "roles": ["member"],
    }


def test_create_requires_all_identity_fields(
    tmp_path: Path,
) -> None:
    client, _, writer, _, _ = _fixture(
        tmp_path
    )

    cases = (
        ("username", None),
        ("display_name", None),
        ("email", None),
        ("password", None),
        ("username", "   "),
        ("display_name", "   "),
        ("email", "   "),
        ("password", ""),
    )

    for field, value in cases:
        payload = _create_payload()

        if value is None:
            del payload[field]
        else:
            payload[field] = value

        response = client.post(
            "/api/v1/admin/users",
            json=payload,
        )

        assert response.status_code == 422

    assert writer.creates == []


def test_create_notification_preferences_are_opt_in(
    tmp_path: Path,
) -> None:
    client, _, writer, _, _ = _fixture(
        tmp_path
    )

    response = client.post(
        "/api/v1/admin/users",
        json=_create_payload(),
    )

    assert response.status_code == 201

    assert writer.creates[0][
        "email_notifications_enabled"
    ] is False

    assert writer.creates[0][
        "discord_notifications_enabled"
    ] is False

    assert writer.creates[0][
        "discord_account"
    ] is None

    body = response.json()

    assert body[
        "email_notifications_enabled"
    ] is False
    assert body[
        "discord_notifications_enabled"
    ] is False


def test_email_notifications_can_be_enabled_independently(
    tmp_path: Path,
) -> None:
    client, _, writer, _, _ = _fixture(
        tmp_path
    )

    payload = _create_payload()
    payload["email_notifications_enabled"] = True

    response = client.post(
        "/api/v1/admin/users",
        json=payload,
    )

    assert response.status_code == 201

    assert writer.creates[0][
        "email_notifications_enabled"
    ] is True

    assert writer.creates[0][
        "discord_notifications_enabled"
    ] is False


def test_discord_notifications_require_discord_account(
    tmp_path: Path,
) -> None:
    client, _, writer, _, _ = _fixture(
        tmp_path
    )

    payload = _create_payload()
    payload[
        "discord_notifications_enabled"
    ] = True

    response = client.post(
        "/api/v1/admin/users",
        json=payload,
    )

    assert response.status_code == 422
    assert writer.creates == []


def test_create_accepts_optional_discord_account(
    tmp_path: Path,
) -> None:
    client, _, writer, _, _ = _fixture(
        tmp_path
    )

    payload = _create_payload()
    payload.update(
        {
            "discord_account": "atlas-user",
            "discord_notifications_enabled": True,
        }
    )

    response = client.post(
        "/api/v1/admin/users",
        json=payload,
    )

    assert response.status_code == 201

    assert writer.creates[0][
        "discord_account"
    ] == "atlas-user"

    assert writer.creates[0][
        "discord_notifications_enabled"
    ] is True


def test_admin_can_edit_profile_and_preferences(
    tmp_path: Path,
) -> None:
    client, profiles, writer, _, _ = _fixture(
        tmp_path
    )

    target = profiles.create_user(
        "target",
        display_name="Target User",
        email="target@example.test",
        jellyfin_user_id="0123456789abcdef0123456789abcdef",
    )

    response = client.patch(
        (
            "/api/v1/admin/users/"
            f"{target['user_id']}"
        ),
        json={
            "display_name": "Updated User",
            "first_name": "Updated",
            "last_name": "Person",
            "email": "UPDATED@example.test",
            "discord_account": "updated-discord",
            "email_notifications_enabled": True,
            "discord_notifications_enabled": True,
        },
    )

    assert response.status_code == 200

    assert writer.updates == [
        (
            target["user_id"],
            {
                "display_name": "Updated User",
                "first_name": "Updated",
                "last_name": "Person",
                "email": "UPDATED@example.test",
                "discord_account": "updated-discord",
                "email_notifications_enabled": True,
                "discord_notifications_enabled": True,
            },
        )
    ]


def test_required_profile_fields_cannot_be_cleared(
    tmp_path: Path,
) -> None:
    client, profiles, writer, _, _ = _fixture(
        tmp_path
    )

    target = profiles.create_user(
        "target",
        display_name="Target User",
        email="target@example.test",
    )

    for payload in (
        {"display_name": "   "},
        {"email": "   "},
    ):
        response = client.patch(
            (
                "/api/v1/admin/users/"
                f"{target['user_id']}"
            ),
            json=payload,
        )

        assert response.status_code == 422

    assert writer.updates == []


def test_discord_preference_missing_target_is_404(
    tmp_path: Path,
) -> None:
    client, _, writer, _, _ = _fixture(
        tmp_path
    )

    response = client.patch(
        "/api/v1/admin/users/usr_missing",
        json={
            "discord_notifications_enabled": True,
        },
    )

    assert response.status_code == 404
    assert writer.updates == []


def test_admin_password_action_is_credential_safe(
    tmp_path: Path,
) -> None:
    client, profiles, writer, audit, admin = (
        _fixture(tmp_path)
    )

    target = profiles.create_user(
        "target",
        display_name="Target User",
        email="target@example.test",
        jellyfin_user_id="0123456789abcdef0123456789abcdef",
    )

    secret = "new-super-secret-password"

    response = client.post(
        (
            "/api/v1/admin/users/"
            f"{target['user_id']}/password"
        ),
        json={
            "new_password": secret,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "password-set",
    }

    assert writer.passwords == [
        (
            target["user_id"],
            secret,
        )
    ]

    assert audit.events == [
        (
            "security.identity.user_password_set",
            {
                "actor_user_id": admin["user_id"],
                "target_user_id": target["user_id"],
            },
        )
    ]

    assert secret not in response.text
    assert secret not in repr(audit.events)


def test_admin_password_rejects_unlinked_user(
    tmp_path: Path,
) -> None:
    client, profiles, writer, audit, _ = (
        _fixture(tmp_path)
    )

    target = profiles.create_user(
        "unlinked",
        display_name="Unlinked User",
        email="unlinked@example.test",
    )

    response = client.post(
        (
            "/api/v1/admin/users/"
            f"{target['user_id']}/password"
        ),
        json={
            "new_password": "must-not-be-used",
        },
    )

    assert response.status_code == 409
    assert writer.passwords == []
    assert audit.events == []
