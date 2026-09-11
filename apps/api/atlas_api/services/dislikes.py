"""Application adapter for authenticated Dislikes operations."""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Mapping, Any

from atlas.dislike_service import (
    DislikeMutationResult,
    DislikeService,
)
from atlas.dislikes import (
    DislikeError,
    DislikeStore,
    default_dislike_store,
)
from atlas.media.jellyfin import default_jellyfin_provider

from atlas_api.events import RuntimeEventJournalPublisher


class DislikesAPIError(RuntimeError):
    """Base error for the HTTP-facing Dislikes application boundary."""


class DislikeNotFoundError(DislikesAPIError):
    """Raised when a caller-visible dislike does not exist."""


class DislikeConflictError(DislikesAPIError):
    """Raised when a duplicate dislike relationship already exists."""


class DislikeRequestError(DislikesAPIError):
    """Raised when a dislike request violates a supported contract."""


class DislikesUnavailableError(DislikesAPIError):
    """Raised when Dislike state or its provider cannot be used safely."""


@dataclass(frozen=True)
class DislikesAPIService:
    """Self-scoped application service for Dislikes HTTP routes."""

    store: DislikeStore
    mutations: DislikeService

    def list_for_user(
        self,
        user_id: str,
    ) -> list[dict[str, Any]]:
        """Return only dislikes owned by one authenticated user."""

        try:
            return self.store.list(
                user_id=user_id
            )
        except (
            DislikeError,
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise DislikesUnavailableError(
                "Dislikes are unavailable."
            ) from error

    def add_for_user(
        self,
        user_id: str,
        provider: str,
        item_id: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> DislikeMutationResult:
        """Add one Dislike using the authenticated user as owner."""

        try:
            return self.mutations.add(
                user_id,
                provider,
                item_id,
                metadata=metadata,
            )
        except DislikeError as error:
            message = str(error)

            if message.startswith(
                "dislike already exists:"
            ):
                raise DislikeConflictError(
                    "Dislike already exists."
                ) from error

            if (
                message.startswith("unsupported media provider:")
                or message.startswith("provider is required")
                or message.startswith("item_id is required")
                or message.startswith("item_id exceeds")
                or message.startswith("dislike metadata")
                or message.startswith("invalid dislike")
            ):
                raise DislikeRequestError(
                    "Dislike request is invalid."
                ) from error

            raise DislikesUnavailableError(
                "Dislike could not be created."
            ) from error

    def remove_for_user(
        self,
        user_id: str,
        dislike_id: str,
    ) -> DislikeMutationResult:
        """Remove only a Dislike owned by the authenticated user."""

        try:
            record = self.store.get(
                dislike_id
            )
        except DislikeError as error:
            message = str(error)

            if message.startswith(
                "dislike not found:"
            ):
                raise DislikeNotFoundError(
                    "Dislike was not found."
                ) from error

            raise DislikesUnavailableError(
                "Dislikes are unavailable."
            ) from error
        except (
            OSError,
            json.JSONDecodeError,
        ) as error:
            raise DislikesUnavailableError(
                "Dislikes are unavailable."
            ) from error

        # Do not distinguish another user's Dislike from an unknown
        # Dislike. The API must not disclose cross-user relationships.
        if record["user_id"] != user_id:
            raise DislikeNotFoundError(
                "Dislike was not found."
            )

        try:
            return self.mutations.remove(
                dislike_id
            )
        except DislikeError as error:
            if str(error).startswith(
                "dislike not found:"
            ):
                raise DislikeNotFoundError(
                    "Dislike was not found."
                ) from error

            raise DislikesUnavailableError(
                "Dislike could not be removed."
            ) from error
        except OSError as error:
            raise DislikesUnavailableError(
                "Dislike could not be removed."
            ) from error


def build_default_dislikes_api_service(
) -> DislikesAPIService:
    """Build the process-default Dislikes application service."""

    store = default_dislike_store()

    mutations = DislikeService(
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

    return DislikesAPIService(
        store=store,
        mutations=mutations,
    )
