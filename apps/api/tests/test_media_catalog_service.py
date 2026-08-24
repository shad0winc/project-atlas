"""Bounded media-catalog service regressions."""

from __future__ import annotations

import pytest

from atlas.media import MediaItem
from atlas_api.services.media_catalog import (
    MediaCatalogService,
)


class FakeProvider:
    name = "jellyfin"

    def __init__(self) -> None:
        self.requested: list[str] = []

    def list_media_item_ids(
        self,
        *,
        page_size: int = 200,
    ) -> tuple[str, ...]:
        return tuple(
            f"item-{index}"
            for index in range(1, 51)
        )

    def get_item(
        self,
        item_id: str,
    ) -> MediaItem:
        self.requested.append(item_id)

        return MediaItem(
            provider="jellyfin",
            item_id=item_id,
            media_type="movie",
            title=f"Title {item_id}",
        )


class TestMediaCatalogService:
    def test_hydrates_only_requested_page(
        self,
    ) -> None:
        provider = FakeProvider()
        service = MediaCatalogService(provider)

        result = service.read_page(
            page=2,
            page_size=3,
        )

        assert result.provider == "jellyfin"
        assert result.page == 2
        assert result.page_size == 3
        assert result.total == 50

        assert provider.requested == [
            "item-4",
            "item-5",
            "item-6",
        ]

        assert tuple(
            item.item_id
            for item in result.items
        ) == (
            "item-4",
            "item-5",
            "item-6",
        )

    def test_page_beyond_catalog_is_empty(
        self,
    ) -> None:
        provider = FakeProvider()
        service = MediaCatalogService(provider)

        result = service.read_page(
            page=100,
            page_size=24,
        )

        assert result.total == 50
        assert result.items == ()
        assert provider.requested == []

    @pytest.mark.parametrize(
        ("page", "page_size"),
        [
            (0, 24),
            (-1, 24),
            (True, 24),
            (1, 0),
            (1, 101),
            (1, True),
        ],
    )
    def test_rejects_invalid_pagination(
        self,
        page: int,
        page_size: int,
    ) -> None:
        service = MediaCatalogService(
            FakeProvider()
        )

        with pytest.raises(ValueError):
            service.read_page(
                page=page,
                page_size=page_size,
            )
