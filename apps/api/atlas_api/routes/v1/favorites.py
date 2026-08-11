"""Authenticated Favorites routes for version 1 of the Atlas API."""

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
from atlas_api.schemas.favorites import (
    FavoriteCreateRequest,
    FavoriteListResponse,
    FavoriteResponse,
)
from atlas_api.security import require_permission
from atlas_api.services.favorites import (
    FavoriteConflictError,
    FavoriteNotFoundError,
    FavoriteRequestError,
    FavoritesAPIService,
    FavoritesUnavailableError,
    build_default_favorites_api_service,
)


router = APIRouter(
    prefix="/favorites",
    tags=["favorites"],
)


require_favorites_read = require_permission(
    "favorites.read"
)

require_favorites_write = require_permission(
    "favorites.write"
)


@lru_cache(maxsize=1)
def get_favorites_api_service(
) -> FavoritesAPIService:
    """Return the process-wide Favorites application service."""

    return build_default_favorites_api_service()


@router.get(
    "",
    response_model=FavoriteListResponse,
    status_code=status.HTTP_200_OK,
    summary="List the authenticated user's favorites",
)
def list_favorites(
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_favorites_read),
    ],
    service: Annotated[
        FavoritesAPIService,
        Depends(get_favorites_api_service),
    ],
) -> FavoriteListResponse:
    """Return only Favorites owned by the authenticated user."""

    try:
        records = service.list_for_user(
            current_user.user_id
        )
    except FavoritesUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Favorites are unavailable.",
        ) from error

    return FavoriteListResponse(
        favorites=tuple(
            FavoriteResponse.from_record(record)
            for record in records
        )
    )


@router.post(
    "",
    response_model=FavoriteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Favorite one media item",
)
def create_favorite(
    request: FavoriteCreateRequest,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_favorites_write),
    ],
    service: Annotated[
        FavoritesAPIService,
        Depends(get_favorites_api_service),
    ],
) -> FavoriteResponse:
    """Create one Favorite owned by the authenticated user."""

    try:
        result = service.add_for_user(
            current_user.user_id,
            request.provider,
            request.item_id,
        )
    except FavoriteConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Favorite already exists.",
        ) from error
    except FavoriteRequestError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Favorite request is invalid.",
        ) from error
    except FavoritesUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Favorite could not be created.",
        ) from error

    return FavoriteResponse.from_record(
        result.record
    )


@router.delete(
    "/{favorite_id}",
    response_model=FavoriteResponse,
    status_code=status.HTTP_200_OK,
    summary="Remove one authenticated-user favorite",
)
def delete_favorite(
    favorite_id: str,
    current_user: Annotated[
        AuthenticatedUser,
        Depends(require_favorites_write),
    ],
    service: Annotated[
        FavoritesAPIService,
        Depends(get_favorites_api_service),
    ],
) -> FavoriteResponse:
    """Remove a Favorite only when it belongs to the authenticated user."""

    try:
        result = service.remove_for_user(
            current_user.user_id,
            favorite_id,
        )
    except FavoriteNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Favorite was not found.",
        ) from error
    except FavoritesUnavailableError as error:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Favorite could not be removed.",
        ) from error

    return FavoriteResponse.from_record(
        result.record
    )


__all__ = [
    "create_favorite",
    "delete_favorite",
    "get_favorites_api_service",
    "list_favorites",
    "require_favorites_read",
    "require_favorites_write",
    "router",
]
