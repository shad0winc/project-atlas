"""Authenticated playback routes for Atlas API v1."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, status

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_settings, get_user_profile_store
from atlas_api.playback_capabilities import PlaybackCapabilityService
from atlas_api.schemas.playback import (
    PlaybackActionResponse,
    PlaybackSessionResponse,
)
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


@lru_cache(maxsize=1)
def get_playback_capability_service() -> PlaybackCapabilityService:
    return PlaybackCapabilityService(get_settings())


@router.get(
    "/{provider}/{item_id}/session",
    response_model=PlaybackSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve one safe Atlas Theater playback session",
)
def read_playback_session(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_playback_read),
    ],
    profiles: Annotated[
        UserProfileStore,
        Depends(get_user_profile_store),
    ],
    service: Annotated[
        PlaybackService,
        Depends(get_playback_service),
    ],
    capabilities: Annotated[
        PlaybackCapabilityService,
        Depends(get_playback_capability_service),
    ],
    provider: Annotated[str, Path(min_length=1, max_length=32)],
    item_id: Annotated[str, Path(min_length=1, max_length=256)],
) -> PlaybackSessionResponse:
    try:
        profile = profiles.get_user(current_user.user_id)
    except UserProfileError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authenticated Atlas user was not found.",
        ) from exc

    jellyfin_user_id = profile.get("jellyfin_user_id")
    if (
        not isinstance(jellyfin_user_id, str)
        or not jellyfin_user_id.strip()
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback is not configured for this user.",
        )

    try:
        session = service.resolve_library_session(
            provider=provider,
            item_id=item_id,
            jellyfin_user_id=jellyfin_user_id,
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

    capability = capabilities.create_bootstrap(
        user_id=current_user.user_id,
        playable_target_id=session.playable_target_id,
        stream_path=session.stream_path,
    )

    return PlaybackSessionResponse.from_domain(
        session,
        playback_bootstrap_url=(
            "https://playback.shadowinc.co/_atlas/playback/bootstrap"
        ),
        playback_capability=capability,
    )


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
