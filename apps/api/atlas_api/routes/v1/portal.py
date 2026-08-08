"""Portal routes for version 1 of the Atlas HTTP API."""

from __future__ import annotations

from typing import Annotated, Final

from fastapi import APIRouter, Depends, status

from atlas_api.adapters import success_envelope
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_portal_dashboard_service
from atlas_api.schemas import ApiSuccessEnvelopeSchema
from atlas_api.security import require_permission
from atlas_api.services import PortalDashboardService


PORTAL_DASHBOARD_PERMISSIONS: Final = (
    "atlas.dashboard.read",
    "media.read",
    "system.health.read",
)


router = APIRouter(
    prefix="/portal",
    tags=["portal"],
)


require_portal_dashboard_read = require_permission(
    PORTAL_DASHBOARD_PERMISSIONS[0]
)
require_portal_media_read = require_permission(
    PORTAL_DASHBOARD_PERMISSIONS[1]
)
require_portal_operations_read = require_permission(
    PORTAL_DASHBOARD_PERMISSIONS[2]
)


@router.get(
    "/dashboard",
    response_model=ApiSuccessEnvelopeSchema,
    status_code=status.HTTP_200_OK,
    summary="Read the aggregate Atlas Portal dashboard",
)
def read_portal_dashboard(
    _dashboard_user: Annotated[
        AuthenticatedUser,
        Depends(require_portal_dashboard_read),
    ],
    _media_user: Annotated[
        AuthenticatedUser,
        Depends(require_portal_media_read),
    ],
    _operations_user: Annotated[
        AuthenticatedUser,
        Depends(require_portal_operations_read),
    ],
    service: Annotated[
        PortalDashboardService,
        Depends(get_portal_dashboard_service),
    ],
) -> ApiSuccessEnvelopeSchema:
    """Return one aggregate, read-only Portal dashboard."""

    dashboard = service.read_dashboard()

    return success_envelope(
        {
            "dashboard": dashboard.model_dump(
                mode="json",
            ),
        },
        generated_at=dashboard.operational.generated_at,
    )


__all__ = [
    "PORTAL_DASHBOARD_PERMISSIONS",
    "read_portal_dashboard",
    "require_portal_dashboard_read",
    "require_portal_media_read",
    "require_portal_operations_read",
    "router",
]
