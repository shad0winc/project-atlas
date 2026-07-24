"""Default controlled cleanup executor for Project Atlas."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from atlas.cleanup.audit import CleanupAuditWriter
from atlas.cleanup.execution_events import (
    CleanupExecutionEvent,
    CleanupExecutionEventStatus,
)
from atlas.cleanup.execution_identity import (
    new_execution_id,
    normalize_execution_id,
)
from atlas.cleanup.execution_models import (
    CleanupExecutionItem,
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
from atlas.media.mutations import (
    MediaMutationDispatcher,
    MediaMutationDispatchError,
    MediaMutationMode,
)
from atlas.media.provider import (
    MediaProvider,
    ProviderOperation,
)


Clock = Callable[[], datetime]
ExecutionIdFactory = Callable[[], str]


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


class DefaultCleanupExecutor(CleanupExecutor):
    """Execute controlled cleanup reports.

    Dry-run execution never modifies media. Planned deletions are delegated
    to the provider-neutral media mutation dispatcher, which currently
    permits safe delete previews only.

    When an audit writer is supplied, every execution item produces one
    normalized cleanup execution event.
    """

    def __init__(
        self,
        *,
        provider: MediaProvider | None = None,
        audit_writer: CleanupAuditWriter | None = None,
        mutation_dispatcher: MediaMutationDispatcher | None = None,
        clock: Clock | None = None,
        execution_id_factory: ExecutionIdFactory | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            provider: Optional provider used for planned mutations.
            audit_writer: Optional execution-event persistence writer.
            mutation_dispatcher: Optional provider mutation dispatcher.
            clock: Optional timezone-aware datetime provider.
            execution_id_factory: Optional execution ID generator.
        """

        if (
            audit_writer is not None
            and not isinstance(audit_writer, CleanupAuditWriter)
        ):
            raise CleanupExecutionError(
                "audit_writer must be a CleanupAuditWriter"
            )

        if (
            mutation_dispatcher is not None
            and not isinstance(
                mutation_dispatcher,
                MediaMutationDispatcher,
            )
        ):
            raise CleanupExecutionError(
                "mutation_dispatcher must be a "
                "MediaMutationDispatcher"
            )

        if (
            execution_id_factory is not None
            and not callable(execution_id_factory)
        ):
            raise CleanupExecutionError(
                "execution_id_factory must be callable"
            )

        self._provider = provider
        self._audit_writer = audit_writer
        self._mutation_dispatcher = (
            mutation_dispatcher
            or MediaMutationDispatcher()
        )
        self._clock = clock or _utc_now
        self._execution_id_factory = (
            execution_id_factory or new_execution_id
        )

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

        execution_id = self._new_execution_id()
        occurred_at = self._now()
        started_at = self._timestamp(occurred_at)

        if (
            self._provider is not None
            and report.planned_count > 0
        ):
            try:
                self._mutation_dispatcher.validate(
                    provider=self._provider,
                    operation=ProviderOperation.DELETE,
                    mode=MediaMutationMode.PREVIEW,
                )
            except MediaMutationDispatchError as exc:
                raise CleanupExecutionError(
                    str(exc)
                ) from exc

        errors: list[str] = []
        previewed = 0

        for item in report.items:
            if item.status is CleanupExecutionStatus.SKIPPED:
                self._record_event(
                    execution_id=execution_id,
                    item=item,
                    status=CleanupExecutionEventStatus.SKIPPED,
                    message="Cleanup item was not planned",
                    occurred_at=occurred_at,
                    errors=errors,
                )
                continue

            if self._provider is None:
                self._record_event(
                    execution_id=execution_id,
                    item=item,
                    status=CleanupExecutionEventStatus.SKIPPED,
                    message=(
                        "Preview skipped because no media provider "
                        "was configured"
                    ),
                    occurred_at=occurred_at,
                    errors=errors,
                )
                continue

            try:
                result = self._mutation_dispatcher.execute(
                    provider=self._provider,
                    operation=ProviderOperation.DELETE,
                    item_id=item.item_id,
                    mode=MediaMutationMode.PREVIEW,
                )
            except Exception as exc:
                message = str(exc)

                errors.append(
                    f"{item.item_id}: {message}"
                )

                self._record_event(
                    execution_id=execution_id,
                    item=item,
                    status=(
                        CleanupExecutionEventStatus.PREVIEW_FAILED
                    ),
                    message=message,
                    occurred_at=occurred_at,
                    errors=errors,
                )
                continue

            previewed += 1

            self._record_event(
                execution_id=execution_id,
                item=item,
                status=(
                    CleanupExecutionEventStatus.PREVIEW_SUCCEEDED
                ),
                message=result.message,
                occurred_at=occurred_at,
                errors=errors,
            )

        completed_at = self._timestamp(self._now())

        status = self._run_status(
            planned=report.planned_count,
            previewed=previewed,
            errors=errors,
            provider_enabled=self._provider is not None,
        )

        return CleanupExecutionSummary(
            execution_id=execution_id,
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

    def _record_event(
        self,
        *,
        execution_id: str,
        item: CleanupExecutionItem,
        status: CleanupExecutionEventStatus,
        message: str,
        occurred_at: datetime,
        errors: list[str],
    ) -> None:
        """Create and optionally persist one execution event."""

        if self._audit_writer is None:
            return

        event = CleanupExecutionEvent(
            execution_id=execution_id,
            provider=item.provider,
            item_id=item.item_id,
            action=item.decision.action,
            mode=item.mode,
            status=status,
            message=message,
            modified=False,
            occurred_at=occurred_at,
        )

        try:
            self._audit_writer.write(event)
        except Exception as exc:
            errors.append(
                f"audit({item.item_id}): {exc}"
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

    def _new_execution_id(self) -> str:
        """Generate and validate one cleanup execution identifier."""

        try:
            value = self._execution_id_factory()
        except Exception as exc:
            raise CleanupExecutionError(
                f"execution ID generation failed: {exc}"
            ) from exc

        try:
            return normalize_execution_id(value)
        except ValueError as exc:
            raise CleanupExecutionError(str(exc)) from exc

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
