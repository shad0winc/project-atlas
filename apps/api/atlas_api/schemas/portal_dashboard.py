"""Aggregate Portal dashboard response contracts."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from .dashboard import DashboardSummaryResponse
from .dashboard_media import DashboardMediaSummaryResponse
from .health import HealthResponse


PortalSectionStatus = Literal[
    "available",
    "unavailable",
]


class PortalOperationsSummaryResponse(BaseModel):
    """Latest persisted Operations state exposed to the Portal."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    status: PortalSectionStatus
    report: dict[str, Any] | None
    detail: str | None = None

    @model_validator(mode="after")
    def validate_section_state(
        self,
    ) -> "PortalOperationsSummaryResponse":
        """Reject contradictory Operations availability state."""

        if self.status == "available":
            if self.report is None:
                raise ValueError(
                    "available Operations state requires a report"
                )

            if self.detail is not None:
                raise ValueError(
                    "available Operations state cannot include detail"
                )

            return self

        if self.report is not None:
            raise ValueError(
                "unavailable Operations state cannot include a report"
            )

        if self.detail is None or not self.detail.strip():
            raise ValueError(
                "unavailable Operations state requires detail"
            )

        return self


class PortalDashboardResponse(BaseModel):
    """One aggregate dashboard assembled for the Atlas Portal."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    health: HealthResponse
    operational: DashboardSummaryResponse
    media: DashboardMediaSummaryResponse
    operations: PortalOperationsSummaryResponse


__all__ = [
    "PortalDashboardResponse",
    "PortalOperationsSummaryResponse",
    "PortalSectionStatus",
]
