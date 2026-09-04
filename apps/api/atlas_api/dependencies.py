"""FastAPI dependency construction for the Atlas HTTP API."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path

from atlas.downloads import DownloadsService

from atlas.service_lifecycle import (
    ServiceLifecycleService,
    ServiceMaintenanceHistoryService,
    ServiceUpdateService,
)
from atlas.service_lifecycle.providers import (
    RuntimeSnapshotProvider,
)

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
from atlas.password_recovery import (
    PasswordRecoveryStore,
    default_store as default_password_recovery_store,
)
from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas.live_session_policy import (
    LiveSessionPolicyStore,
    default_live_session_policy_store,
)
from atlas_api.auth.exceptions import TokenError
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser, TokenType
from atlas_api.auth.provider import (
    JellyfinAuthenticationClient,
    JellyfinAuthenticationProvider,
)
from atlas_api.auth.service import AuthenticationService
from atlas_api.auth.sessions import RefreshSessionRegistry
from atlas_api.live_sessions import (
    LiveSessionRegistry,
    live_session_registry_from_environment,
)
from atlas_api.auth.throttling import (
    LoginAttemptLimiter,
    PasswordRecoveryRequestLimiter,
)
from atlas_api.core.settings import AtlasAPISettings
from atlas_api.services import (
    DashboardMediaSummaryService,
    DashboardSummaryService,
    PortalDashboardService,
    SchedulerDashboardService,
)
from atlas_api.services.email_sender import SMTPEmailSender
from atlas_api.services.identity_writer import IdentityWriterClient
from atlas_api.services.password_recovery import PasswordRecoveryService


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
def get_identity_writer_client() -> IdentityWriterClient:
    """Return the private identity-mutation client."""

    url = os.getenv(
        "ATLAS_IDENTITY_WRITER_URL",
        "",
    ).strip()

    token = os.getenv(
        "ATLAS_IDENTITY_WRITER_TOKEN",
        "",
    ).strip()

    if not url:
        raise RuntimeError(
            "ATLAS_IDENTITY_WRITER_URL is required."
        )

    if not token:
        raise RuntimeError(
            "ATLAS_IDENTITY_WRITER_TOKEN is required."
        )

    return IdentityWriterClient(
        url,
        token,
    )


@lru_cache(maxsize=1)
def get_password_recovery_store() -> PasswordRecoveryStore:
    """Return durable Atlas password-recovery state."""

    return default_password_recovery_store()


@lru_cache(maxsize=1)
def get_password_recovery_email_sender() -> SMTPEmailSender:
    """Return configured SMTP transport for account recovery."""

    settings = get_settings()

    if not settings.smtp_host:
        raise RuntimeError("ATLAS_SMTP_HOST is required.")

    if not settings.smtp_sender:
        raise RuntimeError("ATLAS_SMTP_SENDER is required.")

    return SMTPEmailSender(
        host=settings.smtp_host,
        port=settings.smtp_port,
        sender=settings.smtp_sender,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        security=settings.smtp_security,
    )


@lru_cache(maxsize=1)
def get_password_recovery_request_limiter() -> PasswordRecoveryRequestLimiter:
    """Return process-local password-recovery request state."""

    return PasswordRecoveryRequestLimiter()


@lru_cache(maxsize=1)
def get_password_recovery_service() -> PasswordRecoveryService:
    """Return the fully composed password-recovery service."""

    settings = get_settings()

    return PasswordRecoveryService(
        users=get_user_profile_store(),
        recoveries=get_password_recovery_store(),
        identity_writer=get_identity_writer_client(),
        email_sender=get_password_recovery_email_sender(),
        base_url=settings.base_url,
        expires_minutes=settings.password_recovery_minutes,
        audit_publisher=get_security_audit_writer().publish,
        request_limiter=get_password_recovery_request_limiter(),
        refresh_sessions=get_refresh_session_registry(),
    )


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
def get_login_attempt_limiter() -> LoginAttemptLimiter:
    """Return process-local account login-attempt state."""

    return LoginAttemptLimiter()


@lru_cache(maxsize=1)
def get_live_session_policy_store() -> LiveSessionPolicyStore:
    """Return durable per-user Live playback concurrency policy."""

    store = default_live_session_policy_store()
    store.initialize()
    return store


@lru_cache(maxsize=1)
def get_live_session_registry() -> LiveSessionRegistry:
    """Return process-local heartbeat state for active Live playback."""

    return live_session_registry_from_environment()


@lru_cache(maxsize=1)
def get_downloads_writer_client():
    """Return the private Downloads mutation client."""
    from atlas_api.services.downloads_writer import DownloadsWriterClient

    return DownloadsWriterClient(
        os.environ.get("ATLAS_DOWNLOADS_WRITER_URL", "http://downloads-writer:8002"),
        os.environ.get("ATLAS_DOWNLOADS_WRITER_TOKEN", ""),
    )


@lru_cache(maxsize=1)
def get_security_audit_writer():
    """Return the process-wide credential-safe security audit writer."""

    from atlas_api.security.audit import SecurityAuditWriter

    return SecurityAuditWriter.from_environment()


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
        refresh_sessions=get_refresh_session_registry(),
        login_attempts=get_login_attempt_limiter(),
        audit_publisher=get_security_audit_writer().publish,
    )


@lru_cache(maxsize=1)
def get_dashboard_summary_service() -> DashboardSummaryService:
    """Return the process-wide operational dashboard service."""

    snapshot_path = os.getenv(
        "ATLAS_DASHBOARD_HEALTH_SNAPSHOT_PATH",
        "/mnt/storage/configs/atlas/runtime/dashboard/health.json",
    ).strip()

    if not snapshot_path:
        raise ValueError(
            "ATLAS_DASHBOARD_HEALTH_SNAPSHOT_PATH cannot be empty"
        )

    return DashboardSummaryService(
        snapshot_path=Path(snapshot_path),
    )


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
    from atlas_api.services.scheduler_dashboard import RuntimeSchedulerProvider
    snapshot_path = os.getenv(
        "ATLAS_DASHBOARD_SCHEDULER_SNAPSHOT_PATH",
        "/mnt/storage/configs/atlas/runtime/dashboard/scheduler.json",
    ).strip()
    if not snapshot_path:
        raise ValueError("ATLAS_DASHBOARD_SCHEDULER_SNAPSHOT_PATH cannot be empty")
    return SchedulerDashboardService(
        RuntimeSchedulerProvider(Path(snapshot_path))
    )


@lru_cache(maxsize=1)
def get_portal_operations_repository() -> FileOperationsRepository:
    """Return the bounded Operations repository used by the Portal dashboard."""

    configured_root = os.getenv(
        "ATLAS_DASHBOARD_OPERATIONS_DIRECTORY",
        "/mnt/storage/configs/atlas/runtime/dashboard/operations/current",
    ).strip()

    if not configured_root:
        raise ValueError(
            "ATLAS_DASHBOARD_OPERATIONS_DIRECTORY cannot be empty"
        )

    return FileOperationsRepository(Path(configured_root))


@lru_cache(maxsize=1)
def get_portal_dashboard_service() -> PortalDashboardService:
    """Return the process-wide aggregate Portal service."""

    return PortalDashboardService(
        get_dashboard_summary_service(),
        get_dashboard_media_summary_service(),
        get_portal_operations_repository(),
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



@lru_cache(maxsize=1)
def get_downloads_service() -> DownloadsService:
    """Return the process-wide read-only Downloads service."""
    snapshot_path = Path(
        os.environ.get(
            "ATLAS_DOWNLOADS_SNAPSHOT_PATH",
            "/mnt/storage/configs/atlas/runtime/downloads/latest.json",
        )
    )
    return DownloadsService(snapshot_path)


@lru_cache(maxsize=1)
def get_service_lifecycle_service() -> ServiceLifecycleService:
    """Return the process-wide read-only Service Lifecycle service."""

    snapshot_path = Path(
        os.environ.get(
            "ATLAS_SERVICE_LIFECYCLE_SNAPSHOT_PATH",
            (
                "/mnt/storage/configs/atlas/runtime/"
                "services/latest.json"
            ),
        )
    )

    provider = RuntimeSnapshotProvider(
        snapshot_path
    )

    return ServiceLifecycleService(provider)


@lru_cache(maxsize=1)
def get_service_update_service() -> ServiceUpdateService:
    """Return the process-wide read-only Update Discovery service."""

    return ServiceUpdateService(
        get_service_lifecycle_service()
    )


@lru_cache(maxsize=1)
def get_service_maintenance_history_service(
) -> ServiceMaintenanceHistoryService:
    """Return the process-wide read-only Maintenance History service."""

    return ServiceMaintenanceHistoryService(
        get_service_lifecycle_service()
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        _bearer_scheme
    ),
    jwt_service: JWTService = Depends(get_jwt_service),
    profiles: UserProfileStore = Depends(get_user_profile_store),
    audit_writer=Depends(get_security_audit_writer),
) -> AuthenticatedUser:
    """Validate an access token and resolve its active Atlas profile."""

    if credentials is None or credentials.scheme.lower() != "bearer":
        _publish_credential_rejection(
            audit_writer,
            "security.authentication.access_rejected",
            reason="missing_bearer",
        )
        raise _unauthorized("Bearer authentication is required.")

    return _resolve_token_user(
        credentials.credentials,
        expected_type=TokenType.ACCESS,
        jwt_service=jwt_service,
        profiles=profiles,
        invalid_token_message=None,
        audit_writer=audit_writer,
        rejection_event="security.authentication.access_rejected",
    )


def resolve_refresh_user(
    refresh_token: str,
    *,
    jwt_service: JWTService,
    profiles: UserProfileStore,
    audit_writer=None,
) -> AuthenticatedUser:
    """Validate a refresh token and resolve its active Atlas profile."""

    normalized_token = refresh_token.strip()
    if not normalized_token:
        _publish_credential_rejection(
            audit_writer,
            "security.session.credential_rejected",
            reason="missing_value",
        )
        raise _unauthorized("Refresh token is invalid or expired.")

    return _resolve_token_user(
        normalized_token,
        expected_type=TokenType.REFRESH,
        jwt_service=jwt_service,
        profiles=profiles,
        invalid_token_message="Refresh token is invalid or expired.",
        audit_writer=audit_writer,
        rejection_event="security.session.credential_rejected",
    )


def _resolve_token_user(
    token: str,
    *,
    expected_type: TokenType,
    jwt_service: JWTService,
    profiles: UserProfileStore,
    invalid_token_message: str | None,
    audit_writer,
    rejection_event: str,
) -> AuthenticatedUser:
    try:
        claims = jwt_service.decode_token(
            token,
            expected_type=expected_type,
        )
    except TokenError as error:
        _publish_credential_rejection(
            audit_writer,
            rejection_event,
            reason="invalid_or_expired",
        )
        message = invalid_token_message or str(error)
        raise _unauthorized(message) from error

    try:
        profile = profiles.get_user(claims.subject)
    except UserProfileError as error:
        _publish_credential_rejection(
            audit_writer,
            rejection_event,
            reason="profile_unavailable",
            user_id=claims.subject,
        )
        message = (
            invalid_token_message
            or "Authenticated Atlas user was not found."
        )
        raise _unauthorized(message) from error

    if profile["status"] != "active":
        _publish_credential_rejection(
            audit_writer,
            rejection_event,
            reason="profile_inactive",
            user_id=claims.subject,
        )
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
    get_password_recovery_service.cache_clear()
    get_password_recovery_store.cache_clear()
    get_password_recovery_email_sender.cache_clear()
    get_password_recovery_request_limiter.cache_clear()
    get_refresh_session_registry.cache_clear()
    get_login_attempt_limiter.cache_clear()
    get_downloads_writer_client.cache_clear()
    get_security_audit_writer.cache_clear()
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


def _publish_credential_rejection(
    audit_writer,
    event_name: str,
    *,
    reason: str,
    user_id: str | None = None,
) -> None:
    # Direct unit calls may leave FastAPI's Depends marker unresolved. Runtime
    # requests always receive the composed SecurityAuditWriter instance.
    if not hasattr(audit_writer, "publish"):
        return

    payload = {"reason": reason}
    if user_id is not None:
        payload["user_id"] = user_id

    audit_writer.publish(event_name, payload)


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
