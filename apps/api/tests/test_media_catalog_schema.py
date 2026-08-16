"""Media-catalog API schema regressions."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from atlas.media import MediaItem
from atlas_api.schemas.media_catalog import (
    MediaCatalogItemResponse,
    MediaCatalogResponse,
)


class TestMediaCatalogSchema:
    def test_adapts_provider_media_item(
        self,
    ) -> None:
        item = MediaItem(
            provider="jellyfin",
            item_id="jf-123",
            media_type="movie",
            title="Interstellar",
            metadata={
                "year": 2014,
                "library": "Movies",
            },
        )

        response = (
            MediaCatalogItemResponse.from_domain(item)
        )

        assert response.provider == "jellyfin"
        assert response.item_id == "jf-123"
        assert response.media_type == "movie"
        assert response.title == "Interstellar"
        assert response.year == 2014
        assert response.library == "Movies"

    def test_item_response_forbids_extra_fields(
        self,
    ) -> None:
        with pytest.raises(ValidationError):
            MediaCatalogItemResponse(
                provider="jellyfin",
                item_id="jf-123",
                media_type="movie",
                title="Interstellar",
                unexpected=True,
            )

    def test_catalog_response_is_frozen(
        self,
    ) -> None:
        response = MediaCatalogResponse(
            provider="jellyfin",
            page=1,
            page_size=24,
            total=0,
            items=(),
        )

        with pytest.raises(ValidationError):
            response.page = 2

    def test_from_domain_rejects_unvalidated_input(
        self,
    ) -> None:
        with pytest.raises(TypeError):
            MediaCatalogItemResponse.from_domain(
                object()
            )
