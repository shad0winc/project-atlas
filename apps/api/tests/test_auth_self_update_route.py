"""Self-service current-user mutation contracts."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.authorization import AuthorizationService
from atlas_api.dependencies import get_identity_writer_client
from atlas_api.main import create_app
from atlas_api.routes.v1.auth import require_current_user_update
from atlas_api.security.dependencies import get_authorization_service


USER = AuthenticatedUser(
    user_id="usr_123",
    username="michael",
    display_name="Michael",
    roles=("member",),
    provider="jellyfin",
)


def profile(
    *,
    display_name: str = "Michael",
    first_name: str | None = "Michael",
    last_name: str | None = "Atlas",
    email: str = "michael@example.com",
    discord_account: str | None = None,
    email_notifications_enabled: bool = False,
    discord_notifications_enabled: bool = False,
) -> dict[str, object]:
    return {
        "schema_version": 2,
        "user_id": USER.user_id,
        "username": USER.username,
        "display_name": display_name,
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "birthday": "",
        "discord_account": discord_account,
        "email_notifications_enabled": email_notifications_enabled,
        "discord_notifications_enabled": discord_notifications_enabled,
        "roles": ["member"],
        "permission_overrides": {"allow": [], "deny": []},
        "status": "active",
        "jellyfin_user_id": "0123456789abcdef0123456789abcdef",
        "created_at": "2026-08-29T00:00:00Z",
        "updated_at": "2026-08-29T00:00:00Z",
    }


class WriterDouble:
    def __init__(self) -> None:
        self.identifier: str | None = None
        self.updates: dict[str, object] | None = None

    def update_user(
        self,
        identifier: str,
        updates: dict[str, object],
    ) -> dict[str, object]:
        self.identifier = identifier
        self.updates = updates

        current = profile()
        current.update(updates)
        return current


def client_with(
    writer: WriterDouble,
) -> tuple[TestClient, object]:
    app = create_app()
    app.dependency_overrides[
        require_current_user_update
    ] = lambda: USER
    app.dependency_overrides[
        get_identity_writer_client
    ] = lambda: writer
    app.dependency_overrides[
        get_authorization_service
    ] = lambda: AuthorizationService()

    return TestClient(app), app


def test_self_update_delegates_supported_profile_fields() -> None:
    writer = WriterDouble()
    client, app = client_with(writer)

    try:
        response = client.patch(
            "/api/v1/auth/me",
            json={
                "display_name": "  Atlas User  ",
                "first_name": " Michael ",
                "last_name": " Atlas ",
                "email": " michael@example.com ",
                "discord_account": " atlas-user ",
                "email_notifications_enabled": True,
                "discord_notifications_enabled": True,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert writer.identifier == USER.user_id
    assert writer.updates == {
        "display_name": "Atlas User",
        "first_name": "Michael",
        "last_name": "Atlas",
        "email": "michael@example.com",
        "discord_account": "atlas-user",
        "email_notifications_enabled": True,
        "discord_notifications_enabled": True,
    }

    body = response.json()
    assert body["display_name"] == "Atlas User"
    assert body["email"] == "michael@example.com"
    assert body["discord_account"] == "atlas-user"
    assert body["email_notifications_enabled"] is True
    assert body["discord_notifications_enabled"] is True


def test_self_update_can_clear_optional_profile_fields() -> None:
    writer = WriterDouble()
    client, app = client_with(writer)

    try:
        response = client.patch(
            "/api/v1/auth/me",
            json={
                "first_name": "",
                "last_name": None,
                "discord_account": "",
                "discord_notifications_enabled": False,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert writer.updates == {
        "first_name": None,
        "last_name": None,
        "discord_account": None,
        "discord_notifications_enabled": False,
    }


def test_self_update_rejects_privileged_fields() -> None:
    writer = WriterDouble()
    client, app = client_with(writer)

    try:
        response = client.patch(
            "/api/v1/auth/me",
            json={
                "display_name": "Atlas User",
                "roles": ["owner"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert writer.identifier is None
    assert writer.updates is None


def test_self_update_rejects_blank_display_name_without_writer_call() -> None:
    writer = WriterDouble()
    client, app = client_with(writer)

    try:
        response = client.patch(
            "/api/v1/auth/me",
            json={"display_name": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert writer.identifier is None
    assert writer.updates is None


def test_self_update_rejects_blank_email_without_writer_call() -> None:
    writer = WriterDouble()
    client, app = client_with(writer)

    try:
        response = client.patch(
            "/api/v1/auth/me",
            json={"email": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert writer.identifier is None
    assert writer.updates is None
