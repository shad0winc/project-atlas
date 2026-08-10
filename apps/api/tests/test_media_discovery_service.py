"""Tests for the Atlas media discovery API service."""

from __future__ import annotations

import pytest

from atlas.media_requests import (
    MediaDiscoveryAvailability,
    MediaDiscoveryItem,
    MediaDiscoveryPage,
    MediaRequestProviderOperationError,
    MediaSeriesDetail,
    MediaSeriesSeason,
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


def _detail(
) -> MediaSeriesDetail:
    return MediaSeriesDetail(
        provider_media_id="1399",
        title="Game of Thrones",
        year=2011,
        status="returning",
        in_production=True,
        is_anime=True,
        availability="not_tracked",
        seasons=(
            MediaSeriesSeason(
                season_number=1,
                name="Season 1",
                episode_count=10,
                air_date="2011-04-17",
            ),
        ),
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
        self.detail_calls: list[
            str
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

    def get_tv_detail(
        self,
        provider_media_id: str | int,
    ) -> MediaSeriesDetail:
        self.detail_calls.append(
            str(provider_media_id)
        )

        if self.error is not None:
            raise self.error

        return _detail()


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


def test_tv_detail_normalizes_provider_identity() -> None:
    provider = DiscoveryProviderStub()

    detail = MediaDiscoveryAPIService(
        provider
    ).tv_detail(
        " 1399 "
    )

    assert detail.provider_media_id == "1399"
    assert provider.detail_calls == [
        "1399"
    ]


@pytest.mark.parametrize(
    "provider_media_id",
    [
        "",
        "abc",
        "0",
        -1,
        True,
    ],
)
def test_tv_detail_rejects_invalid_provider_identity(
    provider_media_id: object,
) -> None:
    with pytest.raises(
        MediaDiscoveryValidationError,
        match="provider_media_id",
    ):
        MediaDiscoveryAPIService(
            DiscoveryProviderStub()
        ).tv_detail(
            provider_media_id  # type: ignore[arg-type]
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


def test_provider_requires_all_read_methods() -> None:
    with pytest.raises(
        TypeError,
    ):
        MediaDiscoveryAPIService(
            object()  # type: ignore[arg-type]
        )

def test_provider_requires_tv_detail_method() -> None:
    class IncompleteProvider:
        def search_media(
            self,
            query: str,
            *,
            page: int = 1,
        ) -> MediaDiscoveryPage:
            return _page()

        def discover_media(
            self,
            media_type: str,
            *,
            page: int = 1,
        ) -> MediaDiscoveryPage:
            return _page()

    with pytest.raises(
        TypeError,
        match="get_tv_detail",
    ):
        MediaDiscoveryAPIService(
            IncompleteProvider()  # type: ignore[arg-type]
        )
