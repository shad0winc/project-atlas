"""Media dashboard routes for version 1 of the Atlas API."""

from functools import lru_cache
import os
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, status

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.dashboard_media import (
    DashboardMediaSummaryResponse,
)
from atlas_api.security import require_permission
from atlas_api.services.dashboard_media import (
    DashboardMediaSummaryService,
)


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)

require_media_dashboard_read = require_permission(
    "media.read"
)


@lru_cache(maxsize=1)
def get_dashboard_media_summary_service(
) -> DashboardMediaSummaryService:
    """Return the process-wide media dashboard service."""

    snapshot_path = Path(
        os.getenv(
            "ATLAS_ARI_LATEST_FILE",
            "/mnt/storage/configs/atlas/ari/latest.json",
        )
    )

    return DashboardMediaSummaryService(
        snapshot_path
    )


@router.get(
    "/media",
    response_model=DashboardMediaSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Read Atlas media-library statistics",
)
def read_dashboard_media_summary(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_media_dashboard_read),
    ],
    service: Annotated[
        DashboardMediaSummaryService,
        Depends(
            get_dashboard_media_summary_service
        ),
    ],
) -> DashboardMediaSummaryResponse:
    """Return the latest validated ARI media statistics."""

    return service.read_summary()
