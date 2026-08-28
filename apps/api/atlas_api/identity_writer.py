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
from atlas.user_profiles import UserProfileError, UserProfileStore


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
    root = Path(
        os.getenv(
            "ATLAS_USERS_DIR",
            "/mnt/storage/configs/atlas/users",
        )
    ).expanduser().resolve()

    return UserProfileStore(root)


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


class UserUpdateRequest(BaseModel):
    """Bounded identity fields accepted from the authorized Atlas API."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = None
    email: str | None = None
    status: str | None = None
    roles: list[str] | None = None


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


@app.get("/health")
def health() -> dict[str, str]:
    """Return process liveness without disclosing identity state."""

    return {
        "status": "healthy",
    }


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
        return _user_store().update_user(
            identifier,
            updates,
        )
    except UserProfileError as error:
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
    "/internal/v1/invitations",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_require_service_token)],
)
def create_invitation(
    request: InvitationCreateRequest,
) -> dict[str, Any]:
    """Create an invitation in canonical Atlas identity storage."""

    try:
        issue = _invitation_store().create(
            email=request.email,
            role=request.role,
            created_by=request.created_by,
            expires_in=timedelta(
                days=request.days,
            ),
        )
    except InvitationError as error:
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
