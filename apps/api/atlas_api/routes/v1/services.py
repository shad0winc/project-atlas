"""Read-only Service Lifecycle routes for version 1 of the Atlas HTTP API."""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from atlas.service_lifecycle import (
    ServiceLifecycleError,
    ServiceLifecycleService,
    ServiceUpdateService,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_service_lifecycle_service,
    get_service_update_service,
)
from atlas_api.schemas.service_lifecycle import (
    ManagedServiceDetailResponse,
    ManagedServiceListResponse,
    ServiceLifecycleHealthResponse,
    ServiceLifecycleSummaryResponse,
    ServiceUpdateReportResponse,
)
from atlas_api.security import require_permission


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
