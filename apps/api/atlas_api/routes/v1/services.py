"""Service Lifecycle reports and admin host maintenance routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from typing import Annotated, Final
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Response,
    status,
)

from atlas.service_lifecycle import (
    ImageReference,
    ServiceLifecycleError,
    ServiceLifecycleService,
    ServiceMaintenanceHistoryService,
    ServiceUpdatePlan,
    ServiceUpdateService,
    UpdateStatus,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_service_lifecycle_service,
    get_service_maintenance_history_service,
    get_service_update_service,
)
from atlas_api.schemas.service_lifecycle import (
    ManagedServiceDetailResponse,
    ManagedServiceListResponse,
    ServiceLifecycleHealthResponse,
    ServiceLifecycleSummaryResponse,
    ServiceMaintenanceHistoryResponse,
    ServiceUpdateReportResponse,
)
from atlas_api.security import require_permission, require_role
from atlas_api.service_maintenance import (
    ServiceMaintenanceClient, ServiceMaintenanceError, get_service_maintenance_client,
)



SERVICE_LIFECYCLE_READ_PERMISSION: Final = (
    "system.health.read"
)

router = APIRouter(
    prefix="/services",
    tags=["services"],
)

require_service_lifecycle_read = require_permission(
    SERVICE_LIFECYCLE_READ_PERMISSION
)


@router.get(
    "",
    response_model=ManagedServiceListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Atlas-managed services",
)
def list_managed_services(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_service_lifecycle_read),
    ],
    service: Annotated[
        ServiceLifecycleService,
        Depends(get_service_lifecycle_service),
    ],
) -> ManagedServiceListResponse:
    """Return normalized configured managed-service identities."""

    try:
        services = service.list_services()
    except ServiceLifecycleError as error:
        raise _unavailable() from error

    return ManagedServiceListResponse.from_domain(
        services
    )


@router.get(
    "/health",
    response_model=ServiceLifecycleHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Read aggregate Atlas service health",
)
def read_service_lifecycle_health(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_service_lifecycle_read),
    ],
    service: Annotated[
        ServiceLifecycleService,
        Depends(get_service_lifecycle_service),
    ],
) -> ServiceLifecycleHealthResponse:
    """Return aggregate health for configured managed services."""

    try:
        health = service.inspect_health_report()
    except ServiceLifecycleError as error:
        raise _unavailable() from error

    return ServiceLifecycleHealthResponse.from_domain(
        health
    )


@router.get(
    "/summary",
    response_model=ServiceLifecycleSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Read Atlas infrastructure summary",
)
def read_service_lifecycle_summary(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_service_lifecycle_read),
    ],
    service: Annotated[
        ServiceLifecycleService,
        Depends(get_service_lifecycle_service),
    ],
) -> ServiceLifecycleSummaryResponse:
    """Return the normalized read-only infrastructure summary."""

    try:
        summary = service.inspect_summary()
    except ServiceLifecycleError as error:
        raise _unavailable() from error

    return ServiceLifecycleSummaryResponse.from_domain(
        summary
    )


@router.get(
    "/updates",
    response_model=ServiceUpdateReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Read Atlas service update availability",
)
def read_service_updates(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_service_lifecycle_read),
    ],
    service: Annotated[
        ServiceUpdateService,
        Depends(get_service_update_service),
    ],
) -> ServiceUpdateReportResponse:
    """Return canonical read-only Update Discovery metadata."""

    try:
        report = service.inspect_updates()
    except ServiceLifecycleError as error:
        raise _unavailable() from error

    return ServiceUpdateReportResponse.from_domain(
        report
    )


require_bazarr_preview_admin = require_role("global_admin")
BAZARR_IMAGE_REPOSITORY = "lscr.io/linuxserver/bazarr"
SHA256_DIGEST = re.compile(r"sha256:[a-f0-9]{64}")


def _host_request(client: ServiceMaintenanceClient, operation: str, actor: str | None = None) -> dict:
    try:
        return client.request(operation, actor)
    except ServiceMaintenanceError as error:
        code = str(error)
        conflict = code in {"operation_busy", "maintenance_required", "reviewed_operation_unavailable"}
        raise HTTPException(
            status_code=409 if conflict else 503,
            detail={
                "code": code,
                "message": {
                    "operation_busy": "A service operation is already running.",
                    "maintenance_required": "Enable maintenance mode before changing services.",
                    "reviewed_operation_unavailable": "No reviewed operation is available.",
                }.get(code, "Service maintenance is unavailable."),
            },
        ) from error


@router.get("/maintenance", summary="Read host service maintenance status")
def read_host_maintenance(
    response: Response,
    _user: Annotated[AuthenticatedUser, Depends(require_bazarr_preview_admin)],
    client: Annotated[ServiceMaintenanceClient, Depends(get_service_maintenance_client)],
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return _host_request(client, "status")


@router.post("/updates/refresh", status_code=202, summary="Scan current service images")
def start_service_scan(
    response: Response,
    user: Annotated[AuthenticatedUser, Depends(require_bazarr_preview_admin)],
    client: Annotated[ServiceMaintenanceClient, Depends(get_service_maintenance_client)],
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return _host_request(client, "scan", user.user_id)


@router.post("/bazarr/apply", status_code=202, summary="Apply the reviewed Bazarr operation")
def apply_bazarr_update(
    response: Response,
    user: Annotated[AuthenticatedUser, Depends(require_bazarr_preview_admin)],
    client: Annotated[ServiceMaintenanceClient, Depends(get_service_maintenance_client)],
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return _host_request(client, "bazarr.apply", user.user_id)


@router.post("/bazarr/rollback", status_code=202, summary="Restore the reviewed Bazarr backup")
def rollback_bazarr_update(
    response: Response,
    user: Annotated[AuthenticatedUser, Depends(require_bazarr_preview_admin)],
    client: Annotated[ServiceMaintenanceClient, Depends(get_service_maintenance_client)],
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return _host_request(client, "bazarr.rollback", user.user_id)


@router.get("/bazarr/update-preview", summary="Preview a Bazarr image update")
def preview_bazarr_update(
    response: Response,
    current_user: Annotated[AuthenticatedUser, Depends(require_bazarr_preview_admin)],
    service: Annotated[ServiceUpdateService, Depends(get_service_update_service)],
) -> dict[str, object]:
    """Build a dry-run plan from trusted discovery data for the allow-listed service."""

    response.headers["Cache-Control"] = "no-store"
    try:
        update = service.inspect_update("bazarr")
        observed_at = datetime.fromisoformat(update.evaluated_at.replace("Z", "+00:00"))
        age = datetime.now(timezone.utc) - observed_at
        if age > timedelta(hours=2) or age < -timedelta(minutes=5):
            raise HTTPException(
                status_code=409,
                detail="Run a fresh service scan before preparing this update.",
            )
        available = update.available_image
        local_digest = update.details.get("local_descriptor_digest")
        if (
            update.service_identifier != "bazarr"
            or update.status is not UpdateStatus.UPDATE_AVAILABLE
            or available is None
            or update.current_image.repository != BAZARR_IMAGE_REPOSITORY
            or available.repository != BAZARR_IMAGE_REPOSITORY
            or available.tag is None
            or available.tag != update.current_image.tag
            or update.details.get("registry_comparison") is not True
            or not isinstance(local_digest, str)
            or not SHA256_DIGEST.fullmatch(local_digest)
            or not SHA256_DIGEST.fullmatch(available.digest or "")
            or local_digest == available.digest
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A verified Bazarr image update is not available to preview.",
            )

        plan = ServiceUpdatePlan(
            plan_id=uuid4().hex,
            service_identifier="bazarr",
            service_name=update.service_name,
            requested_by=current_user.user_id,
            current_image=ImageReference(
                repository=BAZARR_IMAGE_REPOSITORY,
                tag=update.current_image.tag,
                digest=local_digest,
            ),
            target_image=available,
            warnings=(
                "Execution requires a verified backup of the Bazarr configuration and database.",
                "Execution must keep the current image for rollback and verify Bazarr health after replacement.",
            ),
            details={"update_evaluated_at": update.evaluated_at},
        )
    except ServiceLifecycleError as error:
        raise _unavailable() from error

    return {"plan": plan.to_dict()}


@router.get(
    "/history",
    response_model=ServiceMaintenanceHistoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Read Atlas service maintenance history",
)
def read_service_maintenance_history(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_service_lifecycle_read),
    ],
    service: Annotated[
        ServiceMaintenanceHistoryService,
        Depends(get_service_maintenance_history_service),
    ],
) -> ServiceMaintenanceHistoryResponse:
    """Return canonical read-only Service Lifecycle maintenance history."""

    try:
        report = service.inspect_history()
    except ServiceLifecycleError as error:
        raise _unavailable() from error

    return ServiceMaintenanceHistoryResponse.from_domain(report)


@router.get(
    "/{service_identifier}",
    response_model=ManagedServiceDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Read one Atlas-managed service",
)
def read_managed_service(
    service_identifier: str,
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_service_lifecycle_read),
    ],
    service: Annotated[
        ServiceLifecycleService,
        Depends(get_service_lifecycle_service),
    ],
) -> ManagedServiceDetailResponse:
    """Return normalized detail for one managed-service identity."""

    try:
        managed_service = service.inspect_service(
            service_identifier
        )
    except ServiceLifecycleError as error:
        if _looks_not_found(error):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Atlas managed service was not found.",
            ) from error

        raise _unavailable() from error

    return ManagedServiceDetailResponse.from_domain(
        managed_service
    )


def _looks_not_found(
    error: ServiceLifecycleError,
) -> bool:
    """Classify the domain's existing unknown-service contract."""

    message = str(error).casefold()

    return (
        "not found" in message
        or "unknown service" in message
    )


def _unavailable() -> HTTPException:
    """Return a non-leaking Service Lifecycle availability error."""

    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Service Lifecycle is unavailable.",
    )


__all__ = [
    "SERVICE_LIFECYCLE_READ_PERMISSION",
    "require_service_lifecycle_read",
    "router",
]
