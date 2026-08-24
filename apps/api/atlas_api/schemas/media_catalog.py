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

        return cls(
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
