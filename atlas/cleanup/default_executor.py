"""Default controlled cleanup executor for Project Atlas."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from atlas.cleanup.audit import CleanupAuditWriter
from atlas.cleanup.deletion_intent_repository import (
    JsonCleanupDeletionIntentRepository,
)
from atlas.cleanup.deletion_intents import (
    CleanupDeletionIntent,
)
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
from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
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
    to the provider-neutral media mutation dispatcher. Execute-mode deletion
    requires an injected durable deletion-intent repository so provider
    mutation cannot begin without a replay barrier.

    When an audit writer is supplied, every execution item produces one
    normalized cleanup execution event.
    """

    def __init__(
        self,
        *,
        provider: MediaProvider | None = None,
        audit_writer: CleanupAuditWriter | None = None,
        mutation_dispatcher: MediaMutationDispatcher | None = None,
        deletion_intent_repository: (
            JsonCleanupDeletionIntentRepository | None
        ) = None,
        cleanup_service: object | None = None,
        clock: Clock | None = None,
        execution_id_factory: ExecutionIdFactory | None = None,
    ) -> None:
        """Initialize the executor.

        Args:
            provider: Optional provider used for planned mutations.
            audit_writer: Optional execution-event persistence writer.
            mutation_dispatcher: Optional provider mutation dispatcher.
            deletion_intent_repository: Optional durable destructive-mutation
                replay barrier required for execute mode.
            cleanup_service: Optional authoritative cleanup evaluator used for
                fresh policy and retention revalidation before live deletion.
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
            deletion_intent_repository is not None
            and not isinstance(
                deletion_intent_repository,
                JsonCleanupDeletionIntentRepository,
            )
        ):
            raise CleanupExecutionError(
                "deletion_intent_repository must be a "
                "JsonCleanupDeletionIntentRepository"
            )

        if (
            cleanup_service is not None
            and not callable(
                getattr(cleanup_service, "evaluate", None)
            )
        ):
            raise CleanupExecutionError(
                "cleanup_service must expose callable evaluate"
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
        self._deletion_intent_repository = (
            deletion_intent_repository
        )
        self._cleanup_service = cleanup_service
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

        if (
            self._provider is not None
            and self._provider.name != report.provider
        ):
            raise CleanupExecutionError(
                "media provider does not match execution report provider"
            )

        if (
            report.mode is CleanupExecutionMode.EXECUTE
            and self._deletion_intent_repository is None
        ):
            raise CleanupExecutionError(
                "execute mode requires a deletion-intent repository"
            )

        if (
            report.mode is CleanupExecutionMode.EXECUTE
            and report.planned_count > 0
            and self._provider is None
        ):
            raise CleanupExecutionError(
                "execute mode requires a media provider"
            )

        execution_id = self._new_execution_id()
        occurred_at = self._now()
        started_at = self._timestamp(occurred_at)

        if (
            self._provider is not None
            and report.planned_count > 0
        ):
            mutation_mode = (
                MediaMutationMode.LIVE
                if report.mode is CleanupExecutionMode.EXECUTE
                else MediaMutationMode.PREVIEW
            )

            try:
                self._mutation_dispatcher.validate(
                    provider=self._provider,
                    operation=ProviderOperation.DELETE,
                    mode=mutation_mode,
                )
            except MediaMutationDispatchError as exc:
                raise CleanupExecutionError(
                    str(exc)
                ) from exc

        if (
            report.mode is CleanupExecutionMode.EXECUTE
            and report.planned_count > 0
            and self._cleanup_service is None
        ):
            raise CleanupExecutionError(
                "execute mode requires a cleanup service "
                "for fresh revalidation"
            )

        errors: list[str] = []
        successful = 0
        modified = 0

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

            if report.mode is CleanupExecutionMode.EXECUTE:
                cleanup_service = self._cleanup_service

                if cleanup_service is None:
                    raise CleanupExecutionError(
                        "execute mode requires a cleanup service "
                        "for fresh revalidation"
                    )

                evaluate = getattr(
                    cleanup_service,
                    "evaluate",
                    None,
                )

                if not callable(evaluate):
                    raise CleanupExecutionError(
                        "cleanup_service must expose callable evaluate"
                    )

                try:
                    fresh_decision = evaluate(
                        item.provider,
                        item.item_id,
                    )

                    if not isinstance(
                        fresh_decision,
                        CleanupDecision,
                    ):
                        raise CleanupExecutionError(
                            "fresh cleanup revalidation returned "
                            "an invalid cleanup decision"
                        )

                    if (
                        fresh_decision.provider != item.provider
                        or fresh_decision.item_id != item.item_id
                    ):
                        raise CleanupExecutionError(
                            "fresh cleanup revalidation decision "
                            "does not match execution item"
                        )
                except Exception as exc:
                    message = (
                        "fresh cleanup revalidation failed: "
                        f"{exc}"
                    )

                    errors.append(
                        f"{item.item_id}: {message}"
                    )

                    self._record_event(
                        execution_id=execution_id,
                        item=item,
                        status=(
                            CleanupExecutionEventStatus.DELETE_FAILED
                        ),
                        message=message,
                        occurred_at=occurred_at,
                        errors=errors,
                    )
                    continue

                if (
                    fresh_decision.action
                    is not CleanupAction.DELETE
                ):
                    self._record_event(
                        execution_id=execution_id,
                        item=item,
                        status=CleanupExecutionEventStatus.SKIPPED,
                        message=(
                            "Cleanup delete skipped after fresh "
                            "policy/retention revalidation: "
                            f"{fresh_decision.action.value}"
                        ),
                        occurred_at=occurred_at,
                        errors=errors,
                    )

                    successful += 1
                    continue

                repository = self._deletion_intent_repository

                if repository is None:
                    raise CleanupExecutionError(
                        "execute mode requires a deletion-intent repository"
                    )

                intent = CleanupDeletionIntent(
                    execution_id=execution_id,
                    provider=item.provider,
                    item_id=item.item_id,
                    created_at=occurred_at,
                )

                try:
                    repository.save(intent)
                except Exception as exc:
                    message = str(exc)

                    errors.append(
                        f"{item.item_id}: {message}"
                    )

                    self._record_event(
                        execution_id=execution_id,
                        item=item,
                        status=(
                            CleanupExecutionEventStatus.DELETE_FAILED
                        ),
                        message=message,
                        occurred_at=occurred_at,
                        errors=errors,
                    )
                    continue

            try:
                result = self._mutation_dispatcher.execute(
                    provider=self._provider,
                    operation=ProviderOperation.DELETE,
                    item_id=item.item_id,
                    mode=(
                        MediaMutationMode.LIVE
                        if report.mode is CleanupExecutionMode.EXECUTE
                        else MediaMutationMode.PREVIEW
                    ),
                )
            except Exception as exc:
                message = str(exc)

                errors.append(
                    f"{item.item_id}: {message}"
                )

                failed_status = (
                    CleanupExecutionEventStatus.DELETE_INDETERMINATE
                    if report.mode is CleanupExecutionMode.EXECUTE
                    else CleanupExecutionEventStatus.PREVIEW_FAILED
                )

                self._record_event(
                    execution_id=execution_id,
                    item=item,
                    status=failed_status,
                    message=message,
                    occurred_at=occurred_at,
                    errors=errors,
                )
                continue

            successful += 1

            if report.mode is CleanupExecutionMode.EXECUTE:
                modified += 1

                repository = self._deletion_intent_repository

                if repository is None:
                    raise CleanupExecutionError(
                        "execute mode requires a deletion-intent repository"
                    )

                audit_succeeded = self._record_event(
                    execution_id=execution_id,
                    item=item,
                    status=(
                        CleanupExecutionEventStatus.DELETE_SUCCEEDED
                    ),
                    message=result.message,
                    occurred_at=occurred_at,
                    errors=errors,
                    modified=True,
                )

                if audit_succeeded:
                    try:
                        repository.remove(
                            item.provider,
                            item.item_id,
                        )
                    except Exception as exc:
                        errors.append(
                            f"{item.item_id}: deletion-intent "
                            f"finalization failed: {exc}"
                        )

                continue

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
            successful=successful,
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
            modified=modified,
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
        modified: bool = False,
    ) -> bool:
        """Create and optionally persist one execution event.

        Returns:
            True when no audit writer is configured or persistence succeeds.
            False when audit persistence fails.
        """

        if self._audit_writer is None:
            return True

        event = CleanupExecutionEvent(
            execution_id=execution_id,
            provider=item.provider,
            item_id=item.item_id,
            action=item.decision.action,
            mode=item.mode,
            status=status,
            message=message,
            modified=modified,
            occurred_at=occurred_at,
        )

        try:
            self._audit_writer.write(event)
        except Exception as exc:
            errors.append(
                f"audit({item.item_id}): {exc}"
            )
            return False

        return True

    @staticmethod
    def _run_status(
        *,
        planned: int,
        successful: int,
        errors: list[str],
        provider_enabled: bool,
    ) -> CleanupRunStatus:
        """Return the normalized execution status."""

        if not errors:
            return CleanupRunStatus.SUCCESS

        if (
            provider_enabled
            and planned > 0
            and successful == 0
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
