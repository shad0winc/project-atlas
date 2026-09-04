"""Private least-privilege mutation service for Atlas identity state."""

from __future__ import annotations

import argparse
import hmac
import os
from datetime import timedelta
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from atlas.identity import default_identity_paths
from atlas.invitations import InvitationError, InvitationStore
from atlas.custom_roles import (
    CustomRoleDefinition,
    CustomRoleError,
    default_custom_role_store,
)
from atlas_api.authorization import BUILT_IN_ROLES, normalize_role_name
from atlas.user_profiles import (
    UserProfileError,
    UserProfileStore,
    VALID_ROLES,
    default_store,
)
from atlas_api.services.jellyfin_identity import (
    JellyfinIdentityClient,
)
from atlas_api.services.user_provisioning import (
    UserProvisioningCompensationError,
    UserProvisioningConflictError,
    UserProvisioningError,
    UserProvisioningService,
)
from atlas.live_session_policy import (
    LiveSessionPolicyError,
    default_live_session_policy_store,
)


def _required_environment(name: str) -> str:
    value = os.getenv(name, "").strip()

    if not value:
        raise RuntimeError(
            f"{name} is required."
        )

    return value


SERVICE_TOKEN = _required_environment(
    "ATLAS_IDENTITY_WRITER_TOKEN"
)


def _user_store() -> UserProfileStore:
    return default_store()


def _user_provisioning_service() -> UserProvisioningService:
    """Return the privileged Atlas/Jellyfin provisioning service.

    Jellyfin administrator credentials are resolved only inside the private
    identity-writer process rather than the public Atlas API process.
    """

    base_url = _required_environment(
        "ATLAS_JELLYFIN_URL"
    )

    api_key = _required_environment(
        "ATLAS_JELLYFIN_API_KEY"
    )

    raw_timeout = os.getenv(
        "ATLAS_JELLYFIN_TIMEOUT_SECONDS",
        "10",
    ).strip()

    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as error:
        raise RuntimeError(
            "ATLAS_JELLYFIN_TIMEOUT_SECONDS must be numeric."
        ) from error

    if timeout_seconds <= 0:
        raise RuntimeError(
            "ATLAS_JELLYFIN_TIMEOUT_SECONDS must be greater than zero."
        )

    jellyfin = JellyfinIdentityClient(
        base_url,
        api_key,
        timeout_seconds=timeout_seconds,
    )

    return UserProvisioningService(
        _user_store(),
        jellyfin,
    )


def _jellyfin_identity_client() -> JellyfinIdentityClient:
    """Return the privileged Jellyfin identity lifecycle client."""

    base_url = _required_environment(
        "ATLAS_JELLYFIN_URL"
    )
    api_key = _required_environment(
        "ATLAS_JELLYFIN_API_KEY"
    )
    raw_timeout = os.getenv(
        "ATLAS_JELLYFIN_TIMEOUT_SECONDS",
        "10",
    ).strip()

    try:
        timeout_seconds = float(raw_timeout)
    except ValueError as error:
        raise RuntimeError(
            "ATLAS_JELLYFIN_TIMEOUT_SECONDS must be numeric."
        ) from error

    if timeout_seconds <= 0:
        raise RuntimeError(
            "ATLAS_JELLYFIN_TIMEOUT_SECONDS must be greater than zero."
        )

    return JellyfinIdentityClient(
        base_url,
        api_key,
        timeout_seconds=timeout_seconds,
    )


def _invitation_store() -> InvitationStore:
    store = InvitationStore(
        default_identity_paths()
    )
    store.initialize()
    return store


def _require_service_token(
    authorization: str | None = Header(
        default=None,
        alias="Authorization",
    ),
) -> None:
    prefix = "Bearer "

    if (
        authorization is None
        or not authorization.startswith(prefix)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid service authentication is required.",
        )

    supplied = authorization[len(prefix):]

    if not hmac.compare_digest(
        supplied,
        SERVICE_TOKEN,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid service authentication is required.",
        )


class UserCreateRequest(BaseModel):
    """Bounded Atlas/Jellyfin user-provisioning request."""

    model_config = ConfigDict(extra="forbid")

    username: str
    email: str
    password: str
    roles: list[str]
    display_name: str
    first_name: str | None = None
    last_name: str | None = None
    discord_account: str | None = None
    email_notifications_enabled: bool = False
    discord_notifications_enabled: bool = False


class UserUpdateRequest(BaseModel):
    """Bounded identity fields accepted from the authorized Atlas API."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    discord_account: str | None = None
    email_notifications_enabled: bool | None = None
    discord_notifications_enabled: bool | None = None
    status: str | None = None
    roles: list[str] | None = None


class UserPasswordRequest(BaseModel):
    """Dedicated credential mutation accepted from Atlas API."""

    model_config = ConfigDict(extra="forbid")

    new_password: str


class InvitationCreateRequest(BaseModel):
    """Bounded invitation creation request."""

    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    role: str = "user"
    days: int = Field(default=7, ge=1)
    created_by: str


class InvitationRevokeRequest(BaseModel):
    """Invitation revocation audit identity."""

    model_config = ConfigDict(extra="forbid")

    revoked_by: str


app = FastAPI(
    title="Atlas Identity Writer",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


class CustomRoleCreateRequest(BaseModel):
    """Private custom-role creation contract."""

    model_config = ConfigDict(extra="forbid")

    name: str
    display_name: str
    description: str = ""
    permissions: list[str]
    assignable: bool = True


class CustomRoleUpdateRequest(BaseModel):
    """Private custom-role update contract."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    description: str | None = None
    permissions: list[str] | None = None
    assignable: bool | None = None


def _custom_role_store():
    return default_custom_role_store(reserved_names=VALID_ROLES)


def _custom_role_payload(role: CustomRoleDefinition) -> dict[str, Any]:
    return {
        "name": role.name,
        "display_name": role.display_name,
        "description": role.description,
        "permissions": sorted(role.permissions),
        "assignable": role.assignable,
    }


_SUPPORTED_CUSTOM_PERMISSIONS = frozenset(
    permission
    for role in BUILT_IN_ROLES.values()
    for permission in role.permissions
    if permission != "*"
)


def _validate_custom_role_permissions(permissions: frozenset[str]) -> None:
    unsupported = sorted(set(permissions) - _SUPPORTED_CUSTOM_PERMISSIONS)
    if unsupported:
        raise CustomRoleError(
            "Unsupported custom-role permission patterns: " + ", ".join(unsupported)
        )


def _assert_role_assignable(role_name: str) -> None:
    normalized = normalize_role_name(role_name)
    built_in = BUILT_IN_ROLES.get(normalized)
    if built_in is not None:
        if not built_in.assignable:
            raise UserProfileError(f"Role '{normalized}' is protected from new assignments.")
        return
    custom = _custom_role_store().get(normalized)
    if custom is None:
        raise UserProfileError(f"Unknown Atlas role: {normalized}")
    if not custom.assignable:
        raise UserProfileError(f"Role '{normalized}' is not available for new assignments.")


def _assert_new_roles_assignable(requested_roles: list[str], existing_roles: object) -> None:
    if not isinstance(existing_roles, (list, tuple)):
        existing_roles = ()
    existing = {normalize_role_name(str(role)) for role in existing_roles}
    for role in requested_roles:
        normalized = normalize_role_name(role)
        if normalized not in existing:
            _assert_role_assignable(normalized)


def _safe_user_response(
    profile: dict[str, Any],
) -> dict[str, Any]:
    """Return only non-secret identity fields from the private writer."""

    return {
        "user_id": profile["user_id"],
        "username": profile["username"],
        "display_name": profile["display_name"],
        "first_name": profile.get("first_name"),
        "last_name": profile.get("last_name"),
        "email": profile.get("email"),
        "roles": list(profile["roles"]),
        "status": profile["status"],
        "jellyfin_user_id": profile.get("jellyfin_user_id"),
    }


class LiveSessionLimitRequest(BaseModel):
    """Private mutation payload for one Atlas Live-session limit."""

    model_config = ConfigDict(extra="forbid")
    limit: Any


@app.get("/health")
def health() -> dict[str, str]:
    """Return process liveness without disclosing identity state."""

    return {
        "status": "healthy",
    }


@app.post(
    "/internal/v1/users",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_service_token)],
)
def create_user(
    request: UserCreateRequest,
) -> dict[str, Any]:
    """Provision one linked Atlas and Jellyfin identity."""

    try:
        for role in request.roles:
            _assert_role_assignable(role)

        profile = _user_provisioning_service().provision_user(
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

        return _safe_user_response(profile)

    except UserProvisioningConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    except UserProvisioningCompensationError as error:
        # Deliberately do not expose the orphaned Jellyfin identifier through
        # the HTTP response. The later audit integration can record it on the
        # trusted server side.
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "User provisioning failed and requires "
                "administrator recovery."
            ),
        ) from error

    except UserProvisioningError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from error

    except (CustomRoleError, UserProfileError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error


@app.patch(
    "/internal/v1/users/{identifier}",
    dependencies=[Depends(_require_service_token)],
)
def update_user(
    identifier: str,
    request: UserUpdateRequest,
) -> dict[str, Any]:
    """Persist an already-authorized administrator user mutation."""

    updates = request.model_dump(
        exclude_unset=True
    )

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one user update field is required.",
        )

    try:
        store = _user_store()
        if request.roles is not None:
            current = store.get_user(identifier)
            _assert_new_roles_assignable(
                request.roles,
                current.get("roles", ()),
            )
        return store.update_user(
            identifier,
            updates,
        )
    except (CustomRoleError, UserProfileError, ValueError) as error:
        message = str(error)

        if "not found" in message.lower():
            code = status.HTTP_404_NOT_FOUND
        else:
            code = status.HTTP_400_BAD_REQUEST

        raise HTTPException(
            status_code=code,
            detail=message,
        ) from error


@app.post(
    "/internal/v1/users/{identifier}/password",
    dependencies=[Depends(_require_service_token)],
)
def set_user_password(
    identifier: str,
    request: UserPasswordRequest,
) -> dict[str, str]:
    """Set a user's Jellyfin password without persisting it in Atlas."""

    if not request.new_password:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password is required.",
        )

    try:
        profile = _user_store().get_user(identifier)
    except UserProfileError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        ) from error

    jellyfin_user_id = str(
        profile.get("jellyfin_user_id") or ""
    ).strip()

    if not jellyfin_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Atlas user is not linked to Jellyfin.",
        )

    try:
        _jellyfin_identity_client().set_password(
            jellyfin_user_id,
            request.new_password,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    except Exception as error:
        status_code = getattr(error, "status_code", 502)
        raise HTTPException(
            status_code=status_code,
            detail=str(error),
        ) from error

    return {"status": "password-set"}


@app.post(
    "/internal/v1/roles",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_service_token)],
)
def create_custom_role(request: CustomRoleCreateRequest) -> dict[str, Any]:
    """Persist one already-authorized custom role."""
    try:
        permissions = frozenset(request.permissions)
        _validate_custom_role_permissions(permissions)
        role = _custom_role_store().create(
            CustomRoleDefinition(
                name=request.name,
                display_name=request.display_name,
                description=request.description,
                permissions=permissions,
                assignable=request.assignable,
            )
        )
    except (CustomRoleError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return _custom_role_payload(role)


@app.patch(
    "/internal/v1/roles/{role_name}",
    dependencies=[Depends(_require_service_token)],
)
def update_custom_role(role_name: str, request: CustomRoleUpdateRequest) -> dict[str, Any]:
    """Persist one already-authorized custom-role update."""
    changes = request.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one role update field is required.")
    try:
        store = _custom_role_store()
        current = store.get(role_name)

        if current is None:
            raise CustomRoleError("Custom role not found.")

        effective_permissions = frozenset(
            changes.get("permissions", current.permissions)
        )
        _validate_custom_role_permissions(effective_permissions)
        role = store.update(
            role_name,
            display_name=changes.get(
                "display_name",
                current.display_name,
            ),
            description=changes.get(
                "description",
                current.description,
            ),
            permissions=changes.get(
                "permissions",
                current.permissions,
            ),
            assignable=changes.get(
                "assignable",
                current.assignable,
            ),
        )
    except (CustomRoleError, ValueError) as error:
        message = str(error)
        code = status.HTTP_404_NOT_FOUND if "not found" in message.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=message) from error
    return _custom_role_payload(role)


@app.delete(
    "/internal/v1/roles/{role_name}",
    dependencies=[Depends(_require_service_token)],
)
def delete_custom_role(role_name: str) -> dict[str, Any]:
    """Delete an unassigned custom role without touching user profiles."""
    assigned_roles = {
        role
        for profile in _user_store().list_users()
        for role in profile["roles"]
    }
    try:
        _custom_role_store().delete(role_name, assigned_roles=assigned_roles)
    except CustomRoleError as error:
        message = str(error)
        code = status.HTTP_404_NOT_FOUND if "not found" in message.lower() else status.HTTP_409_CONFLICT
        raise HTTPException(status_code=code, detail=message) from error
    return {"status": "deleted", "name": role_name.strip().lower()}


@app.post(
    "/internal/v1/invitations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_service_token)],
)
def create_invitation(
    request: InvitationCreateRequest,
) -> dict[str, Any]:
    """Create an invitation in canonical Atlas identity storage."""

    try:
        _assert_role_assignable(request.role)
        issue = _invitation_store().create(
            email=request.email,
            role=request.role,
            created_by=request.created_by,
            expires_in=timedelta(
                days=request.days,
            ),
        )
    except (CustomRoleError, InvitationError, UserProfileError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error

    return {
        "invitation": issue.invitation,
        "token": issue.token,
    }


@app.post(
    "/internal/v1/invitations/{invite_id}/revoke",
    dependencies=[Depends(_require_service_token)],
)
def revoke_invitation(
    invite_id: str,
    request: InvitationRevokeRequest,
) -> dict[str, Any]:
    """Revoke an invitation after API authorization has succeeded."""

    try:
        return _invitation_store().revoke(
            invite_id,
            revoked_by=request.revoked_by,
        )
    except InvitationError as error:
        message = str(error)

        if "not found" in message.lower():
            code = status.HTTP_404_NOT_FOUND
        else:
            code = status.HTTP_409_CONFLICT

        raise HTTPException(
            status_code=code,
            detail=message,
        ) from error


@app.patch(
    "/internal/v1/live-session-policy/default",
    dependencies=[Depends(_require_service_token)],
)
def set_live_session_default_limit(
    request: LiveSessionLimitRequest,
) -> dict[str, int]:
    """Persist one already-authorized global Live-session limit."""
    try:
        limit = default_live_session_policy_store().set_default_limit(request.limit)
    except LiveSessionPolicyError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return {"default_limit": limit}


@app.put(
    "/internal/v1/live-session-policy/users/{user_id}",
    dependencies=[Depends(_require_service_token)],
)
def set_live_session_user_override(
    user_id: str,
    request: LiveSessionLimitRequest,
) -> dict[str, Any]:
    """Persist one already-authorized per-user Live-session override."""
    try:
        limit = default_live_session_policy_store().set_override(
            user_id,
            request.limit,
        )
    except LiveSessionPolicyError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return {"user_id": user_id.strip(), "override_limit": limit}


@app.delete(
    "/internal/v1/live-session-policy/users/{user_id}",
    dependencies=[Depends(_require_service_token)],
)
def clear_live_session_user_override(user_id: str) -> dict[str, Any]:
    """Remove one already-authorized per-user Live-session override."""
    try:
        default_live_session_policy_store().clear_override(user_id)
    except LiveSessionPolicyError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error
    return {"user_id": user_id.strip(), "override_limit": None}


def main() -> None:
    """Run the private identity-writer ASGI application."""

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        default="127.0.0.1",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
    )
    args = parser.parse_args()

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
