"""Safety contracts for destructive cleanup execute wiring."""

from __future__ import annotations

from dataclasses import replace
from tempfile import TemporaryDirectory
import unittest

from atlas.cleanup.audit import CleanupAuditWriter
from atlas.cleanup.deletion_intent_repository import (
    JsonCleanupDeletionIntentRepository,
)
from atlas.cleanup.deletion_intents import CleanupDeletionIntent
from atlas.cleanup.default_executor import DefaultCleanupExecutor
from atlas.cleanup.execution_events import (
    CleanupExecutionEventStatus,
)
from atlas.cleanup.execution_models import CleanupExecutionMode
from atlas.cleanup.models import CleanupAction
from atlas.cleanup.executor import (
    CleanupExecutionError,
    CleanupRunStatus,
)
from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
)
from atlas.media.provider import (
    ProviderMutationResult,
    ProviderOperation,
)

from tests.core.test_default_cleanup_executor import (
    COMPLETED_AT,
    EXECUTION_ID,
    STARTED_AT,
    make_clock,
    make_item,
    make_report,
)


def make_execute_report():
    """Convert the existing normalized dry-run fixture to execute mode."""
    report = make_report()

    items = tuple(
        replace(
            item,
            mode=CleanupExecutionMode.EXECUTE,
        )
        for item in report.items
    )

    return replace(
        report,
        items=items,
        mode=CleanupExecutionMode.EXECUTE,
    )


class RecordingAuditWriter(CleanupAuditWriter):
    """Collect execution events for deterministic assertions."""

    def __init__(self) -> None:
        self.events = []

    def write(self, event) -> None:
        self.events.append(event)


class PlannedDeleteCleanupService:
    """Return a fresh DELETE decision for existing execute contracts."""

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ):
        decision = make_item(
            item_id=item_id,
            action=CleanupAction.DELETE,
        ).decision

        if decision.provider != provider:
            raise AssertionError(
                "fresh decision provider must match execution provider"
            )

        return decision


class LiveDeleteProvider:
    """Provider double exposing controlled live-delete capability."""

    name = "jellyfin"

    def __init__(
        self,
        *,
        repository: JsonCleanupDeletionIntentRepository | None = None,
        fail_after_entry: bool = False,
    ) -> None:
        self.repository = repository
        self.fail_after_entry = fail_after_entry
        self.calls: list[str] = []
        self.intent_visible_during_delete = False

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider="jellyfin",
            capabilities=frozenset(
                {
                    ProviderCapability.DELETE,
                }
            ),
        )

    def delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.calls.append(item_id)

        if self.repository is not None:
            self.intent_visible_during_delete = (
                self.repository.get(
                    "jellyfin",
                    item_id,
                )
                is not None
            )

        if self.fail_after_entry:
            raise RuntimeError(
                "delete transport interrupted after dispatch"
            )

        return ProviderMutationResult(
            provider="jellyfin",
            operation=ProviderOperation.DELETE,
            item_id=item_id,
            success=True,
            message="Deleted",
            executed_at="2026-09-13T21:40:00Z",
        )


class NoLiveDeleteProvider:
    """Provider lacking the explicit destructive delete capability."""

    name = "jellyfin"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            provider="jellyfin",
            capabilities=frozenset(),
        )

    def delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.calls.append(item_id)
        raise AssertionError(
            "delete_item must not be called without live-delete capability"
        )


class CleanupExecuteWiringTests(unittest.TestCase):
    """Lock the v1 destructive cleanup execution safety boundary."""

    def test_success_persists_intent_before_delete_then_finalizes(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            provider = LiveDeleteProvider(
                repository=repository,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                audit_writer=audit,
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(
                provider.calls,
                ["delete-1"],
            )
            self.assertTrue(
                provider.intent_visible_during_delete
            )

            self.assertIsNone(
                repository.get(
                    "jellyfin",
                    "delete-1",
                )
            )

            self.assertEqual(
                summary.status,
                CleanupRunStatus.SUCCESS,
            )
            self.assertEqual(summary.modified, 1)

            self.assertEqual(
                audit.events[0].status,
                CleanupExecutionEventStatus.DELETE_SUCCEEDED,
            )
            self.assertTrue(audit.events[0].modified)

    def test_dispatch_exception_is_indeterminate_and_retains_intent(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            provider = LiveDeleteProvider(
                repository=repository,
                fail_after_entry=True,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                audit_writer=audit,
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(
                provider.calls,
                ["delete-1"],
            )
            self.assertTrue(
                provider.intent_visible_during_delete
            )

            intent = repository.get(
                "jellyfin",
                "delete-1",
            )
            self.assertIsNotNone(intent)
            assert intent is not None
            self.assertEqual(
                intent.execution_id,
                EXECUTION_ID,
            )

            self.assertEqual(
                summary.status,
                CleanupRunStatus.FAILED,
            )
            self.assertEqual(summary.modified, 0)

            self.assertEqual(
                audit.events[0].status,
                CleanupExecutionEventStatus.DELETE_INDETERMINATE,
            )
            self.assertFalse(audit.events[0].modified)

    def test_existing_intent_blocks_replay_before_provider_call(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)

            repository.save(
                CleanupDeletionIntent(
                    execution_id=EXECUTION_ID,
                    provider="jellyfin",
                    item_id="delete-1",
                    created_at=STARTED_AT,
                )
            )

            provider = LiveDeleteProvider(
                repository=repository,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                audit_writer=audit,
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(provider.calls, [])
            self.assertIsNotNone(
                repository.get(
                    "jellyfin",
                    "delete-1",
                )
            )

            self.assertEqual(
                summary.status,
                CleanupRunStatus.FAILED,
            )

            self.assertEqual(
                audit.events[0].status,
                CleanupExecutionEventStatus.DELETE_FAILED,
            )
            self.assertFalse(audit.events[0].modified)

    def test_execute_requires_deletion_intent_repository(
        self,
    ) -> None:
        provider = LiveDeleteProvider()

        executor = DefaultCleanupExecutor(
            provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "deletion-intent repository",
        ):
            executor.execute(
                make_execute_report()
            )

        self.assertEqual(provider.calls, [])

    def test_live_preflight_fails_before_intent_or_provider_mutation(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            provider = NoLiveDeleteProvider()

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
            )

            with self.assertRaisesRegex(
                CleanupExecutionError,
                "does not support live delete",
            ):
                executor.execute(
                    make_execute_report()
                )

            self.assertEqual(provider.calls, [])
            self.assertEqual(repository.list(), ())


class UnsuccessfulLiveDeleteProvider(LiveDeleteProvider):
    """Return an explicit unsuccessful result after live dispatch."""

    def delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.calls.append(item_id)

        if self.repository is not None:
            self.intent_visible_during_delete = (
                self.repository.get(
                    "jellyfin",
                    item_id,
                )
                is not None
            )

        return ProviderMutationResult(
            provider="jellyfin",
            operation=ProviderOperation.DELETE,
            item_id=item_id,
            success=False,
            message="Provider rejected live delete",
            executed_at="2026-09-13T21:45:00Z",
        )


class RemoveFailingRepository(
    JsonCleanupDeletionIntentRepository
):
    """Preserve the pending intent when finalization fails."""

    def remove(
        self,
        provider,
        item_id,
    ):
        raise RuntimeError(
            "deletion-intent finalization unavailable"
        )


class FailingExecuteAuditWriter(CleanupAuditWriter):
    """Simulate durable audit persistence failure."""

    def write(self, event) -> None:
        raise RuntimeError("audit persistence unavailable")


class CleanupExecuteWiringHardeningTests(unittest.TestCase):
    """Harden destructive cleanup post-dispatch behavior."""

    def test_unsuccessful_live_result_is_indeterminate_and_retains_intent(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            provider = UnsuccessfulLiveDeleteProvider(
                repository=repository,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                audit_writer=audit,
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(
                provider.calls,
                ["delete-1"],
            )
            self.assertTrue(
                provider.intent_visible_during_delete
            )

            intent = repository.get(
                "jellyfin",
                "delete-1",
            )
            self.assertIsNotNone(intent)

            self.assertEqual(
                summary.status,
                CleanupRunStatus.FAILED,
            )
            self.assertEqual(summary.modified, 0)

            self.assertEqual(
                len(audit.events),
                3,
            )
            self.assertEqual(
                audit.events[0].status,
                CleanupExecutionEventStatus.DELETE_INDETERMINATE,
            )
            self.assertFalse(
                audit.events[0].modified
            )

            self.assertIn(
                "Provider rejected live delete",
                summary.errors[0],
            )

    def test_remove_failure_retains_intent_after_confirmed_delete(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = RemoveFailingRepository(root)
            provider = LiveDeleteProvider(
                repository=repository,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                audit_writer=audit,
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(
                provider.calls,
                ["delete-1"],
            )
            self.assertTrue(
                provider.intent_visible_during_delete
            )

            intent = repository.get(
                "jellyfin",
                "delete-1",
            )
            self.assertIsNotNone(intent)

            self.assertEqual(
                summary.status,
                CleanupRunStatus.PARTIAL,
            )
            self.assertEqual(summary.modified, 1)

            self.assertEqual(
                audit.events[0].status,
                CleanupExecutionEventStatus.DELETE_SUCCEEDED,
            )
            self.assertTrue(
                audit.events[0].modified
            )

            self.assertTrue(
                any(
                    "deletion-intent finalization failed"
                    in error
                    for error in summary.errors
                )
            )

    def test_audit_failure_after_confirmed_delete_retains_intent(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            provider = LiveDeleteProvider(
                repository=repository,
            )

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                audit_writer=FailingExecuteAuditWriter(),
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(
                provider.calls,
                ["delete-1"],
            )
            self.assertTrue(
                provider.intent_visible_during_delete
            )

            self.assertEqual(summary.modified, 1)
            self.assertEqual(
                summary.status,
                CleanupRunStatus.PARTIAL,
            )

            self.assertTrue(
                any(
                    "audit(delete-1): "
                    "audit persistence unavailable"
                    in error
                    for error in summary.errors
                )
            )

            # A confirmed provider deletion with failed durable audit
            # finalization must retain the replay barrier. Removing it
            # would make a later retry indistinguishable from a clean
            # completed transaction.
            self.assertIsNotNone(
                repository.get(
                    "jellyfin",
                    "delete-1",
                )
            )


def make_multi_execute_report():
    """Create an execute report containing two planned deletions."""
    report = make_report()

    items = tuple(
        replace(
            item,
            mode=CleanupExecutionMode.EXECUTE,
        )
        for item in (
            make_item(
                item_id="delete-1",
                action=CleanupAction.DELETE,
            ),
            make_item(
                item_id="delete-2",
                action=CleanupAction.DELETE,
            ),
        )
    )

    return replace(
        report,
        items=items,
        mode=CleanupExecutionMode.EXECUTE,
    )


class PartiallyFailingLiveDeleteProvider(LiveDeleteProvider):
    """Confirm one delete and lose certainty on the second."""

    def delete_item(
        self,
        item_id: str,
    ) -> ProviderMutationResult:
        self.calls.append(item_id)

        if self.repository is not None:
            intent_visible = (
                self.repository.get(
                    "jellyfin",
                    item_id,
                )
                is not None
            )

            if not intent_visible:
                raise AssertionError(
                    "deletion intent must exist before live dispatch"
                )

        if item_id == "delete-2":
            raise RuntimeError(
                "second delete transport interrupted after dispatch"
            )

        return ProviderMutationResult(
            provider="jellyfin",
            operation=ProviderOperation.DELETE,
            item_id=item_id,
            success=True,
            message="Deleted",
            executed_at="2026-09-13T22:15:00Z",
        )


class CleanupExecuteWiringMultiItemTests(unittest.TestCase):
    """Prove mixed destructive outcomes retain correct replay barriers."""

    def test_success_then_indeterminate_is_partial_with_one_modified(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            provider = PartiallyFailingLiveDeleteProvider(
                repository=repository,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                audit_writer=audit,
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_multi_execute_report()
            )

            self.assertEqual(
                provider.calls,
                ["delete-1", "delete-2"],
            )

            self.assertEqual(summary.total, 2)
            self.assertEqual(summary.planned, 2)
            self.assertEqual(summary.skipped, 0)
            self.assertEqual(summary.modified, 1)
            self.assertEqual(
                summary.status,
                CleanupRunStatus.PARTIAL,
            )

            self.assertIsNone(
                repository.get(
                    "jellyfin",
                    "delete-1",
                )
            )

            uncertain = repository.get(
                "jellyfin",
                "delete-2",
            )
            self.assertIsNotNone(uncertain)

            self.assertEqual(
                tuple(
                    event.status
                    for event in audit.events
                ),
                (
                    CleanupExecutionEventStatus.DELETE_SUCCEEDED,
                    CleanupExecutionEventStatus.DELETE_INDETERMINATE,
                ),
            )

            self.assertEqual(
                tuple(
                    event.modified
                    for event in audit.events
                ),
                (
                    True,
                    False,
                ),
            )

            self.assertTrue(
                any(
                    "delete-2: "
                    "second delete transport interrupted after dispatch"
                    in error
                    for error in summary.errors
                )
            )

    def test_success_then_existing_intent_blocks_second_provider_call(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)

            repository.save(
                CleanupDeletionIntent(
                    execution_id=EXECUTION_ID,
                    provider="jellyfin",
                    item_id="delete-2",
                    created_at=STARTED_AT,
                )
            )

            provider = LiveDeleteProvider(
                repository=repository,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
            cleanup_service=PlannedDeleteCleanupService(),
                audit_writer=audit,
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
            )

            summary = executor.execute(
                make_multi_execute_report()
            )

            # delete-1 reaches the provider and succeeds.
            # delete-2 is blocked by durable intent conflict first.
            self.assertEqual(
                provider.calls,
                ["delete-1"],
            )

            self.assertEqual(summary.total, 2)
            self.assertEqual(summary.planned, 2)
            self.assertEqual(summary.skipped, 0)
            self.assertEqual(summary.modified, 1)
            self.assertEqual(
                summary.status,
                CleanupRunStatus.PARTIAL,
            )

            self.assertIsNone(
                repository.get(
                    "jellyfin",
                    "delete-1",
                )
            )

            blocked = repository.get(
                "jellyfin",
                "delete-2",
            )
            self.assertIsNotNone(blocked)
            assert blocked is not None
            self.assertEqual(
                blocked.execution_id,
                EXECUTION_ID,
            )

            self.assertEqual(
                tuple(
                    event.status
                    for event in audit.events
                ),
                (
                    CleanupExecutionEventStatus.DELETE_SUCCEEDED,
                    CleanupExecutionEventStatus.DELETE_FAILED,
                ),
            )

            self.assertEqual(
                tuple(
                    event.modified
                    for event in audit.events
                ),
                (
                    True,
                    False,
                ),
            )

            self.assertTrue(
                any(
                    "cleanup deletion intent already exists"
                    in error
                    for error in summary.errors
                )
            )


if __name__ == "__main__":
    unittest.main()
