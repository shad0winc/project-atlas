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
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    discord_account: str | None = None
    email_notifications_enabled: bool = False
    discord_notifications_enabled: bool = False


class AdminUserUpdateRequest(BaseModel):
    """Restricted administrator user-update contract."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    discord_account: str | None = None
    email_notifications_enabled: bool | None = None
    discord_notifications_enabled: bool | None = None
    roles: list[str] | None = None
    status: str | None = None


class AdminUserPasswordRequest(BaseModel):
    """Dedicated administrator password mutation contract."""

    model_config = ConfigDict(extra="forbid")

    new_password: str


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

    for optional_field in (
        "first_name",
        "last_name",
        "discord_account",
    ):
        value = profile.get(optional_field)
        if value is not None:
            result[optional_field] = value

    result["email_notifications_enabled"] = bool(
        profile.get("email_notifications_enabled", False)
    )
    result["discord_notifications_enabled"] = bool(
        profile.get("discord_notifications_enabled", False)
    )

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

    if not request.username.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Username is required.",
        )

    if not request.display_name.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Display Name is required.",
        )

    if not request.email.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email Address is required.",
        )

    if not request.password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Password is required.",
        )

    if (
        request.discord_notifications_enabled
        and not (request.discord_account or "").strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Discord notifications require a Discord account."
            ),
        )

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
            discord_account=request.discord_account,
            email_notifications_enabled=(
                request.email_notifications_enabled
            ),
            discord_notifications_enabled=(
                request.discord_notifications_enabled
            ),
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

    if "display_name" in updates:
        if not isinstance(updates["display_name"], str) or not updates["display_name"].strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Display Name is required.",
            )
        updates["display_name"] = updates["display_name"].strip()

    if "email" in updates:
        if not isinstance(updates["email"], str) or not updates["email"].strip():
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Email Address is required.",
            )
        updates["email"] = updates["email"].strip()

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one user update field is required.",
        )

    # Give a missing target normal resource semantics before performing
    # validation that depends on current profile state.
    try:
        target = profiles.get_user(identifier)
    except UserProfileError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from error

    if (
        updates.get("discord_notifications_enabled") is True
        and not (
            updates.get("discord_account")
            or target.get("discord_account")
            or ""
        ).strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Discord notifications require a Discord account."
            ),
        )

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

@router.post("/{identifier}/password")
def set_admin_user_password(
    identifier: str,
    request: AdminUserPasswordRequest,
    current_user: AuthenticatedUser = Depends(require_users_update),
    profiles: UserProfileStore = Depends(get_user_profile_store),
    writer: IdentityWriterClient = Depends(
        get_identity_writer_client
    ),
    audit_writer=Depends(get_security_audit_writer),
) -> dict[str, str]:
    """Set a new Jellyfin-backed password for an Atlas user."""

    if not request.new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password is required.",
        )

    try:
        target = profiles.get_user(identifier)
    except UserProfileError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from error

    if not target.get("jellyfin_user_id"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Atlas user is not linked to Jellyfin.",
        )

    try:
        writer.set_user_password(
            identifier,
            request.new_password,
        )
    except IdentityWriterError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from error

    audit_writer.publish(
        "security.identity.user_password_set",
        {
            "actor_user_id": current_user.user_id,
            "target_user_id": target["user_id"],
        },
    )

    return {"status": "password-set"}
