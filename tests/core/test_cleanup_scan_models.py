"""Tests for Atlas cleanup scan models."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
)
from atlas.cleanup.scan_models import CleanupScanReport
from atlas.policies.models import (
    PolicyAction,
    PolicyDecision,
)
from atlas.retention.models import RetentionDecision


def _decision(
    item_id: str,
    action: CleanupAction,
    *,
    provider: str = "jellyfin",
) -> CleanupDecision:
    protected = action is CleanupAction.KEEP

    policy = PolicyDecision(
        provider=provider,
        item_id=item_id,
        action=(
            PolicyAction.PROTECT
            if protected
            else PolicyAction.IGNORE
        ),
    )

    retention = RetentionDecision(
        provider=provider,
        item_id=item_id,
        eligible=not protected,
        policy=policy,
    )

    return CleanupDecision(
        provider=provider,
        item_id=item_id,
        action=action,
        retention=retention,
    )


class CleanupScanReportTests(unittest.TestCase):
    """Validate normalized cleanup scan reports."""

    def test_report_exposes_summary_counts(self) -> None:
        report = CleanupScanReport(
            provider=" JELLYFIN ",
            decisions=(
                _decision("movie-1", CleanupAction.DELETE),
                _decision("movie-2", CleanupAction.DELETE),
                _decision("movie-3", CleanupAction.KEEP),
                _decision("movie-4", CleanupAction.REVIEW),
            ),
        )

        self.assertEqual(report.provider, "jellyfin")
        self.assertEqual(report.scanned, 4)
        self.assertEqual(report.delete_count, 2)
        self.assertEqual(report.keep_count, 1)
        self.assertEqual(report.review_count, 1)

    def test_decisions_for_filters_by_action(self) -> None:
        delete = _decision(
            "movie-1",
            CleanupAction.DELETE,
        )
        keep = _decision(
            "movie-2",
            CleanupAction.KEEP,
        )

        report = CleanupScanReport(
            provider="jellyfin",
            decisions=(delete, keep),
        )

        self.assertEqual(
            report.decisions_for("delete"),
            (delete,),
        )
        self.assertEqual(
            report.decisions_for(CleanupAction.KEEP),
            (keep,),
        )

    def test_serializes_normalized_contract(self) -> None:
        report = CleanupScanReport(
            provider="jellyfin",
            decisions=(
                _decision("movie-1", CleanupAction.DELETE),
            ),
            scanned_at=datetime(
                2026,
                7,
                20,
                12,
                0,
                tzinfo=timezone.utc,
            ),
        )

        payload = report.to_dict()

        self.assertEqual(payload["provider"], "jellyfin")
        self.assertEqual(
            payload["scanned_at"],
            "2026-07-20T12:00:00Z",
        )
        self.assertEqual(
            payload["summary"],
            {
                "scanned": 1,
                "delete": 1,
                "keep": 0,
                "review": 0,
            },
        )
        self.assertEqual(
            payload["decisions"][0]["item_id"],
            "movie-1",
        )

    def test_rejects_invalid_decision_collection(self) -> None:
        with self.assertRaises(CleanupError):
            CleanupScanReport(
                provider="jellyfin",
                decisions=[],
            )

        with self.assertRaises(CleanupError):
            CleanupScanReport(
                provider="jellyfin",
                decisions=("invalid",),
            )

    def test_rejects_provider_mismatch(self) -> None:
        decision = _decision(
            "movie-1",
            CleanupAction.DELETE,
            provider="emby",
        )

        with self.assertRaises(CleanupError):
            CleanupScanReport(
                provider="jellyfin",
                decisions=(decision,),
            )

    def test_rejects_duplicate_item_ids(self) -> None:
        with self.assertRaises(CleanupError):
            CleanupScanReport(
                provider="jellyfin",
                decisions=(
                    _decision(
                        "movie-1",
                        CleanupAction.DELETE,
                    ),
                    _decision(
                        "movie-1",
                        CleanupAction.KEEP,
                    ),
                ),
            )

    def test_rejects_invalid_action_filter(self) -> None:
        report = CleanupScanReport(
            provider="jellyfin",
        )

        with self.assertRaises(CleanupError):
            report.decisions_for("archive")

    def test_rejects_invalid_timestamp(self) -> None:
        with self.assertRaises(CleanupError):
            CleanupScanReport(
                provider="jellyfin",
                scanned_at=datetime(2026, 7, 20, 12, 0),
            )


if __name__ == "__main__":
    unittest.main()
