"""Jellyfin-backed Ready-to-Watch contracts for Atlas requests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from atlas.media_requests.models import (
    MediaRequest,
    MediaRequestStatus,
    MediaRequestType,
)
from atlas.media_requests.readiness import (
    JellyfinRequestReadiness,
    MediaRequestReadinessError,
)


@dataclass(frozen=True)
class Episode:
    id: str
    season_number: int | None
    episode_number: int | None = None


class RecordingJellyfin:
    def __init__(
        self,
        *,
        item_id: str | None = None,
        episodes: tuple[Episode, ...] = (),
        playable: set[str] | None = None,
    ) -> None:
        self.item_id = item_id
        self.episodes = episodes
        self.playable = set(playable or ())
        self.lookups: list[tuple[str, str]] = []
        self.episode_lists: list[str] = []
        self.playability_checks: list[str] = []

    def find_item_by_tmdb(
        self,
        tmdb_id: str,
        *,
        media_type: str,
    ) -> str | None:
        self.lookups.append(
            (
                tmdb_id,
                media_type,
            )
        )
        return self.item_id

    def list_series_episodes(
        self,
        series_id: str,
    ) -> tuple[Episode, ...]:
        self.episode_lists.append(series_id)
        return self.episodes

    def is_item_playable(
        self,
        item_id: str,
    ) -> bool:
        self.playability_checks.append(item_id)
        return item_id in self.playable


def request(
    *,
    media_type: MediaRequestType = MediaRequestType.MOVIE,
    provider_media_id: str = "157336",
    season_number: int | None = None,
) -> MediaRequest:
    return MediaRequest(
        request_id="request-001",
        user_id="user-001",
        media_type=media_type,
        provider="jellyseerr",
        provider_media_id=provider_media_id,
        title="Example",
        season_number=season_number,
        status=MediaRequestStatus.PROCESSING,
        provider_request_id="42",
        created_at="2026-09-13T04:00:00Z",
        updated_at="2026-09-13T04:30:00Z",
    )


def test_movie_ready_requires_exact_tmdb_item_to_be_playable() -> None:
    jellyfin = RecordingJellyfin(
        item_id="movie-abc",
        playable={"movie-abc"},
    )
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(request()) is True
    assert jellyfin.lookups == [("157336", "movie")]
    assert jellyfin.playability_checks == ["movie-abc"]
    assert jellyfin.episode_lists == []


def test_movie_missing_from_jellyfin_is_not_ready() -> None:
    jellyfin = RecordingJellyfin(item_id=None)
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(request()) is False
    assert jellyfin.playability_checks == []


def test_movie_present_but_not_playable_is_not_ready() -> None:
    jellyfin = RecordingJellyfin(item_id="movie-abc")
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(request()) is False
    assert jellyfin.playability_checks == ["movie-abc"]


@pytest.mark.parametrize(
    "media_type",
    (
        MediaRequestType.TV,
        MediaRequestType.ANIME_TV,
    ),
)
def test_requested_season_requires_playable_episode_in_that_season(
    media_type: MediaRequestType,
) -> None:
    jellyfin = RecordingJellyfin(
        item_id="series-abc",
        episodes=(
            Episode("s01e01", 1, 1),
            Episode("s02e01", 2, 1),
            Episode("s02e02", 2, 2),
        ),
        playable={"s01e01", "s02e02"},
    )
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(
        request(
            media_type=media_type,
            season_number=2,
        )
    ) is True

    assert jellyfin.lookups == [("157336", "tv")]
    assert jellyfin.episode_lists == ["series-abc"]
    assert "s02e02" in jellyfin.playability_checks


def test_playable_episode_from_other_season_does_not_make_requested_season_ready() -> None:
    jellyfin = RecordingJellyfin(
        item_id="series-abc",
        episodes=(
            Episode("s01e01", 1, 1),
            Episode("s02e01", 2, 1),
        ),
        playable={"s01e01"},
    )
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(
        request(
            media_type=MediaRequestType.TV,
            season_number=2,
        )
    ) is False

    assert jellyfin.playability_checks == ["s02e01"]


def test_requested_season_with_no_imported_episode_is_not_ready() -> None:
    jellyfin = RecordingJellyfin(
        item_id="series-abc",
        episodes=(
            Episode("s01e01", 1, 1),
        ),
        playable={"s01e01"},
    )
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(
        request(
            media_type=MediaRequestType.TV,
            season_number=2,
        )
    ) is False

    assert jellyfin.playability_checks == []


def test_series_without_explicit_season_requires_real_playable_episode() -> None:
    jellyfin = RecordingJellyfin(
        item_id="series-abc",
        episodes=(
            Episode("episode-1", 1, 1),
            Episode("episode-2", 1, 2),
        ),
        playable={"episode-2"},
    )
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(
        request(
            media_type=MediaRequestType.TV,
        )
    ) is True

    assert "series-abc" not in jellyfin.playability_checks
    assert jellyfin.playability_checks == [
        "episode-1",
        "episode-2",
    ]


def test_series_shell_without_episodes_is_not_ready() -> None:
    jellyfin = RecordingJellyfin(
        item_id="series-abc",
        episodes=(),
        playable={"series-abc"},
    )
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(
        request(
            media_type=MediaRequestType.TV,
        )
    ) is False

    assert jellyfin.playability_checks == []


@pytest.mark.parametrize(
    "media_type",
    (
        MediaRequestType.MOVIE,
        MediaRequestType.ANIME_MOVIE,
    ),
)
def test_movie_and_anime_movie_use_jellyfin_movie_identity(
    media_type: MediaRequestType,
) -> None:
    jellyfin = RecordingJellyfin(
        item_id="movie-abc",
        playable={"movie-abc"},
    )
    readiness = JellyfinRequestReadiness(jellyfin)

    assert readiness.is_ready(
        request(media_type=media_type)
    ) is True

    assert jellyfin.lookups == [("157336", "movie")]


def test_readiness_rejects_non_processing_request() -> None:
    jellyfin = RecordingJellyfin(
        item_id="movie-abc",
        playable={"movie-abc"},
    )
    readiness = JellyfinRequestReadiness(jellyfin)

    non_processing = MediaRequest(
        request_id="request-001",
        user_id="user-001",
        media_type=MediaRequestType.MOVIE,
        provider="jellyseerr",
        provider_media_id="157336",
        title="Example",
        status=MediaRequestStatus.APPROVED,
        provider_request_id="42",
        created_at="2026-09-13T04:00:00Z",
        updated_at="2026-09-13T04:30:00Z",
    )

    with pytest.raises(
        MediaRequestReadinessError,
        match="processing",
    ):
        readiness.is_ready(non_processing)


@pytest.mark.parametrize(
    "provider_media_id",
    (
        "abc",
        "0",
        "tmdb:157336",
    ),
)
def test_readiness_requires_positive_numeric_tmdb_identity(
    provider_media_id: str,
) -> None:
    jellyfin = RecordingJellyfin()
    readiness = JellyfinRequestReadiness(jellyfin)

    with pytest.raises(
        MediaRequestReadinessError,
        match="TMDB",
    ):
        readiness.is_ready(
            request(
                provider_media_id=provider_media_id,
            )
        )


def test_sports_request_is_not_supported_by_jellyfin_request_readiness() -> None:
    jellyfin = RecordingJellyfin()
    readiness = JellyfinRequestReadiness(jellyfin)

    with pytest.raises(
        MediaRequestReadinessError,
        match="media type",
    ):
        readiness.is_ready(
            request(
                media_type=MediaRequestType.SPORTS,
            )
        )
