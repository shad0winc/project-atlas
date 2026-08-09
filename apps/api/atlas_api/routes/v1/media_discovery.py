"""Authenticated read-only media discovery routes."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from atlas_api.auth.models import (
    AuthenticatedUser,
)
from atlas_api.schemas.media_discovery import (
    MediaDiscoveryPageResponse,
)
from atlas_api.security.dependencies import (
    require_permission,
)
from atlas_api.services.media_discovery import (
    MediaDiscoveryAPIService,
    MediaDiscoveryUnavailableError,
    MediaDiscoveryValidationError,
    build_default_media_discovery_api_service,
)


router = APIRouter(
    prefix="/media",
    tags=["media"],
)

require_media_discovery_read = (
    require_permission(
        "media.read"
    )
)


@lru_cache(maxsize=1)
def _cached_media_discovery_service(
) -> MediaDiscoveryAPIService:
    return (
        build_default_media_discovery_api_service()
    )


def get_media_discovery_api_service(
) -> MediaDiscoveryAPIService:
    """Return the process-cached discovery service."""

    try:
        return (
            _cached_media_discovery_service()
        )
    except MediaDiscoveryUnavailableError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Media discovery is unavailable."
            ),
        ) from exc


@router.get(
    "/search",
    response_model=MediaDiscoveryPageResponse,
)
def search_media(
    query: str = Query(
        ...,
        min_length=1,
        max_length=200,
    ),
    page: int = Query(
        1,
        ge=1,
    ),
    _user: AuthenticatedUser = Depends(require_media_discovery_read),
    service: MediaDiscoveryAPIService = Depends(
        get_media_discovery_api_service
    ),
) -> MediaDiscoveryPageResponse:
    """Search Jellyseerr-backed movie and TV discovery."""

    try:
        result = service.search(
            query,
            page=page,
        )
    except MediaDiscoveryValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Media search query is invalid."
            ),
        ) from exc
    except MediaDiscoveryUnavailableError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Media discovery is unavailable."
            ),
        ) from exc

    return (
        MediaDiscoveryPageResponse
        .from_domain(result)
    )


@router.get(
    "/discover",
    response_model=MediaDiscoveryPageResponse,
)
def discover_media(
    media_type: Literal[
        "movie",
        "tv",
    ] = Query(...),
    page: int = Query(
        1,
        ge=1,
    ),
    _user: AuthenticatedUser = Depends(require_media_discovery_read),
    service: MediaDiscoveryAPIService = Depends(
        get_media_discovery_api_service
    ),
) -> MediaDiscoveryPageResponse:
    """Browse one Jellyseerr movie or TV discovery page."""

    try:
        result = service.discover(
            media_type,
            page=page,
        )
    except MediaDiscoveryValidationError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_400_BAD_REQUEST
            ),
            detail=(
                "Media discovery request is invalid."
            ),
        ) from exc
    except MediaDiscoveryUnavailableError as exc:
        raise HTTPException(
            status_code=(
                status.HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Media discovery is unavailable."
            ),
        ) from exc

    return (
        MediaDiscoveryPageResponse
        .from_domain(result)
    )
