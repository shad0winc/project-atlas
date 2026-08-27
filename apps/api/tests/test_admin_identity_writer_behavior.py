"""Behavioral contracts for administrator identity-writer delegation."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from atlas.user_profiles import UserProfileStore
from atlas_api.authorization import AuthorizationService
from atlas_api.routes.v1 import admin_invitations, admin_users
from atlas_api.services.identity_writer import IdentityWriterError


class RecordingWriter:
    """Test writer that records privileged mutation requests."""

    def __init__(self) -> None:
        self.user_updates: list[
            tuple[str, dict[str, Any]]
        ] = []
        self.invitation_creates: list[
            dict[str, Any]
        ] = []
        self.invitation_revocations: list[
            tuple[str, str]
        ] = []

    def update_user(
        self,
        identifier: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        self.user_updates.append(
            (identifier, dict(updates))
        )

        return {
            "user_id": identifier,
            "username": "target",
            "display_name": "Target User",
            "roles": list(
                updates.get(
                    "roles",
                    ["member"],
                )
            ),
            "status": updates.get(
                "status",
                "active",
            ),
        }

    def create_invitation(
        self,
        *,
        email: str | None,
        role: str,
        days: int,
        created_by: str,
    ) -> dict[str, Any]:
        payload = {
            "email": email,
            "role": role,
            "days": days,
            "created_by": created_by,
        }
        self.invitation_creates.append(payload)

        return {
            "invitation": {
                "invite_id": "inv_test",
                "email": email,
                "role": role,
                "status": "pending",
                "created_by": created_by,
                "token_hash": "must-not-leak",
            },
            "token": "one-time-token",
        }

    def revoke_invitation(
        self,
        invite_id: str,
        *,
        revoked_by: str,
    ) -> dict[str, Any]:
        self.invitation_revocations.append(
            (invite_id, revoked_by)
        )

        return {
            "invite_id": invite_id,
            "email": "invitee@example.test",
            "role": "user",
            "status": "revoked",
            "revoked_by": revoked_by,
            "token_hash": "must-not-leak",
        }


class FailingWriter(RecordingWriter):
    """Writer that returns one configured transport/domain failure."""

    def __init__(
        self,
        status_code: int,
        message: str,
    ) -> None:
        super().__init__()
        self.status_code = status_code
        self.message = message

    def update_user(
        self,
        identifier: str,
        updates: dict[str, Any],
    ) -> dict[str, Any]:
        raise IdentityWriterError(
            self.message,
            status_code=self.status_code,
        )

    def create_invitation(
        self,
        *,
        email: str | None,
        role: str,
        days: int,
        created_by: str,
    ) -> dict[str, Any]:
        raise IdentityWriterError(
            self.message,
            status_code=self.status_code,
        )

    def revoke_invitation(
        self,
        invite_id: str,
        *,
        revoked_by: str,
    ) -> dict[str, Any]:
        raise IdentityWriterError(
            self.message,
            status_code=self.status_code,
        )


def _actor(user_id: str):
    return SimpleNamespace(
        user_id=user_id,
        username="administrator",
        display_name="Administrator",
        roles=("global_admin",),
    )


def test_user_status_update_delegates_exact_payload(
    tmp_path,
) -> None:
    profiles = UserProfileStore(
        tmp_path / "users"
    )
    target = profiles.create_user(
        "target",
    )

    writer = RecordingWriter()

    result = admin_users.update_admin_user(
        target["user_id"],
        admin_users.AdminUserUpdateRequest(
            status="disabled",
        ),
        current_user=_actor("actor"),
        profiles=profiles,
        writer=writer,
        authorization=AuthorizationService(),
    )

    assert writer.user_updates == [
        (
            target["user_id"],
            {
                "status": "disabled",
            },
        )
    ]

    assert result == {
        "user_id": target["user_id"],
        "username": "target",
        "display_name": "Target User",
        "roles": ["member"],
        "status": "disabled",
    }


def test_role_assignment_is_authorized_before_writer_call(
    tmp_path,
) -> None:
    profiles = UserProfileStore(
        tmp_path / "users"
    )

    actor = profiles.create_user(
        "atlas-admin",
        role="atlas_admin",
    )

    target = profiles.create_user(
        "target",
    )

    writer = RecordingWriter()

    with pytest.raises(HTTPException) as captured:
        admin_users.update_admin_user(
            target["user_id"],
            admin_users.AdminUserUpdateRequest(
                roles=["member"],
            ),
            current_user=_actor(
                actor["user_id"]
            ),
            profiles=profiles,
            writer=writer,
            authorization=AuthorizationService(),
        )

    assert captured.value.status_code == 403
    assert writer.user_updates == []


def test_invitation_create_preserves_public_response_shape() -> None:
    writer = RecordingWriter()

    result = admin_invitations.create_admin_invitation(
        admin_invitations.InvitationCreateRequest(
            email="invitee@example.test",
            role="user",
            days=14,
        ),
        user=_actor("admin-123"),
        writer=writer,
    )

    assert writer.invitation_creates == [
        {
            "email": "invitee@example.test",
            "role": "user",
            "days": 14,
            "created_by": "admin-123",
        }
    ]

    assert result["invite_id"] == "inv_test"
    assert result["email"] == "invitee@example.test"
    assert result["role"] == "user"
    assert result["status"] == "pending"
    assert result["created_by"] == "admin-123"
    assert result["token"] == "one-time-token"

    assert "invitation" not in result
    assert "token_hash" not in result


def test_invitation_revoke_delegates_actor_and_hides_secret() -> None:
    writer = RecordingWriter()

    result = admin_invitations.revoke_admin_invitation(
        "inv_test",
        user=_actor("admin-456"),
        writer=writer,
    )

    assert writer.invitation_revocations == [
        (
            "inv_test",
            "admin-456",
        )
    ]

    assert result["invite_id"] == "inv_test"
    assert result["status"] == "revoked"
    assert result["revoked_by"] == "admin-456"
    assert "token_hash" not in result


@pytest.mark.parametrize(
    ("operation", "status_code"),
    [
        ("user", 404),
        ("invite_create", 409),
        ("invite_revoke", 502),
    ],
)
def test_writer_failure_status_is_preserved(
    tmp_path,
    operation: str,
    status_code: int,
) -> None:
    writer = FailingWriter(
        status_code,
        "writer failure",
    )

    with pytest.raises(HTTPException) as captured:
        if operation == "user":
            profiles = UserProfileStore(
                tmp_path / "users"
            )
            target = profiles.create_user(
                "target",
            )

            admin_users.update_admin_user(
                target["user_id"],
                admin_users.AdminUserUpdateRequest(
                    status="disabled",
                ),
                current_user=_actor("admin"),
                profiles=profiles,
                writer=writer,
                authorization=AuthorizationService(),
            )

        elif operation == "invite_create":
            admin_invitations.create_admin_invitation(
                admin_invitations.InvitationCreateRequest(
                    email=None,
                    role="user",
                    days=7,
                ),
                user=_actor("admin"),
                writer=writer,
            )

        else:
            admin_invitations.revoke_admin_invitation(
                "inv_test",
                user=_actor("admin"),
                writer=writer,
            )

    assert captured.value.status_code == status_code
    assert captured.value.detail == "writer failure"


def test_users_update_permission_rejection_prevents_writer_resolution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.include_router(
        admin_users.router,
        prefix="/api/v1",
    )

    writer_resolved = False

    def reject_permission():
        raise HTTPException(
            status_code=403,
            detail="denied before writer",
        )

    def resolve_writer():
        nonlocal writer_resolved
        writer_resolved = True
        return RecordingWriter()

    app.dependency_overrides[
        admin_users.require_users_update
    ] = reject_permission

    app.dependency_overrides[
        admin_users.get_identity_writer_client
    ] = resolve_writer

    client = TestClient(app)

    response = client.patch(
        "/api/v1/admin/users/target",
        json={
            "status": "disabled",
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "denied before writer"
    )
    assert writer_resolved is False
