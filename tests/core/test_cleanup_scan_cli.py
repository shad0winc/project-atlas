"""Tests for the Atlas cleanup scan CLI."""

from __future__ import annotations

import io
import json
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, call, patch

from atlas.cleanup.models import CleanupError
from atlas.cleanup_cli import main
from atlas.media.provider import MediaProviderError


def _report() -> Mock:
    """Build a normalized mock cleanup scan report."""

    report = Mock()
    report.provider = "jellyfin"
    report.scanned = 2
    report.delete_count = 1
    report.keep_count = 1
    report.review_count = 0
    report.decisions = ()
    report.scanned_at = datetime(
        2026,
        7,
        20,
        12,
        0,
        tzinfo=timezone.utc,
    )
    report.to_dict.return_value = {
        "provider": "jellyfin",
        "scanned_at": "2026-07-20T12:00:00Z",
        "summary": {
            "scanned": 2,
            "delete": 1,
            "keep": 1,
            "review": 0,
        },
        "decisions": [],
    }

    return report


class CleanupScanCliTests(unittest.TestCase):
    """Validate cleanup scan CLI behavior."""

    def test_scan_human_output(self) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-1",
            "movie-2",
        )

        scanner = Mock()
        scanner.scan.return_value = _report()

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "scan",
                    "jellyfin",
                ],
                scanner=scanner,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 0)
        self.assertIn(
            "Atlas Cleanup Scan",
            stdout.getvalue(),
        )
        self.assertIn(
            "Scanned: 2",
            stdout.getvalue(),
        )
        self.assertIn(
            "Delete: 1",
            stdout.getvalue(),
        )
        self.assertIn(
            "Keep: 1",
            stdout.getvalue(),
        )

    def test_scan_json_output(self) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-1",
            "movie-2",
        )

        report = _report()
        scanner = Mock()
        scanner.scan.return_value = report

        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            result = main(
                [
                    "scan",
                    "jellyfin",
                    "--json",
                ],
                scanner=scanner,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 0)

        payload = json.loads(stdout.getvalue())

        self.assertEqual(
            payload["provider"],
            "jellyfin",
        )
        self.assertEqual(
            payload["summary"]["scanned"],
            2,
        )
        report.to_dict.assert_called_once_with()

    def test_scan_enumerates_and_forwards_items(
        self,
    ) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-1",
            "series-1",
        )

        scanner = Mock()
        scanner.scan.return_value = _report()

        result = main(
            [
                "scan",
                " JELLYFIN ",
                "--page-size",
                "50",
            ],
            scanner=scanner,
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

    def test_scan_rejects_unsupported_provider(
        self,
    ) -> None:
        provider = Mock()
        scanner = Mock()
        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "scan",
                    "plex",
                ],
                scanner=scanner,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "unsupported cleanup scan provider",
            stderr.getvalue(),
        )
        provider.list_media_item_ids.assert_not_called()
        scanner.scan.assert_not_called()

    def test_scan_reports_provider_error(self) -> None:
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
                    "scan",
                    "jellyfin",
                ],
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup scan failed: "
            "Jellyfin is unreachable",
            stderr.getvalue(),
        )

    def test_scan_reports_scanner_error(self) -> None:
        provider = Mock()
        provider.list_media_item_ids.return_value = (
            "movie-1",
        )

        scanner = Mock()
        scanner.scan.side_effect = CleanupError(
            "evaluation failed"
        )

        stderr = io.StringIO()

        with patch("sys.stderr", stderr):
            result = main(
                [
                    "scan",
                    "jellyfin",
                ],
                scanner=scanner,
                jellyfin_provider=provider,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "cleanup scan failed: evaluation failed",
            stderr.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
