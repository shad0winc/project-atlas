"""Contract tests for the media-library detail endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import unittest

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas_api.auth.models import AuthenticatedUser
from atlas_api.main import create_app
from atlas_api.routes.v1.media_libraries import (
    get_media_library_detail_service,
    require_media_library_read,
)
from atlas_api.services.media_library import (
    MediaLibraryDetailService,
)


def _authenticated_user() -> AuthenticatedUser:
    """Return a stable authenticated user for endpoint tests."""

    return AuthenticatedUser(
        user_id="usr_media_library",
        username="michael",
        display_name="Michael",
        roles=("member",),
        provider="jellyfin",
        metadata={},
    )


def _missing_snapshot_service(
) -> MediaLibraryDetailService:
    """Return a deterministic unavailable-detail service."""

    return MediaLibraryDetailService(
        Path("/missing/atlas/latest.json"),
        clock=lambda: datetime(
            2026,
            7,
            28,
            2,
            0,
            tzinfo=timezone.utc,
        ),
    )


class MediaLibraryEndpointTests(
    unittest.TestCase
):
    """Verify the authorized media-library detail endpoint."""

    def setUp(self) -> None:
        self.app = create_app()

        self.app.dependency_overrides[
            require_media_library_read
        ] = _authenticated_user

        self.app.dependency_overrides[
            get_media_library_detail_service
        ] = _missing_snapshot_service

        self.client = TestClient(
            self.app
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_media_library_detail_returns_success(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/libraries/movies"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

    def test_media_library_detail_returns_stable_contract(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/libraries/movies"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            {
                "id": "movies",
                "label": "Movies",
                "status": "unavailable",
                "generated_at": "2026-07-28T02:00:00Z",
                "count": None,
                "detail": (
                    "Unable to read the latest ARI snapshot: "
                    "FileNotFoundError"
                ),
                "filesystem": None,
                "provider": None,
                "validation": {
                    "configured": False,
                    "path_matches": None,
                    "synchronization": "unknown",
                },
            },
            response.json(),
        )

    def test_media_library_identity_is_normalized(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/libraries/%20Movies%20"
        )

        self.assertEqual(
            200,
            response.status_code,
        )
        self.assertEqual(
            "movies",
            response.json()["id"],
        )

    def test_unknown_media_library_returns_not_found(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/libraries/games"
        )

        self.assertEqual(
            404,
            response.status_code,
        )
        self.assertEqual(
            {
                "detail": (
                    "Atlas media library was not found."
                )
            },
            response.json(),
        )

    def test_media_library_requires_authentication(
        self,
    ) -> None:
        def unauthenticated() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication is required.",
                headers={
                    "WWW-Authenticate": "Bearer"
                },
            )

        self.app.dependency_overrides[
            require_media_library_read
        ] = unauthenticated

        response = self.client.get(
            "/api/v1/media/libraries/movies"
        )

        self.assertEqual(
            401,
            response.status_code,
        )
        self.assertEqual(
            "Bearer",
            response.headers["www-authenticate"],
        )

    def test_media_library_rejects_missing_permission(
        self,
    ) -> None:
        def forbidden() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "No assigned role or direct grant "
                    "provides the requested permission."
                ),
            )

        self.app.dependency_overrides[
            require_media_library_read
        ] = forbidden

        response = self.client.get(
            "/api/v1/media/libraries/movies"
        )

        self.assertEqual(
            403,
            response.status_code,
        )
        self.assertEqual(
            {
                "detail": (
                    "No assigned role or direct grant "
                    "provides the requested permission."
                )
            },
            response.json(),
        )

    def test_openapi_registers_media_library_route(
        self,
    ) -> None:
        response = self.client.get(
            "/api/openapi.json"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertIn(
            "/api/v1/media/libraries/{library_id}",
            response.json()["paths"],
        )


if __name__ == "__main__":
    unittest.main()
