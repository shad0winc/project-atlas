"""Transport schemas for read-only Atlas media discovery."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
)

from atlas.media_requests import (
    MediaDiscoveryItem,
    MediaDiscoveryPage,
    MediaSeriesDetail,
    MediaSeriesSeason,
)


class MediaDiscoveryItemResponse(
    BaseModel
):
    """One normalized movie/TV discovery item."""

    model_config = ConfigDict(
        frozen=True
    )

    provider_media_id: str
    media_type: str
    title: str
    year: int | None
    overview: str | None
    poster_path: str | None
    availability: str
    request_eligible: bool

    @classmethod
    def from_domain(
        cls,
        item: MediaDiscoveryItem,
    ) -> "MediaDiscoveryItemResponse":
        return cls(
            provider_media_id=(
                item.provider_media_id
            ),
            media_type=(
                item.media_type.value
            ),
            title=item.title,
            year=item.year,
            overview=item.overview,
            poster_path=item.poster_path,
            availability=(
                item.availability.value
            ),
            request_eligible=(
                item.request_eligible
            ),
        )


class MediaDiscoveryPageResponse(
    BaseModel
):
    """One normalized page of Atlas media discovery."""

    model_config = ConfigDict(
        frozen=True
    )

    items: list[
        MediaDiscoveryItemResponse
    ]
    page: int
    total_pages: int
    next_page: int | None

    @classmethod
    def from_domain(
        cls,
        page: MediaDiscoveryPage,
    ) -> "MediaDiscoveryPageResponse":
        return cls(
            items=[
                MediaDiscoveryItemResponse
                .from_domain(item)
                for item
                in page.items
            ],
            page=page.page,
            total_pages=(
                page.total_pages
            ),
            next_page=(
                page.next_page
            ),
        )

class MediaSeriesSeasonResponse(
    BaseModel
):
    """One normalized non-special TV season."""

    model_config = ConfigDict(
        frozen=True
    )

    season_number: int
    name: str
    episode_count: int
    air_date: str | None

    @classmethod
    def from_domain(
        cls,
        season: MediaSeriesSeason,
    ) -> "MediaSeriesSeasonResponse":
        return cls(
            season_number=(
                season.season_number
            ),
            name=season.name,
            episode_count=(
                season.episode_count
            ),
            air_date=(
                season.air_date
            ),
        )


class MediaSeriesDetailResponse(
    BaseModel
):
    """Normalized TV-series detail for explicit season selection."""

    model_config = ConfigDict(
        frozen=True
    )

    provider_media_id: str
    title: str
    year: int | None
    overview: str | None
    poster_path: str | None
    status: str
    in_production: bool
    is_ongoing: bool
    is_anime: bool
    availability: str
    request_eligible: bool
    seasons: list[
        MediaSeriesSeasonResponse
    ]

    @classmethod
    def from_domain(
        cls,
        detail: MediaSeriesDetail,
    ) -> "MediaSeriesDetailResponse":
        return cls(
            provider_media_id=(
                detail.provider_media_id
            ),
            title=detail.title,
            year=detail.year,
            overview=detail.overview,
            poster_path=(
                detail.poster_path
            ),
            status=(
                detail.status.value
            ),
            in_production=(
                detail.in_production
            ),
            is_ongoing=(
                detail.is_ongoing
            ),
            is_anime=(
                detail.is_anime
            ),
            availability=(
                detail.availability.value
            ),
            request_eligible=(
                detail.request_eligible
            ),
            seasons=[
                MediaSeriesSeasonResponse
                .from_domain(season)
                for season
                in detail.seasons
            ],
        )
