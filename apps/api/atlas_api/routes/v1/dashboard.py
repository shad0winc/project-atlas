"""Dashboard routes for version 1 of the Atlas HTTP API."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, status

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.dashboard import DashboardSummaryResponse
from atlas_api.security import require_permission
from atlas_api.services.dashboard import DashboardSummaryService


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)

require_dashboard_read = require_permission(
    "atlas.dashboard.read"
)


@lru_cache(maxsize=1)
def get_dashboard_summary_service() -> DashboardSummaryService:
    """Return the process-wide dashboard summary service."""

    return DashboardSummaryService()


@router.get(
    "/summary",
    response_model=DashboardSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Read the Atlas operational dashboard summary",
)
def read_dashboard_summary(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_dashboard_read),
    ],
    service: Annotated[
        DashboardSummaryService,
        Depends(get_dashboard_summary_service),
    ],
) -> DashboardSummaryResponse:
    """Return live operational health adapted for the Atlas Portal."""

    return service.read_summary()
