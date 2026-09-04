# Authenticated Sports Live TV playback routes.

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas.live_session_policy import (
    LiveSessionPolicyError,
    LiveSessionPolicyStore,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_live_session_policy_store,
    get_live_session_registry,
    get_user_profile_store,
)
from atlas_api.playback_capabilities import PlaybackCapabilityService
from atlas_api.live_sessions import (
    LiveSessionLimitExceeded,
    LiveSessionNotFound,
    LiveSessionRegistry,
)
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
    live_policy: Annotated[
        LiveSessionPolicyStore,
        Depends(get_live_session_policy_store),
    ],
    live_sessions: Annotated[
        LiveSessionRegistry,
        Depends(get_live_session_registry),
    ],
    response: Response,
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

    try:
        effective_limit = live_policy.effective_limit(current_user.user_id)
    except LiveSessionPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live playback policy is unavailable.",
        ) from exc

    try:
        live_session = live_sessions.admit(
            user_id=current_user.user_id,
            target_id=atlas_channel_id,
            limit=effective_limit,
        )
    except LiveSessionLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live session limit reached.",
        ) from exc

    try:
        capability = capabilities.create_bootstrap(
            user_id=current_user.user_id,
            playable_target_id=session.playable_target_id,
            stream_path=session.stream_path,
        )
    except Exception:
        live_sessions.release(
            session_id=live_session.session_id,
            user_id=current_user.user_id,
        )
        raise

    response.headers["X-Atlas-Live-Session-ID"] = live_session.session_id
    response.headers["X-Atlas-Live-Session-TTL"] = str(
        live_sessions.ttl_seconds
    )

    return PlaybackSessionResponse.from_domain(
        session,
        playback_bootstrap_url=(
            "https://playback.shadowinc.co/_atlas/playback/bootstrap"
        ),
        playback_capability=capability,
    )


@router.post(
    "/sessions/{session_id}/heartbeat",
    status_code=status.HTTP_200_OK,
    summary="Heartbeat one authenticated-user Live session",
)
def heartbeat_sports_live_session(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_sports_read),
    ],
    live_sessions: Annotated[
        LiveSessionRegistry,
        Depends(get_live_session_registry),
    ],
    session_id: Annotated[
        str,
        Path(min_length=1, max_length=256),
    ],
) -> dict[str, object]:
    try:
        record = live_sessions.heartbeat(
            session_id=session_id,
            user_id=current_user.user_id,
        )
    except LiveSessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live session was not found.",
        ) from exc

    return {
        "session_id": record.session_id,
        "active": True,
        "ttl_seconds": live_sessions.ttl_seconds,
    }


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Release one authenticated-user Live session",
)
def release_sports_live_session(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_sports_read),
    ],
    live_sessions: Annotated[
        LiveSessionRegistry,
        Depends(get_live_session_registry),
    ],
    session_id: Annotated[
        str,
        Path(min_length=1, max_length=256),
    ],
) -> Response:
    released = live_sessions.release(
        session_id=session_id,
        user_id=current_user.user_id,
    )

    if not released:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live session was not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)
