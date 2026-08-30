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
)
from atlas_api.security import require_permission
from atlas_api.services.sports import (
    SportsAPIService,
    SportsEventNotFoundError,
    SportsProviderNotFoundError,
    SportsWriterTransportError,
    build_default_sports_api_service,
)


SPORTS_READ_PERMISSION: Final = "sports.read"
SPORTS_EVENTS_REQUEST_PERMISSION: Final = (
    "sports.events.request"
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
