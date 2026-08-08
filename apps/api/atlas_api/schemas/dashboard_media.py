"""Media dashboard response contracts."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


MediaLibraryStatus = Literal[
    "available",
    "unavailable",
]


class MediaLibraryResponse(BaseModel):
    """One media-library statistic exposed to the Portal."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    id: str
    label: str
    count: int | None
    status: MediaLibraryStatus
    detail: str | None = None


class DashboardMediaSummaryResponse(BaseModel):
    """Stable media-library summary returned by the Atlas API."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    generated_at: str
    libraries: tuple[MediaLibraryResponse, ...]
