"""Authenticated Sports routes for version 1 of the Atlas API."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Final

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.sports import (
    SportsEventListResponse,
    SportsEventResponse,
    SportsSubscriptionCreateRequest,
    SportsSubscriptionResponse,
    SportsFollowCreateRequest,
    SportsFollowListResponse,
    SportsFollowResponse,
    SportsRecordingIntentRequest,
    SportsSearchResponse,
    SportsSearchResultResponse,
)
from atlas_api.security import require_permission
from atlas_api.services.sports import (
    SportsAPIService,
    SportsEventNotFoundError,
    SportsProviderNotFoundError,
    SportsProviderRateLimitError,
    SportsRecordingTargetUnsupportedError,
    SportsSubscriptionNotFoundError,
    SportsWriterTransportError,
    build_default_sports_api_service,
)


SPORTS_READ_PERMISSION: Final = "sports.read"
SPORTS_EVENTS_REQUEST_PERMISSION: Final = (
    "sports.events.request"
)
SPORTS_RECORDINGS_MANAGE_PERMISSION: Final = (
    "sports.recordings.manage"
)

router = APIRouter(
    prefix="/sports",
    tags=["sports"],
)

require_sports_read = require_permission(
    SPORTS_READ_PERMISSION
)

require_sports_events_request = require_permission(
    SPORTS_EVENTS_REQUEST_PERMISSION
)
require_sports_recordings_manage = require_permission(
    SPORTS_RECORDINGS_MANAGE_PERMISSION
)


@lru_cache(maxsize=1)
def get_sports_api_service(
) -> SportsAPIService:
    """Return the process-wide Sports application service."""

    return build_default_sports_api_service()


@router.get(
    "/events",
    response_model=SportsEventListResponse,
    summary="List Sports events for the authenticated user",
)
def list_sports_events(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_sports_read),
    ],
    service: Annotated[
        SportsAPIService,
        Depends(get_sports_api_service),
    ],
    provider: Annotated[
        str,
        Query(min_length=1),
    ] = "thesportsdb",
    provider_event_id: Annotated[
        list[str] | None,
        Query(),
    ] = None,
    team_id: Annotated[
        list[str] | None,
        Query(),
    ] = None,
    league_id: Annotated[
        list[str] | None,
        Query(),
    ] = None,
) -> SportsEventListResponse:
    try:
        events = service.list_events_for_user(
            user_id=current_user.user_id,
            provider_name=provider,
            provider_event_ids=(
                tuple(provider_event_id)
                if provider_event_id
                else None
            ),
            team_ids=(
                tuple(team_id)
                if team_id
                else None
            ),
            league_ids=(
                tuple(league_id)
                if league_id
                else None
            ),
        )
    except SportsProviderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except SportsWriterTransportError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return SportsEventListResponse(
        events=[
            SportsEventResponse(**event)
            for event in events
        ]
    )


@router.post(
    "/subscriptions",
    response_model=SportsSubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request one Sports event",
)
def create_sports_subscription(
    request: SportsSubscriptionCreateRequest,
    response: Response,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_sports_events_request),
    ],
    service: Annotated[
        SportsAPIService,
        Depends(get_sports_api_service),
    ],
) -> SportsSubscriptionResponse:
    try:
        subscription, created = (
            service.create_event_subscription(
                user_id=current_user.user_id,
                provider_name=request.provider,
                provider_event_id=request.provider_event_id,
            )
        )
    except SportsEventNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SportsProviderNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error
    except SportsWriterTransportError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    if not created:
        response.status_code = status.HTTP_200_OK

    return SportsSubscriptionResponse(
        subscription_id=str(
            subscription["subscription_id"]
        ),
        type=str(subscription["type"]),
        provider=str(subscription["provider"]),
        provider_event_id=str(
            subscription["id"]
        ),
        name=str(subscription["name"]),
        user_id=str(subscription["user"]),
        enabled=bool(
            subscription.get("enabled", True)
        ),
        created_at=subscription["created_at"],
    )

@router.get("/search/teams", response_model=SportsSearchResponse, summary="Search Sports teams")
def search_sports_teams(
    current_user: Annotated[AuthenticatedUser, Depends(require_sports_read)],
    service: Annotated[SportsAPIService, Depends(get_sports_api_service)],
    query: Annotated[str, Query(min_length=1)],
    provider: Annotated[str, Query(min_length=1)] = "thesportsdb",
) -> SportsSearchResponse:
    try:
        items = service.search_teams(provider_name=provider, query=query)
    except SportsProviderRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Sports provider is temporarily rate limited. "
                "Try again shortly."
            ),
            headers={
                "Retry-After": str(error.retry_after_seconds),
            },
        ) from error
    except (SportsProviderNotFoundError, SportsWriterTransportError) as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return SportsSearchResponse(results=[SportsSearchResultResponse(**item) for item in items])


@router.get("/search/leagues", response_model=SportsSearchResponse, summary="Search Sports leagues")
def search_sports_leagues(
    current_user: Annotated[AuthenticatedUser, Depends(require_sports_read)],
    service: Annotated[SportsAPIService, Depends(get_sports_api_service)],
    query: Annotated[str, Query(min_length=1)],
    provider: Annotated[str, Query(min_length=1)] = "thesportsdb",
) -> SportsSearchResponse:
    try:
        items = service.search_leagues(provider_name=provider, query=query)
    except SportsProviderRateLimitError as error:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                "Sports provider is temporarily rate limited. "
                "Try again shortly."
            ),
            headers={
                "Retry-After": str(error.retry_after_seconds),
            },
        ) from error
    except (SportsProviderNotFoundError, SportsWriterTransportError) as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return SportsSearchResponse(results=[SportsSearchResultResponse(**item) for item in items])


def _follow_response(subscription: dict[str, object]) -> SportsFollowResponse:
    return SportsFollowResponse(
        subscription_id=str(subscription["subscription_id"]),
        type=str(subscription["type"]),
        provider=str(subscription["provider"]),
        provider_id=str(subscription["id"]),
        name=str(subscription["name"]),
        user_id=str(subscription["user"]),
        enabled=bool(subscription.get("enabled", True)),
        record=bool(subscription.get("record", False)),
        created_at=subscription.get("created_at"),
    )


@router.get("/follows", response_model=SportsFollowListResponse, summary="List the authenticated user's Sports follows")
def list_sports_follows(
    current_user: Annotated[AuthenticatedUser, Depends(require_sports_read)],
    service: Annotated[SportsAPIService, Depends(get_sports_api_service)],
) -> SportsFollowListResponse:
    try:
        items = service.list_subscriptions_for_user(user_id=current_user.user_id)
    except SportsWriterTransportError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    return SportsFollowListResponse(subscriptions=[_follow_response(item) for item in items])


@router.post("/follows", response_model=SportsFollowResponse, status_code=status.HTTP_201_CREATED, summary="Follow a Sports event, team, or league")
def create_sports_follow(
    request: SportsFollowCreateRequest,
    response: Response,
    current_user: Annotated[AuthenticatedUser, Depends(require_sports_events_request)],
    service: Annotated[SportsAPIService, Depends(get_sports_api_service)],
) -> SportsFollowResponse:
    subscription_type = request.type.strip().lower()
    if subscription_type not in {"event", "team", "league"}:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Sports follow type must be event, team, or league.")
    try:
        subscription, created = service.create_follow_subscription(
            user_id=current_user.user_id,
            provider_name=request.provider,
            subscription_type=subscription_type,
            provider_id=request.provider_id,
        )
    except SportsWriterTransportError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    if not created:
        response.status_code = status.HTTP_200_OK
    return _follow_response(subscription)


@router.patch(
    "/follows/{subscription_id}/recording",
    response_model=SportsFollowResponse,
    summary="Update recording intent for an event subscription",
)
def update_sports_recording_intent(
    subscription_id: str,
    request: SportsRecordingIntentRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_sports_recordings_manage),
    ],
    service: Annotated[
        SportsAPIService,
        Depends(get_sports_api_service),
    ],
) -> SportsFollowResponse:
    try:
        subscription = service.update_follow_recording(
            user_id=current_user.user_id,
            subscription_id=subscription_id,
            record=request.record,
        )
    except SportsSubscriptionNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except SportsRecordingTargetUnsupportedError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from error
    except SportsWriterTransportError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(error),
        ) from error

    return _follow_response(subscription)


@router.delete("/follows/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Unfollow a Sports event, team, or league")
def remove_sports_follow(
    subscription_id: str,
    current_user: Annotated[AuthenticatedUser, Depends(require_sports_events_request)],
    service: Annotated[SportsAPIService, Depends(get_sports_api_service)],
) -> Response:
    try:
        removed = service.remove_follow_subscription(user_id=current_user.user_id, subscription_id=subscription_id)
    except SportsWriterTransportError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(error)) from error
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sports subscription was not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
