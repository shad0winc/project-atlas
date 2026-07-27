"""Contract tests for the media dashboard endpoint."""

from __future__ import annotations

from pathlib import Path
import unittest

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.main import create_app
from atlas_api.routes.v1.dashboard_media import (
    get_dashboard_media_summary_service,
    require_media_dashboard_read,
)
from atlas_api.services.dashboard_media import (
    DashboardMediaSummaryService,
)


def _authenticated_user() -> AuthenticatedUser:
    """Return a stable authenticated user for endpoint tests."""

    return AuthenticatedUser(
        user_id="usr_media_dashboard",
        username="michael",
        display_name="Michael",
        roles=("member",),
        provider="jellyfin",
        metadata={},
    )


class DashboardMediaEndpointTests(
    unittest.TestCase
):
    """Verify the authorized media summary endpoint."""

    def setUp(self) -> None:
        self.app = create_app()
        self.app.dependency_overrides[
            require_media_dashboard_read
        ] = _authenticated_user
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
        def unauthenticated() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        self.app.dependency_overrides[
            require_media_dashboard_read
        ] = unauthenticated

        response = self.client.get(
            "/api/v1/dashboard/media"
        )

        self.assertEqual(
            401,
            response.status_code,
        )
        self.assertEqual(
            response.headers["www-authenticate"],
            "Bearer",
        )

    def test_media_summary_rejects_missing_permission(
        self,
    ) -> None:
        def forbidden() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "No assigned role or direct grant provides the "
                    "requested permission."
                ),
            )

        self.app.dependency_overrides[
            require_media_dashboard_read
        ] = forbidden

        response = self.client.get(
            "/api/v1/dashboard/media"
        )

        self.assertEqual(
            403,
            response.status_code,
        )
        self.assertEqual(
            {
                "detail": (
                    "No assigned role or direct grant provides the "
                    "requested permission."
                )
            },
            response.json(),
        )


if __name__ == "__main__":
    unittest.main()
