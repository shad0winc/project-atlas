"""Analytics for Atlas Retention Intelligence reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Final

from atlas.ari.models import ARIReport
from atlas.ari.service import (
    ARIService,
    ARIServiceError,
)


SECONDS_PER_DAY: Final = 86_400


class ARIAnalyticsError(RuntimeError):
    """Raised when ARI analytics cannot be calculated."""


@dataclass(frozen=True)
class SnapshotLoadFailure:
    """A historical snapshot that could not be loaded."""

    path: Path
    error: str


@dataclass(frozen=True)
class ARIHistory:
    """Loaded ARI history and skipped snapshot diagnostics."""

    reports: tuple[ARIReport, ...]
    skipped: tuple[SnapshotLoadFailure, ...]

    @property
    def loaded_count(
        self,
    ) -> int:
        """Return the number of valid reports."""

        return len(self.reports)

    @property
    def skipped_count(
        self,
    ) -> int:
        """Return the number of skipped snapshots."""

        return len(self.skipped)


@dataclass(frozen=True)
class StorageChange:
    """Storage utilization change across an ARI reporting period."""

    start_timestamp: str
    end_timestamp: str
    start_used_bytes: int
    end_used_bytes: int
    change_bytes: int
    elapsed_seconds: float

    @property
    def elapsed_days(
        self,
    ) -> float:
        """Return the reporting period in days."""

        return self.elapsed_seconds / SECONDS_PER_DAY

    @property
    def average_bytes_per_day(
        self,
    ) -> float:
        """Return the average storage change per day."""

        if self.elapsed_seconds == 0:
            return 0.0

        return (
            self.change_bytes
            / self.elapsed_seconds
            * SECONDS_PER_DAY
        )


class ARIAnalytics:
    """Calculates analytics from historical ARI reports."""

    def __init__(
        self,
        service: ARIService,
    ) -> None:
        self._service = service

    @property
    def service(
        self,
    ) -> ARIService:
        """Return the configured ARI service."""

        return self._service

    def load_history(
        self,
    ) -> ARIHistory:
        """Load compatible reports and record skipped snapshots."""

        reports_by_timestamp: dict[str, ARIReport] = {}
        skipped: list[SnapshotLoadFailure] = []

        for path in self.service.list_snapshots():
            try:
                report = self.service.load(path)
            except ARIServiceError as error:
                skipped.append(
                    SnapshotLoadFailure(
                        path=path,
                        error=str(error),
                    ),
                )
                continue

            reports_by_timestamp[report.timestamp] = report

        reports = tuple(
            sorted(
                reports_by_timestamp.values(),
                key=lambda report: _parse_timestamp(
                    report.timestamp,
                ),
            ),
        )

        return ARIHistory(
            reports=reports,
            skipped=tuple(skipped),
        )

    def history(
        self,
    ) -> tuple[ARIReport, ...]:
        """Return compatible reports in chronological order."""

        return self.load_history().reports

    def storage_change(
        self,
    ) -> StorageChange:
        """Calculate storage change across compatible history."""

        reports = self.history()

        if len(reports) < 2:
            raise ARIAnalyticsError(
                "at least two unique valid ARI reports are required "
                "to calculate storage change",
            )

        first = reports[0]
        last = reports[-1]

        started_at = _parse_timestamp(
            first.timestamp,
        )
        ended_at = _parse_timestamp(
            last.timestamp,
        )

        elapsed_seconds = (
            ended_at - started_at
        ).total_seconds()

        if elapsed_seconds < 0:
            raise ARIAnalyticsError(
                "ARI report history has a negative time range",
            )

        start_used_bytes = first.storage.used_bytes
        end_used_bytes = last.storage.used_bytes

        return StorageChange(
            start_timestamp=first.timestamp,
            end_timestamp=last.timestamp,
            start_used_bytes=start_used_bytes,
            end_used_bytes=end_used_bytes,
            change_bytes=(
                end_used_bytes
                - start_used_bytes
            ),
            elapsed_seconds=elapsed_seconds,
        )


def _parse_timestamp(
    value: str,
) -> datetime:
    """Parse an ARI timestamp."""

    normalized = value

    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1]
            + "+00:00"
        )

    try:
        timestamp = datetime.fromisoformat(
            normalized,
        )
    except ValueError as error:
        raise ARIAnalyticsError(
            f"invalid ARI report timestamp: {value}",
        ) from error

    if timestamp.tzinfo is None:
        raise ARIAnalyticsError(
            f"ARI report timestamp lacks timezone information: {value}",
        )

    return timestamp
