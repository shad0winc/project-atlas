"""Administrator Live-session concurrency policy routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from atlas.live_session_policy import LiveSessionPolicyError, LiveSessionPolicyStore
from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_identity_writer_client,
    get_live_session_policy_store,
    get_security_audit_writer,
    get_user_profile_store,
)
from atlas_api.security.dependencies import require_permission
from atlas_api.services.identity_writer import IdentityWriterClient, IdentityWriterError


router = APIRouter(prefix="/admin/live-sessions", tags=["admin-live-sessions"])
require_live_sessions_manage = require_permission("atlas.live_sessions.manage")


class AdminLiveSessionLimitRequest(BaseModel):
    """Strict administrator contract for one concurrency limit."""

    model_config = ConfigDict(extra="forbid")
    limit: Any


def _validated_limit(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Live-session limit must be a positive integer.",
        )
    return value


def _policy_response(
    policy: LiveSessionPolicyStore,
    profiles: UserProfileStore,
) -> dict[str, Any]:
    snapshot = policy.snapshot()
    overrides = snapshot["overrides"]
    users = []
    for profile in profiles.list_users():
        user_id = str(profile["user_id"])
        override = overrides.get(user_id)
        users.append(
            {
                "user_id": user_id,
                "username": str(profile["username"]),
                "display_name": str(profile["display_name"]),
                "override_limit": override,
                "effective_limit": (
                    override if override is not None else snapshot["default_limit"]
                ),
            }
        )
    users.sort(
        key=lambda row: (
            str(row["display_name"]).casefold(),
            str(row["username"]).casefold(),
            str(row["user_id"]),
        )
    )
    return {
        "version": snapshot["version"],
        "default_limit": snapshot["default_limit"],
        "users": users,
    }


@router.get("")
def read_admin_live_session_policy(
    _user: AuthenticatedUser = Depends(require_live_sessions_manage),
    policy: LiveSessionPolicyStore = Depends(get_live_session_policy_store),
    profiles: UserProfileStore = Depends(get_user_profile_store),
) -> dict[str, Any]:
    """Return administrator-safe Live-session policy state."""
    try:
        return _policy_response(policy, profiles)
    except (LiveSessionPolicyError, UserProfileError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live-session policy is unavailable.",
        ) from error


@router.patch("/default")
def update_admin_live_session_default(
    request: AdminLiveSessionLimitRequest,
    current_user: AuthenticatedUser = Depends(require_live_sessions_manage),
    writer: IdentityWriterClient = Depends(get_identity_writer_client),
    audit_writer=Depends(get_security_audit_writer),
) -> dict[str, int]:
    """Update the global Live-session concurrency default."""
    limit = _validated_limit(request.limit)
    try:
        result = writer.set_live_session_default_limit(limit)
    except IdentityWriterError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    persisted = int(result["default_limit"])
    audit_writer.publish(
        "security.live_sessions.default_limit_updated",
        {"actor_user_id": current_user.user_id, "default_limit": persisted},
    )
    return {"default_limit": persisted}


@router.put("/users/{user_id}")
def update_admin_live_session_user_override(
    user_id: str,
    request: AdminLiveSessionLimitRequest,
    current_user: AuthenticatedUser = Depends(require_live_sessions_manage),
    profiles: UserProfileStore = Depends(get_user_profile_store),
    writer: IdentityWriterClient = Depends(get_identity_writer_client),
    audit_writer=Depends(get_security_audit_writer),
) -> dict[str, Any]:
    """Set one user's explicit Live-session concurrency override."""
    limit = _validated_limit(request.limit)
    try:
        target = profiles.get_user(user_id)
    except UserProfileError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from error
    target_id = str(target["user_id"])
    try:
        result = writer.set_live_session_user_override(target_id, limit)
    except IdentityWriterError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    persisted = int(result["override_limit"])
    audit_writer.publish(
        "security.live_sessions.user_override_updated",
        {
            "actor_user_id": current_user.user_id,
            "target_user_id": target_id,
            "override_limit": persisted,
        },
    )
    return {"user_id": target_id, "override_limit": persisted}


@router.delete("/users/{user_id}")
def clear_admin_live_session_user_override(
    user_id: str,
    current_user: AuthenticatedUser = Depends(require_live_sessions_manage),
    profiles: UserProfileStore = Depends(get_user_profile_store),
    writer: IdentityWriterClient = Depends(get_identity_writer_client),
    audit_writer=Depends(get_security_audit_writer),
) -> dict[str, Any]:
    """Return one user to the global Live-session concurrency default."""
    try:
        target = profiles.get_user(user_id)
    except UserProfileError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.") from error
    target_id = str(target["user_id"])
    try:
        writer.clear_live_session_user_override(target_id)
    except IdentityWriterError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
    audit_writer.publish(
        "security.live_sessions.user_override_cleared",
        {"actor_user_id": current_user.user_id, "target_user_id": target_id},
    )
    return {"user_id": target_id, "override_limit": None}
