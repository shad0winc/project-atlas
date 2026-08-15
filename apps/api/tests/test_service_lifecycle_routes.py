"""HTTP contract tests for read-only Service Lifecycle API routes."""

from __future__ import annotations

import unittest

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas.service_lifecycle import ServiceLifecycleError
from atlas_api.dependencies import (
    get_service_lifecycle_service,
    get_service_maintenance_history_service,
    get_service_update_service,
)
from atlas_api.main import create_app
from atlas_api.routes.v1.services import (
    require_service_lifecycle_read,
)


class Serializable:
    """Deterministic stand-in for one serialized domain contract."""

    def __init__(
        self,
        payload: dict[str, object],
    ) -> None:
        self.payload = payload

    def to_dict(self) -> dict[str, object]:
        return dict(self.payload)


class FakeServiceLifecycleService:
    """Read-only Service Lifecycle double for HTTP contract tests."""

    def __init__(self) -> None:
        self.fail_list = False
        self.fail_health = False
        self.fail_summary = False
        self.inspect_calls: list[str] = []

        self.services = (
            Serializable(
                {
                    "identifier": "jellyfin",
                    "name": "Jellyfin",
                    "provider": "docker-compose",
                    "enabled": True,
                }
            ),
            Serializable(
                {
                    "identifier": "sonarr",
                    "name": "Sonarr",
                    "provider": "docker-compose",
                    "enabled": True,
                }
            ),
        )

    def list_services(self):
        if self.fail_list:
            raise ServiceLifecycleError(
                "service provider failed to list services"
            )

        return self.services

    def inspect_service(
        self,
        identifier: str,
    ):
        self.inspect_calls.append(identifier)

        normalized = identifier.strip().casefold()

        for service in self.services:
            if (
                service.to_dict().get("identifier")
                == normalized
            ):
                return service

        raise ServiceLifecycleError(
            f"Docker Compose service was not found: {normalized}"
        )

    def inspect_health_report(self):
        if self.fail_health:
            raise ServiceLifecycleError(
                "service provider failed to inspect health"
            )

        return Serializable(
            {
                "status": "healthy",
                "score": 100,
                "total_services": 2,
                "counts": {
                    "healthy": 2,
                    "degraded": 0,
                    "unhealthy": 0,
                    "unknown": 0,
                },
                "services": [],
                "evaluated_at": "2026-08-14T00:00:00Z",
            }
        )

    def inspect_summary(self):
        if self.fail_summary:
            raise ServiceLifecycleError(
                "service provider failed to inspect runtime"
            )

        return Serializable(
            {
                "provider": "docker-compose",
                "compose_project": "project-atlas",
                "total_services": 2,
                "service_counts": {
                    "enabled": 2,
                    "disabled": 0,
                },
                "runtime_counts": {
                    "running": 2,
                    "stopped": 0,
                    "restarting": 0,
                    "failed": 0,
                    "unknown": 0,
                },
                "health_counts": {
                    "healthy": 2,
                    "degraded": 0,
                    "unhealthy": 0,
                    "unknown": 0,
                },
                "score": 100,
                "status": "healthy",
                "services": [],
                "evaluated_at": "2026-08-14T00:00:00Z",
            }
        )


class FakeServiceUpdateService:
    """Deterministic read-only Update Discovery HTTP double."""

    def __init__(self) -> None:
        self.fail = False
        self.calls = 0

    def inspect_updates(self):
        self.calls += 1

        if self.fail:
            raise ServiceLifecycleError(
                "service provider failed to inspect update"
            )

        return Serializable(
            {
                "status": "updates-available",
                "provider": "docker-compose",
                "total_services": 2,
                "counts": {
                    "current": 1,
                    "update-available": 1,
                    "mutable-tag": 0,
                    "unknown": 0,
                    "unsupported": 0,
                },
                "requires_attention": True,
                "attention": [
                    {
                        "service_identifier": "sonarr",
                        "service_name": "Sonarr",
                        "status": "update-available",
                    }
                ],
                "updates": [
                    {
                        "service_identifier": "sonarr",
                        "service_name": "Sonarr",
                        "status": "update-available",
                    },
                    {
                        "service_identifier": "jellyfin",
                        "service_name": "Jellyfin",
                        "status": "current",
                    },
                ],
                "evaluated_at": "2026-08-15T00:00:00Z",
            }
        )


class FakeServiceMaintenanceHistoryService:
    """Deterministic read-only Maintenance History HTTP double."""

    def __init__(self) -> None:
        self.fail = False
        self.calls = 0

    def inspect_history(self):
        self.calls += 1
        if self.fail:
            raise ServiceLifecycleError(
                "service provider failed to inspect maintenance history"
            )
        return Serializable({
            "provider": "docker-compose",
            "generated_at": "2026-08-15T00:00:00Z",
            "total_records": 2,
            "counts": {"success": 1, "partial": 0, "failed": 1},
            "requires_attention": True,
            "latest_record": None,
            "latest_success": None,
            "latest_failure": None,
            "records": [],
        })


class ServiceLifecycleRouteTests(unittest.TestCase):
    """Verify GET-only Service Lifecycle HTTP behavior."""

    def setUp(self) -> None:
        self.app = create_app()
        self.service = FakeServiceLifecycleService()
        self.update_service = FakeServiceUpdateService()
        self.history_service = FakeServiceMaintenanceHistoryService()

        self.app.dependency_overrides[
            get_service_lifecycle_service
        ] = lambda: self.service

        self.app.dependency_overrides[
            get_service_update_service
        ] = lambda: self.update_service

        self.app.dependency_overrides[
            get_service_maintenance_history_service
        ] = lambda: self.history_service

        self.app.dependency_overrides[
            require_service_lifecycle_read
        ] = lambda: object()

        self.client = TestClient(self.app)

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.client.close()

    def test_lists_managed_services(self) -> None:
        response = self.client.get(
            "/api/v1/services"
        )

        self.assertEqual(
            status.HTTP_200_OK,
            response.status_code,
        )

        payload = response.json()

        self.assertEqual(2, payload["count"])
        self.assertEqual(
            ["jellyfin", "sonarr"],
            [
                item["identifier"]
                for item in payload["services"]
            ],
        )

    def test_reads_managed_service_detail(self) -> None:
        response = self.client.get(
            "/api/v1/services/SONARR"
        )

        self.assertEqual(
            status.HTTP_200_OK,
            response.status_code,
        )

        self.assertEqual(
            "sonarr",
            response.json()["service"]["identifier"],
        )

        self.assertEqual(
            ["SONARR"],
            self.service.inspect_calls,
        )

    def test_unknown_managed_service_returns_404(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/services/missing"
        )

        self.assertEqual(
            status.HTTP_404_NOT_FOUND,
            response.status_code,
        )

        self.assertEqual(
            {
                "detail":
                    "Atlas managed service was not found."
            },
            response.json(),
        )

    def test_reads_aggregate_health(self) -> None:
        response = self.client.get(
            "/api/v1/services/health"
        )

        self.assertEqual(
            status.HTTP_200_OK,
            response.status_code,
        )

        self.assertEqual(
            "healthy",
            response.json()["health"]["status"],
        )

        self.assertEqual(
            100,
            response.json()["health"]["score"],
        )

    def test_reads_infrastructure_summary(self) -> None:
        response = self.client.get(
            "/api/v1/services/summary"
        )

        self.assertEqual(
            status.HTTP_200_OK,
            response.status_code,
        )

        payload = response.json()["summary"]

        self.assertEqual(
            "docker-compose",
            payload["provider"],
        )

        self.assertEqual(
            2,
            payload["total_services"],
        )

    def test_reads_service_update_report(self) -> None:
        response = self.client.get(
            "/api/v1/services/updates"
        )

        self.assertEqual(
            status.HTTP_200_OK,
            response.status_code,
        )

        report = response.json()["report"]

        self.assertEqual(
            "updates-available",
            report["status"],
        )
        self.assertEqual(
            "docker-compose",
            report["provider"],
        )
        self.assertEqual(
            2,
            report["total_services"],
        )
        self.assertEqual(
            1,
            report["counts"]["update-available"],
        )
        self.assertTrue(
            report["requires_attention"]
        )
        self.assertEqual(
            1,
            self.update_service.calls,
        )

    def test_update_provider_failure_returns_503(self) -> None:
        self.update_service.fail = True

        response = self.client.get(
            "/api/v1/services/updates"
        )

        self.assertEqual(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            response.status_code,
        )

        self.assertEqual(
            {
                "detail":
                    "Service Lifecycle is unavailable."
            },
            response.json(),
        )

    def test_reads_service_maintenance_history(self) -> None:
        response = self.client.get("/api/v1/services/history")
        self.assertEqual(status.HTTP_200_OK, response.status_code)
        report = response.json()["report"]
        self.assertEqual("docker-compose", report["provider"])
        self.assertEqual(2, report["total_records"])
        self.assertEqual(1, report["counts"]["failed"])
        self.assertTrue(report["requires_attention"])
        self.assertEqual(1, self.history_service.calls)

    def test_maintenance_history_provider_failure_returns_503(self) -> None:
        self.history_service.fail = True
        response = self.client.get("/api/v1/services/history")
        self.assertEqual(status.HTTP_503_SERVICE_UNAVAILABLE, response.status_code)
        self.assertEqual({"detail": "Service Lifecycle is unavailable."}, response.json())

    def test_provider_failure_returns_503(self) -> None:
        self.service.fail_list = True

        response = self.client.get(
            "/api/v1/services"
        )

        self.assertEqual(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            response.status_code,
        )

        self.assertEqual(
            {
                "detail":
                    "Service Lifecycle is unavailable."
            },
            response.json(),
        )

    def test_permission_is_required(self) -> None:
        def forbidden():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden.",
            )

        self.app.dependency_overrides[
            require_service_lifecycle_read
        ] = forbidden

        for path in (
            "/api/v1/services",
            "/api/v1/services/history",
            "/api/v1/services/updates",
        ):
            response = self.client.get(path)

            self.assertEqual(
                status.HTTP_403_FORBIDDEN,
                response.status_code,
            )

    def test_static_routes_are_not_detail(
        self,
    ) -> None:
        health = self.client.get(
            "/api/v1/services/health"
        )
        summary = self.client.get(
            "/api/v1/services/summary"
        )
        history = self.client.get(
            "/api/v1/services/history"
        )
        updates = self.client.get(
            "/api/v1/services/updates"
        )

        self.assertEqual(200, health.status_code)
        self.assertEqual(200, summary.status_code)
        self.assertEqual(200, history.status_code)
        self.assertEqual(200, updates.status_code)
        self.assertEqual([], self.service.inspect_calls)
        self.assertEqual(1, self.history_service.calls)
        self.assertEqual(1, self.update_service.calls)

    def test_openapi_registers_get_only_service_routes(
        self,
    ) -> None:
        schema = self.client.app.openapi()

        paths = (
            "/api/v1/services",
            "/api/v1/services/health",
            "/api/v1/services/summary",
            "/api/v1/services/history",
            "/api/v1/services/updates",
            "/api/v1/services/{service_identifier}",
        )

        for path in paths:
            self.assertIn(
                path,
                schema["paths"],
            )

            self.assertIn(
                "get",
                schema["paths"][path],
            )

            for method in (
                "post",
                "put",
                "patch",
                "delete",
            ):
                self.assertNotIn(
                    method,
                    schema["paths"][path],
                )


if __name__ == "__main__":
    unittest.main()
