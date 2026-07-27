"""Contract tests for the Atlas dashboard summary endpoint."""

import unittest

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas.health import HealthCheck, HealthReport
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.main import create_app
from atlas_api.routes.v1.dashboard import (
    get_dashboard_summary_service,
    require_dashboard_read,
)
from atlas_api.services.dashboard import DashboardSummaryService


def _authenticated_user() -> AuthenticatedUser:
    """Return a stable authenticated user for endpoint tests."""

    return AuthenticatedUser(
        user_id="usr_dashboard",
        username="michael",
        display_name="Michael",
        roles=("member",),
        provider="jellyfin",
        metadata={},
    )


class DashboardSummaryEndpointTests(unittest.TestCase):
    """Verify the authorized dashboard summary endpoint contract."""

    def setUp(self) -> None:
        report = HealthReport(
            checks=[
                HealthCheck(
                    "Docker Engine",
                    "infrastructure",
                    "healthy",
                ),
                HealthCheck(
                    "jellyfin",
                    "services",
                    "healthy",
                ),
                HealthCheck(
                    "Movies",
                    "storage",
                    "healthy",
                ),
            ],
            generated_at="2026-07-26T18:00:00Z",
        )

        self.app = create_app()
        self.app.dependency_overrides[
            require_dashboard_read
        ] = _authenticated_user
        self.app.dependency_overrides[
            get_dashboard_summary_service
        ] = lambda: DashboardSummaryService(lambda: report)

        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_dashboard_summary_returns_success(self) -> None:
        response = self.client.get(
            "/api/v1/dashboard/summary"
        )

        self.assertEqual(response.status_code, 200)

    def test_dashboard_summary_returns_stable_contract(self) -> None:
        response = self.client.get(
            "/api/v1/dashboard/summary"
        )
        payload = response.json()

        self.assertEqual(
            set(payload),
            {
                "generated_at",
                "metrics",
            },
        )
        self.assertEqual(
            payload["generated_at"],
            "2026-07-26T18:00:00Z",
        )
        self.assertEqual(
            [metric["id"] for metric in payload["metrics"]],
            [
                "system-health",
                "infrastructure",
                "services",
                "storage",
            ],
        )

        expected_metric_fields = {
            "id",
            "label",
            "value",
            "description",
            "status",
            "detail",
        }

        for metric in payload["metrics"]:
            self.assertEqual(
                set(metric),
                expected_metric_fields,
            )

    def test_dashboard_summary_requires_authentication(self) -> None:
        def unauthenticated() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication is required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        self.app.dependency_overrides[
            require_dashboard_read
        ] = unauthenticated

        response = self.client.get(
            "/api/v1/dashboard/summary"
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.headers["www-authenticate"],
            "Bearer",
        )

    def test_dashboard_summary_rejects_missing_permission(
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
            require_dashboard_read
        ] = forbidden

        response = self.client.get(
            "/api/v1/dashboard/summary"
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "No assigned role or direct grant provides the "
                    "requested permission."
                )
            },
        )


if __name__ == "__main__":
    unittest.main()
