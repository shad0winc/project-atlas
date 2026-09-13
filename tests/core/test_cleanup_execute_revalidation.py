"""Fresh destructive-boundary revalidation contracts for cleanup execute."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlas.cleanup.audit import CleanupAuditWriter
from atlas.cleanup.deletion_intent_repository import (
    JsonCleanupDeletionIntentRepository,
)
from atlas.cleanup.default_executor import DefaultCleanupExecutor
from atlas.cleanup.execution_events import (
    CleanupExecutionEventStatus,
)
from atlas.cleanup.execution_models import CleanupExecutionMode
from atlas.cleanup.executor import CleanupExecutionError, CleanupRunStatus
from atlas.cleanup.models import CleanupAction
from atlas.cleanup.service import CleanupService
from atlas.favorites import FavoriteStore
from atlas.media.capabilities import (
    ProviderCapabilities,
    ProviderCapability,
)
from atlas.media.provider import (
    ProviderMutationResult,
    ProviderOperation,
)
from atlas.policies.providers import PolicyProviders
from atlas.policies.service import PolicyService
from atlas.retention.service import RetentionService

from tests.core.test_default_cleanup_executor import (
    COMPLETED_AT,
    EXECUTION_ID,
    STARTED_AT,
    make_clock,
    make_item,
    make_report,
)


USER_A = "usr_" + ("a" * 32)


def make_execute_report():
    """Convert the normalized executor fixture to execute mode."""
    report = make_report()

    return replace(
        report,
        items=tuple(
            replace(
                item,
                mode=CleanupExecutionMode.EXECUTE,
            )
            for item in report.items
        ),
        mode=CleanupExecutionMode.EXECUTE,
    )


class RecordingAuditWriter(CleanupAuditWriter):
    """Collect cleanup execution events."""

    def __init__(self) -> None:
        self.events = []

    def write(self, event) -> None:
        self.events.append(event)


class OrderingLiveDeleteProvider:
    """Record whether revalidation and intent persistence preceded delete."""

    name = "jellyfin"

    def __init__(
        self,
        *,
        repository: JsonCleanupDeletionIntentRepository,
        evaluations: list[tuple[str, str]],
    ) -> None:
        self.repository = repository
        self.evaluations = evaluations
        self.calls: list[str] = []
        self.intent_visible_during_delete = False
        self.evaluation_visible_during_delete = False

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

        self.intent_visible_during_delete = (
            self.repository.get(
                "jellyfin",
                item_id,
            )
            is not None
        )

        self.evaluation_visible_during_delete = (
            ("jellyfin", item_id)
            in self.evaluations
        )

        return ProviderMutationResult(
            provider="jellyfin",
            operation=ProviderOperation.DELETE,
            item_id=item_id,
            success=True,
            message="Deleted",
            executed_at="2026-09-13T22:40:00Z",
        )


class RecordingCleanupService:
    """Delegate authoritative cleanup evaluation while recording calls."""

    def __init__(
        self,
        service: CleanupService,
        evaluations: list[tuple[str, str]],
    ) -> None:
        self.service = service
        self.evaluations = evaluations

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ):
        self.evaluations.append(
            (
                provider,
                item_id,
            )
        )

        return self.service.evaluate(
            provider,
            item_id,
        )


class RaisingCleanupService:
    """Fail authoritative revalidation before destructive mutation."""

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ):
        raise RuntimeError("fresh policy state unavailable")


class InvalidCleanupService:
    """Return a value that is not a normalized CleanupDecision."""

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ):
        return {"action": "delete"}


class MismatchedCleanupService:
    """Return a valid decision for a different media identity."""

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ):
        return make_item(
            item_id="different-item",
            action=CleanupAction.DELETE,
        ).decision


class MappingCleanupService:
    """Return deterministic fresh decisions by media item."""

    def __init__(self, decisions) -> None:
        self.decisions = decisions
        self.calls: list[tuple[str, str]] = []

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ):
        self.calls.append((provider, item_id))
        return self.decisions[item_id]


class CleanupExecuteFreshRevalidationTests(unittest.TestCase):
    """Require fresh policy/retention state before live deletion."""

    def _services(
        self,
        root: str,
    ) -> tuple[
        FavoriteStore,
        CleanupService,
    ]:
        favorites = FavoriteStore(Path(root))

        policy = PolicyService(
            providers=PolicyProviders(
                favorites=favorites,
            ),
        )

        retention = RetentionService(
            policy_service=policy,
        )

        cleanup = CleanupService(
            retention_service=retention,
        )

        return favorites, cleanup

    def test_execute_requires_cleanup_service_for_fresh_revalidation(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            evaluations: list[tuple[str, str]] = []

            provider = OrderingLiveDeleteProvider(
                repository=repository,
                evaluations=evaluations,
            )

            executor = DefaultCleanupExecutor(
                provider=provider,
                deletion_intent_repository=repository,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            with self.assertRaisesRegex(
                CleanupExecutionError,
                "cleanup service",
            ):
                executor.execute(
                    make_execute_report()
                )

            self.assertEqual(evaluations, [])
            self.assertEqual(provider.calls, [])
            self.assertEqual(repository.list(), ())

    def test_favorite_added_after_plan_blocks_live_delete(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            favorites, cleanup = self._services(root)

            # The plan was created while the item was eligible.
            planned = cleanup.evaluate(
                "jellyfin",
                "delete-1",
            )
            self.assertIs(
                planned.action,
                CleanupAction.DELETE,
            )

            report = make_execute_report()

            # Protection changes after planning but before execute.
            favorites.add(
                USER_A,
                "jellyfin",
                "delete-1",
                media_type="movie",
                title="Protected after planning",
            )

            repository = JsonCleanupDeletionIntentRepository(root)
            evaluations: list[tuple[str, str]] = []
            recording_cleanup = RecordingCleanupService(
                cleanup,
                evaluations,
            )

            provider = OrderingLiveDeleteProvider(
                repository=repository,
                evaluations=evaluations,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
                audit_writer=audit,
                deletion_intent_repository=repository,
                cleanup_service=recording_cleanup,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(report)

            self.assertEqual(
                evaluations,
                [
                    (
                        "jellyfin",
                        "delete-1",
                    ),
                ],
            )

            self.assertEqual(provider.calls, [])
            self.assertEqual(repository.list(), ())
            self.assertEqual(summary.modified, 0)

            # A stale planned DELETE becoming protected is a safe
            # non-destructive outcome, not an uncertain provider mutation.
            self.assertEqual(
                summary.status,
                CleanupRunStatus.SUCCESS,
            )

            delete_events = [
                event
                for event in audit.events
                if event.item_id == "delete-1"
            ]

            self.assertEqual(len(delete_events), 1)

            delete_event = delete_events[0]

            self.assertIs(
                delete_event.status,
                CleanupExecutionEventStatus.SKIPPED,
            )
            self.assertFalse(delete_event.modified)
            self.assertIn(
                "fresh policy/retention revalidation: keep",
                delete_event.message,
            )

            self.assertEqual(len(audit.events), 3)

    def test_still_eligible_item_revalidates_before_intent_and_delete(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            _, cleanup = self._services(root)

            repository = JsonCleanupDeletionIntentRepository(root)
            evaluations: list[tuple[str, str]] = []
            recording_cleanup = RecordingCleanupService(
                cleanup,
                evaluations,
            )

            provider = OrderingLiveDeleteProvider(
                repository=repository,
                evaluations=evaluations,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
                audit_writer=audit,
                deletion_intent_repository=repository,
                cleanup_service=recording_cleanup,
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
                evaluations,
                [
                    (
                        "jellyfin",
                        "delete-1",
                    ),
                ],
            )

            self.assertEqual(
                provider.calls,
                ["delete-1"],
            )
            self.assertTrue(
                provider.evaluation_visible_during_delete
            )
            self.assertTrue(
                provider.intent_visible_during_delete
            )

            self.assertEqual(
                summary.status,
                CleanupRunStatus.SUCCESS,
            )
            self.assertEqual(summary.modified, 1)

            self.assertIsNone(
                repository.get(
                    "jellyfin",
                    "delete-1",
                )
            )

            self.assertEqual(
                audit.events[0].status,
                CleanupExecutionEventStatus.DELETE_SUCCEEDED,
            )
            self.assertTrue(
                audit.events[0].modified
            )


    def test_revalidation_exception_fails_before_intent_or_provider(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            evaluations: list[tuple[str, str]] = []

            provider = OrderingLiveDeleteProvider(
                repository=repository,
                evaluations=evaluations,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
                audit_writer=audit,
                deletion_intent_repository=repository,
                cleanup_service=RaisingCleanupService(),
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(provider.calls, [])
            self.assertEqual(repository.list(), ())
            self.assertEqual(summary.modified, 0)
            self.assertEqual(
                summary.status,
                CleanupRunStatus.FAILED,
            )
            self.assertEqual(len(summary.errors), 1)
            self.assertIn(
                "fresh cleanup revalidation failed",
                summary.errors[0],
            )
            self.assertIn(
                "fresh policy state unavailable",
                summary.errors[0],
            )

            delete_events = [
                event
                for event in audit.events
                if event.item_id == "delete-1"
            ]

            self.assertEqual(len(delete_events), 1)
            self.assertIs(
                delete_events[0].status,
                CleanupExecutionEventStatus.DELETE_FAILED,
            )
            self.assertFalse(delete_events[0].modified)

    def test_invalid_fresh_decision_fails_before_intent_or_provider(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            evaluations: list[tuple[str, str]] = []

            provider = OrderingLiveDeleteProvider(
                repository=repository,
                evaluations=evaluations,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
                audit_writer=audit,
                deletion_intent_repository=repository,
                cleanup_service=InvalidCleanupService(),
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(provider.calls, [])
            self.assertEqual(repository.list(), ())
            self.assertEqual(summary.modified, 0)
            self.assertEqual(
                summary.status,
                CleanupRunStatus.FAILED,
            )
            self.assertEqual(len(summary.errors), 1)
            self.assertIn(
                "invalid cleanup decision",
                summary.errors[0],
            )

            delete_events = [
                event
                for event in audit.events
                if event.item_id == "delete-1"
            ]

            self.assertEqual(len(delete_events), 1)
            self.assertIs(
                delete_events[0].status,
                CleanupExecutionEventStatus.DELETE_FAILED,
            )
            self.assertFalse(delete_events[0].modified)

    def test_mismatched_fresh_decision_fails_before_intent_or_provider(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            repository = JsonCleanupDeletionIntentRepository(root)
            evaluations: list[tuple[str, str]] = []

            provider = OrderingLiveDeleteProvider(
                repository=repository,
                evaluations=evaluations,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
                audit_writer=audit,
                deletion_intent_repository=repository,
                cleanup_service=MismatchedCleanupService(),
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(
                make_execute_report()
            )

            self.assertEqual(provider.calls, [])
            self.assertEqual(repository.list(), ())
            self.assertEqual(summary.modified, 0)
            self.assertEqual(
                summary.status,
                CleanupRunStatus.FAILED,
            )
            self.assertEqual(len(summary.errors), 1)
            self.assertIn(
                "does not match execution item",
                summary.errors[0],
            )

            delete_events = [
                event
                for event in audit.events
                if event.item_id == "delete-1"
            ]

            self.assertEqual(len(delete_events), 1)
            self.assertIs(
                delete_events[0].status,
                CleanupExecutionEventStatus.DELETE_FAILED,
            )
            self.assertFalse(delete_events[0].modified)

    def test_mixed_fresh_skip_and_delete_succeeds_safely(
        self,
    ) -> None:
        with TemporaryDirectory() as root:
            base_report = make_execute_report()

            first_delete = next(
                item
                for item in base_report.items
                if item.item_id == "delete-1"
            )

            second_delete = replace(
                make_item(
                    item_id="delete-2",
                    action=CleanupAction.DELETE,
                ),
                mode=CleanupExecutionMode.EXECUTE,
            )

            report = replace(
                base_report,
                items=(
                    first_delete,
                    second_delete,
                    *tuple(
                        item
                        for item in base_report.items
                        if item.item_id != "delete-1"
                    ),
                ),
            )

            decisions = {
                "delete-1": make_item(
                    item_id="delete-1",
                    action=CleanupAction.KEEP,
                ).decision,
                "delete-2": make_item(
                    item_id="delete-2",
                    action=CleanupAction.DELETE,
                ).decision,
            }

            cleanup = MappingCleanupService(decisions)

            repository = JsonCleanupDeletionIntentRepository(root)
            evaluations = cleanup.calls

            provider = OrderingLiveDeleteProvider(
                repository=repository,
                evaluations=evaluations,
            )
            audit = RecordingAuditWriter()

            executor = DefaultCleanupExecutor(
                provider=provider,
                audit_writer=audit,
                deletion_intent_repository=repository,
                cleanup_service=cleanup,
                clock=make_clock(
                    STARTED_AT,
                    COMPLETED_AT,
                ),
                execution_id_factory=lambda: EXECUTION_ID,
            )

            summary = executor.execute(report)

            self.assertEqual(
                cleanup.calls,
                [
                    ("jellyfin", "delete-1"),
                    ("jellyfin", "delete-2"),
                ],
            )

            self.assertEqual(
                provider.calls,
                ["delete-2"],
            )

            self.assertEqual(repository.list(), ())

            self.assertEqual(
                summary.status,
                CleanupRunStatus.SUCCESS,
            )
            self.assertEqual(summary.modified, 1)
            self.assertEqual(summary.errors, ())

            delete_1_events = [
                event
                for event in audit.events
                if event.item_id == "delete-1"
            ]
            delete_2_events = [
                event
                for event in audit.events
                if event.item_id == "delete-2"
            ]

            self.assertEqual(len(delete_1_events), 1)
            self.assertEqual(len(delete_2_events), 1)

            self.assertIs(
                delete_1_events[0].status,
                CleanupExecutionEventStatus.SKIPPED,
            )
            self.assertFalse(
                delete_1_events[0].modified
            )

            self.assertIs(
                delete_2_events[0].status,
                CleanupExecutionEventStatus.DELETE_SUCCEEDED,
            )
            self.assertTrue(
                delete_2_events[0].modified
            )



if __name__ == "__main__":
    unittest.main()
