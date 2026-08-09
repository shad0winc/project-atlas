"""Transport schemas for read-only Atlas media discovery."""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
)

from atlas.media_requests import (
    MediaDiscoveryItem,
    MediaDiscoveryPage,
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
