"""Default controlled cleanup executor for Project Atlas."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from atlas.cleanup.audit import CleanupAuditWriter
from atlas.cleanup.execution_events import (
    CleanupExecutionEvent,
    CleanupExecutionEventStatus,
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
from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
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

    When an audit writer is supplied, every execution item produces one
    normalized cleanup execution event.
    """

    def __init__(
        self,
        *,
        provider: MediaProvider | None = None,
        audit_writer: CleanupAuditWriter | None = None,
        clock: Clock | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            provider: Optional provider used to preview planned deletions.
            audit_writer: Optional execution-event persistence writer.
            clock: Optional timezone-aware datetime provider.
        """

        if (
            audit_writer is not None
            and not isinstance(audit_writer, CleanupAuditWriter)
        ):
            raise CleanupExecutionError(
                "audit_writer must be a CleanupAuditWriter"
            )

        self._provider = provider
        self._audit_writer = audit_writer
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

        occurred_at = self._now()
        started_at = self._timestamp(occurred_at)

        if (
            self._provider is not None
            and report.planned_count > 0
        ):
            capabilities = self._provider_capabilities(
                self._provider,
            )

            if not capabilities.supports(
                ProviderCapability.PREVIEW_DELETE,
            ):
                raise CleanupExecutionError(
                    (
                        f"{report.provider} does not support "
                        "delete previews"
                    )
                )

            preview_delete_item = getattr(
                self._provider,
                "preview_delete_item",
                None,
            )

            if not callable(preview_delete_item):
                raise CleanupExecutionError(
                    "provider declares delete preview support "
                    "but does not implement preview_delete_item"
                )

        errors: list[str] = []
        previewed = 0

        for item in report.items:
            if item.status is CleanupExecutionStatus.SKIPPED:
                self._record_event(
                    item=item,
                    status=CleanupExecutionEventStatus.SKIPPED,
                    message="Cleanup item was not planned",
                    occurred_at=occurred_at,
                    errors=errors,
                )
                continue

            if self._provider is None:
                self._record_event(
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
                result = self._provider.preview_delete_item(
                    item.item_id
                )
                self._validate_preview_result(
                    result=result,
                    provider=report.provider,
                    item_id=item.item_id,
                )
            except Exception as exc:
                message = str(exc)

                errors.append(
                    f"{item.item_id}: {message}"
                )

                self._record_event(
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
    def _provider_capabilities(
        provider: MediaProvider,
    ) -> ProviderCapabilities:
        """Return and validate provider capabilities."""

        get_capabilities = getattr(
            provider,
            "get_capabilities",
            None,
        )

        if not callable(get_capabilities):
            raise CleanupExecutionError(
                "provider must implement get_capabilities"
            )

        capabilities = get_capabilities()

        if not isinstance(
            capabilities,
            ProviderCapabilities,
        ):
            raise CleanupExecutionError(
                "provider must return ProviderCapabilities"
            )

        return capabilities

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
