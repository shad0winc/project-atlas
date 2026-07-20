"""Tests for the Atlas cleanup execution service."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from atlas.cleanup import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
    CleanupExecutionMode,
    CleanupExecutionService,
    CleanupExecutionStatus,
    CleanupScanReport,
)
from atlas.policies.models import PolicyDecision
from atlas.retention.models import RetentionDecision


NOW = datetime(
    2026,
    7,
    20,
    12,
    0,
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


def make_scan() -> CleanupScanReport:
    """Create a cleanup scan containing every action."""

    return CleanupScanReport(
        provider="jellyfin",
        decisions=(
            make_decision(
                item_id="delete-1",
                action=CleanupAction.DELETE,
            ),
            make_decision(
                item_id="keep-1",
                action=CleanupAction.KEEP,
            ),
            make_decision(
                item_id="review-1",
                action=CleanupAction.REVIEW,
            ),
        ),
        scanned_at=NOW,
    )


class CleanupExecutionServiceTests(unittest.TestCase):
    """Tests for CleanupExecutionService."""

    def setUp(self) -> None:
        self.service = CleanupExecutionService(
            clock=lambda: NOW
        )

    def test_plan_converts_scan_to_execution_report(
        self,
    ) -> None:
        report = self.service.plan(make_scan())

        self.assertEqual(report.provider, "jellyfin")
        self.assertEqual(
            report.mode,
            CleanupExecutionMode.DRY_RUN,
        )
        self.assertEqual(report.created_at, NOW)
        self.assertEqual(report.total, 3)
        self.assertEqual(report.planned_count, 1)
        self.assertEqual(report.skipped_count, 2)
        self.assertEqual(report.modified_count, 0)

    def test_delete_is_planned_and_others_are_skipped(
        self,
    ) -> None:
        report = self.service.plan(make_scan())

        self.assertEqual(
            tuple(item.status for item in report.items),
            (
                CleanupExecutionStatus.PLANNED,
                CleanupExecutionStatus.SKIPPED,
                CleanupExecutionStatus.SKIPPED,
            ),
        )

    def test_plan_preserves_scan_decision_order(
        self,
    ) -> None:
        report = self.service.plan(make_scan())

        self.assertEqual(
            tuple(item.item_id for item in report.items),
            (
                "delete-1",
                "keep-1",
                "review-1",
            ),
        )

    def test_plan_preserves_source_decisions(
        self,
    ) -> None:
        scan = make_scan()

        report = self.service.plan(scan)

        self.assertEqual(
            tuple(item.decision for item in report.items),
            scan.decisions,
        )

    def test_empty_scan_returns_empty_report(self) -> None:
        scan = CleanupScanReport(
            provider="jellyfin",
            decisions=(),
            scanned_at=NOW,
        )

        report = self.service.plan(scan)

        self.assertEqual(report.items, ())
        self.assertEqual(report.total, 0)
        self.assertEqual(report.planned_count, 0)
        self.assertEqual(report.skipped_count, 0)
        self.assertEqual(report.modified_count, 0)

    def test_all_items_share_report_timestamp(
        self,
    ) -> None:
        report = self.service.plan(make_scan())

        self.assertTrue(
            all(
                item.planned_at == report.created_at
                for item in report.items
            )
        )

    def test_accepts_string_dry_run_mode(self) -> None:
        report = self.service.plan(
            make_scan(),
            mode="dry_run",
        )

        self.assertEqual(
            report.mode,
            CleanupExecutionMode.DRY_RUN,
        )

    def test_rejects_invalid_scan_type(self) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "scan must be a CleanupScanReport",
        ):
            self.service.plan(object())

    def test_rejects_invalid_execution_mode(self) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "invalid cleanup execution mode",
        ):
            self.service.plan(
                make_scan(),
                mode="delete",
            )

    def test_rejects_non_datetime_clock_value(
        self,
    ) -> None:
        service = CleanupExecutionService(
            clock=lambda: "2026-07-20T12:00:00Z"
        )

        with self.assertRaisesRegex(
            CleanupError,
            "clock must return a datetime",
        ):
            service.plan(make_scan())

    def test_rejects_naive_clock_timestamp(self) -> None:
        service = CleanupExecutionService(
            clock=lambda: datetime(
                2026,
                7,
                20,
                12,
                0,
            )
        )

        with self.assertRaisesRegex(
            CleanupError,
            "timezone-aware datetime",
        ):
            service.plan(make_scan())

    def test_clock_is_called_once_per_plan(self) -> None:
        calls = 0

        def clock() -> datetime:
            nonlocal calls
            calls += 1
            return NOW

        service = CleanupExecutionService(clock=clock)

        service.plan(make_scan())

        self.assertEqual(calls, 1)


if __name__ == "__main__":
    unittest.main()
