"""Contract tests for the media dashboard endpoint."""

from __future__ import annotations

from pathlib import Path
import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from atlas_api.dependencies import get_current_user
from atlas_api.main import create_app
from atlas_api.routes.v1.dashboard_media import (
    get_dashboard_media_summary_service,
)
from atlas_api.services.dashboard_media import (
    DashboardMediaSummaryService,
)


class DashboardMediaEndpointTests(
    unittest.TestCase
):
    """Verify the authenticated media summary endpoint."""

    def setUp(self) -> None:
        self.app = create_app()
        self.app.dependency_overrides[
            get_current_user
        ] = lambda: object()
        self.app.dependency_overrides[
            get_dashboard_media_summary_service
        ] = lambda: DashboardMediaSummaryService(
            Path("/missing/atlas/latest.json")
        )

        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_media_summary_returns_success(self) -> None:
        response = self.client.get(
            "/api/v1/dashboard/media"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

    def test_media_summary_returns_stable_contract(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/dashboard/media"
        )
        payload = response.json()

        self.assertEqual(
            {
                "generated_at",
                "libraries",
            },
            set(payload),
        )
        self.assertEqual(
            [
                "movies",
                "television",
                "anime-movies",
                "anime-television",
                "music",
                "books",
                "photos",
            ],
            [
                library["id"]
                for library in payload["libraries"]
            ],
        )

        expected_fields = {
            "id",
            "label",
            "count",
            "status",
            "detail",
        }

        for library in payload["libraries"]:
            self.assertEqual(
                expected_fields,
                set(library),
            )

    def test_media_summary_requires_authentication(
        self,
    ) -> None:
        def unauthorized() -> None:
            raise HTTPException(
                status_code=401,
                detail="Unauthorized",
            )

        self.app.dependency_overrides[
            get_current_user
        ] = unauthorized

        response = self.client.get(
            "/api/v1/dashboard/media"
        )

        self.assertEqual(
            401,
            response.status_code,
        )


if __name__ == "__main__":
    unittest.main()
