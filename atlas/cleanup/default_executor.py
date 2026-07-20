"""Default controlled cleanup executor for Project Atlas."""

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
from atlas.media.provider import (
    MediaProvider,
    ProviderMutationResult,
    ProviderOperation,
)


Clock = Callable[[], datetime]


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


class DefaultCleanupExecutor(CleanupExecutor):
    """Execute controlled cleanup reports.

    Dry-run execution never modifies media. When a media provider is
    supplied, planned deletions are sent only to the provider's safe
    ``preview_delete_item`` operation.
    """

    def __init__(
        self,
        *,
        provider: MediaProvider | None = None,
        clock: Clock | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            provider: Optional provider used to preview planned deletions.
            clock: Optional timezone-aware datetime provider.
        """

        self._provider = provider
        self._clock = clock or _utc_now

    def execute(
        self,
        report: CleanupExecutionReport,
    ) -> CleanupExecutionSummary:
        """Execute one normalized cleanup report."""

        if not isinstance(report, CleanupExecutionReport):
            raise CleanupExecutionError(
                "report must be a CleanupExecutionReport"
            )

        if report.mode is not CleanupExecutionMode.DRY_RUN:
            raise CleanupExecutionError(
                "default cleanup executor supports dry-run mode only"
            )

        if (
            self._provider is not None
            and self._provider.name != report.provider
        ):
            raise CleanupExecutionError(
                "media provider does not match execution report provider"
            )

        started_at = self._timestamp(self._now())

        errors: list[str] = []
        previewed = 0

        for item in report.items:
            if item.status is CleanupExecutionStatus.SKIPPED:
                continue

            if self._provider is None:
                continue

            try:
                result = self._provider.preview_delete_item(
                    item.item_id
                )
                self._validate_preview_result(
                    result=result,
                    provider=report.provider,
                    item_id=item.item_id,
                )
            except Exception as exc:
                errors.append(
                    f"{item.item_id}: {exc}"
                )
                continue

            previewed += 1

        completed_at = self._timestamp(self._now())

        status = self._run_status(
            planned=report.planned_count,
            previewed=previewed,
            errors=errors,
            provider_enabled=self._provider is not None,
        )

        return CleanupExecutionSummary(
            provider=report.provider,
            mode=report.mode,
            status=status,
            started_at=started_at,
            completed_at=completed_at,
            total=report.total,
            planned=report.planned_count,
            skipped=report.skipped_count,
            modified=0,
            errors=tuple(errors),
        )

    @staticmethod
    def _validate_preview_result(
        *,
        result: ProviderMutationResult,
        provider: str,
        item_id: str,
    ) -> None:
        """Validate the relationship between a preview and its item."""

        if not isinstance(result, ProviderMutationResult):
            raise CleanupExecutionError(
                "provider preview must return "
                "ProviderMutationResult"
            )

        if result.provider != provider:
            raise CleanupExecutionError(
                "provider preview result provider does not match "
                "execution report"
            )

        if result.item_id != item_id:
            raise CleanupExecutionError(
                "provider preview result item_id does not match "
                "execution item"
            )

        if result.operation is not ProviderOperation.DELETE:
            raise CleanupExecutionError(
                "provider preview result operation must be delete"
            )

        if not result.success:
            raise CleanupExecutionError(
                result.message
            )

    @staticmethod
    def _run_status(
        *,
        planned: int,
        previewed: int,
        errors: list[str],
        provider_enabled: bool,
    ) -> CleanupRunStatus:
        """Return the normalized execution status."""

        if not errors:
            return CleanupRunStatus.SUCCESS

        if (
            provider_enabled
            and planned > 0
            and previewed == 0
        ):
            return CleanupRunStatus.FAILED

        return CleanupRunStatus.PARTIAL

    def _now(self) -> datetime:
        """Return a validated timezone-aware UTC datetime."""

        value = self._clock()

        if not isinstance(value, datetime):
            raise CleanupExecutionError(
                "clock must return a datetime"
            )

        if value.tzinfo is None or value.utcoffset() is None:
            raise CleanupExecutionError(
                "clock must return a timezone-aware datetime"
            )

        return value.astimezone(timezone.utc)

    @staticmethod
    def _timestamp(
        value: datetime,
    ) -> str:
        """Serialize a datetime as UTC ISO-8601."""

        return (
            value.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
