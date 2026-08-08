"""Media-library detail routes for version 1 of the Atlas API."""

from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.media_library import (
    MediaLibraryDetailResponse,
)
from atlas_api.security import require_permission
from atlas_api.services.media_library import (
    MediaLibraryDetailService,
)


router = APIRouter(
    prefix="/media/libraries",
    tags=["media"],
)


require_media_library_read = require_permission(
    "media.read"
)


@lru_cache(maxsize=1)
def get_media_library_detail_service(
) -> MediaLibraryDetailService:
    """Return the process-wide media-library detail service."""

    snapshot_path = Path(
        os.getenv(
            "ATLAS_ARI_LATEST_FILE",
            "/mnt/storage/configs/atlas/ari/latest.json",
        )
    )

    return MediaLibraryDetailService(
        snapshot_path
    )


@router.get(
    "/{library_id}",
    response_model=MediaLibraryDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Read one Atlas media-library detail",
)
def read_media_library_detail(
    library_id: str,
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_media_library_read),
    ],
    service: Annotated[
        MediaLibraryDetailService,
        Depends(get_media_library_detail_service),
    ],
) -> MediaLibraryDetailResponse:
    """Return normalized detail for one Atlas media library."""

    try:
        detail = service.read_detail(
            library_id
        )
    except KeyError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Atlas media library was not found.",
        ) from error

    return MediaLibraryDetailResponse.from_domain(
        detail
    )
