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
    get_sports_resource_pool,
    get_sports_session_registry,
    get_user_profile_store,
)
from atlas_api.playback_capabilities import PlaybackCapabilityService
from atlas.sports_resource_pool import (
    SportsResourceLeaseNotFound,
    SportsResourcePool,
    SportsResourcePoolExhausted,
    SportsResourcePoolStateError,
    SportsResourceUserLimitExceeded,
)
from atlas.sports_session_registry import (
    SportsSessionLimitExceeded,
    SportsSessionNotFound,
    SportsSessionRegistry,
    SportsSessionStateError,
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


_SPORTS_SOURCE_KIND_ORDER = {
    "licensed_subscription": 0,
    "official_free": 1,
    "user_owned_ota": 2,
    "community_public": 3,
}
_MAX_SPORTS_SOURCE_CANDIDATES = 4


def _sports_resource_candidates(
    *,
    atlas_channel_id: str,
    live_sources: list[dict[str, object]],
    source_registry: dict[
        str,
        list[dict[str, object]],
    ],
) -> tuple[
    tuple[str, ...],
    dict[str, int],
]:
    matching = [
        source
        for source in live_sources
        if source.get("atlas_channel_id")
        == atlas_channel_id
    ]

    if len(matching) != 1:
        raise SportsWriterTransportError(
            "Private Sports service returned ambiguous "
            "LiveSource resource metadata."
        )

    raw_resource_ids = matching[0].get(
        "resource_source_ids"
    )

    if (
        not isinstance(raw_resource_ids, list)
        or not raw_resource_ids
    ):
        raise SportsWriterTransportError(
            "Sports LiveSource has no configured "
            "resource association."
        )

    associated_ids: list[str] = []

    for raw_source_id in raw_resource_ids:
        if (
            not isinstance(raw_source_id, str)
            or not raw_source_id.strip()
        ):
            raise SportsWriterTransportError(
                "Sports LiveSource resource association "
                "is invalid."
            )

        associated_ids.append(
            raw_source_id.strip()
        )

    raw_sources = source_registry.get(
        "sources"
    )

    if not isinstance(raw_sources, list):
        raise SportsWriterTransportError(
            "Sports source registry is unavailable."
        )

    by_id: dict[
        str,
        dict[str, object],
    ] = {}

    for raw in raw_sources:
        if not isinstance(raw, dict):
            raise SportsWriterTransportError(
                "Sports source registry entry is invalid."
            )

        raw_source_id = raw.get(
            "source_id"
        )

        if (
            not isinstance(raw_source_id, str)
            or not raw_source_id.strip()
        ):
            raise SportsWriterTransportError(
                "Sports source registry entry is invalid."
            )

        source_id = raw_source_id.strip()

        if source_id in by_id:
            raise SportsWriterTransportError(
                "Sports source registry contains "
                "duplicate source identity."
            )

        by_id[source_id] = raw

    eligible: list[
        tuple[int, int, str, int]
    ] = []

    for source_id in associated_ids:
        source = by_id.get(
            source_id
        )

        if source is None:
            continue

        enabled = source.get(
            "enabled"
        )
        kind = source.get(
            "kind"
        )
        priority = source.get(
            "priority"
        )
        capacity = source.get(
            "max_connections"
        )

        if not isinstance(enabled, bool):
            raise SportsWriterTransportError(
                "Sports source enabled state is invalid."
            )

        if not enabled:
            continue

        if (
            not isinstance(kind, str)
            or kind
            not in _SPORTS_SOURCE_KIND_ORDER
        ):
            raise SportsWriterTransportError(
                "Sports source kind is invalid."
            )

        if (
            isinstance(priority, bool)
            or not isinstance(priority, int)
            or priority < 0
            or priority > 10000
        ):
            raise SportsWriterTransportError(
                "Sports source priority is invalid."
            )

        if (
            isinstance(capacity, bool)
            or not isinstance(capacity, int)
            or capacity < 1
            or capacity > 1000
        ):
            raise SportsWriterTransportError(
                "Sports source capacity is invalid."
            )

        eligible.append(
            (
                _SPORTS_SOURCE_KIND_ORDER[
                    kind
                ],
                priority,
                source_id,
                capacity,
            )
        )

    eligible.sort(
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        )
    )

    selected = eligible[
        :_MAX_SPORTS_SOURCE_CANDIDATES
    ]

    if not selected:
        raise SportsResourcePoolExhausted(
            "No eligible Sports resource "
            "candidates are available."
        )

    return (
        tuple(
            item[2]
            for item in selected
        ),
        {
            item[2]: item[3]
            for item in selected
        },
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
    "/availability",
    status_code=status.HTTP_200_OK,
    summary="Resolve safe Sports Live availability for one provider event",
)
def read_sports_live_availability(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_sports_read),
    ],
    sports: Annotated[
        SportsAPIService,
        Depends(get_sports_api_service),
    ],
    provider_event_id: Annotated[
        str,
        Query(min_length=1, max_length=256),
    ],
    provider: Annotated[
        str,
        Query(min_length=1, max_length=64),
    ] = "thesportsdb",
) -> dict[str, object]:
    del current_user
    try:
        availability = sports.get_live_availability(
            provider_name=provider,
            provider_event_id=provider_event_id,
        )
    except SportsWriterTransportError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sports live availability is unavailable.",
        ) from exc

    return {
        "available": bool(availability["available"]),
        "atlas_channel_id": availability["atlas_channel_id"],
    }


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
        SportsSessionRegistry,
        Depends(get_sports_session_registry),
    ],
    resource_pool: Annotated[
        SportsResourcePool,
        Depends(get_sports_resource_pool),
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
        effective_limit = live_policy.effective_limit(current_user.user_id)
    except LiveSessionPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live playback policy is unavailable.",
        ) from exc

    try:
        live_sources = sports.list_live_sources()
        source_registry = sports.get_source_registry()

        (
            candidate_source_ids,
            capacities,
        ) = _sports_resource_candidates(
            atlas_channel_id=atlas_channel_id,
            live_sources=live_sources,
            source_registry=source_registry,
        )

        resource_lease = resource_pool.acquire(
            user_id=current_user.user_id,
            target_id=atlas_channel_id,
            candidate_source_ids=(
                candidate_source_ids
            ),
            capacities=capacities,
            user_limit=effective_limit,
        )
    except SportsResourceUserLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live session limit reached.",
        ) from exc
    except SportsResourcePoolExhausted as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sports upstream capacity is unavailable.",
        ) from exc
    except (
        SportsResourcePoolStateError,
        SportsWriterTransportError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Sports resource admission is unavailable.",
        ) from exc

    try:
        live_session = live_sessions.admit(
            user_id=current_user.user_id,
            target_id=atlas_channel_id,
            limit=effective_limit,
            resource_lease_id=(
                resource_lease.lease_id
            ),
        )
    except SportsSessionLimitExceeded as exc:
        resource_pool.release(
            lease_id=resource_lease.lease_id,
            user_id=current_user.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Live session limit reached.",
        ) from exc
    except SportsSessionStateError as exc:
        resource_pool.release(
            lease_id=resource_lease.lease_id,
            user_id=current_user.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live session admission is unavailable.",
        ) from exc
    except Exception:
        resource_pool.release(
            lease_id=resource_lease.lease_id,
            user_id=current_user.user_id,
        )
        raise

    try:
        session = playback.resolve_live_session(
            provider="jellyfin",
            item_id=jellyfin_item_id,
            jellyfin_user_id=jellyfin_user_id,
            subtitle_stream_index=_subtitle_stream_index(subtitle),
        )
    except PlaybackNotFoundError as exc:
        live_sessions.release(
            session_id=live_session.session_id,
            user_id=current_user.user_id,
        )
        resource_pool.release(
            lease_id=resource_lease.lease_id,
            user_id=current_user.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Sports live channel is not available.",
        ) from exc
    except PlaybackUnavailableError as exc:
        live_sessions.release(
            session_id=live_session.session_id,
            user_id=current_user.user_id,
        )
        resource_pool.release(
            lease_id=resource_lease.lease_id,
            user_id=current_user.user_id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Playback is not configured.",
        ) from exc
    except Exception:
        live_sessions.release(
            session_id=live_session.session_id,
            user_id=current_user.user_id,
        )
        resource_pool.release(
            lease_id=resource_lease.lease_id,
            user_id=current_user.user_id,
        )
        raise

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
        resource_pool.release(
            lease_id=resource_lease.lease_id,
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
        SportsSessionRegistry,
        Depends(get_sports_session_registry),
    ],
    resource_pool: Annotated[
        SportsResourcePool,
        Depends(get_sports_resource_pool),
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
    except SportsSessionNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live session was not found.",
        ) from exc
    except SportsSessionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live session state is unavailable.",
        ) from exc

    if record.resource_lease_id is not None:
        try:
            resource_pool.heartbeat(
                lease_id=record.resource_lease_id,
                user_id=current_user.user_id,
            )
        except (
            SportsResourceLeaseNotFound,
            SportsResourcePoolStateError,
        ) as exc:
            live_sessions.release(
                session_id=record.session_id,
                user_id=current_user.user_id,
            )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live session resource lease is unavailable.",
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
        SportsSessionRegistry,
        Depends(get_sports_session_registry),
    ],
    resource_pool: Annotated[
        SportsResourcePool,
        Depends(get_sports_resource_pool),
    ],
    session_id: Annotated[
        str,
        Path(min_length=1, max_length=256),
    ],
) -> Response:
    try:
        released = live_sessions.release_record(
            session_id=session_id,
            user_id=current_user.user_id,
        )
    except SportsSessionStateError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Live session state is unavailable.",
        ) from exc

    if released is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Live session was not found.",
        )

    if released.resource_lease_id is not None:
        try:
            resource_pool.release(
                lease_id=released.resource_lease_id,
                user_id=current_user.user_id,
            )
        except SportsResourcePoolStateError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Live session resource release is unavailable.",
            ) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
