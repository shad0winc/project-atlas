"""Authenticated media-catalog routes for Atlas API v1."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
    HTTPException,
    status,
)

from atlas.media import MediaProviderError

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.media_catalog import (
    MediaCatalogItemResponse,
    MediaCatalogResponse,
)
from atlas_api.security import require_permission
from atlas_api.services.media_catalog import (
    MediaCatalogService,
    build_default_media_catalog_service,
)


router = APIRouter(
    prefix="/media/catalog",
    tags=["media"],
)


require_media_catalog_read = require_permission(
    "media.read"
)


@lru_cache(maxsize=1)
def get_media_catalog_service(
) -> MediaCatalogService:
    """Return the process-wide media catalog service."""

    return build_default_media_catalog_service()


@router.get(
    "",
    response_model=MediaCatalogResponse,
    status_code=status.HTTP_200_OK,
    summary="Read one bounded Jellyfin media catalog page",
)
def read_media_catalog(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_media_catalog_read),
    ],
    service: Annotated[
        MediaCatalogService,
        Depends(get_media_catalog_service),
    ],
    page: Annotated[
        int,
        Query(ge=1),
    ] = 1,
    page_size: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 24,
) -> MediaCatalogResponse:
    """Return one authenticated provider-backed media page."""

    try:
        catalog = service.read_page(
            page=page,
            page_size=page_size,
        )
    except MediaProviderError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media catalog is unavailable.",
        ) from error

    return MediaCatalogResponse(
        provider=catalog.provider,
        page=catalog.page,
        page_size=catalog.page_size,
        total=catalog.total,
        items=tuple(
            MediaCatalogItemResponse.from_domain(item)
            for item in catalog.items
        ),
    )
