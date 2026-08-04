"""Tests for the aggregate Atlas Portal dashboard endpoint."""

from __future__ import annotations

from fastapi import HTTPException, status
from fastapi.testclient import TestClient
import pytest

from atlas.health import HealthCheck, HealthReport
from atlas.operations import OperationsReportNotFoundError
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    clear_dependency_caches,
    get_portal_dashboard_service,
)
from atlas_api.main import create_app
from atlas_api.routes.v1.portal import (
    PORTAL_DASHBOARD_PERMISSIONS,
    require_portal_dashboard_read,
    require_portal_media_read,
    require_portal_operations_read,
)
from atlas_api.services import (
    DashboardMediaSummaryService,
    DashboardSummaryService,
    PortalDashboardService,
)
from atlas_api.schemas.dashboard_media import (
    DashboardMediaSummaryResponse,
    MediaLibraryResponse,
)


GENERATED_AT = "2026-08-04T04:30:00Z"


@pytest.fixture(autouse=True)
def api_environment(
    monkeypatch: pytest.MonkeyPatch,
):
    """Provide isolated valid API settings for every route test."""

    monkeypatch.setenv(
        "ATLAS_JWT_SECRET",
        "m023-11-portal-route-test-secret-0001",
    )

    clear_dependency_caches()

    yield

    clear_dependency_caches()


def authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="portal-admin",
        username="portal-admin",
        display_name="Portal Administrator",
        roles=("administrator",),
        provider="test",
        metadata={},
    )


class StubMediaService(DashboardMediaSummaryService):
    def __init__(self) -> None:
        pass

    def read_summary(
        self,
    ) -> DashboardMediaSummaryResponse:
        return DashboardMediaSummaryResponse(
            generated_at=GENERATED_AT,
            libraries=(
                MediaLibraryResponse(
                    id="movies",
                    label="Movies",
                    count=12,
                    status="available",
                    detail=None,
                ),
            ),
        )


class MissingOperationsRepository:
    def latest(self):
        raise OperationsReportNotFoundError(
            "latest Operations report was not found"
        )


def portal_service() -> PortalDashboardService:
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
        generated_at=GENERATED_AT,
    )

    return PortalDashboardService(
        DashboardSummaryService(lambda: report),
        StubMediaService(),
        MissingOperationsRepository(),
    )


def test_portal_dashboard_permissions_are_stable() -> None:
    assert PORTAL_DASHBOARD_PERMISSIONS == (
        "atlas.dashboard.read",
        "media.read",
        "system.health.read",
    )


def test_portal_dashboard_returns_shared_envelope() -> None:
    app = create_app()

    app.dependency_overrides[
        require_portal_dashboard_read
    ] = authenticated_user
    app.dependency_overrides[
        require_portal_media_read
    ] = authenticated_user
    app.dependency_overrides[
        require_portal_operations_read
    ] = authenticated_user
    app.dependency_overrides[
        get_portal_dashboard_service
    ] = portal_service

    try:
        response = TestClient(app).get(
            "/api/v1/portal/dashboard"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    payload = response.json()

    assert payload["schema_version"] == 1
    assert payload["api_version"] == "v1"
    assert payload["success"] is True
    assert payload["generated_at"] == GENERATED_AT

    dashboard = payload["data"]["dashboard"]

    assert set(dashboard) == {
        "health",
        "operational",
        "media",
        "operations",
    }
    assert dashboard["health"] == {
        "status": "ok",
        "service": "atlas-api",
        "api_version": "v1",
    }
    assert dashboard["operations"]["status"] == (
        "unavailable"
    )


def test_portal_dashboard_requires_authentication() -> None:
    app = create_app()
    response = TestClient(app).get(
        "/api/v1/portal/dashboard"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_portal_dashboard_rejects_missing_permission() -> None:
    app = create_app()

    app.dependency_overrides[
        require_portal_dashboard_read
    ] = authenticated_user

    def forbidden() -> AuthenticatedUser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission is required.",
        )

    app.dependency_overrides[
        require_portal_media_read
    ] = forbidden
    app.dependency_overrides[
        require_portal_operations_read
    ] = authenticated_user

    try:
        response = TestClient(app).get(
            "/api/v1/portal/dashboard"
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Permission is required.",
    }


def test_openapi_registers_portal_dashboard() -> None:
    app = create_app()
    operation = app.openapi()["paths"][
        "/api/v1/portal/dashboard"
    ]["get"]

    assert operation["tags"] == ["portal"]
    assert operation["summary"] == (
        "Read the aggregate Atlas Portal dashboard"
    )

    schema = operation["responses"]["200"][
        "content"
    ]["application/json"]["schema"]

    assert schema == {
        "$ref": (
            "#/components/schemas/"
            "ApiSuccessEnvelopeSchema"
        )
    }


def test_portal_dependency_is_cached() -> None:
    clear_dependency_caches()

    first = get_portal_dashboard_service()
    second = get_portal_dashboard_service()

    assert first is second

    clear_dependency_caches()

    third = get_portal_dashboard_service()

    assert third is not first

    clear_dependency_caches()
