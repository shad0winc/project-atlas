"""HTTP contract tests for Atlas media discovery."""

from __future__ import annotations

import unittest

from fastapi import (
    HTTPException,
    status,
)
from fastapi.testclient import (
    TestClient,
)

from atlas.media_requests import (
    MediaDiscoveryAvailability,
    MediaDiscoveryItem,
    MediaDiscoveryPage,
    MediaSeriesDetail,
    MediaSeriesSeason,
)

from atlas_api.auth.models import (
    AuthenticatedUser,
)
from atlas_api.main import (
    create_app,
)
from atlas_api.routes.v1.media_discovery import (
    get_media_discovery_api_service,
    require_media_discovery_read,
)
from atlas_api.services.media_discovery import (
    MediaDiscoveryUnavailableError,
)


USER_ID = "usr_" + ("a" * 32)


def authenticated_user(
) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=USER_ID,
        username="michael",
        display_name="Michael",
        roles=("member",),
        provider="jellyfin",
        metadata={},
    )


def result_page(
) -> MediaDiscoveryPage:
    return MediaDiscoveryPage(
        items=(
            MediaDiscoveryItem(
                provider_media_id="157336",
                media_type="movie",
                title="Interstellar",
                year=2014,
                overview="Space.",
                poster_path="/poster.jpg",
                availability="not_tracked",
            ),
            MediaDiscoveryItem(
                provider_media_id="1396",
                media_type="tv",
                title="Breaking Bad",
                year=2008,
                availability="available",
            ),
        ),
        page=1,
        total_pages=3,
    )


def series_detail(
) -> MediaSeriesDetail:
    return MediaSeriesDetail(
        provider_media_id="1399",
        title="Game of Thrones",
        year=2011,
        overview="Dragons.",
        poster_path="/got.jpg",
        status="returning",
        in_production=True,
        is_anime=True,
        availability="not_tracked",
        seasons=(
            MediaSeriesSeason(
                season_number=1,
                name="Season 1",
                episode_count=10,
                availability="not_tracked",
                requestability_known=True,
                request_eligible=True,
                air_date="2011-04-17",
            ),
            MediaSeriesSeason(
                season_number=2,
                name="Season 2",
                episode_count=10,
                availability="not_tracked",
                requestability_known=True,
                request_eligible=True,
                air_date="2012-04-01",
            ),
        ),
    )


class DiscoveryServiceStub:
    def __init__(
        self,
        *,
        unavailable: bool = False,
    ) -> None:
        self.unavailable = unavailable
        self.search_calls: list[
            tuple[str, int]
        ] = []
        self.discover_calls: list[
            tuple[str, int]
        ] = []
        self.detail_calls: list[
            str
        ] = []

    def search(
        self,
        query: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        self.search_calls.append(
            (
                query,
                page,
            )
        )

        if self.unavailable:
            raise MediaDiscoveryUnavailableError(
                "unavailable"
            )

        return result_page()

    def discover(
        self,
        media_type: str,
        *,
        page: int = 1,
    ) -> MediaDiscoveryPage:
        self.discover_calls.append(
            (
                media_type,
                page,
            )
        )

        if self.unavailable:
            raise MediaDiscoveryUnavailableError(
                "unavailable"
            )

        return result_page()

    def tv_detail(
        self,
        provider_media_id: str | int,
    ) -> MediaSeriesDetail:
        self.detail_calls.append(
            str(provider_media_id)
        )

        if self.unavailable:
            raise MediaDiscoveryUnavailableError(
                "unavailable"
            )

        return series_detail()


class MediaDiscoveryEndpointTests(
    unittest.TestCase
):
    def setUp(self) -> None:
        self.app = create_app()
        self.service = (
            DiscoveryServiceStub()
        )

        self.app.dependency_overrides[
            require_media_discovery_read
        ] = authenticated_user

        self.app.dependency_overrides[
            get_media_discovery_api_service
        ] = lambda: self.service

        self.client = TestClient(
            self.app
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_search_returns_normalized_discovery_contract(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/search"
            "?query=Interstellar&page=1"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            [
                (
                    "Interstellar",
                    1,
                )
            ],
            self.service.search_calls,
        )

        payload = response.json()

        self.assertEqual(
            1,
            payload["page"],
        )

        self.assertEqual(
            3,
            payload["total_pages"],
        )

        self.assertEqual(
            2,
            payload["next_page"],
        )

        self.assertEqual(
            {
                "provider_media_id":
                    "157336",
                "media_type":
                    "movie",
                "title":
                    "Interstellar",
                "year":
                    2014,
                "overview":
                    "Space.",
                "poster_path":
                    "/poster.jpg",
                "availability":
                    "not_tracked",
                "request_eligible":
                    True,
            },
            payload["items"][0],
        )

        self.assertFalse(
            payload["items"][1][
                "request_eligible"
            ]
        )

    def test_discover_returns_movie_page(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/discover"
            "?media_type=movie&page=2"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            [
                (
                    "movie",
                    2,
                )
            ],
            self.service.discover_calls,
        )

    def test_tv_detail_returns_normalized_series_contract(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/tv/1399"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            [
                "1399"
            ],
            self.service.detail_calls,
        )

        self.assertEqual(
            {
                "provider_media_id": "1399",
                "title": "Game of Thrones",
                "year": 2011,
                "overview": "Dragons.",
                "poster_path": "/got.jpg",
                "status": "returning",
                "in_production": True,
                "is_ongoing": True,
                "is_anime": True,
                "availability": "not_tracked",
                "request_eligible": True,
                "seasons": [
                    {
                        "season_number": 1,
                        "name": "Season 1",
                        "episode_count": 10,
                        "availability": "not_tracked",
                        "requestability_known": True,
                        "request_eligible": True,
                        "air_date": "2011-04-17",
                    },
                    {
                        "season_number": 2,
                        "name": "Season 2",
                        "episode_count": 10,
                        "availability": "not_tracked",
                        "requestability_known": True,
                        "request_eligible": True,
                        "air_date": "2012-04-01",
                    },
                ],
            },
            response.json(),
        )

    def test_tv_detail_rejects_nonpositive_identity(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/tv/0"
        )

        self.assertEqual(
            422,
            response.status_code,
        )

    def test_tv_detail_provider_failure_is_generic_503(
        self,
    ) -> None:
        self.app.dependency_overrides[
            get_media_discovery_api_service
        ] = lambda: (
            DiscoveryServiceStub(
                unavailable=True
            )
        )

        response = self.client.get(
            "/api/v1/media/tv/1399"
        )

        self.assertEqual(
            503,
            response.status_code,
        )

        self.assertEqual(
            {
                "detail":
                    "Media discovery is unavailable."
            },
            response.json(),
        )

    def test_discover_rejects_specialized_or_unknown_types(
        self,
    ) -> None:
        for media_type in (
            "anime_tv",
            "sports",
            "person",
        ):
            with self.subTest(
                media_type=media_type
            ):
                response = (
                    self.client.get(
                        "/api/v1/media/discover"
                        "?media_type="
                        + media_type
                    )
                )

                self.assertEqual(
                    422,
                    response.status_code,
                )

    def test_page_must_be_positive(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/discover"
            "?media_type=movie&page=0"
        )

        self.assertEqual(
            422,
            response.status_code,
        )

    def test_search_requires_nonempty_query(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/media/search"
            "?query="
        )

        self.assertEqual(
            422,
            response.status_code,
        )

    def test_discovery_requires_authentication(
        self,
    ) -> None:
        def unauthenticated(
        ) -> AuthenticatedUser:
            raise HTTPException(
                status_code=(
                    status.HTTP_401_UNAUTHORIZED
                ),
                detail=(
                    "Bearer authentication "
                    "is required."
                ),
                headers={
                    "WWW-Authenticate":
                        "Bearer"
                },
            )

        self.app.dependency_overrides[
            require_media_discovery_read
        ] = unauthenticated

        response = self.client.get(
            "/api/v1/media/discover"
            "?media_type=movie"
        )

        self.assertEqual(
            401,
            response.status_code,
        )

    def test_discovery_requires_media_read_permission(
        self,
    ) -> None:
        def forbidden(
        ) -> AuthenticatedUser:
            raise HTTPException(
                status_code=(
                    status.HTTP_403_FORBIDDEN
                ),
                detail=(
                    "No assigned role or direct "
                    "grant provides the requested "
                    "permission."
                ),
            )

        self.app.dependency_overrides[
            require_media_discovery_read
        ] = forbidden

        response = self.client.get(
            "/api/v1/media/search"
            "?query=Interstellar"
        )

        self.assertEqual(
            403,
            response.status_code,
        )

    def test_provider_failure_is_generic_503(
        self,
    ) -> None:
        self.app.dependency_overrides[
            get_media_discovery_api_service
        ] = lambda: (
            DiscoveryServiceStub(
                unavailable=True
            )
        )

        response = self.client.get(
            "/api/v1/media/search"
            "?query=Interstellar"
        )

        self.assertEqual(
            503,
            response.status_code,
        )

        self.assertEqual(
            {
                "detail":
                    "Media discovery is unavailable."
            },
            response.json(),
        )

    def test_openapi_registers_discovery_and_series_routes(
        self,
    ) -> None:
        schema = self.client.app.openapi()

        self.assertIn(
            "/api/v1/media/search",
            schema["paths"],
        )

        self.assertIn(
            "/api/v1/media/discover",
            schema["paths"],
        )

        self.assertIn(
            "/api/v1/media/tv/{provider_media_id}",
            schema["paths"],
        )


if __name__ == "__main__":
    unittest.main()
