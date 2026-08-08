"""Contract tests for the Atlas API health endpoint."""

import unittest

from fastapi.testclient import TestClient

from atlas_api.main import create_app


class HealthEndpointTests(unittest.TestCase):
    """Verify the public health endpoint contract."""

    def setUp(self) -> None:
        self.client = TestClient(create_app())

    def test_health_returns_success(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(response.status_code, 200)

    def test_health_returns_stable_contract(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(
            response.json(),
            {
                "status": "ok",
                "service": "atlas-api",
                "api_version": "v1",
            },
        )

    def test_health_rejects_unknown_fields_in_contract(self) -> None:
        response = self.client.get("/api/v1/health")

        self.assertEqual(
            set(response.json()),
            {
                "status",
                "service",
                "api_version",
            },
        )


if __name__ == "__main__":
    unittest.main()
