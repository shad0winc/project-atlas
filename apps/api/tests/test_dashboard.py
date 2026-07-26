"""Contract tests for the Atlas dashboard summary endpoint."""

import unittest

from fastapi import HTTPException
from fastapi.testclient import TestClient

from atlas.health import HealthCheck, HealthReport
from atlas_api.dependencies import get_current_user
from atlas_api.main import create_app
from atlas_api.routes.v1.dashboard import (
    get_dashboard_summary_service,
)
from atlas_api.services.dashboard import DashboardSummaryService


class DashboardSummaryEndpointTests(unittest.TestCase):
    """Verify the authenticated dashboard summary endpoint contract."""

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
        self.app.dependency_overrides[get_current_user] = lambda: object()
        self.app.dependency_overrides[
            get_dashboard_summary_service
        ] = lambda: DashboardSummaryService(lambda: report)

        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_dashboard_summary_returns_success(self) -> None:
        response = self.client.get("/api/v1/dashboard/summary")

        self.assertEqual(response.status_code, 200)

    def test_dashboard_summary_returns_stable_contract(self) -> None:
        response = self.client.get("/api/v1/dashboard/summary")
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
        def unauthorized():
            raise HTTPException(status_code=401, detail="Unauthorized")

        self.app.dependency_overrides[get_current_user] = unauthorized

        response = self.client.get("/api/v1/dashboard/summary")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
