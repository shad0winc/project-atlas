"""Authenticated playback routes for Atlas API v1."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.playback import PlaybackActionResponse
from atlas_api.security import require_permission
from atlas_api.services.playback import (
    PlaybackNotFoundError,
    PlaybackService,
    PlaybackUnavailableError,
    build_default_playback_service,
)


router = APIRouter(prefix="/media/playback", tags=["media"])
require_playback_read = require_permission("media.read")


@lru_cache(maxsize=1)
def get_playback_service() -> PlaybackService:
    return build_default_playback_service()


@router.get(
    "/{provider}/{item_id}",
    response_model=PlaybackActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve one safe Atlas playback action",
)
def read_playback_action(
    _current_user: Annotated[
        AuthenticatedUser,
        Depends(require_playback_read),
    ],
    service: Annotated[
        PlaybackService,
        Depends(get_playback_service),
    ],
    provider: Annotated[str, Path(min_length=1, max_length=32)],
    item_id: Annotated[str, Path(min_length=1, max_length=256)],
) -> PlaybackActionResponse:
    try:
        action = service.resolve_library_item(
            provider=provider,
            item_id=item_id,
        )
    except PlaybackNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Playback target was not found.",
        ) from exc
    except PlaybackUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback is not configured.",
        ) from exc

    return PlaybackActionResponse.from_domain(action)
