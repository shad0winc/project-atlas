"""Public administrator user-provisioning contracts."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

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
        self.calls: list[dict[str, object]] = []

    def create_user(self, **kwargs):
        self.calls.append(dict(kwargs))

        return {
            "user_id": "atlas-created",
            "username": kwargs["username"],
            "display_name": (
                kwargs["display_name"]
                or kwargs["username"].title()
            ),
            "email": kwargs["email"].lower(),
            "roles": list(kwargs["roles"]),
            "status": "active",
            "jellyfin_user_id": "jellyfin-created",
        }


class NoopAudit:
    def publish(self, event_name, payload=None):
        return None


def _authenticated(profile):
    return AuthenticatedUser(
        user_id=str(profile["user_id"]),
        username=str(profile["username"]),
        display_name=str(profile["display_name"]),
        roles=tuple(profile["roles"]),
        provider="atlas",
        metadata={},
    )


def test_global_admin_can_provision_linked_user() -> None:
    with TemporaryDirectory() as temporary:
        profiles = UserProfileStore(Path(temporary))

        admin = profiles.create_user(
            "atlas-admin",
            roles=("global_admin",),
        )

        writer = RecordingWriter()
        app = create_app()

        app.dependency_overrides[get_user_profile_store] = (
            lambda: profiles
        )
        app.dependency_overrides[get_current_user] = (
            lambda: _authenticated(admin)
        )
        app.dependency_overrides[get_identity_writer_client] = (
            lambda: writer
        )
        app.dependency_overrides[get_security_audit_writer] = (
            lambda: NoopAudit()
        )

        response = TestClient(app).post(
            "/api/v1/admin/users",
            json={
                "username": "new-user",
                "email": "NEW@example.test",
                "password": "initial-password",
                "roles": ["member"],
                "display_name": "New User",
            },
        )

        assert response.status_code == 201

        body = response.json()

        assert body["username"] == "new-user"
        assert body["email"] == "new@example.test"
        assert body["roles"] == ["member"]
        assert body["status"] == "active"
        assert body["jellyfin_user_id"] == "jellyfin-created"

        assert "password" not in body
        assert "initial-password" not in response.text

        assert writer.calls == [
            {
                "username": "new-user",
                "email": "NEW@example.test",
                "password": "initial-password",
                "roles": ["member"],
                "display_name": "New User",
                "first_name": None,
                "last_name": None,
            }
        ]


def test_member_cannot_provision_user() -> None:
    with TemporaryDirectory() as temporary:
        profiles = UserProfileStore(Path(temporary))

        member = profiles.create_user(
            "ordinary-member",
            roles=("member",),
        )

        writer = RecordingWriter()
        app = create_app()

        app.dependency_overrides[get_user_profile_store] = (
            lambda: profiles
        )
        app.dependency_overrides[get_current_user] = (
            lambda: _authenticated(member)
        )
        app.dependency_overrides[get_identity_writer_client] = (
            lambda: writer
        )
        app.dependency_overrides[get_security_audit_writer] = (
            lambda: NoopAudit()
        )

        response = TestClient(app).post(
            "/api/v1/admin/users",
            json={
                "username": "forbidden-user",
                "email": "forbidden@example.test",
                "password": "initial-password",
            },
        )

        assert response.status_code == 403
        assert writer.calls == []


def test_unknown_create_field_is_rejected() -> None:
    with TemporaryDirectory() as temporary:
        profiles = UserProfileStore(Path(temporary))

        admin = profiles.create_user(
            "atlas-admin",
            roles=("global_admin",),
        )

        writer = RecordingWriter()
        app = create_app()

        app.dependency_overrides[get_user_profile_store] = (
            lambda: profiles
        )
        app.dependency_overrides[get_current_user] = (
            lambda: _authenticated(admin)
        )
        app.dependency_overrides[get_identity_writer_client] = (
            lambda: writer
        )
        app.dependency_overrides[get_security_audit_writer] = (
            lambda: NoopAudit()
        )

        response = TestClient(app).post(
            "/api/v1/admin/users",
            json={
                "username": "new-user",
                "email": "new@example.test",
                "password": "initial-password",
                "admin": True,
            },
        )

        assert response.status_code == 422
        assert writer.calls == []


class RecordingAudit:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def publish(self, event_name, payload=None):
        self.events.append(
            (
                event_name,
                dict(payload or {}),
            )
        )


def test_successful_provisioning_emits_safe_audit_event() -> None:
    with TemporaryDirectory() as temporary:
        profiles = UserProfileStore(Path(temporary))

        admin = profiles.create_user(
            "atlas-admin",
            roles=("global_admin",),
        )

        writer = RecordingWriter()
        audit = RecordingAudit()
        app = create_app()

        app.dependency_overrides[get_user_profile_store] = (
            lambda: profiles
        )
        app.dependency_overrides[get_current_user] = (
            lambda: _authenticated(admin)
        )
        app.dependency_overrides[get_identity_writer_client] = (
            lambda: writer
        )
        app.dependency_overrides[get_security_audit_writer] = (
            lambda: audit
        )

        response = TestClient(app).post(
            "/api/v1/admin/users",
            json={
                "username": "audited-user",
                "email": "audited@example.test",
                "password": "do-not-audit-this",
                "roles": ["member"],
            },
        )

        assert response.status_code == 201

        assert audit.events == [
            (
                "security.identity.user_provisioned",
                {
                    "actor_user_id": admin["user_id"],
                    "created_user_id": "atlas-created",
                    "jellyfin_user_id": "jellyfin-created",
                    "username": "audited-user",
                },
            )
        ]

        serialized = repr(audit.events)

        assert "do-not-audit-this" not in serialized
        assert "audited@example.test" not in serialized


def test_recovery_required_failure_emits_safe_audit_event() -> None:
    from atlas_api.services.identity_writer import (
        IdentityWriterError,
    )

    class RecoveryRequiredWriter:
        def create_user(self, **kwargs):
            raise IdentityWriterError(
                (
                    "User provisioning failed and requires "
                    "administrator recovery."
                ),
                status_code=500,
            )

    with TemporaryDirectory() as temporary:
        profiles = UserProfileStore(Path(temporary))

        admin = profiles.create_user(
            "atlas-admin",
            roles=("global_admin",),
        )

        audit = RecordingAudit()
        app = create_app()

        app.dependency_overrides[get_user_profile_store] = (
            lambda: profiles
        )
        app.dependency_overrides[get_current_user] = (
            lambda: _authenticated(admin)
        )
        app.dependency_overrides[get_identity_writer_client] = (
            lambda: RecoveryRequiredWriter()
        )
        app.dependency_overrides[get_security_audit_writer] = (
            lambda: audit
        )

        response = TestClient(app).post(
            "/api/v1/admin/users",
            json={
                "username": "orphan-candidate",
                "email": "orphan@example.test",
                "password": "never-audit-this",
                "roles": ["member"],
            },
        )

        assert response.status_code == 500

        assert audit.events == [
            (
                "security.identity.user_provisioning_recovery_required",
                {
                    "actor_user_id": admin["user_id"],
                    "requested_username": "orphan-candidate",
                },
            )
        ]

        serialized = repr(audit.events)

        assert "never-audit-this" not in serialized
        assert "orphan@example.test" not in serialized
