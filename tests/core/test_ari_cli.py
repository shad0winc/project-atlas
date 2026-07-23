"""Tests for the Atlas ARI analytics CLI."""

from __future__ import annotations

import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from atlas.ari.analytics import (
    ARIAnalyticsError,
    ARIHistory,
    CapacityForecast,
    SnapshotLoadFailure,
    StorageChange,
    StorageInterval,
)
from atlas.ari_cli import (
    default_service,
    main,
)


def _report(
    timestamp: str = "2026-07-22T12:00:00Z",
) -> Mock:
    report = Mock()
    report.timestamp = timestamp
    report.atlas = SimpleNamespace(
        version="0.9.0",
        hostname="atlas",
        schema_version=1,
    )
    report.storage = SimpleNamespace(
        media_root="/mnt/storage/media",
        capacity="1.8T",
        capacity_bytes=2_000_000_000_000,
        used="1.0G",
        used_bytes=1_000_000_000,
        available="1.8T",
        available_bytes=1_999_000_000_000,
        utilization_percent=1,
    )
    report.jellyfin = SimpleNamespace(
        server_name="Atlas",
        version="10.10.7",
        counts=SimpleNamespace(
            total_items=12,
        ),
    )
    report.to_dict.return_value = {
        "timestamp": timestamp,
        "atlas": {
            "version": "0.9.0",
            "hostname": "atlas",
            "schema_version": 1,
        },
    }
    return report


def _history() -> ARIHistory:
    return ARIHistory(
        reports=(
            _report("2026-07-20T12:00:00Z"),
            _report("2026-07-22T12:00:00Z"),
        ),
        skipped=(
            SnapshotLoadFailure(
                path=Path("/tmp/legacy.json"),
                error="unsupported schema",
            ),
        ),
    )


def _change() -> StorageChange:
    return StorageChange(
        start_timestamp="2026-07-20T12:00:00Z",
        end_timestamp="2026-07-22T12:00:00Z",
        start_used_bytes=1_000,
        end_used_bytes=3_000,
        change_bytes=2_000,
        elapsed_seconds=172_800,
    )


def _intervals() -> tuple[StorageInterval, ...]:
    return (
        StorageInterval(
            start_timestamp="2026-07-20T12:00:00Z",
            end_timestamp="2026-07-21T12:00:00Z",
            start_used_bytes=1_000,
            end_used_bytes=2_500,
            change_bytes=1_500,
            elapsed_seconds=86_400,
        ),
        StorageInterval(
            start_timestamp="2026-07-21T12:00:00Z",
            end_timestamp="2026-07-22T12:00:00Z",
            start_used_bytes=2_500,
            end_used_bytes=3_000,
            change_bytes=500,
            elapsed_seconds=86_400,
        ),
    )


def _forecast() -> CapacityForecast:
    return CapacityForecast(
        as_of_timestamp="2026-07-22T12:00:00Z",
        capacity_bytes=10_000,
        used_bytes=3_000,
        available_bytes=7_000,
        positive_interval_count=2,
        average_growth_bytes_per_day=1_000.0,
        days_until_full=7.0,
        estimated_full_timestamp=(
            "2026-07-29T12:00:00+00:00"
        ),
    )


class ARICliTests(unittest.TestCase):
    """Validate ARI analytics command behavior."""

    def test_default_service_uses_environment_directory(
        self,
    ) -> None:
        with patch.dict(
            os.environ,
            {
                "ATLAS_ARI_DIR": "/tmp/custom-ari",
            },
        ):
            service = default_service()

        self.assertEqual(
            service.snapshot_directory,
            Path("/tmp/custom-ari"),
        )

    def test_latest_human_output(self) -> None:
        service = Mock()
        service.latest.return_value = _report()
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                ["latest"],
                service=service,
                analytics=Mock(),
            )

        rendered = output.getvalue()

        self.assertEqual(result, 0)
        self.assertIn(
            "Atlas ARI Latest",
            rendered,
        )
        self.assertIn(
            "Timestamp: 2026-07-22T12:00:00Z",
            rendered,
        )
        self.assertIn(
            "Jellyfin items: 12",
            rendered,
        )

    def test_latest_json_output(self) -> None:
        service = Mock()
        service.latest.return_value = _report()
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                ["latest", "--json"],
                service=service,
                analytics=Mock(),
            )

        payload = json.loads(
            output.getvalue()
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            payload["timestamp"],
            "2026-07-22T12:00:00Z",
        )

    def test_history_human_output(self) -> None:
        analytics = Mock()
        analytics.load_history.return_value = (
            _history()
        )
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                ["history"],
                service=Mock(),
                analytics=analytics,
            )

        rendered = output.getvalue()

        self.assertEqual(result, 0)
        self.assertIn(
            "Valid reports: 2",
            rendered,
        )
        self.assertIn(
            "Skipped snapshots: 1",
            rendered,
        )
        self.assertIn(
            "/tmp/legacy.json",
            rendered,
        )

    def test_history_json_output(self) -> None:
        analytics = Mock()
        analytics.load_history.return_value = (
            _history()
        )
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                ["history", "--json"],
                service=Mock(),
                analytics=analytics,
            )

        payload = json.loads(
            output.getvalue()
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            payload["loaded_count"],
            2,
        )
        self.assertEqual(
            payload["skipped_count"],
            1,
        )
        self.assertEqual(
            payload["skipped"][0]["path"],
            "/tmp/legacy.json",
        )
        self.assertEqual(
            len(payload["reports"]),
            2,
        )

    def test_growth_human_output(self) -> None:
        analytics = Mock()
        analytics.load_history.return_value = (
            _history()
        )
        analytics.storage_change.return_value = (
            _change()
        )
        analytics.storage_intervals.return_value = (
            _intervals()
        )
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                ["growth"],
                service=Mock(),
                analytics=analytics,
            )

        rendered = output.getvalue()

        self.assertEqual(result, 0)
        self.assertIn(
            "Atlas ARI Growth",
            rendered,
        )
        self.assertIn(
            "Intervals: 2",
            rendered,
        )
        self.assertIn(
            "Growth intervals: 2",
            rendered,
        )
        self.assertIn(
            "Average change:",
            rendered,
        )

    def test_growth_json_output(self) -> None:
        analytics = Mock()
        analytics.load_history.return_value = (
            _history()
        )
        analytics.storage_change.return_value = (
            _change()
        )
        analytics.storage_intervals.return_value = (
            _intervals()
        )
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                ["growth", "--json"],
                service=Mock(),
                analytics=analytics,
            )

        payload = json.loads(
            output.getvalue()
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            payload["change"]["change_bytes"],
            2_000,
        )
        self.assertEqual(
            len(payload["intervals"]),
            2,
        )
        self.assertTrue(
            payload["intervals"][0]["is_growth"]
        )

    def test_forecast_human_output(self) -> None:
        analytics = Mock()
        analytics.load_history.return_value = (
            _history()
        )
        analytics.capacity_forecast.return_value = (
            _forecast()
        )
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                ["forecast"],
                service=Mock(),
                analytics=analytics,
            )

        rendered = output.getvalue()

        self.assertEqual(result, 0)
        self.assertIn(
            "Atlas ARI Forecast",
            rendered,
        )
        self.assertIn(
            "Positive growth intervals: 2",
            rendered,
        )
        self.assertIn(
            "Runway: 7.00 days",
            rendered,
        )

    def test_forecast_json_output(self) -> None:
        analytics = Mock()
        analytics.load_history.return_value = (
            _history()
        )
        analytics.capacity_forecast.return_value = (
            _forecast()
        )
        output = StringIO()

        with redirect_stdout(output):
            result = main(
                ["forecast", "--json"],
                service=Mock(),
                analytics=analytics,
            )

        payload = json.loads(
            output.getvalue()
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            payload["forecast"]["days_until_full"],
            7.0,
        )
        self.assertEqual(
            payload["history"]["skipped_count"],
            1,
        )

    def test_analytics_error_returns_nonzero(
        self,
    ) -> None:
        analytics = Mock()
        analytics.load_history.return_value = (
            _history()
        )
        analytics.capacity_forecast.side_effect = (
            ARIAnalyticsError(
                "insufficient growth history"
            )
        )
        error_output = StringIO()

        with redirect_stderr(error_output):
            result = main(
                ["forecast"],
                service=Mock(),
                analytics=analytics,
            )

        self.assertEqual(result, 1)
        self.assertIn(
            "ARI forecast failed",
            error_output.getvalue(),
        )
        self.assertIn(
            "insufficient growth history",
            error_output.getvalue(),
        )


if __name__ == "__main__":
    unittest.main()
