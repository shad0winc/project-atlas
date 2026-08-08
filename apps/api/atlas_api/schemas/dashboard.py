"""Dashboard summary response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


DashboardMetricStatus = Literal[
    "healthy",
    "warning",
    "offline",
    "unknown",
]


class DashboardMetricResponse(BaseModel):
    """One normalized operational metric displayed by the Atlas Portal."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str
    label: str
    value: str
    description: str
    status: DashboardMetricStatus
    detail: str | None = None


class DashboardSummaryResponse(BaseModel):
    """Stable operational dashboard summary returned by the Atlas API."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    generated_at: str
    metrics: tuple[DashboardMetricResponse, ...]
