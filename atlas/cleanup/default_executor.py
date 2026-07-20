"""Default dry-run cleanup executor for Project Atlas."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from atlas.cleanup.execution_models import (
    CleanupExecutionMode,
    CleanupExecutionReport,
    CleanupExecutionStatus,
)
from atlas.cleanup.executor import (
    CleanupExecutionError,
    CleanupExecutionSummary,
    CleanupExecutor,
    CleanupRunStatus,
)


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


class DefaultCleanupExecutor(CleanupExecutor):
    """Execute validated cleanup plans without modifying media.

    The default Atlas cleanup executor currently supports dry-run reports
    only. It walks an immutable execution plan and returns a normalized
    summary without calling a media provider or modifying external state.

    Structural report validation belongs to CleanupExecutionReport.
    This executor is responsible only for execution orchestration.
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            clock: Optional timezone-aware datetime provider used for
                deterministic execution timestamps.
        """

        self._clock = clock or _utc_now

    def execute(
        self,
        report: CleanupExecutionReport,
    ) -> CleanupExecutionSummary:
        """Execute one validated dry-run cleanup plan.

        Args:
            report: Immutable cleanup execution report.

        Returns:
            A normalized summary of the completed dry run.

        Raises:
            CleanupExecutionError: If the report type, mode, item status,
                mutation state, or injected clock is invalid.
        """

        if not isinstance(report, CleanupExecutionReport):
            raise CleanupExecutionError(
                "report must be a CleanupExecutionReport"
            )

        if report.mode is not CleanupExecutionMode.DRY_RUN:
            raise CleanupExecutionError(
                "only dry-run cleanup execution is supported"
            )

        started_at = self._now()

        planned = 0
        skipped = 0
        modified = 0

        for item in report.items:
            if item.status is CleanupExecutionStatus.PLANNED:
                planned += 1
            elif item.status is CleanupExecutionStatus.SKIPPED:
                skipped += 1
            else:
                raise CleanupExecutionError(
                    "unsupported cleanup execution status: "
                    f"{item.status}"
                )

            if item.modified:
                modified += 1

        if modified:
            raise CleanupExecutionError(
                "dry-run cleanup execution cannot modify media"
            )

        completed_at = self._now()

        return CleanupExecutionSummary(
            provider=report.provider,
            mode=report.mode,
            status=CleanupRunStatus.SUCCESS,
            started_at=_timestamp(started_at),
            completed_at=_timestamp(completed_at),
            total=report.total,
            planned=planned,
            skipped=skipped,
            modified=modified,
            errors=(),
        )

    def _now(self) -> datetime:
        """Return a validated timezone-aware UTC timestamp."""

        value = self._clock()

        if not isinstance(value, datetime):
            raise CleanupExecutionError(
                "execution clock must return a datetime"
            )

        if value.tzinfo is None or value.utcoffset() is None:
            raise CleanupExecutionError(
                "execution clock must return a "
                "timezone-aware datetime"
            )

        return value.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    """Serialize a timezone-aware datetime as a UTC timestamp."""

    return (
        value.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
