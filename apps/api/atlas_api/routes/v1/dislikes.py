"""Authenticated Dislikes routes for version 1 of the Atlas API."""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.schemas.dislikes import (
    DislikeCreateRequest,
    DislikeListResponse,
    DislikeResponse,
)
from atlas_api.security import require_permission
from atlas_api.services.dislikes import (
    DislikeConflictError,
    DislikeNotFoundError,
    DislikeRequestError,
    DislikesAPIService,
    DislikesUnavailableError,
    build_default_dislikes_api_service,
)


router = APIRouter(
    prefix="/dislikes",
    tags=["dislikes"],
)


require_dislikes_read = require_permission(
    "dislikes.read"
)

require_dislikes_write = require_permission(
    "dislikes.write"
)


@lru_cache(maxsize=1)
def get_dislikes_api_service(
) -> DislikesAPIService:
    """Return the process-wide Dislikes application service."""

    return build_default_dislikes_api_service()


@router.get(
    "",
    response_model=DislikeListResponse,
    status_code=status.HTTP_200_OK,
    summary="List the authenticated user's dislikes",
)
def list_dislikes(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_dislikes_read),
    ],
    service: Annotated[
        DislikesAPIService,
        Depends(get_dislikes_api_service),
    ],
) -> DislikeListResponse:
    """Return only Dislikes owned by the authenticated user."""

    try:
        records = service.list_for_user(
            current_user.user_id
        )
    except DislikesUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dislikes are unavailable.",
        ) from error

    return DislikeListResponse(
        dislikes=tuple(
            DislikeResponse.from_record(record)
            for record in records
        )
    )


@router.post(
    "",
    response_model=DislikeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dislike one media item",
)
def create_dislike(
    request: DislikeCreateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_dislikes_write),
    ],
    service: Annotated[
        DislikesAPIService,
        Depends(get_dislikes_api_service),
    ],
) -> DislikeResponse:
    """Create one Dislike owned by the authenticated user."""

    try:
        result = service.add_for_user(
            current_user.user_id,
            request.provider,
            request.item_id,
        )
    except DislikeConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Dislike already exists.",
        ) from error
    except DislikeRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dislike request is invalid.",
        ) from error
    except DislikesUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dislike could not be created.",
        ) from error

    return DislikeResponse.from_record(
        result.record
    )


@router.delete(
    "/{dislike_id}",
    response_model=DislikeResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove one authenticated-user dislike",
)
def delete_dislike(
    dislike_id: str,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_dislikes_write),
    ],
    service: Annotated[
        DislikesAPIService,
        Depends(get_dislikes_api_service),
    ],
) -> DislikeResponse:
    """Remove a Dislike only when it belongs to the authenticated user."""

    try:
        result = service.remove_for_user(
            current_user.user_id,
            dislike_id,
        )
    except DislikeNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dislike was not found.",
        ) from error
    except DislikesUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Dislike could not be removed.",
        ) from error

    return DislikeResponse.from_record(
        result.record
    )


__all__ = [
    "create_dislike",
    "delete_dislike",
    "get_dislikes_api_service",
    "list_dislikes",
    "require_dislikes_read",
    "require_dislikes_write",
    "router",
]
