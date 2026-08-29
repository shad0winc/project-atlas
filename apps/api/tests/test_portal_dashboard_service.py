"""Tests for aggregate Atlas Portal dashboard assembly."""

from __future__ import annotations

from atlas.health import HealthCheck, HealthReport
from atlas.operations import (
    OperationFinding,
    OperationsComparisonService,
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
    SchedulerDashboardService,
)
from atlas_api.services.portal_dashboard import (
    PORTAL_COMPARISON_HISTORY_LIMIT,
    PORTAL_RECENT_ATTENTION_LIMIT,
)


GENERATED_AT = "2026-08-04T04:00:00Z"
PREVIOUS_AT = "2026-08-04T03:00:00Z"


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


def finding(
    identifier: str,
    *,
    status: str = "healthy",
    severity: str = "info",
    message: str | None = None,
    recommendation: str | None = None,
) -> OperationFinding:
    return OperationFinding(
        identifier=identifier,
        name=identifier.rsplit(".", 1)[-1].title(),
        status=status,
        severity=severity,
        message=message or f"{identifier}: {status}",
        recommendation=recommendation,
        metadata={},
    )


def operations_report(
    *,
    report_id: str = "portal-latest",
    generated_at: str = GENERATED_AT,
    findings: tuple[OperationFinding, ...] | None = None,
) -> OperationsReport:
    if findings is None:
        findings = (
            finding("system.memory"),
        )

    return OperationsReport(
        report_id=report_id,
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="ef779047",
        generated_at=generated_at,
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=findings,
            ),
        ),
    )



class StubSchedulerService(
    SchedulerDashboardService,
):
    def __init__(self) -> None:
        pass

    def read_summary(self):
        from atlas_api.schemas.portal_dashboard import (
            PortalSchedulerSummaryResponse,
        )

        return PortalSchedulerSummaryResponse(
            status="available",
            registered_count=0,
            enabled_count=0,
            disabled_count=0,
            due_count=0,
            running_count=0,
            failed_count=0,
            recent_failures=(),
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


class RecordingRepository:
    def __init__(
        self,
        reports: tuple[OperationsReport, ...],
    ) -> None:
        self.reports = reports
        self.latest_count = 0
        self.history_limits: list[int] = []

    def latest(self) -> OperationsReport:
        self.latest_count += 1

        if not self.reports:
            raise OperationsReportNotFoundError(
                "latest Operations report was not found"
            )

        return self.reports[0]

    def history(
        self,
        limit: int = 25,
    ) -> tuple[OperationsReport, ...]:
        self.history_limits.append(limit)
        return self.reports[:limit]


def service(
    repository: RecordingRepository,
) -> PortalDashboardService:
    return PortalDashboardService(
        DashboardSummaryService(health_report),
        StubMediaService(),
        repository,
        StubSchedulerService(),
        OperationsComparisonService(),
    )


def test_missing_report_normalizes_complete_unavailable_state() -> None:
    repository = RecordingRepository(())

    dashboard = service(repository).read_dashboard()

    assert dashboard.operations.status == "unavailable"
    assert dashboard.operations.report is None
    assert dashboard.operations.summary is None
    assert dashboard.operations.recent_attention == ()
    assert dashboard.operations.comparison.status == (
        "unavailable"
    )
    assert repository.latest_count == 1
    assert repository.history_limits == []


def test_one_report_provides_summary_without_comparison() -> None:
    latest = operations_report()
    repository = RecordingRepository((latest,))

    dashboard = service(repository).read_dashboard()
    operations = dashboard.operations

    assert operations.status == "available"
    assert operations.summary is not None
    assert operations.summary.status == "healthy"
    assert operations.summary.score == 100
    assert operations.summary.attention_count == 0
    assert operations.summary.generated_at == GENERATED_AT
    assert operations.summary.currentness == "historical"
    assert operations.comparison.status == "unavailable"
    assert operations.recent_attention == ()
    assert repository.history_limits == [
        PORTAL_COMPARISON_HISTORY_LIMIT,
    ]


def test_two_reports_provide_canonical_comparison_metrics() -> None:
    previous = operations_report(
        report_id="previous",
        generated_at=PREVIOUS_AT,
        findings=(
            finding("system.memory"),
        ),
    )
    current = operations_report(
        report_id="current",
        findings=(
            finding(
                "system.memory",
                status="warning",
                severity="warning",
            ),
        ),
    )

    repository = RecordingRepository(
        (current, previous),
    )

    operations = service(repository).read_dashboard().operations
    comparison = operations.comparison

    assert comparison.status == "available"
    assert comparison.score_delta == -50
    assert comparison.attention_delta == 1
    assert comparison.added_count == 0
    assert comparison.removed_count == 0
    assert comparison.changed_count == 1
    assert comparison.unchanged_count == 0
    assert comparison.difference_count == 1
    assert comparison.detail is None


def test_recent_attention_uses_canonical_order_and_limit() -> None:
    findings = (
        finding(
            "system.warning-z",
            status="warning",
            severity="warning",
        ),
        finding(
            "system.critical-c",
            status="critical",
            severity="critical",
        ),
        finding(
            "system.warning-a",
            status="warning",
            severity="warning",
        ),
        finding(
            "system.critical-a",
            status="critical",
            severity="critical",
        ),
        finding(
            "system.warning-b",
            status="warning",
            severity="warning",
        ),
        finding(
            "system.critical-b",
            status="critical",
            severity="critical",
        ),
        finding("system.healthy"),
    )

    current = operations_report(
        findings=findings,
    )
    repository = RecordingRepository((current,))

    attention = (
        service(repository)
        .read_dashboard()
        .operations
        .recent_attention
    )

    assert len(attention) == PORTAL_RECENT_ATTENTION_LIMIT
    assert [
        item.identifier
        for item in attention
    ] == [
        finding.identifier
        for finding in current.attention_findings[
            :PORTAL_RECENT_ATTENTION_LIMIT
        ]
    ]
    assert attention[0].severity == "critical"
    assert attention[0].section == "system"


def test_recent_attention_exposes_stable_fields() -> None:
    current = operations_report(
        findings=(
            finding(
                "system.memory",
                status="warning",
                severity="warning",
                message="Memory usage is elevated",
                recommendation="Review memory pressure.",
            ),
        ),
    )

    repository = RecordingRepository((current,))
    attention = (
        service(repository)
        .read_dashboard()
        .operations
        .recent_attention[0]
    )

    assert attention.model_dump() == {
        "section": "system",
        "identifier": "system.memory",
        "name": "Memory",
        "status": "warning",
        "severity": "warning",
        "message": "Memory usage is elevated",
        "recommendation": "Review memory pressure.",
    }


def test_service_does_not_mutate_reports() -> None:
    previous = operations_report(
        report_id="previous",
        generated_at=PREVIOUS_AT,
    )
    current = operations_report(
        report_id="current",
    )

    before = (
        current.to_dict(),
        previous.to_dict(),
    )

    service(
        RecordingRepository(
            (current, previous),
        )
    ).read_dashboard()

    assert (
        current.to_dict(),
        previous.to_dict(),
    ) == before


def test_service_rejects_repository_without_history() -> None:
    class LatestOnlyRepository:
        def latest(self) -> OperationsReport:
            return operations_report()

    try:
        PortalDashboardService(
            DashboardSummaryService(health_report),
            StubMediaService(),
            LatestOnlyRepository(),  # type: ignore[arg-type]
            StubSchedulerService(),
        )
    except TypeError as error:
        assert str(error) == (
            "operations_repository must provide history()"
        )
    else:
        raise AssertionError("TypeError was not raised")


def test_service_rejects_invalid_comparison_service() -> None:
    try:
        PortalDashboardService(
            DashboardSummaryService(health_report),
            StubMediaService(),
            RecordingRepository(()),
            StubSchedulerService(),
            object(),  # type: ignore[arg-type]
        )
    except TypeError as error:
        assert str(error) == (
            "comparison_service must be an "
            "OperationsComparisonService"
        )
    else:
        raise AssertionError("TypeError was not raised")
