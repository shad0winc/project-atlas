"""FastAPI dependency construction for the Atlas HTTP API."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.exceptions import TokenError
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser, TokenType
from atlas_api.auth.provider import (
    JellyfinAuthenticationClient,
    JellyfinAuthenticationProvider,
)
from atlas_api.auth.service import AuthenticationService
from atlas_api.core.settings import AtlasAPISettings


_bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_settings() -> AtlasAPISettings:
    """Return validated process-wide API settings."""

    return AtlasAPISettings.from_environment()


@lru_cache(maxsize=1)
def get_jwt_service() -> JWTService:
    """Return the process-wide JWT service."""

    return JWTService(get_settings())


@lru_cache(maxsize=1)
def get_user_profile_store() -> UserProfileStore:
    """Return the Atlas user-profile store."""

    root = Path(
        os.getenv(
            "ATLAS_USERS_DIR",
            "/mnt/storage/configs/atlas/users",
        )
    ).expanduser().resolve()

    return UserProfileStore(root)


@lru_cache(maxsize=1)
def get_jellyfin_authentication_client() -> JellyfinAuthenticationClient:
    """Return the Jellyfin authentication HTTP client."""

    base_url = os.getenv(
        "ATLAS_JELLYFIN_URL",
        "http://jellyfin:8096",
    )

    timeout_seconds = _positive_float_environment(
        "ATLAS_JELLYFIN_TIMEOUT_SECONDS",
        default=10.0,
    )

    return JellyfinAuthenticationClient(
        base_url,
        timeout_seconds=timeout_seconds,
    )


@lru_cache(maxsize=1)
def get_authentication_service() -> AuthenticationService:
    """Return the fully composed Atlas authentication service."""

    provider = JellyfinAuthenticationProvider(
        get_jellyfin_authentication_client(),
        get_user_profile_store(),
    )

    return AuthenticationService(
        provider,
        get_jwt_service(),
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _bearer_scheme
    ),
    jwt_service: JWTService = Depends(get_jwt_service),
    profiles: UserProfileStore = Depends(get_user_profile_store),
) -> AuthenticatedUser:
    """Validate an access token and resolve its active Atlas profile."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized("Bearer authentication is required.")

    try:
        claims = jwt_service.decode_token(
            credentials.credentials,
            expected_type=TokenType.ACCESS,
        )
    except TokenError as error:
        raise _unauthorized(str(error)) from error

    try:
        profile = profiles.get_user(claims.subject)
    except UserProfileError as error:
        raise _unauthorized("Authenticated Atlas user was not found.") from error

    if profile["status"] != "active":
        raise _unauthorized("Authenticated Atlas user is disabled.")

    return AuthenticatedUser(
        user_id=profile["user_id"],
        username=profile["username"],
        display_name=profile["display_name"],
        roles=tuple(profile["roles"]),
        provider="jellyfin",
        metadata={
            "jellyfin_user_id": profile.get("jellyfin_user_id"),
        },
    )


def clear_dependency_caches() -> None:
    """Clear cached dependencies for tests and controlled reconfiguration."""

    get_authentication_service.cache_clear()
    get_jellyfin_authentication_client.cache_clear()
    get_user_profile_store.cache_clear()
    get_jwt_service.cache_clear()
    get_settings.cache_clear()


def _positive_float_environment(
    name: str,
    *,
    default: float,
) -> float:
    raw_value = os.getenv(name)

    if raw_value is None:
        return default

    try:
        value = float(raw_value)
    except ValueError as error:
        raise ValueError(f"{name} must be a number.") from error

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero.")

    return value


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )
