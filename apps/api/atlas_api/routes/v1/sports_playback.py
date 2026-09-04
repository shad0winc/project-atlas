# Authenticated Sports Live TV playback routes.

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import get_user_profile_store
from atlas_api.playback_capabilities import PlaybackCapabilityService
from atlas_api.routes.v1.playback import (
    get_playback_capability_service,
    get_playback_service,
)
from atlas_api.routes.v1.sports import (
    get_sports_api_service,
    require_sports_read,
)
from atlas_api.schemas.playback import PlaybackSessionResponse
from atlas_api.services.playback import (
    PlaybackNotFoundError,
    PlaybackService,
    PlaybackUnavailableError,
)
from atlas_api.services.sports import (
    SportsAPIService,
    SportsLiveTvBindingNotFoundError,
    SportsWriterTransportError,
)


router = APIRouter(prefix="/sports/live", tags=["sports"])


def _subtitle_stream_index(value: str | None) -> int | None:
    if value is None:
        return None

    normalized = value.strip().lower()
    if not normalized or normalized == "auto":
        return None
    if normalized == "off":
        return -1

    try:
        index = int(normalized)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Subtitle selection must be auto, off, "
                "or a stream index."
            ),
        ) from exc

    if index < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Subtitle stream index must be non-negative.",
        )

    return index


@router.get(
    "/{atlas_channel_id}/session",
    response_model=PlaybackSessionResponse,
    status_code=status.HTTP_200_OK,
    summary="Resolve one exact Sports Watch Live session",
)
def read_sports_live_session(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_sports_read),
    ],
    sports: Annotated[
        SportsAPIService,
        Depends(get_sports_api_service),
    ],
    profiles: Annotated[
        UserProfileStore,
        Depends(get_user_profile_store),
    ],
    playback: Annotated[
        PlaybackService,
        Depends(get_playback_service),
    ],
    capabilities: Annotated[
        PlaybackCapabilityService,
        Depends(get_playback_capability_service),
    ],
    atlas_channel_id: Annotated[
        str,
        Path(min_length=1, max_length=256),
    ],
    subtitle: Annotated[
        str | None,
        Query(max_length=16),
    ] = None,
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
        binding = sports.get_live_tv_binding(
            atlas_channel_id=atlas_channel_id
        )
    except SportsLiveTvBindingNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sports live channel is not available.",
        ) from exc
    except SportsWriterTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sports live channel resolution is unavailable.",
        ) from exc

    jellyfin_item_id = str(
        binding.get("jellyfin_item_id", "")
    ).strip()
    if (
        binding.get("atlas_channel_id") != atlas_channel_id
        or not jellyfin_item_id
    ):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sports live channel resolution is unavailable.",
        )

    try:
        session = playback.resolve_live_session(
            provider="jellyfin",
            item_id=jellyfin_item_id,
            jellyfin_user_id=jellyfin_user_id,
            subtitle_stream_index=_subtitle_stream_index(subtitle),
        )
    except PlaybackNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sports live channel is not available.",
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
