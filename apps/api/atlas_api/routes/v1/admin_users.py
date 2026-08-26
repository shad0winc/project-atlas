"""Administrator user-management routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_user_profile_store
from atlas_api.security.dependencies import (
    get_authorization_service,
    require_permission,
)
from atlas_api.security.permissions import evaluate_permission


router = APIRouter(
    prefix="/admin/users",
    tags=["admin-users"],
)

require_users_read = require_permission("users.read")
require_users_update = require_permission("users.update")


class AdminUserUpdateRequest(BaseModel):
    """Restricted administrator user-update contract."""

    model_config = ConfigDict(extra="forbid")

    roles: list[str] | None = None
    status: str | None = None


def _public_user(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the safe administrator-facing user representation."""

    return {
        "user_id": profile["user_id"],
        "username": profile["username"],
        "display_name": profile["display_name"],
        "roles": list(profile["roles"]),
        "status": profile["status"],
    }


@router.get("")
def list_admin_users(
    _user: AuthenticatedUser = Depends(require_users_read),
    profiles: UserProfileStore = Depends(get_user_profile_store),
) -> dict[str, list[dict[str, Any]]]:
    """List Atlas users for an authorized administrator."""

    return {
        "users": [
            _public_user(profile)
            for profile in profiles.list_users()
        ]
    }


@router.get("/{identifier}")
def get_admin_user(
    identifier: str,
    _user: AuthenticatedUser = Depends(require_users_read),
    profiles: UserProfileStore = Depends(get_user_profile_store),
) -> dict[str, Any]:
    """Return one Atlas user for an authorized administrator."""

    try:
        profile = profiles.get_user(identifier)
    except UserProfileError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from error

    return _public_user(profile)


@router.patch("/{identifier}")
def update_admin_user(
    identifier: str,
    request: AdminUserUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_users_update),
    profiles: UserProfileStore = Depends(get_user_profile_store),
    authorization=Depends(get_authorization_service),
) -> dict[str, Any]:
    """Update only supported administrator-managed user fields."""

    updates = request.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one user update field is required.",
        )

    # Give a missing target normal resource semantics before attempting
    # domain mutation.
    try:
        profiles.get_user(identifier)
    except UserProfileError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from error

    # Role assignment is a distinct authorization capability from ordinary
    # profile mutation.
    if "roles" in updates:
        try:
            actor_profile = profiles.get_user(current_user.user_id)
        except UserProfileError as error:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authenticated Atlas user was not found.",
            ) from error

        decision = evaluate_permission(
            actor_profile,
            "roles.assign",
            authorization=authorization,
        )

        if not decision.allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=decision.reason,
            )

    try:
        updated = profiles.update_user(
            identifier,
            updates,
        )
    except UserProfileError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return _public_user(updated)
