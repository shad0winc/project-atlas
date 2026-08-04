"""Aggregate Atlas Portal dashboard assembly."""

from __future__ import annotations

from atlas.operations import (
    OperationsReportNotFoundError,
    OperationsRepository,
)
from atlas_api.schemas.dashboard import DashboardSummaryResponse
from atlas_api.schemas.dashboard_media import (
    DashboardMediaSummaryResponse,
)
from atlas_api.schemas.health import HealthResponse
from atlas_api.schemas.portal_dashboard import (
    PortalDashboardResponse,
    PortalOperationsSummaryResponse,
)

from .dashboard import DashboardSummaryService
from .dashboard_media import DashboardMediaSummaryService


class PortalDashboardService:
    """Compose existing read-only services into one Portal contract."""

    def __init__(
        self,
        dashboard_service: DashboardSummaryService,
        media_service: DashboardMediaSummaryService,
        operations_repository: OperationsRepository,
    ) -> None:
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

        self._dashboard_service = dashboard_service
        self._media_service = media_service
        self._operations_repository = operations_repository

    def read_dashboard(self) -> PortalDashboardResponse:
        """Return one aggregate, read-only Portal dashboard."""

        operational = self._dashboard_service.read_summary()
        media = self._media_service.read_summary()
        operations = self._read_operations_summary()

        return PortalDashboardResponse(
            health=HealthResponse(
                status="ok",
                service="atlas-api",
                api_version="v1",
            ),
            operational=operational,
            media=media,
            operations=operations,
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
            )

        return PortalOperationsSummaryResponse(
            status="available",
            report=report.to_dict(),
            detail=None,
        )


__all__ = [
    "PortalDashboardService",
]
