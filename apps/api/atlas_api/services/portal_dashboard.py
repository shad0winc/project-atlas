"""Aggregate Atlas Portal dashboard assembly."""

from __future__ import annotations

from typing import Final

from atlas.operations import (
    OperationFinding,
    OperationsComparisonService,
    OperationsReport,
    OperationsReportNotFoundError,
    OperationsRepository,
    OperationsSectionId,
)
from atlas_api.schemas.dashboard import DashboardSummaryResponse
from atlas_api.schemas.dashboard_media import (
    DashboardMediaSummaryResponse,
)
from atlas_api.schemas.health import HealthResponse
from atlas_api.schemas.portal_dashboard import (
    PortalDashboardResponse,
    PortalOperationsAttentionResponse,
    PortalOperationsComparisonResponse,
    PortalOperationsReportSummaryResponse,
    PortalOperationsSummaryResponse,
)

from .dashboard import DashboardSummaryService
from .dashboard_media import DashboardMediaSummaryService

from .scheduler_dashboard import SchedulerDashboardService

PORTAL_RECENT_ATTENTION_LIMIT: Final = 5
PORTAL_COMPARISON_HISTORY_LIMIT: Final = 2


class PortalDashboardService:
    """Compose existing read-only services into one Portal contract."""

    def __init__(
        self,
        dashboard_service: DashboardSummaryService,
        media_service: DashboardMediaSummaryService,
        operations_repository: OperationsRepository,
        scheduler_service: SchedulerDashboardService,
        comparison_service: OperationsComparisonService | None = None,
    ) -> None:
        if not isinstance(
            scheduler_service,
            SchedulerDashboardService,
        ):
            raise TypeError(
                "scheduler_service must be a "
                "SchedulerDashboardService"
            )

        if not isinstance(
            dashboard_service,
            DashboardSummaryService,
        ):
            raise TypeError(
                "dashboard_service must be a "
                "DashboardSummaryService"
            )

        if not isinstance(
            media_service,
            DashboardMediaSummaryService,
        ):
            raise TypeError(
                "media_service must be a "
                "DashboardMediaSummaryService"
            )

        if not callable(
            getattr(
                operations_repository,
                "latest",
                None,
            )
        ):
            raise TypeError(
                "operations_repository must provide latest()"
            )

        if not callable(
            getattr(
                operations_repository,
                "history",
                None,
            )
        ):
            raise TypeError(
                "operations_repository must provide history()"
            )

        if comparison_service is None:
            comparison_service = OperationsComparisonService()

        if not isinstance(
            comparison_service,
            OperationsComparisonService,
        ):
            raise TypeError(
                "comparison_service must be an "
                "OperationsComparisonService"
            )

        self._dashboard_service = dashboard_service
        self._media_service = media_service
        self._operations_repository = operations_repository
        self._comparison_service = comparison_service
        self._scheduler_service = scheduler_service

    def read_dashboard(self) -> PortalDashboardResponse:
        """Return one aggregate, read-only Portal dashboard."""

        operational = self._dashboard_service.read_summary()
        media = self._media_service.read_summary()
        operations = self._read_operations_summary()
        scheduler = self._scheduler_service.read_summary()

        return PortalDashboardResponse(
            health=HealthResponse(
                status="ok",
                service="atlas-api",
                api_version="v1",
            ),
            operational=operational,
            media=media,
            operations=operations,
            scheduler=scheduler,
        )

    def _read_operations_summary(
        self,
    ) -> PortalOperationsSummaryResponse:
        try:
            report = self._operations_repository.latest()
        except OperationsReportNotFoundError:
            return PortalOperationsSummaryResponse(
                status="unavailable",
                report=None,
                detail=(
                    "No persisted Operations report is available."
                ),
                summary=None,
                comparison=PortalOperationsComparisonResponse(
                    status="unavailable",
                    detail=(
                        "At least two persisted Operations reports "
                        "are required for comparison."
                    ),
                ),
                recent_attention=(),
            )

        return PortalOperationsSummaryResponse(
            status="available",
            report=report.to_dict(),
            detail=None,
            summary=PortalOperationsReportSummaryResponse(
                status=report.status.value,
                score=report.score,
                attention_count=len(
                    report.attention_findings
                ),
                generated_at=report.generated_at,
            ),
            comparison=self._read_comparison(),
            recent_attention=tuple(
                self._attention_response(
                    report,
                    finding,
                )
                for finding in report.attention_findings[
                    :PORTAL_RECENT_ATTENTION_LIMIT
                ]
            ),
        )

    def _read_comparison(
        self,
    ) -> PortalOperationsComparisonResponse:
        reports = self._operations_repository.history(
            limit=PORTAL_COMPARISON_HISTORY_LIMIT,
        )

        if len(reports) < PORTAL_COMPARISON_HISTORY_LIMIT:
            return PortalOperationsComparisonResponse(
                status="unavailable",
                detail=(
                    "At least two persisted Operations reports "
                    "are required for comparison."
                ),
            )

        comparison = self._comparison_service.compare(
            reports[1],
            reports[0],
        )

        return PortalOperationsComparisonResponse(
            status="available",
            score_delta=comparison.score_delta,
            attention_delta=comparison.attention_delta,
            added_count=comparison.added_count,
            removed_count=comparison.removed_count,
            changed_count=comparison.changed_count,
            unchanged_count=comparison.unchanged_count,
            difference_count=comparison.difference_count,
            detail=None,
        )

    @staticmethod
    def _attention_response(
        report: OperationsReport,
        finding: OperationFinding,
    ) -> PortalOperationsAttentionResponse:
        return PortalOperationsAttentionResponse(
            section=_finding_section(
                report,
                finding,
            ).value,
            identifier=finding.identifier,
            name=finding.name,
            status=finding.status.value,
            severity=finding.severity.value,
            message=finding.message,
            recommendation=finding.recommendation,
        )


def _finding_section(
    report: OperationsReport,
    target: OperationFinding,
) -> OperationsSectionId:
    for section in report.sections:
        if target in section.findings:
            return section.identifier

    raise ValueError(
        "attention finding does not belong to the report"
    )


__all__ = [
    "PORTAL_COMPARISON_HISTORY_LIMIT",
    "PORTAL_RECENT_ATTENTION_LIMIT",
    "PortalDashboardService",
]
