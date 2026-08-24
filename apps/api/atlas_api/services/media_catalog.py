"""Bounded authenticated media-catalog assembly."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from atlas.media import MediaItem
from atlas.media.jellyfin import (
    JellyfinProvider,
    default_jellyfin_provider,
)


class MediaCatalogProvider(Protocol):
    """Minimum provider surface required by the catalog."""

    name: str

    def list_media_item_ids(
        self,
        *,
        page_size: int = 200,
    ) -> tuple[str, ...]:
        """Return catalog item identities."""

    def get_item(
        self,
        item_id: str,
    ) -> MediaItem:
        """Return one normalized catalog item."""


@dataclass(frozen=True, slots=True)
class MediaCatalogPage:
    """Validated bounded catalog page."""

    provider: str
    page: int
    page_size: int
    total: int
    items: tuple[MediaItem, ...]


class MediaCatalogService:
    """Read bounded pages from one media provider."""

    def __init__(
        self,
        provider: MediaCatalogProvider,
    ) -> None:
        if provider is None:
            raise TypeError(
                "provider is required"
            )

        self._provider = provider

    def read_page(
        self,
        *,
        page: int,
        page_size: int,
    ) -> MediaCatalogPage:
        """Return one bounded provider-backed media page."""

        if (
            isinstance(page, bool)
            or not isinstance(page, int)
            or page < 1
        ):
            raise ValueError(
                "page must be a positive integer"
            )

        if (
            isinstance(page_size, bool)
            or not isinstance(page_size, int)
            or page_size < 1
            or page_size > 100
        ):
            raise ValueError(
                "page_size must be between 1 and 100"
            )

        item_ids = self._provider.list_media_item_ids()

        start = (page - 1) * page_size
        stop = start + page_size

        selected_ids = item_ids[start:stop]

        items = tuple(
            self._provider.get_item(item_id)
            for item_id in selected_ids
        )

        return MediaCatalogPage(
            provider=self._provider.name,
            page=page,
            page_size=page_size,
            total=len(item_ids),
            items=items,
        )


def build_default_media_catalog_service(
) -> MediaCatalogService:
    """Build the configured Jellyfin-backed media catalog."""

    provider: JellyfinProvider = (
        default_jellyfin_provider()
    )

    return MediaCatalogService(provider)
