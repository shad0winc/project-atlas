"""Tests for the live Atlas Operations report endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from atlas.operations import (
    HostOperationsContextProvider,
    OperationFinding,
    OperationsReport,
    OperationsSection,
    OperationsService,
)
from atlas.operations.collectors import (
    DockerCollector,
    SystemCollector,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    clear_dependency_caches,
    get_operations_service,
)
from atlas_api.main import create_app
from atlas_api.routes.v1.operations import (
    OPERATIONS_REPORT_PERMISSION,
    require_operations_report_read,
)


GENERATED_AT = "2026-08-04T02:30:00Z"


def operations_report() -> OperationsReport:
    """Return one deterministic report fixture."""

    return OperationsReport(
        report_id="operations-report",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="7e08571b",
        generated_at=GENERATED_AT,
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(
                    OperationFinding(
                        identifier="system.memory",
                        name="Memory",
                        status="healthy",
                        severity="info",
                        message="Memory usage is healthy",
                        metadata={
                            "percent": 40,
                        },
                    ),
                ),
            ),
        ),
    )


class FakeOperationsService:
    """Deterministic Operations service used by route tests."""

    def __init__(self) -> None:
        self.report = operations_report()
        self.collect_count = 0

    def collect(self) -> OperationsReport:
        self.collect_count += 1
        return self.report


def authenticated_user() -> AuthenticatedUser:
    """Return one authenticated test user."""

    return AuthenticatedUser(
        user_id="atlas-admin",
        username="admin",
        display_name="Atlas Administrator",
        roles=("administrator",),
        provider="jellyfin",
        metadata={},
    )


def test_operations_report_permission_is_stable() -> None:
    assert OPERATIONS_REPORT_PERMISSION == "system.health.read"


def test_operations_service_factory_uses_production_collectors() -> None:
    clear_dependency_caches()

    service = get_operations_service()

    assert isinstance(service, OperationsService)
    assert isinstance(
        service.context_provider,
        HostOperationsContextProvider,
    )
    assert tuple(
        type(collector)
        for collector in service.collectors
    ) == (
        SystemCollector,
        DockerCollector,
    )

    clear_dependency_caches()


def test_dependency_cache_clear_rebuilds_operations_service() -> None:
    clear_dependency_caches()
    first = get_operations_service()

    clear_dependency_caches()
    second = get_operations_service()

    assert first is not second

    clear_dependency_caches()


def test_operations_report_endpoint_returns_shared_envelope() -> None:
    app = create_app()
    service = FakeOperationsService()

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_service
    ] = lambda: service

    try:
        response = TestClient(app).get(
            "/api/v1/operations/report"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.collect_count == 1

    payload = response.json()

    assert payload["schema_version"] == 1
    assert payload["api_version"] == "v1"
    assert payload["success"] is True
    assert payload["generated_at"] == GENERATED_AT

    report = payload["data"]["report"]

    assert report["report_id"] == "operations-report"
    assert report["hostname"] == "docker"
    assert report["generated_at"] == GENERATED_AT
    assert report["status"] == "healthy"
    assert report["score"] == 100
    assert report["sections"][0]["identifier"] == "system"


def test_operations_report_endpoint_does_not_mutate_report() -> None:
    app = create_app()
    service = FakeOperationsService()
    before = service.report.to_dict()

    app.dependency_overrides[
        require_operations_report_read
    ] = authenticated_user
    app.dependency_overrides[
        get_operations_service
    ] = lambda: service

    try:
        response = TestClient(app).get(
            "/api/v1/operations/report"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.report.to_dict() == before


def test_openapi_registers_operations_report_endpoint() -> None:
    app = create_app()
    response = TestClient(app).get(
        "/api/openapi.json"
    )

    assert response.status_code == 200

    operation = response.json()["paths"][
        "/api/v1/operations/report"
    ]["get"]

    assert operation["tags"] == ["operations"]
    assert operation["summary"] == (
        "Collect a live Atlas Operations report"
    )

    response_schema = operation["responses"]["200"][
        "content"
    ]["application/json"]["schema"]

    assert response_schema == {
        "$ref": (
            "#/components/schemas/"
            "ApiSuccessEnvelopeSchema"
        )
    }
