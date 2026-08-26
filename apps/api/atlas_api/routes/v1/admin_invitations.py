"""Administrator invitation-management routes."""

from __future__ import annotations

from datetime import timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field

from atlas.identity import IdentityPaths
from atlas.invitations import InvitationError, InvitationStore
from atlas.user_profiles import UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_user_profile_store
from atlas_api.security.dependencies import require_permission


router = APIRouter(
    prefix="/admin/invitations",
    tags=["admin-invitations"],
)


InvitationStatus = Literal[
    "pending",
    "completed",
    "revoked",
    "expired",
]

InvitationRole = Literal[
    "admin",
    "user",
]


class InvitationCreateRequest(BaseModel):
    """Restricted administrator invitation-create payload."""

    model_config = ConfigDict(extra="forbid")

    email: str | None = None
    role: InvitationRole = "user"
    days: int = Field(
        default=7,
        ge=1,
    )


def get_invitation_store(
    profiles: UserProfileStore = Depends(
        get_user_profile_store
    ),
) -> InvitationStore:
    """Return the invitation store sharing Atlas identity state."""

    store = InvitationStore(
        IdentityPaths(profiles.root)
    )

    store.initialize()

    return store


def _public_invitation(
    invitation: dict[str, Any],
) -> dict[str, Any]:
    """Return a durable administrator-safe invitation record."""

    return {
        key: value
        for key, value in invitation.items()
        if key not in {
            "token",
            "token_hash",
        }
    }


def _actor_id(
    user: AuthenticatedUser,
) -> str:
    """Return the authenticated Atlas identity reference."""

    return user.user_id


def _translate_domain_error(
    error: InvitationError,
) -> HTTPException:
    """Translate invitation-domain errors into HTTP semantics."""

    message = str(error)

    if "not found" in message.lower():
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invitation not found.",
        )

    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=message,
    )


@router.get("")
def list_admin_invitations(
    invitation_status: Annotated[
        InvitationStatus | None,
        Query(alias="status"),
    ] = None,
    _user: AuthenticatedUser = Depends(
        require_permission("users.read")
    ),
    invitations: InvitationStore = Depends(
        get_invitation_store
    ),
) -> dict[str, list[dict[str, Any]]]:
    """List administrator-visible invitations."""

    try:
        records = invitations.list(
            status=invitation_status,
        )
    except InvitationError as error:
        raise _translate_domain_error(error) from error

    return {
        "items": [
            _public_invitation(record)
            for record in records
        ]
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
def create_admin_invitation(
    payload: InvitationCreateRequest,
    user: AuthenticatedUser = Depends(
        require_permission("users.create")
    ),
    invitations: InvitationStore = Depends(
        get_invitation_store
    ),
) -> dict[str, Any]:
    """Create an invitation and disclose its token exactly once."""

    try:
        issue = invitations.create(
            email=payload.email,
            role=payload.role,
            created_by=_actor_id(user),
            expires_in=timedelta(
                days=payload.days
            ),
        )
    except InvitationError as error:
        raise _translate_domain_error(error) from error

    result = _public_invitation(
        issue.invitation
    )

    result["token"] = issue.token

    return result


@router.get("/{invite_id}")
def get_admin_invitation(
    invite_id: str,
    _user: AuthenticatedUser = Depends(
        require_permission("users.read")
    ),
    invitations: InvitationStore = Depends(
        get_invitation_store
    ),
) -> dict[str, Any]:
    """Return one administrator-visible invitation."""

    try:
        record = invitations.get(invite_id)
    except InvitationError as error:
        raise _translate_domain_error(error) from error

    return _public_invitation(record)


@router.post("/{invite_id}/revoke")
def revoke_admin_invitation(
    invite_id: str,
    user: AuthenticatedUser = Depends(
        require_permission("users.update")
    ),
    invitations: InvitationStore = Depends(
        get_invitation_store
    ),
) -> dict[str, Any]:
    """Revoke one pending invitation."""

    try:
        record = invitations.revoke(
            invite_id,
            revoked_by=_actor_id(user),
        )
    except InvitationError as error:
        raise _translate_domain_error(error) from error

    return _public_invitation(record)
