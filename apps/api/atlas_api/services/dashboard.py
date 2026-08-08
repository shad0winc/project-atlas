"""Operational dashboard summary assembly."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from atlas.health import (
    HealthCheck,
    HealthReport,
    HealthStatus,
    collect_operational_health,
)
from atlas_api.schemas.dashboard import (
    DashboardMetricResponse,
    DashboardMetricStatus,
    DashboardSummaryResponse,
)


HealthReportFactory = Callable[[], HealthReport]


_STATUS_SEVERITY = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.UNKNOWN: 1,
    HealthStatus.WARNING: 2,
    HealthStatus.CRITICAL: 3,
}


class DashboardSummaryService:
    """Adapt shared Atlas health diagnostics into a Portal summary contract."""

    def __init__(
        self,
        report_factory: HealthReportFactory = collect_operational_health,
    ) -> None:
        if not callable(report_factory):
            raise TypeError("report_factory must be callable")

        self._report_factory = report_factory

    def read_summary(self) -> DashboardSummaryResponse:
        """Collect live operational health and return the dashboard summary."""

        report = self._report_factory()

        if not isinstance(report, HealthReport):
            raise TypeError("report_factory must return a HealthReport")

        return DashboardSummaryResponse(
            generated_at=report.generated_at,
            metrics=(
                self._overall_metric(report),
                self._category_metric(
                    report,
                    category="infrastructure",
                    metric_id="infrastructure",
                    label="Infrastructure",
                    description=(
                        "Docker, storage, GPU, and other Atlas infrastructure "
                        "dependencies."
                    ),
                ),
                self._category_metric(
                    report,
                    category="services",
                    metric_id="services",
                    label="Services",
                    description=(
                        "Operational state of the media and supporting service "
                        "containers."
                    ),
                ),
                self._category_metric(
                    report,
                    category="storage",
                    metric_id="storage",
                    label="Storage",
                    description=(
                        "Write-access health for Atlas media and download "
                        "storage paths."
                    ),
                ),
            ),
        )

    @staticmethod
    def _overall_metric(report: HealthReport) -> DashboardMetricResponse:
        return DashboardMetricResponse(
            id="system-health",
            label="System health",
            value=f"{report.score}%",
            description=(
                "Aggregate health across Atlas core, infrastructure, services, "
                "storage, project files, and enabled modules."
            ),
            status=_dashboard_status(report.status),
            detail=f"{len(report.checks)} checks",
        )

    @staticmethod
    def _category_metric(
        report: HealthReport,
        *,
        category: str,
        metric_id: str,
        label: str,
        description: str,
    ) -> DashboardMetricResponse:
        checks = tuple(
            check
            for check in report.checks
            if check.category == category
        )

        if not checks:
            return DashboardMetricResponse(
                id=metric_id,
                label=label,
                value="Unknown",
                description=description,
                status="unknown",
                detail="No checks reported",
            )

        score = _average_score(checks)
        status = _worst_status(checks)

        return DashboardMetricResponse(
            id=metric_id,
            label=label,
            value=f"{score}%",
            description=description,
            status=_dashboard_status(status),
            detail=_check_summary(checks),
        )


def _average_score(checks: Iterable[HealthCheck]) -> int:
    normalized_checks = tuple(checks)

    if not normalized_checks:
        return 0

    return round(
        sum(check.score for check in normalized_checks)
        / len(normalized_checks)
    )


def _worst_status(checks: Iterable[HealthCheck]) -> HealthStatus:
    normalized_checks = tuple(checks)

    if not normalized_checks:
        return HealthStatus.UNKNOWN

    return max(
        normalized_checks,
        key=lambda check: _STATUS_SEVERITY[check.status],
    ).status


def _dashboard_status(status: HealthStatus) -> DashboardMetricStatus:
    return {
        HealthStatus.HEALTHY: "healthy",
        HealthStatus.WARNING: "warning",
        HealthStatus.CRITICAL: "offline",
        HealthStatus.UNKNOWN: "unknown",
    }[status]


def _check_summary(checks: Iterable[HealthCheck]) -> str:
    normalized_checks = tuple(checks)
    healthy_count = sum(
        check.status is HealthStatus.HEALTHY
        for check in normalized_checks
    )

    return f"{healthy_count} of {len(normalized_checks)} checks healthy"
