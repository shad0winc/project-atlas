"""Contract tests for Atlas TV-series detail models."""

from __future__ import annotations

import pytest

from atlas.media_requests import (
    MediaDiscoveryAvailability,
    MediaSeriesDetail,
    MediaSeriesError,
    MediaSeriesSeason,
    MediaSeriesStatus,
)


def _season(
    number: int = 1,
) -> MediaSeriesSeason:
    return MediaSeriesSeason(
        season_number=number,
        name=f" Season {number} ",
        episode_count=10,
        air_date="2026-01-15",
    )


def _detail(
    *,
    seasons: tuple[
        MediaSeriesSeason,
        ...,
    ] | None = None,
) -> MediaSeriesDetail:
    return MediaSeriesDetail(
        provider_media_id=" 1399 ",
        title=" Game of Thrones ",
        year=2011,
        overview=" Dragons. ",
        poster_path="/poster.jpg",
        status="returning",
        in_production=False,
        is_anime=True,
        availability="not_tracked",
        seasons=(
            seasons
            if seasons is not None
            else (
                _season(2),
                _season(1),
            )
        ),
    )


def test_series_season_normalizes_and_serializes() -> None:
    season = _season()

    assert season.name == "Season 1"

    assert season.to_dict() == {
        "season_number": 1,
        "name": "Season 1",
        "episode_count": 10,
        "air_date": "2026-01-15",
    }


def test_series_season_rejects_specials_zero() -> None:
    with pytest.raises(
        MediaSeriesError,
        match="positive integer",
    ):
        MediaSeriesSeason(
            season_number=0,
            name="Specials",
            episode_count=1,
        )


def test_series_season_requires_iso_air_date() -> None:
    with pytest.raises(
        MediaSeriesError,
        match="ISO date",
    ):
        MediaSeriesSeason(
            season_number=1,
            name="Season 1",
            episode_count=1,
            air_date="January 1",
        )


def test_series_detail_normalizes_sorts_and_serializes() -> None:
    detail = _detail()

    assert detail.provider_media_id == "1399"
    assert detail.title == "Game of Thrones"
    assert detail.status is MediaSeriesStatus.RETURNING
    assert detail.is_ongoing is True
    assert detail.is_anime is True
    assert detail.request_eligible is True

    assert [
        season.season_number
        for season in detail.seasons
    ] == [
        1,
        2,
    ]

    payload = detail.to_dict()

    assert payload["provider_media_id"] == "1399"
    assert payload["status"] == "returning"
    assert payload["in_production"] is False
    assert payload["is_ongoing"] is True
    assert payload["is_anime"] is True
    assert payload["availability"] == "not_tracked"
    assert payload["request_eligible"] is True
    assert [
        item["season_number"]
        for item in payload["seasons"]
    ] == [
        1,
        2,
    ]


def test_in_production_marks_unknown_series_ongoing() -> None:
    detail = MediaSeriesDetail(
        provider_media_id="1",
        title="Example",
        status=MediaSeriesStatus.UNKNOWN,
        in_production=True,
        is_anime=False,
        availability=(
            MediaDiscoveryAvailability
            .NOT_TRACKED
        ),
        seasons=(
            _season(),
        ),
    )

    assert detail.is_ongoing is True


def test_ended_series_is_not_ongoing() -> None:
    detail = MediaSeriesDetail(
        provider_media_id="1",
        title="Example",
        status=MediaSeriesStatus.ENDED,
        in_production=False,
        is_anime=False,
        availability="available",
        seasons=(
            _season(),
        ),
    )

    assert detail.is_ongoing is False
    assert detail.request_eligible is False


def test_series_detail_rejects_duplicate_season_numbers() -> None:
    with pytest.raises(
        MediaSeriesError,
        match="unique",
    ):
        _detail(
            seasons=(
                _season(1),
                _season(1),
            )
        )


def test_series_detail_requires_numeric_tmdb_identity() -> None:
    with pytest.raises(
        MediaSeriesError,
        match="TMDB identifier",
    ):
        MediaSeriesDetail(
            provider_media_id="tv:1399",
            title="Example",
            status="unknown",
            in_production=False,
            is_anime=False,
            availability="not_tracked",
            seasons=(),
        )


def test_series_contract_is_publicly_exported() -> None:
    import atlas.media_requests as media_requests

    assert (
        media_requests.MediaSeriesDetail
        is MediaSeriesDetail
    )
    assert (
        media_requests.MediaSeriesSeason
        is MediaSeriesSeason
    )
    assert (
        media_requests.MediaSeriesStatus
        is MediaSeriesStatus
    )
