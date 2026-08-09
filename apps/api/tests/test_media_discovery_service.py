"""Tests for the Atlas media discovery API service."""

from __future__ import annotations

import pytest

from atlas.media_requests import (
    MediaDiscoveryAvailability,
    MediaDiscoveryItem,
    MediaDiscoveryPage,
    MediaRequestProviderOperationError,
)

from atlas_api.services.media_discovery import (
    MediaDiscoveryAPIService,
    MediaDiscoveryUnavailableError,
    MediaDiscoveryValidationError,
)


def _page(
) -> MediaDiscoveryPage:
    return MediaDiscoveryPage(
        items=(
            MediaDiscoveryItem(
                provider_media_id="157336",
                media_type="movie",
                title="Interstellar",
                year=2014,
                availability=(
                    MediaDiscoveryAvailability
                    .NOT_TRACKED
                ),
            ),
        ),
        page=1,
        total_pages=3,
    )


class DiscoveryProviderStub:
    def __init__(
        self,
        *,
        error: Exception | None = None,
    ) -> None:
        self.error = error
        self.search_calls: list[
            tuple[str, int]
        ] = []
        self.discover_calls: list[
            tuple[str, int]
        ] = []

    def search_media(
        self,
        query: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        self.search_calls.append(
            (
                query,
                page,
            )
        )

        if self.error is not None:
            raise self.error

        return _page()

    def discover_media(
        self,
        media_type: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        self.discover_calls.append(
            (
                media_type,
                page,
            )
        )

        if self.error is not None:
            raise self.error

        return _page()


def test_search_normalizes_query_and_forwards_page() -> None:
    provider = DiscoveryProviderStub()

    result = MediaDiscoveryAPIService(
        provider
    ).search(
        " Interstellar ",
        page=2,
    )

    assert result.items
    assert provider.search_calls == [
        (
            "Interstellar",
            2,
        )
    ]


def test_discover_forwards_normalized_type() -> None:
    provider = DiscoveryProviderStub()

    MediaDiscoveryAPIService(
        provider
    ).discover(
        " MOVIE ",
        page=3,
    )

    assert provider.discover_calls == [
        (
            "movie",
            3,
        )
    ]


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
    ],
)
def test_search_rejects_empty_query(
    query: str,
) -> None:
    with pytest.raises(
        MediaDiscoveryValidationError,
        match="query",
    ):
        MediaDiscoveryAPIService(
            DiscoveryProviderStub()
        ).search(
            query
        )


def test_discover_rejects_unsupported_type() -> None:
    with pytest.raises(
        MediaDiscoveryValidationError,
        match="movie or tv",
    ):
        MediaDiscoveryAPIService(
            DiscoveryProviderStub()
        ).discover(
            "anime_tv"
        )


def test_provider_failure_becomes_unavailable() -> None:
    service = MediaDiscoveryAPIService(
        DiscoveryProviderStub(
            error=(
                MediaRequestProviderOperationError(
                    "unreachable"
                )
            )
        )
    )

    with pytest.raises(
        MediaDiscoveryUnavailableError,
    ):
        service.search(
            "Interstellar"
        )


def test_provider_requires_both_read_methods() -> None:
    with pytest.raises(
        TypeError,
    ):
        MediaDiscoveryAPIService(
            object()  # type: ignore[arg-type]
        )
