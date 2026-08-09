"""Application adapter for authenticated Favorites operations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Any

from atlas.favorite_service import (
    FavoriteMutationResult,
    FavoriteService,
)
from atlas.favorites import (
    FavoriteError,
    FavoriteStore,
    default_favorite_store,
)
from atlas.media.jellyfin import default_jellyfin_provider

from atlas_api.events import RuntimeEventJournalPublisher


class FavoritesAPIError(RuntimeError):
    """Base error for the HTTP-facing Favorites application boundary."""


class FavoriteNotFoundError(FavoritesAPIError):
    """Raised when a caller-visible favorite does not exist."""


class FavoriteConflictError(FavoritesAPIError):
    """Raised when a duplicate favorite relationship already exists."""


class FavoriteRequestError(FavoritesAPIError):
    """Raised when a favorite request violates a supported contract."""


class FavoritesUnavailableError(FavoritesAPIError):
    """Raised when Favorite state or its provider cannot be used safely."""


@dataclass(frozen=True)
class FavoritesAPIService:
    """Self-scoped application service for Favorites HTTP routes."""

    store: FavoriteStore
    mutations: FavoriteService

    def list_for_user(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Return only favorites owned by one authenticated user."""

        try:
            return self.store.list(
                user_id=user_id
            )
        except (
            FavoriteError,
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise FavoritesUnavailableError(
                "Favorites are unavailable."
            ) from error

    def add_for_user(
        self,
        user_id: str,
        provider: str,
        item_id: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> FavoriteMutationResult:
        """Add one Favorite using the authenticated user as owner."""

        try:
            return self.mutations.add(
                user_id,
                provider,
                item_id,
                metadata=metadata,
            )
        except FavoriteError as error:
            message = str(error)

            if message.startswith(
                "favorite already exists:"
            ):
                raise FavoriteConflictError(
                    "Favorite already exists."
                ) from error

            if (
                message.startswith("unsupported media provider:")
                or message.startswith("provider is required")
                or message.startswith("item_id is required")
                or message.startswith("item_id exceeds")
                or message.startswith("favorite metadata")
                or message.startswith("invalid favorite")
            ):
                raise FavoriteRequestError(
                    "Favorite request is invalid."
                ) from error

            raise FavoritesUnavailableError(
                "Favorite could not be created."
            ) from error

    def remove_for_user(
        self,
        user_id: str,
        favorite_id: str,
    ) -> FavoriteMutationResult:
        """Remove only a Favorite owned by the authenticated user."""

        try:
            record = self.store.get(
                favorite_id
            )
        except FavoriteError as error:
            message = str(error)

            if message.startswith(
                "favorite not found:"
            ):
                raise FavoriteNotFoundError(
                    "Favorite was not found."
                ) from error

            raise FavoritesUnavailableError(
                "Favorites are unavailable."
            ) from error
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise FavoritesUnavailableError(
                "Favorites are unavailable."
            ) from error

        # Do not distinguish another user's Favorite from an unknown
        # Favorite. The API must not disclose cross-user relationships.
        if record["user_id"] != user_id:
            raise FavoriteNotFoundError(
                "Favorite was not found."
            )

        try:
            return self.mutations.remove(
                favorite_id
            )
        except FavoriteError as error:
            if str(error).startswith(
                "favorite not found:"
            ):
                raise FavoriteNotFoundError(
                    "Favorite was not found."
                ) from error

            raise FavoritesUnavailableError(
                "Favorite could not be removed."
            ) from error
        except OSError as error:
            raise FavoritesUnavailableError(
                "Favorite could not be removed."
            ) from error


def build_default_favorites_api_service(
) -> FavoritesAPIService:
    """Build the process-default Favorites application service."""

    store = default_favorite_store()

    mutations = FavoriteService(
        store=store,
        providers={
            "jellyfin": default_jellyfin_provider(),
        },
        event_publisher=(
            RuntimeEventJournalPublisher
            .from_environment()
            .publish
        ),
    )

    return FavoritesAPIService(
        store=store,
        mutations=mutations,
    )
