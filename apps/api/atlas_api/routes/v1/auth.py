"""Authentication routes for version 1 of the Atlas HTTP API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from atlas_api.auth.exceptions import (
    AuthenticationProviderError,
    InvalidCredentialsError,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    TokenResponse,
)
from atlas_api.auth.service import AuthenticationService
from atlas_api.dependencies import get_authentication_service
from atlas_api.security import require_permission


router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)

require_current_user_read = require_permission("users.self.read")


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate an Atlas user",
)
def login(
    request: LoginRequest,
    authentication: AuthenticationService = Depends(
        get_authentication_service
    ),
) -> TokenResponse:
    """Authenticate through Jellyfin and issue Atlas tokens."""

    try:
        tokens = authentication.login(
            request.username,
            request.password,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error
    except AuthenticationProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The authentication provider is unavailable.",
        ) from error

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Read the authenticated Atlas user",
)
def read_current_user(
    user: AuthenticatedUser = Depends(require_current_user_read),
) -> CurrentUserResponse:
    """Return the active Atlas profile represented by an access token."""

    return CurrentUserResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        roles=list(user.roles),
        provider=user.provider,
    )
