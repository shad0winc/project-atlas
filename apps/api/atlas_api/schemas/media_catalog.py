"""Authenticated media-catalog API response contracts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict

from atlas.media import MediaItem


class MediaCatalogItemResponse(BaseModel):
    """One provider-backed media item exposed by the Atlas catalog."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    provider: str
    item_id: str
    media_type: str
    title: str
    year: int | None = None
    library: str | None = None
    video_width: int | None = None
    video_height: int | None = None

    @classmethod
    def from_domain(
        cls,
        item: MediaItem,
    ) -> Self:
        """Adapt one validated provider-neutral media item."""

        if not isinstance(item, MediaItem):
            raise TypeError(
                "item must be MediaItem"
            )

        year = item.metadata.get("year")
        library = item.metadata.get("library")

        dimensions = {key: item.metadata.get(key) for key in ("video_width", "video_height")}
        valid_dimensions = all(isinstance(x, int) and not isinstance(x, bool) and 0 < x <= 32768
                               for x in dimensions.values())

        return cls(
            video_width=dimensions["video_width"] if valid_dimensions else None,
            video_height=dimensions["video_height"] if valid_dimensions else None,
            provider=item.provider,
            item_id=item.item_id,
            media_type=item.media_type,
            title=item.title,
            year=(
                year
                if isinstance(year, int)
                and not isinstance(year, bool)
                else None
            ),
            library=(
                library.strip()
                if isinstance(library, str)
                and library.strip()
                else None
            ),
        )


class MediaCatalogResponse(BaseModel):
    """One bounded page of provider-backed Atlas media."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    provider: str
    page: int
    page_size: int
    total: int
    items: tuple[MediaCatalogItemResponse, ...]
