"""Server-side playback action resolution."""

from __future__ import annotations

import os

from atlas.media import MediaProviderError, PlaybackAction
from atlas.media.jellyfin import JellyfinProvider, default_jellyfin_provider


class PlaybackNotFoundError(LookupError):
    """Raised when a playback target cannot be resolved."""


class PlaybackUnavailableError(RuntimeError):
    """Raised when public playback is not configured safely."""


class PlaybackService:
    """Resolve safe user-facing playback capabilities."""

    def __init__(
        self,
        jellyfin: JellyfinProvider,
        *,
        jellyfin_public_url: str,
    ) -> None:
        self._jellyfin = jellyfin
        self._jellyfin_public_url = jellyfin_public_url

    def resolve_library_item(
        self,
        *,
        provider: str,
        item_id: str,
    ) -> PlaybackAction:
        normalized_provider = provider.strip().lower()
        if normalized_provider != "jellyfin":
            raise PlaybackNotFoundError("unsupported playback provider")

        normalized_item_id = item_id.strip()
        if not normalized_item_id:
            raise PlaybackNotFoundError("playback item is required")

        try:
            self._jellyfin.get_item(normalized_item_id)
        except MediaProviderError as exc:
            raise PlaybackNotFoundError(
                "playback item was not found"
            ) from exc

        try:
            return PlaybackAction.jellyfin_library(
                normalized_item_id,
                public_base_url=self._jellyfin_public_url,
            )
        except ValueError as exc:
            raise PlaybackUnavailableError(
                "public Jellyfin playback is not configured safely"
            ) from exc


def build_default_playback_service() -> PlaybackService:
    return PlaybackService(
        default_jellyfin_provider(),
        jellyfin_public_url=os.environ.get(
            "ATLAS_JELLYFIN_PUBLIC_URL",
            "",
        ),
    )
