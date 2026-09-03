"""Administrator user-management routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_identity_writer_client,
    get_security_audit_writer,
    get_user_profile_store,
)
from atlas_api.services.identity_writer import (
    IdentityWriterClient,
    IdentityWriterError,
)
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
require_users_create = require_permission("users.create")
require_users_update = require_permission("users.update")


class AdminUserCreateRequest(BaseModel):
    """Administrator contract for provisioning an Atlas user."""

    model_config = ConfigDict(extra="forbid")

    username: str
    email: str
    password: str
    roles: list[str] = Field(
        default_factory=lambda: ["member"]
    )
    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class AdminUserUpdateRequest(BaseModel):
    """Restricted administrator user-update contract."""

    model_config = ConfigDict(extra="forbid")

    roles: list[str] | None = None
    status: str | None = None


def _public_user(profile: dict[str, Any]) -> dict[str, Any]:
    """Return the safe administrator-facing user representation."""

    result = {
        "user_id": profile["user_id"],
        "username": profile["username"],
        "display_name": profile["display_name"],
        "roles": list(profile["roles"]),
        "status": profile["status"],
    }

    email = profile.get("email")
    if email is not None:
        result["email"] = email

    jellyfin_user_id = profile.get("jellyfin_user_id")
    if jellyfin_user_id is not None:
        result["jellyfin_user_id"] = jellyfin_user_id

    return result


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_admin_user(
    request: AdminUserCreateRequest,
    current_user: AuthenticatedUser = Depends(require_users_create),
    profiles: UserProfileStore = Depends(get_user_profile_store),
    writer: IdentityWriterClient = Depends(
        get_identity_writer_client
    ),
    audit_writer=Depends(get_security_audit_writer),
    authorization=Depends(get_authorization_service),
) -> dict[str, Any]:
    """Provision one linked Atlas/Jellyfin user."""

    try:
        actor_profile = profiles.get_user(
            current_user.user_id
        )
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
        created = writer.create_user(
            username=request.username,
            email=request.email,
            password=request.password,
            roles=request.roles,
            display_name=request.display_name,
            first_name=request.first_name,
            last_name=request.last_name,
        )
    except IdentityWriterError as error:
        if (
            error.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            and "requires administrator recovery" in str(error).lower()
        ):
            audit_writer.publish(
                "security.identity.user_provisioning_recovery_required",
                {
                    "actor_user_id": current_user.user_id,
                    "requested_username": request.username.strip(),
                },
            )

        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from error

    audit_writer.publish(
        "security.identity.user_provisioned",
        {
            "actor_user_id": current_user.user_id,
            "created_user_id": created["user_id"],
            "jellyfin_user_id": created.get("jellyfin_user_id"),
            "username": created["username"],
        },
    )

    return _public_user(created)


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
    writer: IdentityWriterClient = Depends(
        get_identity_writer_client
    ),
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
        updated = writer.update_user(
            identifier,
            updates,
        )
    except IdentityWriterError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from error

    return _public_user(updated)
