"""FastAPI dependency construction for the Atlas HTTP API."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from atlas.operations import (
    FileOperationsRepository,
    HostOperationsContextProvider,
    OperationsComparisonService,
    OperationsRepository,
    OperationsService,
)
from atlas.operations.collectors import (
    DockerCollector,
    SystemCollector,
)
from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.exceptions import TokenError
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser, TokenType
from atlas_api.auth.provider import (
    JellyfinAuthenticationClient,
    JellyfinAuthenticationProvider,
)
from atlas_api.auth.service import AuthenticationService
from atlas_api.auth.sessions import RefreshSessionRegistry
from atlas_api.core.settings import AtlasAPISettings
from atlas_api.services import (
    DashboardMediaSummaryService,
    DashboardSummaryService,
    PortalDashboardService,
    SchedulerDashboardService,
)


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
def get_refresh_session_registry() -> RefreshSessionRegistry:
    """Return process-local single-use refresh-session state."""

    return RefreshSessionRegistry()


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
        get_refresh_session_registry(),
    )


@lru_cache(maxsize=1)
def get_dashboard_summary_service() -> DashboardSummaryService:
    """Return the process-wide operational dashboard service."""

    return DashboardSummaryService()


@lru_cache(maxsize=1)
def get_dashboard_media_summary_service(
) -> DashboardMediaSummaryService:
    """Return the configured media dashboard service."""

    configured_path = os.getenv(
        "ATLAS_ARI_LATEST_PATH",
        "/mnt/storage/configs/atlas/ari/latest.json",
    )

    normalized_path = configured_path.strip()

    if not normalized_path:
        raise ValueError(
            "ATLAS_ARI_LATEST_PATH cannot be empty"
        )

    return DashboardMediaSummaryService(
        Path(normalized_path),
    )


@lru_cache(maxsize=1)
def get_scheduler_dashboard_service() -> SchedulerDashboardService:
    """Return the process-wide scheduler dashboard adapter."""

    from atlas.scheduler import TaskScheduler

    return SchedulerDashboardService(
        TaskScheduler(),
    )


@lru_cache(maxsize=1)
def get_task_scheduler():
    """Return the Atlas scheduler runtime reader."""

    from atlas.scheduler import TaskScheduler

    return TaskScheduler(
        Path(
            os.getenv(
                "ATLAS_SCHEDULER_STATE_FILE",
                "/mnt/storage/configs/atlas/scheduler/tasks.json",
            )
        )
    )


@lru_cache(maxsize=1)
def get_scheduler_dashboard_service() -> SchedulerDashboardService:
    """Return the Portal scheduler widget adapter."""

    return SchedulerDashboardService(
        get_task_scheduler(),
    )


@lru_cache(maxsize=1)
def get_portal_dashboard_service() -> PortalDashboardService:
    """Return the process-wide aggregate Portal service."""

    return PortalDashboardService(
        get_dashboard_summary_service(),
        get_dashboard_media_summary_service(),
        get_operations_repository(),
        get_scheduler_dashboard_service(),
        get_operations_comparison_service(),
    )


@lru_cache(maxsize=1)
def get_operations_service() -> OperationsService:
    """Return the process-wide live Operations service."""

    return OperationsService(
        collectors=(
            SystemCollector(),
            DockerCollector(),
        ),
        context_provider=HostOperationsContextProvider(),
    )


@lru_cache(maxsize=1)
def get_operations_comparison_service() -> OperationsComparisonService:
    """Return the process-wide Operations comparison service."""

    return OperationsComparisonService()


@lru_cache(maxsize=1)
def get_operations_repository() -> OperationsRepository:
    """Return the configured Operations report repository."""

    configured_root = os.getenv(
        "ATLAS_OPERATIONS_DIRECTORY",
    )

    if configured_root is None:
        return FileOperationsRepository()

    normalized_root = configured_root.strip()

    if not normalized_root:
        raise ValueError(
            "ATLAS_OPERATIONS_DIRECTORY cannot be empty",
        )

    return FileOperationsRepository(
        normalized_root,
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

    return _resolve_token_user(
        credentials.credentials,
        expected_type=TokenType.ACCESS,
        jwt_service=jwt_service,
        profiles=profiles,
        invalid_token_message=None,
    )


def resolve_refresh_user(
    refresh_token: str,
    *,
    jwt_service: JWTService,
    profiles: UserProfileStore,
) -> AuthenticatedUser:
    """Validate a refresh token and resolve its active Atlas profile."""

    normalized_token = refresh_token.strip()
    if not normalized_token:
        raise _unauthorized("Refresh token is invalid or expired.")

    return _resolve_token_user(
        normalized_token,
        expected_type=TokenType.REFRESH,
        jwt_service=jwt_service,
        profiles=profiles,
        invalid_token_message="Refresh token is invalid or expired.",
    )


def _resolve_token_user(
    token: str,
    *,
    expected_type: TokenType,
    jwt_service: JWTService,
    profiles: UserProfileStore,
    invalid_token_message: str | None,
) -> AuthenticatedUser:
    try:
        claims = jwt_service.decode_token(
            token,
            expected_type=expected_type,
        )
    except TokenError as error:
        message = invalid_token_message or str(error)
        raise _unauthorized(message) from error

    try:
        profile = profiles.get_user(claims.subject)
    except UserProfileError as error:
        message = (
            invalid_token_message
            or "Authenticated Atlas user was not found."
        )
        raise _unauthorized(message) from error

    if profile["status"] != "active":
        message = (
            invalid_token_message
            or "Authenticated Atlas user is disabled."
        )
        raise _unauthorized(message)

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
    get_dashboard_media_summary_service.cache_clear()
    get_dashboard_summary_service.cache_clear()
    get_jellyfin_authentication_client.cache_clear()
    get_operations_comparison_service.cache_clear()
    get_operations_repository.cache_clear()
    get_operations_service.cache_clear()
    get_scheduler_dashboard_service.cache_clear()
    get_task_scheduler.cache_clear()
    get_portal_dashboard_service.cache_clear()
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
