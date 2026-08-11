"""Tests for Jellyseerr-backed Atlas TV-series detail."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from atlas.media_requests import (
    JellyseerrMediaRequestProvider,
    MediaDiscoveryAvailability,
    MediaRequestProviderError,
    MediaSeriesStatus,
)


def _provider(
) -> JellyseerrMediaRequestProvider:
    return JellyseerrMediaRequestProvider(
        base_url="http://jellyseerr:5055",
        api_key="secret",
    )


def _detail(
    *,
    item_id: int = 1399,
    status: str = "Returning Series",
    in_production: bool = True,
    keywords: object | None = None,
    media_info: object = None,
) -> dict[str, object]:
    return {
        "id": item_id,
        "name": "Game of Thrones",
        "firstAirDate": "2011-04-17",
        "overview": "Dragons.",
        "posterPath": "/poster.jpg",
        "status": status,
        "inProduction": in_production,
        "keywords": (
            [
                {
                    "id": 210024,
                    "name": "anime",
                }
            ]
            if keywords is None
            else keywords
        ),
        "mediaInfo": media_info,
        "seasons": [
            {
                "id": 0,
                "name": "Specials",
                "seasonNumber": 0,
                "episodeCount": 5,
                "airDate": None,
            },
            {
                "id": 1,
                "name": "Season 2",
                "seasonNumber": 2,
                "episodeCount": 10,
                "airDate": "2012-04-01",
            },
            {
                "id": 2,
                "name": "Season 1",
                "seasonNumber": 1,
                "episodeCount": 10,
                "airDate": "2011-04-17",
            },
        ],
    }


def test_tv_detail_uses_provider_endpoint_and_normalizes_metadata() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(),
    ) as get_json:
        detail = provider.get_tv_detail(
            "1399"
        )

    get_json.assert_called_once_with(
        "/api/v1/tv/1399"
    )

    assert detail.provider_media_id == "1399"
    assert detail.title == "Game of Thrones"
    assert detail.year == 2011
    assert detail.status is MediaSeriesStatus.RETURNING
    assert detail.in_production is True
    assert detail.is_ongoing is True
    assert detail.is_anime is True
    assert detail.availability is (
        MediaDiscoveryAvailability
        .NOT_TRACKED
    )
    assert detail.request_eligible is True

    assert [
        season.season_number
        for season in detail.seasons
    ] == [
        1,
        2,
    ]

    for season in detail.seasons:
        assert season.availability is (
            MediaDiscoveryAvailability
            .NOT_TRACKED
        )
        assert (
            season.requestability_known
            is True
        )
        assert season.request_eligible is True


def test_tv_detail_maps_ended_non_anime_series() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            status="Ended",
            in_production=False,
            keywords=[],
            media_info={
                "status": 5,
            },
        ),
    ):
        detail = provider.get_tv_detail(
            1399
        )

    assert detail.status is MediaSeriesStatus.ENDED
    assert detail.is_ongoing is False
    assert detail.is_anime is False
    assert detail.request_eligible is False

    for season in detail.seasons:
        assert season.availability is (
            MediaDiscoveryAvailability
            .UNKNOWN
        )
        assert (
            season.requestability_known
            is False
        )
        assert season.request_eligible is False


def test_tv_detail_normalizes_tracked_per_season_requestability() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            media_info={
                "status": 4,
                "seasons": [
                    {
                        "seasonNumber": 1,
                        "status": 5,
                    },
                    {
                        "seasonNumber": 2,
                        "status": 1,
                    },
                ],
                "requests": [],
            },
        ),
    ):
        detail = provider.get_tv_detail(
            "1399"
        )

    season_1, season_2 = detail.seasons

    assert season_1.availability is (
        MediaDiscoveryAvailability
        .AVAILABLE
    )
    assert (
        season_1.requestability_known
        is True
    )
    assert season_1.request_eligible is False

    assert season_2.availability is (
        MediaDiscoveryAvailability
        .UNKNOWN
    )
    assert (
        season_2.requestability_known
        is True
    )
    assert season_2.request_eligible is True


@pytest.mark.parametrize(
    "request_status",
    [
        1,
        2,
        4,
    ],
)
def test_tv_detail_active_provider_request_blocks_season(
    request_status: int,
) -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            media_info={
                "status": 2,
                "seasons": [
                    {
                        "seasonNumber": 2,
                        "status": 1,
                    },
                ],
                "requests": [
                    {
                        "status": request_status,
                        "is4k": False,
                        "seasons": [
                            {
                                "seasonNumber": 2,
                            },
                        ],
                    },
                ],
            },
        ),
    ):
        detail = provider.get_tv_detail(
            "1399"
        )

    season_1, season_2 = detail.seasons

    assert season_1.availability is (
        MediaDiscoveryAvailability
        .UNKNOWN
    )
    assert season_1.request_eligible is True

    assert season_2.availability is (
        MediaDiscoveryAvailability
        .UNKNOWN
    )
    assert (
        season_2.requestability_known
        is True
    )
    assert season_2.request_eligible is False


def test_tv_detail_ignores_terminal_and_4k_provider_requests() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            media_info={
                "status": 4,
                "seasons": [],
                "requests": [
                    {
                        "status": 3,
                        "is4k": False,
                    },
                    {
                        "status": 5,
                        "is4k": False,
                    },
                    {
                        "status": 2,
                        "is4k": True,
                    },
                ],
            },
        ),
    ):
        detail = provider.get_tv_detail(
            "1399"
        )

    assert all(
        season.request_eligible
        for season in detail.seasons
    )


def test_tv_detail_incomplete_provider_season_state_fails_closed() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            media_info={
                "status": 4,
                "seasons": [
                    {
                        "seasonNumber": 1,
                        "status": 5,
                    },
                ],
            },
        ),
    ):
        detail = provider.get_tv_detail(
            "1399"
        )

    for season in detail.seasons:
        assert season.availability is (
            MediaDiscoveryAvailability
            .UNKNOWN
        )
        assert (
            season.requestability_known
            is False
        )
        assert season.request_eligible is False


def test_tv_detail_malformed_provider_season_state_fails_closed() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            media_info={
                "status": 4,
                "seasons": [
                    {
                        "seasonNumber": 1,
                        "status": "available",
                    },
                ],
                "requests": [],
            },
        ),
    ):
        detail = provider.get_tv_detail(
            "1399"
        )

    assert all(
        not season.requestability_known
        and not season.request_eligible
        for season in detail.seasons
    )


def test_tv_detail_unknown_provider_status_is_preserved_as_unknown() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            status="Hiatus",
            in_production=False,
        ),
    ):
        detail = provider.get_tv_detail(
            "1399"
        )

    assert detail.status is MediaSeriesStatus.UNKNOWN


def test_tv_detail_rejects_mismatched_provider_identity() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            item_id=1400
        ),
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="mismatched",
        ):
            provider.get_tv_detail(
                "1399"
            )


def test_tv_detail_requires_season_array() -> None:
    provider = _provider()
    payload = _detail()
    payload["seasons"] = {}

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=payload,
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="seasons must be an array",
        ):
            provider.get_tv_detail(
                "1399"
            )


def test_tv_detail_rejects_invalid_season_metadata() -> None:
    provider = _provider()
    payload = _detail()
    payload["seasons"] = [
        {
            "name": "Season 1",
            "seasonNumber": 1,
            "episodeCount": -1,
            "airDate": "2011-04-17",
        }
    ]

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=payload,
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="non-negative integer",
        ):
            provider.get_tv_detail(
                "1399"
            )


def test_tv_detail_requires_keyword_array_when_present() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=_detail(
            keywords={}
        ),
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="keywords must be an array",
        ):
            provider.get_tv_detail(
                "1399"
            )


@pytest.mark.parametrize(
    "provider_media_id",
    [
        "",
        "abc",
        0,
        -1,
        True,
    ],
)
def test_tv_detail_requires_positive_numeric_identity(
    provider_media_id: object,
) -> None:
    with pytest.raises(
        MediaRequestProviderError,
    ):
        _provider().get_tv_detail(
            provider_media_id  # type: ignore[arg-type]
        )
