"""Authenticated single-item media-retention routes for Atlas API v1."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    status,
)

from atlas.retention import (
    RetentionError,
    RetentionService,
    default_retention_service,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.media_retention import (
    MediaRetentionResponse,
)
from atlas_api.security import require_permission


router = APIRouter(
    prefix="/media",
    tags=["media"],
)

require_media_retention_read = require_permission(
    "media.read"
)


@lru_cache(maxsize=1)
def get_media_retention_service() -> RetentionService:
    """Return the process-wide authoritative retention service."""

    return default_retention_service()


@router.get(
    "/{provider}/{item_id}/retention",
    response_model=MediaRetentionResponse,
    status_code=status.HTTP_200_OK,
    summary="Read one authoritative Atlas media-retention state",
)
def read_media_retention(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_media_retention_read),
    ],
    service: Annotated[
        RetentionService,
        Depends(get_media_retention_service),
    ],
    provider: Annotated[
        str,
        Path(min_length=1, max_length=32),
    ],
    item_id: Annotated[
        str,
        Path(min_length=1, max_length=256),
    ],
) -> MediaRetentionResponse:
    """Return authoritative retention state without recomputing policy timing."""

    try:
        decision = service.evaluate(
            provider,
            item_id,
        )
    except (RetentionError, TypeError, ValueError) as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media retention state is unavailable.",
        ) from error

    normalized_provider = provider.strip().lower()
    normalized_item_id = item_id.strip()

    if (
        decision.provider.strip().lower()
        != normalized_provider
        or decision.item_id.strip()
        != normalized_item_id
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media retention state is unavailable.",
        )

    return MediaRetentionResponse.from_domain(
        decision
    )


__all__ = [
    "get_media_retention_service",
    "read_media_retention",
    "require_media_retention_read",
    "router",
]
