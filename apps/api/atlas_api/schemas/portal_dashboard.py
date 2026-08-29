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

PortalOperationsStatus = Literal[
    "healthy",
    "warning",
    "critical",
    "unknown",
]


class PortalSchedulerFailureResponse(BaseModel):
    """Bounded scheduler failure information for Portal display."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    task_name: str
    failed_at: str | None
    error: str


class PortalSchedulerSummaryResponse(BaseModel):
    """Compact scheduler health summary for Portal."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    status: PortalSectionStatus
    detail: str | None = None

    registered_count: int | None = None
    enabled_count: int | None = None
    disabled_count: int | None = None
    due_count: int | None = None
    running_count: int | None = None
    failed_count: int | None = None

    last_run_at: str | None = None
    next_run_at: str | None = None

    recent_failures: tuple[
        PortalSchedulerFailureResponse,
        ...
    ] = ()

    @model_validator(mode="after")
    def validate_scheduler_state(
        self,
    ) -> "PortalSchedulerSummaryResponse":
        """Reject contradictory scheduler availability."""

        fields = (
            self.registered_count,
            self.enabled_count,
            self.disabled_count,
            self.due_count,
            self.running_count,
            self.failed_count,
        )

        if self.status == "available":
            if any(
                value is None
                for value in fields
            ):
                raise ValueError(
                    "available scheduler state requires metrics"
                )

            if self.detail is not None:
                raise ValueError(
                    "available scheduler state cannot include detail"
                )

            return self

        if self.detail is None or not self.detail.strip():
            raise ValueError(
                "unavailable scheduler state requires detail"
            )

        if any(
            value is not None
            for value in fields
        ):
            raise ValueError(
                "unavailable scheduler state cannot include metrics"
            )

        return self


class PortalOperationsReportSummaryResponse(BaseModel):
    """Compact summary of the latest persisted Operations report."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    status: PortalOperationsStatus
    score: int
    attention_count: int
    generated_at: str
    currentness: Literal["historical"]


class PortalOperationsComparisonResponse(BaseModel):
    """Compact comparison state for the two newest reports."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    status: PortalSectionStatus
    score_delta: int | None = None
    attention_delta: int | None = None
    added_count: int | None = None
    removed_count: int | None = None
    changed_count: int | None = None
    unchanged_count: int | None = None
    difference_count: int | None = None
    detail: str | None = None

    @model_validator(mode="after")
    def validate_comparison_state(
        self,
    ) -> "PortalOperationsComparisonResponse":
        """Reject contradictory comparison availability state."""

        metric_names = (
            "score_delta",
            "attention_delta",
            "added_count",
            "removed_count",
            "changed_count",
            "unchanged_count",
            "difference_count",
        )

        metrics = tuple(
            getattr(self, name)
            for name in metric_names
        )

        if self.status == "available":
            if any(value is None for value in metrics):
                raise ValueError(
                    "available comparison requires all metrics"
                )

            if self.detail is not None:
                raise ValueError(
                    "available comparison cannot include detail"
                )

            for name in (
                "added_count",
                "removed_count",
                "changed_count",
                "unchanged_count",
                "difference_count",
            ):
                value = getattr(self, name)

                if value is not None and value < 0:
                    raise ValueError(
                        f"{name} must be non-negative"
                    )

            assert self.added_count is not None
            assert self.removed_count is not None
            assert self.changed_count is not None
            assert self.difference_count is not None

            expected_difference_count = (
                self.added_count
                + self.removed_count
                + self.changed_count
            )

            if (
                self.difference_count
                != expected_difference_count
            ):
                raise ValueError(
                    "difference_count must equal added, "
                    "removed, and changed counts"
                )

            return self

        if any(value is not None for value in metrics):
            raise ValueError(
                "unavailable comparison cannot include metrics"
            )

        if self.detail is None or not self.detail.strip():
            raise ValueError(
                "unavailable comparison requires detail"
            )

        return self


class PortalOperationsAttentionResponse(BaseModel):
    """One compact attention finding for Portal display."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    section: str
    identifier: str
    name: str
    status: PortalOperationsStatus
    severity: Literal[
        "critical",
        "warning",
        "info",
    ]
    message: str
    recommendation: str | None = None


class PortalOperationsSummaryResponse(BaseModel):
    """Latest persisted Operations state exposed to the Portal."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    status: PortalSectionStatus
    report: dict[str, Any] | None
    detail: str | None = None
    summary: PortalOperationsReportSummaryResponse | None = None
    comparison: PortalOperationsComparisonResponse
    recent_attention: tuple[
        PortalOperationsAttentionResponse,
        ...,
    ] = ()

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

            if self.summary is None:
                raise ValueError(
                    "available Operations state requires a summary"
                )

            return self

        if self.report is not None:
            raise ValueError(
                "unavailable Operations state cannot include a report"
            )

        if self.summary is not None:
            raise ValueError(
                "unavailable Operations state cannot include a summary"
            )

        if self.recent_attention:
            raise ValueError(
                "unavailable Operations state cannot include attention"
            )

        if self.comparison.status != "unavailable":
            raise ValueError(
                "unavailable Operations state requires an "
                "unavailable comparison"
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
    scheduler: PortalSchedulerSummaryResponse


__all__ = [
    "PortalDashboardResponse",
    "PortalOperationsAttentionResponse",
    "PortalOperationsComparisonResponse",
    "PortalOperationsReportSummaryResponse",
    "PortalOperationsStatus",
    "PortalOperationsSummaryResponse",
    "PortalSchedulerFailureResponse",
    "PortalSchedulerSummaryResponse",
    "PortalSectionStatus",
]
