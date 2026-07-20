"""Tests for the Atlas cleanup scanner."""

from __future__ import annotations

import unittest
from unittest.mock import Mock, call

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
)
from atlas.cleanup.scanner import CleanupScanner
from atlas.policies.models import (
    PolicyAction,
    PolicyDecision,
)
from atlas.retention.models import RetentionDecision


def _decision(
    item_id: str,
    *,
    provider: str = "jellyfin",
    action: CleanupAction = CleanupAction.DELETE,
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


class CleanupScannerTests(unittest.TestCase):
    """Validate provider-neutral cleanup scans."""

    def test_scan_evaluates_each_item(self) -> None:
        service = Mock()
        service.evaluate.side_effect = [
            _decision("movie-1"),
            _decision(
                "movie-2",
                action=CleanupAction.KEEP,
            ),
        ]

        scanner = CleanupScanner(service)

        report = scanner.scan(
            " JELLYFIN ",
            [
                " MOVIE-1 ",
                "MOVIE-2",
            ],
        )

        self.assertEqual(report.provider, "jellyfin")
        self.assertEqual(report.scanned, 2)
        self.assertEqual(report.delete_count, 1)
        self.assertEqual(report.keep_count, 1)
        self.assertEqual(report.review_count, 0)

        self.assertEqual(
            service.evaluate.call_args_list,
            [
                call("jellyfin", "movie-1"),
                call("jellyfin", "movie-2"),
            ],
        )

    def test_empty_scan_returns_empty_report(self) -> None:
        service = Mock()
        scanner = CleanupScanner(service)

        report = scanner.scan(
            "jellyfin",
            (),
        )

        self.assertEqual(report.scanned, 0)
        self.assertEqual(report.decisions, ())
        service.evaluate.assert_not_called()

    def test_scan_preserves_decision_order(self) -> None:
        first = _decision("movie-1")
        second = _decision("movie-2")

        service = Mock()
        service.evaluate.side_effect = [
            first,
            second,
        ]

        report = CleanupScanner(service).scan(
            "jellyfin",
            ("movie-1", "movie-2"),
        )

        self.assertEqual(
            report.decisions,
            (first, second),
        )

    def test_scan_accepts_generators(self) -> None:
        service = Mock()
        service.evaluate.side_effect = [
            _decision("movie-1"),
            _decision("movie-2"),
        ]

        item_ids = (
            item_id
            for item_id in ("movie-1", "movie-2")
        )

        report = CleanupScanner(service).scan(
            "jellyfin",
            item_ids,
        )

        self.assertEqual(report.scanned, 2)

    def test_scan_rejects_invalid_provider(self) -> None:
        scanner = CleanupScanner(Mock())

        with self.assertRaises(CleanupError):
            scanner.scan("", ())

        with self.assertRaises(CleanupError):
            scanner.scan(None, ())  # type: ignore[arg-type]

    def test_scan_rejects_noniterable_item_ids(self) -> None:
        scanner = CleanupScanner(Mock())

        with self.assertRaises(CleanupError):
            scanner.scan(
                "jellyfin",
                None,  # type: ignore[arg-type]
            )

    def test_scan_rejects_invalid_item_ids(self) -> None:
        scanner = CleanupScanner(Mock())

        with self.assertRaises(CleanupError):
            scanner.scan(
                "jellyfin",
                ("movie-1", ""),
            )

        with self.assertRaises(CleanupError):
            scanner.scan(
                "jellyfin",
                ("movie-1", 123),  # type: ignore[arg-type]
            )

    def test_scan_rejects_duplicate_item_ids(self) -> None:
        scanner = CleanupScanner(Mock())

        with self.assertRaises(CleanupError):
            scanner.scan(
                "jellyfin",
                ("movie-1", " MOVIE-1 "),
            )

    def test_service_error_is_propagated(self) -> None:
        service = Mock()
        service.evaluate.side_effect = CleanupError(
            "evaluation failed"
        )

        scanner = CleanupScanner(service)

        with self.assertRaisesRegex(
            CleanupError,
            "evaluation failed",
        ):
            scanner.scan(
                "jellyfin",
                ("movie-1",),
            )


if __name__ == "__main__":
    unittest.main()
