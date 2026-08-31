"""Server-side playback action resolution."""

from __future__ import annotations

import os

from atlas.media import (
    MediaProviderError,
    PlaybackAction,
    PlaybackActionKind,
    PlaybackSession,
    PlaybackSourceType,
    PlaybackTrack,
)
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

    def resolve_library_session(
        self,
        *,
        provider: str,
        item_id: str,
        jellyfin_user_id: str,
    ) -> PlaybackSession:
        normalized_provider = provider.strip().lower()
        if normalized_provider != "jellyfin":
            raise PlaybackNotFoundError("unsupported playback provider")

        normalized_item_id = item_id.strip()
        if not normalized_item_id:
            raise PlaybackNotFoundError("playback item is required")

        normalized_jellyfin_user_id = jellyfin_user_id.strip()
        if not normalized_jellyfin_user_id:
            raise PlaybackUnavailableError(
                "Atlas user is not linked to Jellyfin"
            )

        try:
            item = self._jellyfin.get_item(normalized_item_id)

            playable_target_id = normalized_item_id
            session_title = item.title
            previous_target_id = None
            next_target_id = None

            jellyfin_type = str(
                item.metadata.get("jellyfin_type") or ""
            ).strip().lower()

            if jellyfin_type == "series":
                episodes = self._jellyfin.list_series_episodes(
                    normalized_item_id
                )
                if not episodes:
                    raise PlaybackNotFoundError(
                        "series has no playable episodes"
                    )

                selected = episodes[0]
                playable_target_id = selected["id"]

                season = selected["season_number"]
                episode = selected["episode_number"]
                episode_title = selected["title"]

                if season is not None and episode is not None:
                    session_title = (
                        f"{item.title} — S{season} E{episode} — "
                        f"{episode_title}"
                    )
                else:
                    session_title = f"{item.title} — {episode_title}"

                if len(episodes) > 1:
                    next_target_id = episodes[1]["id"]

            playback = self._jellyfin.get_playback_info(
                playable_target_id,
                user_id=normalized_jellyfin_user_id,
            )
        except PlaybackNotFoundError:
            raise
        except MediaProviderError as exc:
            raise PlaybackNotFoundError(
                "playback item was not found or is not playable"
            ) from exc

        tracks = tuple(
            PlaybackTrack(
                index=track["index"],
                kind=track["kind"],
                label=track["label"],
                language=track["language"],
                codec=track["codec"],
                default=track["default"],
                forced=track["forced"],
            )
            for track in playback["tracks"]
        )

        return PlaybackSession(
            available=True,
            action=PlaybackActionKind.WATCH_NOW,
            label="Watch Now",
            backend="jellyfin",
            source_type=PlaybackSourceType.LIBRARY,
            provider="jellyfin",
            requested_target_id=normalized_item_id,
            playable_target_id=playable_target_id,
            title=session_title,
            media_type=item.media_type,
            duration_ticks=playback["duration_ticks"],
            can_seek=playback["can_seek"],
            stream_path=playback["stream_path"],
            audio_tracks=tuple(
                track for track in tracks if track.kind == "audio"
            ),
            subtitle_tracks=tuple(
                track for track in tracks if track.kind == "subtitle"
            ),
            previous_target_id=previous_target_id,
            next_target_id=next_target_id,
        )

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
