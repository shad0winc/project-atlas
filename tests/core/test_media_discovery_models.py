"""Contract tests for Atlas media discovery models."""

from __future__ import annotations

import pytest

from atlas.media_requests import (
    MediaDiscoveryAvailability,
    MediaDiscoveryError,
    MediaDiscoveryItem,
    MediaDiscoveryPage,
    MediaRequestType,
)


def _item(
    *,
    provider_media_id: str = "157336",
    availability: MediaDiscoveryAvailability = (
        MediaDiscoveryAvailability
        .NOT_TRACKED
    ),
) -> MediaDiscoveryItem:
    return MediaDiscoveryItem(
        provider_media_id=(
            provider_media_id
        ),
        media_type="movie",
        title=" Interstellar ",
        year=2014,
        overview=" Space. ",
        poster_path="/poster.jpg",
        availability=availability,
    )


def test_discovery_item_normalizes_and_serializes() -> None:
    item = _item()

    assert item.provider_media_id == "157336"
    assert item.media_type is MediaRequestType.MOVIE
    assert item.title == "Interstellar"
    assert item.overview == "Space."
    assert item.poster_path == "/poster.jpg"
    assert item.request_eligible is True

    assert item.to_dict() == {
        "provider_media_id": "157336",
        "media_type": "movie",
        "title": "Interstellar",
        "year": 2014,
        "overview": "Space.",
        "poster_path": "/poster.jpg",
        "availability": "not_tracked",
        "request_eligible": True,
    }


def test_discovery_item_requires_provider_media_identity() -> None:
    with pytest.raises(
        MediaDiscoveryError,
        match="provider_media_id is required",
    ):
        _item(
            provider_media_id=""
        )


@pytest.mark.parametrize(
    "value",
    [
        "abc",
        "tmdb:157336",
        "0",
        "-1",
    ],
)
def test_discovery_item_requires_positive_numeric_tmdb_identity(
    value: str,
) -> None:
    with pytest.raises(
        MediaDiscoveryError,
        match="TMDB identifier",
    ):
        _item(
            provider_media_id=value
        )


@pytest.mark.parametrize(
    "media_type",
    [
        "anime_movie",
        "anime_tv",
        "sports",
    ],
)
def test_discovery_item_does_not_guess_specialized_media_types(
    media_type: str,
) -> None:
    with pytest.raises(
        MediaDiscoveryError,
        match="movie or tv",
    ):
        MediaDiscoveryItem(
            provider_media_id="1",
            media_type=media_type,
            title="Example",
            availability="not_tracked",
        )


@pytest.mark.parametrize(
    "availability",
    [
        MediaDiscoveryAvailability.UNKNOWN,
        MediaDiscoveryAvailability.PENDING,
        MediaDiscoveryAvailability.PROCESSING,
        MediaDiscoveryAvailability.PARTIALLY_AVAILABLE,
        MediaDiscoveryAvailability.AVAILABLE,
        MediaDiscoveryAvailability.BLOCKLISTED,
        MediaDiscoveryAvailability.DELETED,
    ],
)
def test_only_untracked_media_is_immediately_request_eligible(
    availability: MediaDiscoveryAvailability,
) -> None:
    assert (
        _item(
            availability=availability
        ).request_eligible
        is False
    )


def test_discovery_page_tracks_provider_pagination() -> None:
    page = MediaDiscoveryPage(
        items=(
            _item(),
        ),
        page=1,
        total_pages=3,
    )

    assert page.next_page == 2

    assert page.to_dict()[
        "next_page"
    ] == 2


def test_discovery_page_last_page_has_no_next_page() -> None:
    page = MediaDiscoveryPage(
        items=(
            _item(),
        ),
        page=3,
        total_pages=3,
    )

    assert page.next_page is None


def test_discovery_page_rejects_duplicate_item_identity() -> None:
    with pytest.raises(
        MediaDiscoveryError,
        match="identities",
    ):
        MediaDiscoveryPage(
            items=(
                _item(),
                _item(),
            ),
            page=1,
            total_pages=1,
        )


def test_discovery_contract_is_publicly_exported() -> None:
    import atlas.media_requests as media_requests

    assert (
        media_requests
        .MediaDiscoveryAvailability
        is MediaDiscoveryAvailability
    )
    assert (
        media_requests
        .MediaDiscoveryItem
        is MediaDiscoveryItem
    )
    assert (
        media_requests
        .MediaDiscoveryPage
        is MediaDiscoveryPage
    )
