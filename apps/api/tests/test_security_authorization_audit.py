"""Audit contracts for centralized Atlas authorization denials."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from atlas.user_profiles import UserProfileError
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.authorization import AuthorizationService
from atlas_api.security.dependencies import require_permission, require_role


USER = AuthenticatedUser(
    user_id="usr_test",
    username="michael",
    display_name="Michael",
    roles=("member",),
    provider="jellyfin",
    metadata={},
)


def profile(
    *,
    roles=None,
    allow=None,
    deny=None,
    status="active",
):
    return {
        "user_id": "usr_test",
        "roles": roles or ["member"],
        "permission_overrides": {
            "allow": allow or [],
            "deny": deny or [],
        },
        "status": status,
    }


class RecordingAuditWriter:
    def __init__(self) -> None:
        self.events = []

    def publish(self, name, payload) -> None:
        self.events.append((name, dict(payload)))


def test_missing_permission_grant_emits_denial_event() -> None:
    profiles = Mock()
    profiles.get_user.return_value = profile(roles=["member"])
    audit = RecordingAuditWriter()
    dependency = require_permission("users.delete")

    with pytest.raises(HTTPException) as caught:
        dependency(USER, profiles, AuthorizationService(), audit)

    assert caught.value.status_code == 403
    assert audit.events == [
        (
            "security.authorization.denied",
            {
                "user_id": "usr_test",
                "username": "michael",
                "provider": "jellyfin",
                "reason": "missing_grant",
                "permission": "users.delete",
            },
        )
    ]


def test_explicit_permission_denial_is_distinguished() -> None:
    profiles = Mock()
    profiles.get_user.return_value = profile(
        roles=["owner"],
        deny=["users.delete"],
    )
    audit = RecordingAuditWriter()
    dependency = require_permission("users.delete")

    with pytest.raises(HTTPException):
        dependency(USER, profiles, AuthorizationService(), audit)

    assert audit.events[0][1]["reason"] == "explicit_denial"
    assert audit.events[0][1]["permission"] == "users.delete"


def test_missing_role_emits_denial_event() -> None:
    profiles = Mock()
    profiles.get_user.return_value = profile(roles=["member"])
    audit = RecordingAuditWriter()
    dependency = require_role("owner")

    with pytest.raises(HTTPException) as caught:
        dependency(USER, profiles, AuthorizationService(), audit)

    assert caught.value.status_code == 403
    assert audit.events[0] == (
        "security.authorization.denied",
        {
            "user_id": "usr_test",
            "username": "michael",
            "provider": "jellyfin",
            "reason": "missing_role",
            "required_role": "owner",
        },
    )


def test_allowed_permission_does_not_emit_denial() -> None:
    profiles = Mock()
    profiles.get_user.return_value = profile(roles=["global_admin"])
    audit = RecordingAuditWriter()
    dependency = require_permission("users.read")

    result = dependency(USER, profiles, AuthorizationService(), audit)

    assert result is USER
    assert audit.events == []


def test_missing_profile_emits_denial_before_401() -> None:
    profiles = Mock()
    profiles.get_user.side_effect = UserProfileError("not found")
    audit = RecordingAuditWriter()
    dependency = require_permission("users.read")

    with pytest.raises(HTTPException) as caught:
        dependency(USER, profiles, AuthorizationService(), audit)

    assert caught.value.status_code == 401
    assert audit.events[0][1]["reason"] == "profile_unavailable_or_inactive"
    assert audit.events[0][1]["permission"] == "users.read"


def test_disabled_profile_emits_denial_before_401() -> None:
    profiles = Mock()
    profiles.get_user.return_value = profile(
        roles=["global_admin"],
        status="disabled",
    )
    audit = RecordingAuditWriter()
    dependency = require_permission("users.read")

    with pytest.raises(HTTPException) as caught:
        dependency(USER, profiles, AuthorizationService(), audit)

    assert caught.value.status_code == 401
    assert audit.events[0][1]["reason"] == "profile_unavailable_or_inactive"
