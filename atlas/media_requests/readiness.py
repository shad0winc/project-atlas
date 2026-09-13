"""Ready-to-Watch evaluation for Atlas media requests."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .models import (
    MediaRequest,
    MediaRequestStatus,
    MediaRequestType,
)


class MediaRequestReadinessError(RuntimeError):
    """Raised when request readiness cannot be evaluated safely."""


@runtime_checkable
class JellyfinEpisode(Protocol):
    """Episode fields required for request readiness."""

    @property
    def id(self) -> object:
        ...

    @property
    def season_number(self) -> object:
        ...


@runtime_checkable
class JellyfinReadinessProvider(Protocol):
    """Jellyfin behavior required to prove Ready-to-Watch."""

    def find_item_by_tmdb(
        self,
        tmdb_id: str,
        *,
        media_type: str,
    ) -> str | None:
        ...

    def list_series_episodes(
        self,
        series_id: str,
    ) -> tuple[JellyfinEpisode, ...]:
        ...

    def is_item_playable(
        self,
        item_id: str,
    ) -> bool:
        ...


class JellyfinRequestReadiness:
    """Prove Atlas request availability from actual Jellyfin playback."""

    def __init__(
        self,
        jellyfin: JellyfinReadinessProvider,
    ) -> None:
        if not isinstance(
            jellyfin,
            JellyfinReadinessProvider,
        ):
            raise MediaRequestReadinessError(
                "jellyfin must provide request-readiness behavior"
            )

        self._jellyfin = jellyfin

    def is_ready(
        self,
        request: MediaRequest,
    ) -> bool:
        """Return whether one PROCESSING request is playable in Jellyfin."""

        if not isinstance(request, MediaRequest):
            raise MediaRequestReadinessError(
                "request must be a MediaRequest"
            )

        if request.status is not MediaRequestStatus.PROCESSING:
            raise MediaRequestReadinessError(
                "media request must be processing before readiness evaluation"
            )

        tmdb_id = self._tmdb_id(
            request.provider_media_id
        )

        if request.media_type in {
            MediaRequestType.MOVIE,
            MediaRequestType.ANIME_MOVIE,
        }:
            return self._movie_ready(
                tmdb_id
            )

        if request.media_type in {
            MediaRequestType.TV,
            MediaRequestType.ANIME_TV,
        }:
            return self._series_ready(
                tmdb_id,
                season_number=request.season_number,
            )

        raise MediaRequestReadinessError(
            "unsupported media type for Jellyfin request readiness: "
            f"{request.media_type.value}"
        )

    def _movie_ready(
        self,
        tmdb_id: str,
    ) -> bool:
        item_id = self._jellyfin.find_item_by_tmdb(
            tmdb_id,
            media_type="movie",
        )

        if item_id is None:
            return False

        return bool(
            self._jellyfin.is_item_playable(
                item_id
            )
        )

    def _series_ready(
        self,
        tmdb_id: str,
        *,
        season_number: int | None,
    ) -> bool:
        series_id = self._jellyfin.find_item_by_tmdb(
            tmdb_id,
            media_type="tv",
        )

        if series_id is None:
            return False

        episodes = self._jellyfin.list_series_episodes(
            series_id
        )

        for episode in episodes:
            episode_season = getattr(
                episode,
                "season_number",
                None,
            )

            if (
                season_number is not None
                and episode_season != season_number
            ):
                continue

            episode_id = getattr(
                episode,
                "id",
                None,
            )

            if (
                not isinstance(episode_id, str)
                or not episode_id.strip()
            ):
                raise MediaRequestReadinessError(
                    "Jellyfin returned an episode without a valid item id"
                )

            if self._jellyfin.is_item_playable(
                episode_id.strip()
            ):
                return True

        return False

    @staticmethod
    def _tmdb_id(
        value: object,
    ) -> str:
        if not isinstance(value, str):
            raise MediaRequestReadinessError(
                "request TMDB identity must be positive numeric text"
            )

        normalized = value.strip()

        if (
            not normalized.isdigit()
            or int(normalized) <= 0
        ):
            raise MediaRequestReadinessError(
                "request TMDB identity must be positive numeric text"
            )

        return normalized
