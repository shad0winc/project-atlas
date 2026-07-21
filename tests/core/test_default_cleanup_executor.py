"""Tests for the default Atlas cleanup executor."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from atlas.cleanup.audit import (
    CleanupAuditError,
    CleanupAuditWriter,
)
from atlas.cleanup.default_executor import DefaultCleanupExecutor
from atlas.cleanup.execution_events import (
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
    CleanupRunStatus,
)
from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
)
from atlas.media import (
    ProviderCapabilities,
    ProviderCapability,
    ProviderMutationResult,
    ProviderOperation,
    RecordingMediaProvider,
)
from atlas.policies.models import PolicyDecision
from atlas.retention.models import RetentionDecision


STARTED_AT = datetime(
    2026,
    7,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)

COMPLETED_AT = datetime(
    2026,
    7,
    20,
    12,
    0,
    1,
    tzinfo=timezone.utc,
)


def make_decision(
    *,
    item_id: str,
    action: CleanupAction,
    provider: str = "jellyfin",
) -> CleanupDecision:
    """Create a normalized cleanup decision."""

    policy = PolicyDecision(
        provider=provider,
        item_id=item_id,
        action="ignore",
        reasons=(),
        evaluated_at="2026-07-20T12:00:00Z",
    )

    retention = RetentionDecision(
        provider=provider,
        item_id=item_id,
        eligible=action is CleanupAction.DELETE,
        policy=policy,
        evaluated_at="2026-07-20T12:00:00Z",
    )

    return CleanupDecision(
        provider=provider,
        item_id=item_id,
        action=action,
        retention=retention,
        evaluated_at="2026-07-20T12:00:00Z",
    )


def make_item(
    *,
    item_id: str,
    action: CleanupAction,
    provider: str = "jellyfin",
) -> CleanupExecutionItem:
    """Create a normalized cleanup execution item."""

    decision = make_decision(
        provider=provider,
        item_id=item_id,
        action=action,
    )

    return CleanupExecutionItem(
        provider=provider,
        item_id=item_id,
        decision=decision,
        mode=CleanupExecutionMode.DRY_RUN,
        status=(
            CleanupExecutionStatus.PLANNED
            if action is CleanupAction.DELETE
            else CleanupExecutionStatus.SKIPPED
        ),
        modified=False,
        planned_at=STARTED_AT,
    )


def make_report() -> CleanupExecutionReport:
    """Create a mixed dry-run cleanup execution report."""

    return CleanupExecutionReport(
        provider="jellyfin",
        items=(
            make_item(
                item_id="delete-1",
                action=CleanupAction.DELETE,
            ),
            make_item(
                item_id="keep-1",
                action=CleanupAction.KEEP,
            ),
            make_item(
                item_id="review-1",
                action=CleanupAction.REVIEW,
            ),
        ),
        mode=CleanupExecutionMode.DRY_RUN,
        created_at=STARTED_AT,
    )


def make_clock(
    *values: datetime,
):
    """Create a deterministic clock returning values in order."""

    remaining = iter(values)

    def clock() -> datetime:
        return next(remaining)

    return clock


class DefaultCleanupExecutorTests(unittest.TestCase):
    """Tests for DefaultCleanupExecutor."""

    def test_execute_returns_successful_summary(
        self,
    ) -> None:
        executor = DefaultCleanupExecutor(
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            )
        )

        summary = executor.execute(make_report())

        self.assertEqual(summary.provider, "jellyfin")
        self.assertEqual(
            summary.mode,
            CleanupExecutionMode.DRY_RUN,
        )
        self.assertEqual(
            summary.status,
            CleanupRunStatus.SUCCESS,
        )
        self.assertTrue(summary.successful)
        self.assertFalse(summary.failed)

    def test_execute_counts_report_items(
        self,
    ) -> None:
        executor = DefaultCleanupExecutor(
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            )
        )

        summary = executor.execute(make_report())

        self.assertEqual(summary.total, 3)
        self.assertEqual(summary.planned, 1)
        self.assertEqual(summary.skipped, 2)
        self.assertEqual(summary.modified, 0)
        self.assertEqual(summary.errors, ())

    def test_execute_serializes_timestamps_as_utc(
        self,
    ) -> None:
        eastern = timezone(timedelta(hours=-4))

        executor = DefaultCleanupExecutor(
            clock=make_clock(
                datetime(
                    2026,
                    7,
                    20,
                    8,
                    0,
                    tzinfo=eastern,
                ),
                datetime(
                    2026,
                    7,
                    20,
                    8,
                    0,
                    1,
                    tzinfo=eastern,
                ),
            )
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.started_at,
            "2026-07-20T12:00:00Z",
        )
        self.assertEqual(
            summary.completed_at,
            "2026-07-20T12:00:01Z",
        )

    def test_execute_empty_report_returns_empty_summary(
        self,
    ) -> None:
        report = CleanupExecutionReport(
            provider="jellyfin",
            items=(),
            mode=CleanupExecutionMode.DRY_RUN,
            created_at=STARTED_AT,
        )

        executor = DefaultCleanupExecutor(
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            )
        )

        summary = executor.execute(report)

        self.assertEqual(summary.total, 0)
        self.assertEqual(summary.planned, 0)
        self.assertEqual(summary.skipped, 0)
        self.assertEqual(summary.modified, 0)
        self.assertEqual(
            summary.status,
            CleanupRunStatus.SUCCESS,
        )

    def test_execute_rejects_invalid_report_type(
        self,
    ) -> None:
        executor = DefaultCleanupExecutor(
            clock=lambda: STARTED_AT
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "report must be a CleanupExecutionReport",
        ):
            executor.execute(object())

    def test_execute_rejects_non_datetime_clock_value(
        self,
    ) -> None:
        executor = DefaultCleanupExecutor(
            clock=lambda: "2026-07-20T12:00:00Z"
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "clock must return a datetime",
        ):
            executor.execute(make_report())

    def test_execute_rejects_naive_clock_timestamp(
        self,
    ) -> None:
        executor = DefaultCleanupExecutor(
            clock=lambda: datetime(
                2026,
                7,
                20,
                12,
                0,
            )
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "timezone-aware datetime",
        ):
            executor.execute(make_report())

    def test_clock_is_called_twice_per_execution(
        self,
    ) -> None:
        calls = 0

        def clock() -> datetime:
            nonlocal calls
            calls += 1
            return STARTED_AT

        executor = DefaultCleanupExecutor(clock=clock)

        executor.execute(make_report())

        self.assertEqual(calls, 2)

    def test_execute_preserves_normalized_provider(
        self,
    ) -> None:
        report = CleanupExecutionReport(
            provider="  JELLYFIN  ",
            items=(),
            mode=CleanupExecutionMode.DRY_RUN,
            created_at=STARTED_AT,
        )

        executor = DefaultCleanupExecutor(
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            )
        )

        summary = executor.execute(report)

        self.assertEqual(summary.provider, "jellyfin")

    def test_summary_can_be_serialized(
        self,
    ) -> None:
        executor = DefaultCleanupExecutor(
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            )
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.to_dict(),
            {
                "provider": "jellyfin",
                "mode": "dry_run",
                "status": "success",
                "started_at": "2026-07-20T12:00:00Z",
                "completed_at": "2026-07-20T12:00:01Z",
                "total": 3,
                "planned": 1,
                "skipped": 2,
                "modified": 0,
                "errors": [],
            },
        )

    def test_execute_previews_only_planned_items(
        self,
    ) -> None:
        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: STARTED_AT,
        )

        executor = DefaultCleanupExecutor(
            provider=provider,
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            tuple(
                request.item_id
                for request in provider.requests
            ),
            ("delete-1",),
        )
        self.assertEqual(summary.planned, 1)
        self.assertEqual(summary.skipped, 2)
        self.assertEqual(summary.modified, 0)
        self.assertEqual(
            summary.status,
            CleanupRunStatus.SUCCESS,
        )

    def test_execute_never_previews_skipped_items(
        self,
    ) -> None:
        report = CleanupExecutionReport(
            provider="jellyfin",
            items=(
                make_item(
                    item_id="keep-1",
                    action=CleanupAction.KEEP,
                ),
                make_item(
                    item_id="review-1",
                    action=CleanupAction.REVIEW,
                ),
            ),
            mode=CleanupExecutionMode.DRY_RUN,
            created_at=STARTED_AT,
        )

        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: STARTED_AT,
        )

        executor = DefaultCleanupExecutor(
            provider=provider,
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(report)

        self.assertEqual(provider.requests, ())
        self.assertEqual(summary.planned, 0)
        self.assertEqual(summary.skipped, 2)
        self.assertEqual(
            summary.status,
            CleanupRunStatus.SUCCESS,
        )

    def test_execute_rejects_mismatched_provider(
        self,
    ) -> None:
        provider = RecordingMediaProvider(
            "plex",
            clock=lambda: STARTED_AT,
        )

        executor = DefaultCleanupExecutor(
            provider=provider,
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "provider does not match",
        ):
            executor.execute(make_report())

        self.assertEqual(provider.requests, ())

    def test_execute_rejects_missing_capability_method(
        self,
    ) -> None:
        class MissingCapabilitiesProvider:
            name = "jellyfin"

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                raise AssertionError(
                    "preview must not be called"
                )

        executor = DefaultCleanupExecutor(
            provider=MissingCapabilitiesProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "provider must implement get_capabilities",
        ):
            executor.execute(make_report())

    def test_execute_rejects_invalid_capability_contract(
        self,
    ) -> None:
        class InvalidCapabilitiesProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ):
                return object()

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                raise AssertionError(
                    "preview must not be called"
                )

        executor = DefaultCleanupExecutor(
            provider=InvalidCapabilitiesProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "provider must return ProviderCapabilities",
        ):
            executor.execute(make_report())

    def test_execute_rejects_provider_without_preview_support(
        self,
    ) -> None:
        class UnsupportedPreviewProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.LIST_MEDIA,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                raise AssertionError(
                    "preview must not be called"
                )

        executor = DefaultCleanupExecutor(
            provider=UnsupportedPreviewProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "jellyfin does not support delete previews",
        ):
            executor.execute(make_report())

    def test_execute_rejects_declared_preview_without_method(
        self,
    ) -> None:
        class MissingPreviewMethodProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.PREVIEW_DELETE,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

        executor = DefaultCleanupExecutor(
            provider=MissingPreviewMethodProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        with self.assertRaisesRegex(
            CleanupExecutionError,
            "declares delete preview support "
            "but does not implement preview_delete_item",
        ):
            executor.execute(make_report())

    def test_execute_rejects_invalid_preview_type(
        self,
    ) -> None:
        class InvalidProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.PREVIEW_DELETE,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

            def preview_delete_item(
                self,
                item_id: str,
            ):
                return object()

        executor = DefaultCleanupExecutor(
            provider=InvalidProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.status,
            CleanupRunStatus.FAILED,
        )
        self.assertEqual(summary.modified, 0)
        self.assertEqual(len(summary.errors), 1)
        self.assertIn(
            "ProviderMutationResult",
            summary.errors[0],
        )

    def test_execute_rejects_mismatched_preview_item_id(
        self,
    ) -> None:
        class MismatchedItemProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.PREVIEW_DELETE,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                return ProviderMutationResult(
                    provider="jellyfin",
                    operation=ProviderOperation.DELETE,
                    item_id="different-item",
                    success=True,
                    message="Preview recorded",
                    executed_at="2026-07-20T12:00:00Z",
                )

        executor = DefaultCleanupExecutor(
            provider=MismatchedItemProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.status,
            CleanupRunStatus.FAILED,
        )
        self.assertEqual(summary.modified, 0)
        self.assertIn(
            "item_id does not match",
            summary.errors[0],
        )

    def test_execute_rejects_mismatched_preview_provider(
        self,
    ) -> None:
        class MismatchedProviderResult:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.PREVIEW_DELETE,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                return ProviderMutationResult(
                    provider="plex",
                    operation=ProviderOperation.DELETE,
                    item_id=item_id,
                    success=True,
                    message="Preview recorded",
                    executed_at="2026-07-20T12:00:00Z",
                )

        executor = DefaultCleanupExecutor(
            provider=MismatchedProviderResult(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.status,
            CleanupRunStatus.FAILED,
        )
        self.assertIn(
            "provider does not match",
            summary.errors[0],
        )

    def test_execute_normalizes_unsuccessful_preview(
        self,
    ) -> None:
        class UnsuccessfulProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.PREVIEW_DELETE,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                return ProviderMutationResult(
                    provider="jellyfin",
                    operation=ProviderOperation.DELETE,
                    item_id=item_id,
                    success=False,
                    message="Provider rejected preview",
                    executed_at="2026-07-20T12:00:00Z",
                )

        executor = DefaultCleanupExecutor(
            provider=UnsuccessfulProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.status,
            CleanupRunStatus.FAILED,
        )
        self.assertEqual(
            summary.errors,
            (
                "delete-1: Provider rejected preview",
            ),
        )
        self.assertEqual(summary.modified, 0)

    def test_execute_normalizes_provider_exception(
        self,
    ) -> None:
        class FailingProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.PREVIEW_DELETE,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                raise RuntimeError(
                    "provider unavailable"
                )

        executor = DefaultCleanupExecutor(
            provider=FailingProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.status,
            CleanupRunStatus.FAILED,
        )
        self.assertEqual(
            summary.errors,
            (
                "delete-1: provider unavailable",
            ),
        )
        self.assertEqual(summary.modified, 0)

    def test_execute_returns_partial_when_some_previews_fail(
        self,
    ) -> None:
        report = CleanupExecutionReport(
            provider="jellyfin",
            items=(
                make_item(
                    item_id="delete-1",
                    action=CleanupAction.DELETE,
                ),
                make_item(
                    item_id="delete-2",
                    action=CleanupAction.DELETE,
                ),
            ),
            mode=CleanupExecutionMode.DRY_RUN,
            created_at=STARTED_AT,
        )

        class PartiallyFailingProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.PREVIEW_DELETE,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                if item_id == "delete-2":
                    raise RuntimeError(
                        "preview failed"
                    )

                return ProviderMutationResult(
                    provider="jellyfin",
                    operation=ProviderOperation.DELETE,
                    item_id=item_id,
                    success=True,
                    message="Preview recorded",
                    executed_at="2026-07-20T12:00:00Z",
                )

        executor = DefaultCleanupExecutor(
            provider=PartiallyFailingProvider(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(report)

        self.assertEqual(
            summary.status,
            CleanupRunStatus.PARTIAL,
        )
        self.assertEqual(summary.planned, 2)
        self.assertEqual(summary.modified, 0)
        self.assertEqual(
            summary.errors,
            (
                "delete-2: preview failed",
            ),
        )


    def test_execute_records_one_event_per_item(
        self,
    ) -> None:
        class RecordingAuditWriter(CleanupAuditWriter):
            def __init__(self) -> None:
                self.events = []

            def write(self, event) -> None:
                self.events.append(event)

        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: STARTED_AT,
        )
        writer = RecordingAuditWriter()

        executor = DefaultCleanupExecutor(
            provider=provider,
            audit_writer=writer,
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.status,
            CleanupRunStatus.SUCCESS,
        )
        self.assertEqual(len(writer.events), 3)
        self.assertEqual(
            tuple(event.item_id for event in writer.events),
            (
                "delete-1",
                "keep-1",
                "review-1",
            ),
        )
        self.assertEqual(
            tuple(event.status for event in writer.events),
            (
                CleanupExecutionEventStatus.PREVIEW_SUCCEEDED,
                CleanupExecutionEventStatus.SKIPPED,
                CleanupExecutionEventStatus.SKIPPED,
            ),
        )
        self.assertTrue(
            all(
                event.occurred_at == STARTED_AT
                for event in writer.events
            )
        )

    def test_successful_preview_event_uses_provider_message(
        self,
    ) -> None:
        class RecordingAuditWriter(CleanupAuditWriter):
            def __init__(self) -> None:
                self.events = []

            def write(self, event) -> None:
                self.events.append(event)

        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: STARTED_AT,
        )
        writer = RecordingAuditWriter()

        executor = DefaultCleanupExecutor(
            provider=provider,
            audit_writer=writer,
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        executor.execute(make_report())

        event = writer.events[0]

        self.assertEqual(event.item_id, "delete-1")
        self.assertEqual(
            event.status,
            CleanupExecutionEventStatus.PREVIEW_SUCCEEDED,
        )
        self.assertEqual(
            event.message,
            "Deletion preview recorded; no media was modified",
        )
        self.assertFalse(event.modified)

    def test_failed_preview_records_failed_event(
        self,
    ) -> None:
        class FailingProvider:
            name = "jellyfin"

            def get_capabilities(
                self,
            ) -> ProviderCapabilities:
                return ProviderCapabilities(
                    provider="jellyfin",
                    capabilities=frozenset(
                        {
                            ProviderCapability.PREVIEW_DELETE,
                        }
                    ),
                    supports_batch_listing=False,
                    supports_batch_preview=False,
                    max_batch_size=None,
                )

            def preview_delete_item(
                self,
                item_id: str,
            ) -> ProviderMutationResult:
                raise RuntimeError("provider unavailable")

        class RecordingAuditWriter(CleanupAuditWriter):
            def __init__(self) -> None:
                self.events = []

            def write(self, event) -> None:
                self.events.append(event)

        writer = RecordingAuditWriter()

        executor = DefaultCleanupExecutor(
            provider=FailingProvider(),
            audit_writer=writer,
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.status,
            CleanupRunStatus.FAILED,
        )

        failed_event = writer.events[0]

        self.assertEqual(failed_event.item_id, "delete-1")
        self.assertEqual(
            failed_event.status,
            CleanupExecutionEventStatus.PREVIEW_FAILED,
        )
        self.assertEqual(
            failed_event.message,
            "provider unavailable",
        )

        self.assertEqual(
            tuple(event.status for event in writer.events[1:]),
            (
                CleanupExecutionEventStatus.SKIPPED,
                CleanupExecutionEventStatus.SKIPPED,
            ),
        )

    def test_planned_item_without_provider_records_skipped_event(
        self,
    ) -> None:
        class RecordingAuditWriter(CleanupAuditWriter):
            def __init__(self) -> None:
                self.events = []

            def write(self, event) -> None:
                self.events.append(event)

        report = CleanupExecutionReport(
            provider="jellyfin",
            items=(
                make_item(
                    item_id="delete-1",
                    action=CleanupAction.DELETE,
                ),
            ),
            mode=CleanupExecutionMode.DRY_RUN,
            created_at=STARTED_AT,
        )
        writer = RecordingAuditWriter()

        executor = DefaultCleanupExecutor(
            audit_writer=writer,
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(report)

        self.assertEqual(
            summary.status,
            CleanupRunStatus.SUCCESS,
        )
        self.assertEqual(len(writer.events), 1)
        self.assertEqual(
            writer.events[0].status,
            CleanupExecutionEventStatus.SKIPPED,
        )
        self.assertIn(
            "no media provider",
            writer.events[0].message,
        )

    def test_audit_failure_makes_successful_run_partial(
        self,
    ) -> None:
        class FailingAuditWriter(CleanupAuditWriter):
            def write(self, event) -> None:
                raise CleanupAuditError("disk unavailable")

        provider = RecordingMediaProvider(
            "jellyfin",
            clock=lambda: STARTED_AT,
        )

        executor = DefaultCleanupExecutor(
            provider=provider,
            audit_writer=FailingAuditWriter(),
            clock=make_clock(
                STARTED_AT,
                COMPLETED_AT,
            ),
        )

        summary = executor.execute(make_report())

        self.assertEqual(
            summary.status,
            CleanupRunStatus.PARTIAL,
        )
        self.assertEqual(summary.modified, 0)
        self.assertEqual(
            len(summary.errors),
            3,
        )
        self.assertEqual(
            summary.errors[0],
            "audit(delete-1): disk unavailable",
        )
        self.assertEqual(
            summary.errors[1],
            "audit(keep-1): disk unavailable",
        )
        self.assertEqual(
            summary.errors[2],
            "audit(review-1): disk unavailable",
        )
        self.assertEqual(
            tuple(
                request.item_id
                for request in provider.requests
            ),
            ("delete-1",),
        )

    def test_rejects_invalid_audit_writer(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            CleanupExecutionError,
            "audit_writer must be a CleanupAuditWriter",
        ):
            DefaultCleanupExecutor(
                audit_writer=object(),
            )


if __name__ == "__main__":
    unittest.main()
