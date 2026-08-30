"""Read-only Downloads routes for version 1 of the Atlas HTTP API."""
from __future__ import annotations
from typing import Annotated, Final
from fastapi import APIRouter, Depends, HTTPException, status
from atlas.downloads import DownloadsError, DownloadsService
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_downloads_service
from atlas_api.schemas.downloads import DownloadsResponse
from atlas_api.security import require_permission

DOWNLOADS_READ_PERMISSION: Final = "monitoring.read"
router = APIRouter(prefix="/downloads", tags=["downloads"])
require_downloads_read = require_permission(DOWNLOADS_READ_PERMISSION)

@router.get("", response_model=DownloadsResponse, status_code=status.HTTP_200_OK, summary="Read bounded download activity")
def read_downloads(
    _current_user: Annotated[AuthenticatedUser, Depends(require_downloads_read)],
    service: Annotated[DownloadsService, Depends(get_downloads_service)],
) -> DownloadsResponse:
    try:
        snapshot = service.current()
    except DownloadsError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Downloads runtime data is unavailable.") from error
    return DownloadsResponse.from_domain(snapshot)

__all__ = ["DOWNLOADS_READ_PERMISSION", "require_downloads_read", "router"]
