"""Authentication routes for version 1 of the Atlas HTTP API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from atlas_api.auth.exceptions import (
    AuthenticationProviderError,
    InvalidCredentialsError,
    TokenError,
)
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.auth.schemas import (
    CurrentUserResponse,
    LoginRequest,
    RefreshRequest,
    TokenResponse,
)
from atlas_api.auth.service import AuthenticationService
from atlas_api.dependencies import (
    get_authentication_service,
    get_jwt_service,
    get_user_profile_store,
    resolve_refresh_user,
)
from atlas_api.security import require_permission
from atlas_api.security.dependencies import get_authorization_service
from atlas_api.security.permissions import build_authorization_subject


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


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate an Atlas token pair",
)
def refresh_tokens(
    request: RefreshRequest,
    authentication: AuthenticationService = Depends(
        get_authentication_service
    ),
    jwt_service: JWTService = Depends(get_jwt_service),
    profiles=Depends(get_user_profile_store),
) -> TokenResponse:
    """Validate a refresh token and issue a replacement token pair."""

    try:
        user = resolve_refresh_user(
            request.refresh_token,
            jwt_service=jwt_service,
            profiles=profiles,
        )
        tokens = authentication.refresh(
            request.refresh_token,
            user,
        )
    except (InvalidCredentialsError, TokenError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    return TokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        token_type=tokens.token_type,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an Atlas refresh session",
)
def logout(
    request: RefreshRequest,
    authentication: AuthenticationService = Depends(
        get_authentication_service
    ),
    jwt_service: JWTService = Depends(get_jwt_service),
    profiles=Depends(get_user_profile_store),
) -> Response:
    """Revoke the supplied refresh session without exposing its state."""

    try:
        user = resolve_refresh_user(
            request.refresh_token,
            jwt_service=jwt_service,
            profiles=profiles,
        )
        authentication.logout(
            request.refresh_token,
            user,
        )
    except (InvalidCredentialsError, TokenError) as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from error

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Read the authenticated Atlas user",
)
def read_current_user(
    user: AuthenticatedUser = Depends(require_current_user_read),
    profiles=Depends(get_user_profile_store),
    authorization=Depends(get_authorization_service),
) -> CurrentUserResponse:
    """Return the authenticated user and effective authorization state."""

    profile = profiles.get_user(user.user_id)
    effective = authorization.resolve(
        build_authorization_subject(profile)
    )

    return CurrentUserResponse(
        user_id=user.user_id,
        username=user.username,
        display_name=user.display_name,
        roles=list(effective.roles),
        provider=user.provider,
        granted_permission_patterns=sorted(
            effective.granted_permissions
        ),
        denied_permission_patterns=sorted(
            effective.denied_permissions
        ),
    )
