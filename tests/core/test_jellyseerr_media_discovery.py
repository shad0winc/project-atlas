"""Tests for Jellyseerr-backed Atlas media discovery."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from atlas.media_requests import (
    JellyseerrMediaRequestProvider,
    MediaDiscoveryAvailability,
    MediaRequestProviderError,
    MediaRequestType,
)


def _provider(
) -> JellyseerrMediaRequestProvider:
    return (
        JellyseerrMediaRequestProvider(
            base_url=(
                "http://jellyseerr:5055"
            ),
            api_key="secret",
        )
    )


def _movie(
    *,
    item_id: int = 157336,
    media_info: object = None,
) -> dict[str, object]:
    return {
        "id": item_id,
        "mediaType": "movie",
        "title": "Interstellar",
        "releaseDate": "2014-11-07",
        "overview": "Space.",
        "posterPath": "/poster.jpg",
        "mediaInfo": media_info,
    }


def _tv(
    *,
    item_id: int = 1396,
    media_info: object = None,
) -> dict[str, object]:
    return {
        "id": item_id,
        "mediaType": "tv",
        "name": "Breaking Bad",
        "firstAirDate": "2008-01-20",
        "overview": "Chemistry.",
        "posterPath": "/tv.jpg",
        "mediaInfo": media_info,
    }


def test_search_normalizes_movie_and_tv_and_filters_people() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={
            "page": 2,
            "totalPages": 4,
            "totalResults": 75,
            "results": [
                _movie(),
                {
                    "id": 287,
                    "mediaType": "person",
                    "name": "Brad Pitt",
                },
                _tv(),
            ],
        },
    ) as get_json:
        page = provider.search_media(
            " Star Wars ",
            page=2,
        )

    get_json.assert_called_once_with(
        "/api/v1/search?"
        "query=Star+Wars&"
        "page=2"
    )

    assert page.page == 2
    assert page.total_pages == 4
    assert page.next_page == 3

    assert [
        item.media_type
        for item in page.items
    ] == [
        MediaRequestType.MOVIE,
        MediaRequestType.TV,
    ]

    assert [
        item.provider_media_id
        for item in page.items
    ] == [
        "157336",
        "1396",
    ]


def test_movie_discovery_uses_jellyseerr_discover_endpoint() -> None:
    provider = _provider()

    payload = _movie()
    payload.pop(
        "mediaType"
    )

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={
            "page": 1,
            "totalPages": 1,
            "totalResults": 1,
            "results": [
                payload
            ],
        },
    ) as get_json:
        page = provider.discover_media(
            "movie"
        )

    get_json.assert_called_once_with(
        "/api/v1/discover/movies?"
        "page=1"
    )

    assert (
        page.items[0].media_type
        is MediaRequestType.MOVIE
    )


def test_tv_discovery_uses_jellyseerr_discover_endpoint() -> None:
    provider = _provider()

    payload = _tv()
    payload.pop(
        "mediaType"
    )

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={
            "page": 3,
            "totalPages": 5,
            "totalResults": 90,
            "results": [
                payload
            ],
        },
    ) as get_json:
        page = provider.discover_media(
            "tv",
            page=3,
        )

    get_json.assert_called_once_with(
        "/api/v1/discover/tv?"
        "page=3"
    )

    assert (
        page.items[0].media_type
        is MediaRequestType.TV
    )


def test_untracked_media_is_request_eligible() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={
            "page": 1,
            "totalPages": 1,
            "results": [
                _movie(
                    media_info=None
                )
            ],
        },
    ):
        item = provider.search_media(
            "Interstellar"
        ).items[0]

    assert (
        item.availability
        is MediaDiscoveryAvailability
        .NOT_TRACKED
    )

    assert item.request_eligible is True


@pytest.mark.parametrize(
    ("status", "availability"),
    [
        (
            1,
            MediaDiscoveryAvailability.UNKNOWN,
        ),
        (
            2,
            MediaDiscoveryAvailability.PENDING,
        ),
        (
            3,
            MediaDiscoveryAvailability.PROCESSING,
        ),
        (
            4,
            MediaDiscoveryAvailability.PARTIALLY_AVAILABLE,
        ),
        (
            5,
            MediaDiscoveryAvailability.AVAILABLE,
        ),
        (
            6,
            MediaDiscoveryAvailability.BLOCKLISTED,
        ),
        (
            7,
            MediaDiscoveryAvailability.DELETED,
        ),
    ],
)
def test_tracked_jellyseerr_statuses_are_not_request_eligible(
    status: int,
    availability: MediaDiscoveryAvailability,
) -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={
            "page": 1,
            "totalPages": 1,
            "results": [
                _movie(
                    media_info={
                        "status":
                            status
                    }
                )
            ],
        },
    ):
        item = provider.search_media(
            "Interstellar"
        ).items[0]

    assert (
        item.availability
        is availability
    )
    assert (
        item.request_eligible
        is False
    )


def test_search_rejects_unknown_media_type() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={
            "page": 1,
            "totalPages": 1,
            "results": [
                {
                    "id": 1,
                    "mediaType": "collection",
                }
            ],
        },
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="mediaType",
        ):
            provider.search_media(
                "Example"
            )


def test_discovery_rejects_specialized_type_guessing() -> None:
    with pytest.raises(
        MediaRequestProviderError,
        match="movie or tv",
    ):
        _provider().discover_media(
            "anime_tv"
        )


@pytest.mark.parametrize(
    "page",
    [
        0,
        -1,
        True,
    ],
)
def test_discovery_requires_positive_page(
    page: object,
) -> None:
    with pytest.raises(
        MediaRequestProviderError,
        match="positive integer",
    ):
        _provider().discover_media(
            "movie",
            page=page,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
    ],
)
def test_search_requires_nonempty_query(
    query: str,
) -> None:
    with pytest.raises(
        MediaRequestProviderError,
        match="query is required",
    ):
        _provider().search_media(
            query
        )


@pytest.mark.parametrize(
    "status",
    [
        0,
        8,
        99,
    ],
)
def test_invalid_media_info_status_fails_closed(
    status: int,
) -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={
            "page": 1,
            "totalPages": 1,
            "results": [
                _movie(
                    media_info={
                        "status": status
                    }
                )
            ],
        },
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="availability status",
        ):
            provider.search_media(
                "Interstellar"
            )


def test_media_info_must_be_object_when_present() -> None:
    provider = _provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={
            "page": 1,
            "totalPages": 1,
            "results": [
                _movie(
                    media_info=[]
                )
            ],
        },
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="mediaInfo",
        ):
            provider.search_media(
                "Interstellar"
            )
