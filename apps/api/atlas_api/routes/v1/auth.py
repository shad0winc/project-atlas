"""Authentication routes for version 1 of the Atlas HTTP API."""

from __future__ import annotations

from fastapi import BackgroundTasks, APIRouter, Depends, HTTPException, Response, status

from atlas_api.auth.exceptions import (
    AuthenticationProviderError,
    AuthenticationRateLimitError,
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
    UpdateCurrentUserRequest,
    PasswordRecoveryRequest,
    PasswordRecoveryResetRequest,
)
from atlas_api.auth.service import AuthenticationService
from atlas_api.dependencies import (
    get_authentication_service,
    get_jwt_service,
    get_identity_writer_client,
    get_security_audit_writer,
    get_user_profile_store,
    resolve_refresh_user,
    get_password_recovery_service,
)
from atlas_api.security import require_permission
from atlas_api.services.identity_writer import IdentityWriterClient, IdentityWriterError
from atlas_api.security.dependencies import get_authorization_service
from atlas_api.security.permissions import build_authorization_subject


from atlas_api.services.password_recovery import PasswordRecoveryService, PasswordRecoveryServiceError

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)

require_current_user_read = require_permission("users.self.read")
require_current_user_update = require_permission("users.self.update")


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
    except AuthenticationRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many authentication attempts. Try again later.",
            headers={
                "Retry-After": str(error.retry_after_seconds),
            },
        ) from error
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
    audit_writer=Depends(get_security_audit_writer),
) -> TokenResponse:
    """Validate a refresh token and issue a replacement token pair."""

    try:
        user = resolve_refresh_user(
            request.refresh_token,
            jwt_service=jwt_service,
            profiles=profiles,
            audit_writer=audit_writer,
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
    audit_writer=Depends(get_security_audit_writer),
) -> Response:
    """Revoke the supplied refresh session without exposing its state."""

    try:
        user = resolve_refresh_user(
            request.refresh_token,
            jwt_service=jwt_service,
            profiles=profiles,
            audit_writer=audit_writer,
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
        username=str(profile["username"]),
        display_name=str(profile["display_name"]),
        first_name=profile.get("first_name") or None,
        last_name=profile.get("last_name") or None,
        email=profile.get("email") or None,
        discord_account=profile.get("discord_account") or None,
        email_notifications_enabled=bool(
            profile.get("email_notifications_enabled", False)
        ),
        discord_notifications_enabled=bool(
            profile.get("discord_notifications_enabled", False)
        ),
        roles=list(effective.roles),
        provider=user.provider,
        granted_permission_patterns=sorted(
            effective.granted_permissions
        ),
        denied_permission_patterns=sorted(
            effective.denied_permissions
        ),
    )


@router.patch(
    "/me",
    response_model=CurrentUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update supported authenticated Atlas user settings",
)
def update_current_user(
    request: UpdateCurrentUserRequest,
    user: AuthenticatedUser = Depends(require_current_user_update),
    writer: IdentityWriterClient = Depends(get_identity_writer_client),
    authorization=Depends(get_authorization_service),
) -> CurrentUserResponse:
    """Update only the authenticated user's supported self-service fields."""

    updates = request.model_dump(exclude_unset=True)

    if not updates:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one supported account setting is required.",
        )

    if "display_name" in updates:
        display_name = updates["display_name"]
        if not isinstance(display_name, str) or not display_name.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Display name cannot be empty.",
            )
        updates["display_name"] = display_name.strip()

    if "email" in updates:
        email = updates["email"]
        if not isinstance(email, str) or not email.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email address cannot be empty.",
            )
        updates["email"] = email.strip()

    for optional_text_field in (
        "first_name",
        "last_name",
        "discord_account",
    ):
        if optional_text_field in updates:
            value = updates[optional_text_field]
            if value is not None and not isinstance(value, str):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{optional_text_field} must be text or null.",
                )
            updates[optional_text_field] = (
                value.strip()
                if isinstance(value, str) and value.strip()
                else None
            )

    try:
        profile = writer.update_user(
            user.user_id,
            updates,
        )
    except IdentityWriterError as error:
        raise HTTPException(
            status_code=error.status_code,
            detail=str(error),
        ) from error

    effective = authorization.resolve(
        build_authorization_subject(profile)
    )

    return CurrentUserResponse(
        user_id=user.user_id,
        username=str(profile["username"]),
        display_name=str(profile["display_name"]),
        first_name=profile.get("first_name") or None,
        last_name=profile.get("last_name") or None,
        email=profile.get("email") or None,
        discord_account=profile.get("discord_account") or None,
        email_notifications_enabled=bool(
            profile.get("email_notifications_enabled", False)
        ),
        discord_notifications_enabled=bool(
            profile.get("discord_notifications_enabled", False)
        ),
        roles=list(effective.roles),
        provider=user.provider,
        granted_permission_patterns=sorted(
            effective.granted_permissions
        ),
        denied_permission_patterns=sorted(
            effective.denied_permissions
        ),
    )

@router.post(
    "/password-recovery/request",
    status_code=status.HTTP_202_ACCEPTED,
)
def request_password_recovery(
    request: PasswordRecoveryRequest,
    background_tasks: BackgroundTasks,
    service: PasswordRecoveryService = Depends(
        get_password_recovery_service
    ),
) -> dict[str, str]:
    """Request recovery without disclosing account existence."""

    background_tasks.add_task(
        service.request_reset,
        request.email,
    )

    return {
        "status": "accepted",
        "message": (
            "If an Atlas account exists for that email, "
            "a password reset link has been sent."
        ),
    }


@router.post(
    "/password-recovery/reset",
)
def reset_password_recovery(
    request: PasswordRecoveryResetRequest,
    service: PasswordRecoveryService = Depends(
        get_password_recovery_service
    ),
) -> dict[str, str]:
    """Consume one password-recovery token."""

    try:
        service.reset_password(
            token=request.token,
            new_password=request.new_password,
        )
    except PasswordRecoveryServiceError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        ) from error

    return {"status": "password-reset"}
