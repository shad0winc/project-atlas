"""Tests for Atlas cleanup execution models."""

from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from atlas.cleanup import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
    CleanupExecutionItem,
    CleanupExecutionMode,
    CleanupExecutionReport,
    CleanupExecutionStatus,
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


def make_retention(
    *,
    provider: str = "jellyfin",
    item_id: str = "item-1",
    eligible: bool = True,
) -> RetentionDecision:
    """Create a normalized retention decision."""

    policy = PolicyDecision(
        provider=provider,
        item_id=item_id,
        action="ignore",
        reasons=(),
        evaluated_at="2026-07-20T12:00:00Z",
    )

    return RetentionDecision(
        provider=provider,
        item_id=item_id,
        eligible=eligible,
        policy=policy,
        evaluated_at="2026-07-20T12:00:00Z",
    )


def make_decision(
    *,
    provider: str = "jellyfin",
    item_id: str = "item-1",
    action: CleanupAction = CleanupAction.DELETE,
) -> CleanupDecision:
    """Create a normalized cleanup decision."""

    return CleanupDecision(
        provider=provider,
        item_id=item_id,
        action=action,
        retention=make_retention(
            provider=provider,
            item_id=item_id,
            eligible=action is CleanupAction.DELETE,
        ),
        evaluated_at="2026-07-20T12:00:00Z",
    )


def make_item(
    *,
    provider: str = "jellyfin",
    item_id: str = "item-1",
    action: CleanupAction = CleanupAction.DELETE,
    status: CleanupExecutionStatus | None = None,
) -> CleanupExecutionItem:
    """Create a normalized cleanup execution item."""

    decision = make_decision(
        provider=provider,
        item_id=item_id,
        action=action,
    )

    if status is None:
        status = (
            CleanupExecutionStatus.PLANNED
            if action is CleanupAction.DELETE
            else CleanupExecutionStatus.SKIPPED
        )

    return CleanupExecutionItem(
        provider=provider,
        item_id=item_id,
        decision=decision,
        status=status,
        planned_at=NOW,
    )


class CleanupExecutionItemTests(unittest.TestCase):
    """Tests for CleanupExecutionItem."""

    def test_delete_decision_becomes_planned(self) -> None:
        item = make_item()

        self.assertEqual(
            item.mode,
            CleanupExecutionMode.DRY_RUN,
        )
        self.assertEqual(
            item.status,
            CleanupExecutionStatus.PLANNED,
        )
        self.assertFalse(item.modified)

    def test_keep_and_review_decisions_are_skipped(self) -> None:
        for action in (
            CleanupAction.KEEP,
            CleanupAction.REVIEW,
        ):
            with self.subTest(action=action):
                item = make_item(action=action)

                self.assertEqual(
                    item.status,
                    CleanupExecutionStatus.SKIPPED,
                )

    def test_rejects_status_that_conflicts_with_decision(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "status does not match",
        ):
            make_item(
                action=CleanupAction.KEEP,
                status=CleanupExecutionStatus.PLANNED,
            )

    def test_dry_run_cannot_claim_media_was_modified(
        self,
    ) -> None:
        decision = make_decision()

        with self.assertRaisesRegex(
            CleanupError,
            "cannot modify media",
        ):
            CleanupExecutionItem(
                provider="jellyfin",
                item_id="item-1",
                decision=decision,
                modified=True,
                planned_at=NOW,
            )

    def test_rejects_mismatched_decision_identity(
        self,
    ) -> None:
        decision = make_decision(item_id="item-2")

        with self.assertRaisesRegex(
            CleanupError,
            "item_id does not match",
        ):
            CleanupExecutionItem(
                provider="jellyfin",
                item_id="item-1",
                decision=decision,
                planned_at=NOW,
            )

    def test_rejects_naive_planned_timestamp(self) -> None:
        decision = make_decision()

        with self.assertRaisesRegex(
            CleanupError,
            "timezone-aware",
        ):
            CleanupExecutionItem(
                provider="jellyfin",
                item_id="item-1",
                decision=decision,
                planned_at=datetime(2026, 7, 20, 12, 0),
            )

    def test_serializes_normalized_contract(self) -> None:
        offset_time = NOW.astimezone(
            timezone(timedelta(hours=-4))
        )

        item = CleanupExecutionItem(
            provider=" JELLYFIN ",
            item_id=" item-1 ",
            decision=make_decision(),
            planned_at=offset_time,
        )

        payload = item.to_dict()

        self.assertEqual(payload["provider"], "jellyfin")
        self.assertEqual(payload["item_id"], "item-1")
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(payload["status"], "planned")
        self.assertFalse(payload["modified"])
        self.assertEqual(
            payload["planned_at"],
            "2026-07-20T12:00:00Z",
        )
        self.assertEqual(
            payload["decision"]["action"],
            "delete",
        )


class CleanupExecutionReportTests(unittest.TestCase):
    """Tests for CleanupExecutionReport."""

    def test_report_exposes_summary_counts(self) -> None:
        report = CleanupExecutionReport(
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
            created_at=NOW,
        )

        self.assertEqual(report.total, 3)
        self.assertEqual(report.planned_count, 1)
        self.assertEqual(report.skipped_count, 2)
        self.assertEqual(report.modified_count, 0)

    def test_items_for_filters_by_status(self) -> None:
        planned = make_item(
            item_id="delete-1",
            action=CleanupAction.DELETE,
        )
        skipped = make_item(
            item_id="keep-1",
            action=CleanupAction.KEEP,
        )

        report = CleanupExecutionReport(
            provider="jellyfin",
            items=(planned, skipped),
            created_at=NOW,
        )

        self.assertEqual(
            report.items_for("planned"),
            (planned,),
        )
        self.assertEqual(
            report.items_for(
                CleanupExecutionStatus.SKIPPED
            ),
            (skipped,),
        )

    def test_rejects_duplicate_item_ids(self) -> None:
        first = make_item(item_id="item-1")
        second = make_item(item_id="item-1")

        with self.assertRaisesRegex(
            CleanupError,
            "duplicate item IDs",
        ):
            CleanupExecutionReport(
                provider="jellyfin",
                items=(first, second),
                created_at=NOW,
            )

    def test_rejects_provider_mismatch(self) -> None:
        item = make_item(
            provider="emby",
            item_id="item-1",
        )

        with self.assertRaisesRegex(
            CleanupError,
            "provider does not match",
        ):
            CleanupExecutionReport(
                provider="jellyfin",
                items=(item,),
                created_at=NOW,
            )

    def test_rejects_non_tuple_items(self) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "items must be a tuple",
        ):
            CleanupExecutionReport(
                provider="jellyfin",
                items=[],
                created_at=NOW,
            )

    def test_rejects_invalid_status_filter(self) -> None:
        report = CleanupExecutionReport(
            provider="jellyfin",
            created_at=NOW,
        )

        with self.assertRaisesRegex(
            CleanupError,
            "invalid cleanup execution status",
        ):
            report.items_for("executed")

    def test_serializes_normalized_report(self) -> None:
        report = CleanupExecutionReport(
            provider=" JELLYFIN ",
            items=(
                make_item(
                    item_id="delete-1",
                    action=CleanupAction.DELETE,
                ),
                make_item(
                    item_id="keep-1",
                    action=CleanupAction.KEEP,
                ),
            ),
            created_at=NOW,
        )

        payload = report.to_dict()

        self.assertEqual(payload["provider"], "jellyfin")
        self.assertEqual(payload["mode"], "dry_run")
        self.assertEqual(
            payload["created_at"],
            "2026-07-20T12:00:00Z",
        )
        self.assertEqual(
            payload["summary"],
            {
                "total": 2,
                "planned": 1,
                "skipped": 1,
                "modified": 0,
            },
        )
        self.assertEqual(len(payload["items"]), 2)


if __name__ == "__main__":
    unittest.main()


class CleanupExecutionModeExtensionTests(unittest.TestCase):
    """Tests for supported cleanup execution modes."""

    def test_execute_mode_is_defined(self) -> None:
        self.assertEqual(
            CleanupExecutionMode.EXECUTE.value,
            "execute",
        )
