"""Tests for aggregate Atlas Portal dashboard assembly."""

from __future__ import annotations

from atlas.health import HealthCheck, HealthReport
from atlas.operations import (
    OperationFinding,
    OperationsReport,
    OperationsReportNotFoundError,
    OperationsSection,
)
from atlas_api.schemas.dashboard_media import (
    DashboardMediaSummaryResponse,
    MediaLibraryResponse,
)
from atlas_api.services import (
    DashboardMediaSummaryService,
    DashboardSummaryService,
    PortalDashboardService,
)


GENERATED_AT = "2026-08-04T04:00:00Z"


def health_report() -> HealthReport:
    return HealthReport(
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


def operations_report() -> OperationsReport:
    return OperationsReport(
        report_id="portal-latest",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="6c110d6a",
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


class StubMediaService(DashboardMediaSummaryService):
    """Return a deterministic media summary without file access."""

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


class RecordingRepository:
    """Repository double that records latest-report reads."""

    def __init__(
        self,
        report: OperationsReport | None,
    ) -> None:
        self.report = report
        self.latest_count = 0

    def latest(self) -> OperationsReport:
        self.latest_count += 1

        if self.report is None:
            raise OperationsReportNotFoundError(
                "latest Operations report was not found"
            )

        return self.report


def test_portal_dashboard_composes_existing_services() -> None:
    dashboard_service = DashboardSummaryService(
        health_report,
    )
    media_service = StubMediaService()
    repository = RecordingRepository(
        operations_report(),
    )

    service = PortalDashboardService(
        dashboard_service,
        media_service,
        repository,
    )

    dashboard = service.read_dashboard()

    assert dashboard.health.model_dump() == {
        "status": "ok",
        "service": "atlas-api",
        "api_version": "v1",
    }
    assert dashboard.operational.generated_at == GENERATED_AT
    assert dashboard.media.generated_at == GENERATED_AT
    assert dashboard.operations.status == "available"
    assert dashboard.operations.report is not None
    assert dashboard.operations.report["report_id"] == (
        "portal-latest"
    )
    assert dashboard.operations.detail is None
    assert repository.latest_count == 1


def test_portal_dashboard_normalizes_missing_operations() -> None:
    repository = RecordingRepository(None)

    service = PortalDashboardService(
        DashboardSummaryService(health_report),
        StubMediaService(),
        repository,
    )

    dashboard = service.read_dashboard()

    assert dashboard.operations.model_dump() == {
        "status": "unavailable",
        "report": None,
        "detail": (
            "No persisted Operations report is available."
        ),
    }
    assert repository.latest_count == 1


def test_portal_dashboard_preserves_media_unavailable_state() -> None:
    class UnavailableMediaService(
        DashboardMediaSummaryService
    ):
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
                        count=None,
                        status="unavailable",
                        detail="ARI snapshot is unavailable.",
                    ),
                ),
            )

    service = PortalDashboardService(
        DashboardSummaryService(health_report),
        UnavailableMediaService(),
        RecordingRepository(operations_report()),
    )

    dashboard = service.read_dashboard()

    library = dashboard.media.libraries[0]

    assert library.status == "unavailable"
    assert library.count is None
    assert library.detail == "ARI snapshot is unavailable."


def test_portal_dashboard_does_not_mutate_operations_report() -> None:
    report = operations_report()
    before = report.to_dict()

    service = PortalDashboardService(
        DashboardSummaryService(health_report),
        StubMediaService(),
        RecordingRepository(report),
    )

    service.read_dashboard()

    assert report.to_dict() == before


def test_portal_dashboard_rejects_invalid_dashboard_service() -> None:
    try:
        PortalDashboardService(
            object(),  # type: ignore[arg-type]
            StubMediaService(),
            RecordingRepository(None),
        )
    except TypeError as error:
        assert str(error) == (
            "dashboard_service must be a "
            "DashboardSummaryService"
        )
    else:
        raise AssertionError("TypeError was not raised")


def test_portal_dashboard_rejects_invalid_media_service() -> None:
    try:
        PortalDashboardService(
            DashboardSummaryService(health_report),
            object(),  # type: ignore[arg-type]
            RecordingRepository(None),
        )
    except TypeError as error:
        assert str(error) == (
            "media_service must be a "
            "DashboardMediaSummaryService"
        )
    else:
        raise AssertionError("TypeError was not raised")


def test_portal_dashboard_rejects_invalid_repository() -> None:
    try:
        PortalDashboardService(
            DashboardSummaryService(health_report),
            StubMediaService(),
            object(),  # type: ignore[arg-type]
        )
    except TypeError as error:
        assert str(error) == (
            "operations_repository must provide latest()"
        )
    else:
        raise AssertionError("TypeError was not raised")
