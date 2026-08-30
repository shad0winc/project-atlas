"""Normalized read-only Downloads domain models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = 1


class DownloadsError(RuntimeError):
    """Raised when bounded Downloads runtime data cannot be produced or read."""


class DownloadState(StrEnum):
    DOWNLOADING = "downloading"
    QUEUED = "queued"
    STALLED = "stalled"
    PAUSED = "paused"
    CHECKING = "checking"
    MOVING = "moving"
    SEEDING = "seeding"
    COMPLETED = "completed"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DownloadItem:
    job_id: str
    name: str
    category: str | None
    state: DownloadState
    progress: float
    total_bytes: int
    downloaded_bytes: int
    download_rate: int
    upload_rate: int
    eta_seconds: int | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "name": self.name,
            "category": self.category,
            "state": self.state.value,
            "progress": self.progress,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "download_rate": self.download_rate,
            "upload_rate": self.upload_rate,
            "eta_seconds": self.eta_seconds,
        }


@dataclass(frozen=True, slots=True)
class DownloadSummary:
    active: int
    queued: int
    completed: int
    error: int
    total_download_rate: int
    total_upload_rate: int

    def to_dict(self) -> dict[str, int]:
        return {
            "active": self.active,
            "queued": self.queued,
            "completed": self.completed,
            "error": self.error,
            "total_download_rate": self.total_download_rate,
            "total_upload_rate": self.total_upload_rate,
        }


@dataclass(frozen=True, slots=True)
class DownloadsSnapshot:
    generated_at: str
    summary: DownloadSummary
    downloads: tuple[DownloadItem, ...]

    @classmethod
    def build(
        cls,
        downloads: Sequence[DownloadItem],
        *,
        total_download_rate: int,
        total_upload_rate: int,
        generated_at: datetime | None = None,
    ) -> "DownloadsSnapshot":
        now = generated_at or datetime.now(timezone.utc)
        normalized_time = now.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        items = tuple(downloads)
        return cls(
            generated_at=normalized_time,
            summary=DownloadSummary(
                active=sum(
                    item.state
                    in {
                        DownloadState.DOWNLOADING,
                        DownloadState.STALLED,
                        DownloadState.CHECKING,
                        DownloadState.MOVING,
                    }
                    for item in items
                ),
                queued=sum(item.state == DownloadState.QUEUED for item in items),
                completed=sum(
                    item.state in {DownloadState.COMPLETED, DownloadState.SEEDING}
                    for item in items
                ),
                error=sum(item.state == DownloadState.ERROR for item in items),
                total_download_rate=max(0, int(total_download_rate)),
                total_upload_rate=max(0, int(total_upload_rate)),
            ),
            downloads=items,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "generated_at": self.generated_at,
            "summary": self.summary.to_dict(),
            "downloads": [item.to_dict() for item in self.downloads],
        }


def require_mapping(value: Any, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DownloadsError(f"{field} must be an object")
    return value
