"""Dashboard routes for version 1 of the Atlas HTTP API."""

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, status

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_current_user
from atlas_api.schemas.dashboard import DashboardSummaryResponse
from atlas_api.services.dashboard import DashboardSummaryService


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
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
        Depends(get_current_user),
    ],
    service: Annotated[
        DashboardSummaryService,
        Depends(get_dashboard_summary_service),
    ],
) -> DashboardSummaryResponse:
    """Return live operational health adapted for the Atlas Portal."""

    return service.read_summary()
