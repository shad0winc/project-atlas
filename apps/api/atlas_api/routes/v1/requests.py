"""Authenticated self-scoped media-request routes."""

from __future__ import annotations

from functools import lru_cache

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.requests import (
    MediaRequestCreateRequest,
    MediaRequestListResponse,
    MediaRequestResponse,
)
from atlas_api.security.dependencies import require_permission
from atlas_api.services.requests import (
    MediaRequestConflictError,
    MediaRequestNotFoundError,
    MediaRequestReconciliationRequiredError,
    MediaRequestValidationError,
    MediaRequestsAPIService,
    MediaRequestsUnavailableError,
    build_default_media_requests_api_service,
)


router = APIRouter(
    prefix="/requests",
    tags=["requests"],
)

require_requests_read = require_permission(
    "requests.read"
)
require_requests_create = require_permission(
    "requests.create"
)
require_requests_cancel = require_permission(
    "requests.cancel"
)


@lru_cache(maxsize=1)
def _cached_media_requests_api_service(
) -> MediaRequestsAPIService:
    return build_default_media_requests_api_service()


def get_media_requests_api_service(
) -> MediaRequestsAPIService:
    """Return the process-cached Request application service."""

    try:
        return _cached_media_requests_api_service()
    except MediaRequestsUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media requests are unavailable.",
        ) from error


@router.get(
    "",
    response_model=MediaRequestListResponse,
)
def list_requests(
    user: AuthenticatedUser = Depends(require_requests_read),
    service: MediaRequestsAPIService = Depends(
        get_media_requests_api_service
    ),
) -> MediaRequestListResponse:
    """Return requests owned by the authenticated user."""

    try:
        requests = service.list_for_user(
            user.user_id
        )
    except MediaRequestsUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media requests are unavailable.",
        ) from error

    return MediaRequestListResponse(
        requests=tuple(
            MediaRequestResponse.from_domain(
                request
            )
            for request in requests
        )
    )


@router.post(
    "",
    response_model=MediaRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_request(
    payload: MediaRequestCreateRequest,
    user: AuthenticatedUser = Depends(require_requests_create),
    service: MediaRequestsAPIService = Depends(
        get_media_requests_api_service
    ),
) -> MediaRequestResponse:
    """Create and submit one request for the authenticated user."""

    try:
        request = service.create_for_user(
            user.user_id,
            media_type=payload.media_type,
            provider_media_id=payload.provider_media_id,
            title=payload.title,
            year=payload.year,
            season_number=payload.season_number,
        )
    except MediaRequestValidationError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Media request is invalid.",
        ) from error
    except MediaRequestReconciliationRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Media request submission requires reconciliation. "
                "Do not retry this request."
            ),
        ) from error
    except MediaRequestConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Media request conflicts with existing state.",
        ) from error
    except MediaRequestsUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media request service is unavailable.",
        ) from error

    return MediaRequestResponse.from_domain(
        request
    )


@router.post(
    "/{request_id}/cancel",
    response_model=MediaRequestResponse,
)
def cancel_request(
    request_id: str,
    user: AuthenticatedUser = Depends(require_requests_cancel),
    service: MediaRequestsAPIService = Depends(
        get_media_requests_api_service
    ),
) -> MediaRequestResponse:
    """Cancel one caller-owned request when its lifecycle permits it."""

    try:
        request = service.cancel_for_user(
            user.user_id,
            request_id,
        )
    except MediaRequestNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media request was not found.",
        ) from error
    except MediaRequestReconciliationRequiredError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Media request cancellation requires reconciliation. "
                "Do not retry this request."
            ),
        ) from error
    except MediaRequestConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Media request cannot be cancelled "
                "in its current state."
            ),
        ) from error
    except MediaRequestsUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Media request service is unavailable.",
        ) from error

    return MediaRequestResponse.from_domain(
        request
    )


__all__ = [
    "get_media_requests_api_service",
    "require_requests_cancel",
    "require_requests_create",
    "require_requests_read",
    "router",
]
