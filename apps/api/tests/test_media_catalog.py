"""Authenticated media-catalog route regressions."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.media import MediaItem
from atlas_api.dependencies import clear_dependency_caches
from atlas_api.main import app
from atlas_api.routes.v1.media_catalog import (
    get_media_catalog_service,
)
from atlas_api.services.media_catalog import (
    MediaCatalogPage,
)


class FakeCatalogService:
    def read_page(
        self,
        *,
        page: int,
        page_size: int,
    ) -> MediaCatalogPage:
        return MediaCatalogPage(
            provider="jellyfin",
            page=page,
            page_size=page_size,
            total=1,
            items=(
                MediaItem(
                    provider="jellyfin",
                    item_id="jf-interstellar",
                    media_type="movie",
                    title="Interstellar",
                    metadata={
                        "year": 2014,
                        "library": "Movies",
                    },
                ),
            ),
        )


class TestMediaCatalogAPI:
    def test_openapi_registers_media_catalog_route(
        self,
    ) -> None:
        schema = app.openapi()

        assert (
            "/api/v1/media/catalog"
            in schema["paths"]
        )

    def test_media_catalog_requires_authentication(
        self,
        monkeypatch,
        tmp_path,
    ) -> None:
        audit_path = tmp_path / "events.jsonl"
        audit_path.write_text("", encoding="utf-8")
        audit_path.chmod(0o660)

        monkeypatch.setenv(
            "ATLAS_JWT_SECRET",
            "atlas-media-catalog-test-secret-0123456789abcdef",
        )
        monkeypatch.setenv(
            "ATLAS_SECURITY_AUDIT_PATH",
            str(audit_path),
        )

        clear_dependency_caches()

        try:
            client = TestClient(app)

            response = client.get(
                "/api/v1/media/catalog"
            )

            assert response.status_code == 401
        finally:
            clear_dependency_caches()
