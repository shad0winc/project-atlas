"""Tests for the Atlas cleanup execution CLI."""

from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, call, patch

from atlas.cleanup.models import CleanupError
from atlas.cleanup_cli import main
from atlas.media.provider import MediaProviderError


NOW = datetime(
    2026,
    7,
    20,
    12,
    0,
    tzinfo=timezone.utc,
)


def _scan_report() -> Mock:
    """Build a mock cleanup scan report."""

    report = Mock()
    report.provider = "jellyfin"
    return report


def _execution_item(
    item_id: str,
    status: str,
) -> Mock:
    """Build a mock execution item."""

    item = Mock()
    item.item_id = item_id
    item.status.value = status
    return item


def _execution_report() -> Mock:
    """Build a normalized mock execution report."""

    report = Mock()
    report.provider = "jellyfin"
    report.mode.value = "dry_run"
    report.total = 3
    report.planned_count = 1
    report.skipped_count = 2
    report.modified_count = 0
    report.items = (
        _execution_item(
            "movie-delete",
            "planned",
        ),
        _execution_item(
            "movie-keep",
            "skipped",
        ),
        _execution_item(
            "movie-review",
            "skipped",
        ),
    )
    report.created_at = NOW
    report.to_dict.return_value = {
        "provider": "jellyfin",
        "mode": "dry_run",
        "created_at": "2026-07-20T12:00:00Z",
        "summary": {
            "total": 3,
            "planned": 1,
            "skipped": 2,
            "modified": 0,
        },
        "items": [],
    }

    return report


class CleanupExecutionCliTests(unittest.TestCase):
    """Validate cleanup execution CLI behavior."""

    def test_execute_human_output(self) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-delete",
            "movie-keep",
            "movie-review",
        )

        scan_report = _scan_report()

        scanner = Mock()
        scanner.scan.return_value = scan_report

        execution_service = Mock()
        execution_service.plan.return_value = (
            _execution_report()
        )

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "execute",
                    "jellyfin",
                    "--dry-run",
                ],
                scanner=scanner,
                execution_service=execution_service,
                jellyfin_provider=provider,
            )

        output = stdout.getvalue()

        self.assertEqual(result, 0)
        self.assertIn(
            "Atlas Cleanup Execution",
            output,
        )
        self.assertIn(
            "Mode: dry_run",
            output,
        )
        self.assertIn(
            "Total: 3",
            output,
        )
        self.assertIn(
            "Planned: 1",
            output,
        )
        self.assertIn(
            "Skipped: 2",
            output,
        )
        self.assertIn(
            "Modified: 0",
            output,
        )
        self.assertIn(
            "movie-delete",
            output,
        )
        self.assertNotIn(
            "movie-keep",
            output,
        )

    def test_execute_json_output(self) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-1",
        )

        scanner = Mock()
        scanner.scan.return_value = _scan_report()

        report = _execution_report()
        execution_service = Mock()
        execution_service.plan.return_value = report

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "execute",
                    "jellyfin",
                    "--json",
                ],
                scanner=scanner,
                execution_service=execution_service,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 0)

        payload = json.loads(stdout.getvalue())

        self.assertEqual(
            payload["provider"],
            "jellyfin",
        )
        self.assertEqual(
            payload["mode"],
            "dry_run",
        )
        self.assertEqual(
            payload["summary"]["planned"],
            1,
        )
        report.to_dict.assert_called_once_with()

    def test_execute_enumerates_and_forwards_scan(
        self,
    ) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-1",
            "series-1",
        )

        scan_report = _scan_report()

        scanner = Mock()
        scanner.scan.return_value = scan_report

        execution_service = Mock()
        execution_service.plan.return_value = (
            _execution_report()
        )

        result = main(
            [
                "execute",
                " JELLYFIN ",
                "--page-size",
                "50",
            ],
            scanner=scanner,
            execution_service=execution_service,
            jellyfin_provider=provider,
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            provider.list_media_item_ids.call_args_list,
            [
                call(page_size=50),
            ],
        )
        scanner.scan.assert_called_once_with(
            "jellyfin",
            (
                "movie-1",
                "series-1",
            ),
        )
        execution_service.plan.assert_called_once_with(
            scan_report,
            mode="dry_run",
        )

    def test_execute_rejects_unsupported_provider(
        self,
    ) -> None:
        provider = Mock()
        scanner = Mock()
        execution_service = Mock()
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "execute",
                    "plex",
                ],
                scanner=scanner,
                execution_service=execution_service,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "unsupported cleanup execution provider",
            stderr.getvalue(),
        )
        provider.list_media_item_ids.assert_not_called()
        scanner.scan.assert_not_called()
        execution_service.plan.assert_not_called()

    def test_execute_reports_provider_error(
        self,
    ) -> None:
        provider = Mock()
        provider.list_media_item_ids.side_effect = (
            MediaProviderError(
                "Jellyfin is unreachable"
            )
        )

        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "execute",
                    "jellyfin",
                ],
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup execution failed: "
            "Jellyfin is unreachable",
            stderr.getvalue(),
        )

    def test_execute_reports_scanner_error(
        self,
    ) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-1",
        )

        scanner = Mock()
        scanner.scan.side_effect = CleanupError(
            "scan failed"
        )

        execution_service = Mock()
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "execute",
                    "jellyfin",
                ],
                scanner=scanner,
                execution_service=execution_service,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup execution failed: scan failed",
            stderr.getvalue(),
        )
        execution_service.plan.assert_not_called()

    def test_execute_reports_planner_error(
        self,
    ) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-1",
        )

        scanner = Mock()
        scanner.scan.return_value = _scan_report()

        execution_service = Mock()
        execution_service.plan.side_effect = CleanupError(
            "planning failed"
        )

        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "execute",
                    "jellyfin",
                ],
                scanner=scanner,
                execution_service=execution_service,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup execution failed: planning failed",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
