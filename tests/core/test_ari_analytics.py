"""Tests for ARI historical analytics."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas.ari import (
    ARIAnalytics,
    ARIAnalyticsError,
    ARIService,
    StorageChange,
)


def sample_snapshot(
    timestamp: str,
    used_bytes: int,
) -> dict:
    """Return a valid ARI snapshot payload."""

    capacity_bytes = 2_000_000_000_000
    available_bytes = (
        capacity_bytes
        - used_bytes
    )

    return {
        "timestamp": timestamp,
        "atlas": {
            "version": "0.9.0-rc.1",
            "hostname": "docker",
            "schema_version": 1,
        },
        "storage": {
            "media_root": "/mnt/storage/media",
            "capacity": "2T",
            "capacity_bytes": capacity_bytes,
            "used": str(used_bytes),
            "used_bytes": used_bytes,
            "available": str(available_bytes),
            "available_bytes": available_bytes,
            "utilization_percent": 1,
        },
        "jellyfin": {
            "server_name": "Atlas",
            "version": "10.10.7",
            "id": "server",
            "libraries": [],
            "users": [],
            "counts": {
                "movies": 0,
                "series": 0,
                "episodes": 0,
                "songs": 0,
                "albums": 0,
                "books": 0,
                "total_items": 0,
            },
        },
        "libraries": {
            "movies": {
                "count": 0,
            },
            "tv": {
                "count": 0,
            },
            "anime_movies": {
                "count": 0,
            },
            "anime_tv": {
                "count": 0,
            },
        },
    }


def write_snapshot(
    path: Path,
    timestamp: str,
    used_bytes: int,
) -> None:
    """Write a valid ARI snapshot."""

    path.write_text(
        json.dumps(
            sample_snapshot(
                timestamp,
                used_bytes,
            ),
        ),
        encoding="utf-8",
    )


class ARIAnalyticsTests(unittest.TestCase):
    """Validate historical ARI calculations."""

    def test_history_returns_reports_in_chronological_order(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            write_snapshot(
                history / "later.json",
                "2026-07-22T12:00:00Z",
                300,
            )
            write_snapshot(
                history / "earlier.json",
                "2026-07-20T12:00:00Z",
                100,
            )

            reports = ARIAnalytics(
                ARIService(directory),
            ).history()

            self.assertEqual(
                [
                    "2026-07-20T12:00:00Z",
                    "2026-07-22T12:00:00Z",
                ],
                [
                    report.timestamp
                    for report in reports
                ],
            )

    def test_history_deduplicates_latest_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            timestamp = "2026-07-22T12:00:00Z"

            write_snapshot(
                directory / "latest.json",
                timestamp,
                300,
            )
            write_snapshot(
                history / "historical.json",
                timestamp,
                300,
            )

            reports = ARIAnalytics(
                ARIService(directory),
            ).history()

            self.assertEqual(
                1,
                len(reports),
            )

    def test_history_returns_empty_without_snapshots(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            reports = ARIAnalytics(
                ARIService(temporary),
            ).history()

            self.assertEqual(
                (),
                reports,
            )

    def test_storage_change_calculates_growth(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            write_snapshot(
                history / "first.json",
                "2026-07-20T12:00:00Z",
                100,
            )
            write_snapshot(
                history / "last.json",
                "2026-07-22T12:00:00Z",
                500,
            )

            change = ARIAnalytics(
                ARIService(directory),
            ).storage_change()

            self.assertIsInstance(
                change,
                StorageChange,
            )
            self.assertEqual(
                400,
                change.change_bytes,
            )
            self.assertEqual(
                2.0,
                change.elapsed_days,
            )
            self.assertEqual(
                200.0,
                change.average_bytes_per_day,
            )

    def test_storage_change_supports_reduced_usage(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            write_snapshot(
                history / "first.json",
                "2026-07-20T12:00:00Z",
                500,
            )
            write_snapshot(
                history / "last.json",
                "2026-07-21T12:00:00Z",
                300,
            )

            change = ARIAnalytics(
                ARIService(directory),
            ).storage_change()

            self.assertEqual(
                -200,
                change.change_bytes,
            )
            self.assertEqual(
                -200.0,
                change.average_bytes_per_day,
            )

    def test_storage_change_requires_two_unique_reports(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)

            write_snapshot(
                directory / "latest.json",
                "2026-07-22T12:00:00Z",
                300,
            )

            with self.assertRaisesRegex(
                ARIAnalyticsError,
                "at least two unique valid ARI reports",
            ):
                ARIAnalytics(
                    ARIService(directory),
                ).storage_change()

    def test_load_history_skips_invalid_snapshots(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            write_snapshot(
                directory / "latest.json",
                "2026-07-22T12:00:00Z",
                300,
            )
            (history / "legacy.json").write_text(
                json.dumps(
                    {
                        "timestamp": "2026-07-05T12:00:00Z",
                        "atlas": "legacy",
                    },
                ),
                encoding="utf-8",
            )

            result = ARIAnalytics(
                ARIService(directory),
            ).load_history()

            self.assertEqual(
                1,
                result.loaded_count,
            )
            self.assertEqual(
                1,
                result.skipped_count,
            )
            self.assertEqual(
                history / "legacy.json",
                result.skipped[0].path,
            )
            self.assertIn(
                "atlas must be an object",
                result.skipped[0].error,
            )

    def test_history_returns_only_valid_reports(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            write_snapshot(
                history / "first.json",
                "2026-07-20T12:00:00Z",
                100,
            )
            write_snapshot(
                history / "second.json",
                "2026-07-21T12:00:00Z",
                200,
            )
            (history / "invalid.json").write_text(
                "not-json",
                encoding="utf-8",
            )

            reports = ARIAnalytics(
                ARIService(directory),
            ).history()

            self.assertEqual(
                2,
                len(reports),
            )

    def test_storage_intervals_returns_point_to_point_changes(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            write_snapshot(
                history / "first.json",
                "2026-07-20T12:00:00Z",
                100,
            )
            write_snapshot(
                history / "second.json",
                "2026-07-21T12:00:00Z",
                250,
            )
            write_snapshot(
                history / "third.json",
                "2026-07-22T12:00:00Z",
                200,
            )

            intervals = ARIAnalytics(
                ARIService(directory),
            ).storage_intervals()

            self.assertEqual(
                2,
                len(intervals),
            )
            self.assertEqual(
                150,
                intervals[0].change_bytes,
            )
            self.assertEqual(
                -50,
                intervals[1].change_bytes,
            )
            self.assertTrue(
                intervals[0].is_growth,
            )
            self.assertFalse(
                intervals[1].is_growth,
            )
            self.assertEqual(
                150.0,
                intervals[0].bytes_per_day,
            )

    def test_storage_intervals_returns_empty_for_one_report(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)

            write_snapshot(
                directory / "latest.json",
                "2026-07-22T12:00:00Z",
                100,
            )

            intervals = ARIAnalytics(
                ARIService(directory),
            ).storage_intervals()

            self.assertEqual(
                (),
                intervals,
            )

    def test_capacity_forecast_uses_only_positive_growth(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            snapshots = (
                (
                    "first.json",
                    "2026-07-20T12:00:00Z",
                    100,
                ),
                (
                    "second.json",
                    "2026-07-21T12:00:00Z",
                    200,
                ),
                (
                    "third.json",
                    "2026-07-22T12:00:00Z",
                    150,
                ),
                (
                    "fourth.json",
                    "2026-07-23T12:00:00Z",
                    250,
                ),
            )

            for name, timestamp, used_bytes in snapshots:
                payload = sample_snapshot(
                    timestamp,
                    used_bytes,
                )
                payload["storage"]["capacity"] = "1000"
                payload["storage"]["capacity_bytes"] = 1000
                payload["storage"]["available"] = str(
                    1000 - used_bytes,
                )
                payload["storage"]["available_bytes"] = (
                    1000 - used_bytes
                )

                (history / name).write_text(
                    json.dumps(payload),
                    encoding="utf-8",
                )

            forecast = ARIAnalytics(
                ARIService(directory),
            ).capacity_forecast()

            self.assertEqual(
                2,
                forecast.positive_interval_count,
            )
            self.assertEqual(
                100.0,
                forecast.average_growth_bytes_per_day,
            )
            self.assertEqual(
                750,
                forecast.available_bytes,
            )
            self.assertEqual(
                7.5,
                forecast.days_until_full,
            )
            self.assertEqual(
                "2026-07-31T00:00:00+00:00",
                forecast.estimated_full_timestamp,
            )

    def test_capacity_forecast_rejects_no_positive_growth(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            write_snapshot(
                history / "first.json",
                "2026-07-20T12:00:00Z",
                200,
            )
            write_snapshot(
                history / "second.json",
                "2026-07-21T12:00:00Z",
                150,
            )

            analytics = ARIAnalytics(
                ARIService(directory),
            )

            with self.assertRaisesRegex(
                ARIAnalyticsError,
                "at least one positive storage-growth interval",
            ):
                analytics.capacity_forecast()

    def test_capacity_forecast_requires_two_reports(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)

            write_snapshot(
                directory / "latest.json",
                "2026-07-22T12:00:00Z",
                100,
            )

            analytics = ARIAnalytics(
                ARIService(directory),
            )

            with self.assertRaisesRegex(
                ARIAnalyticsError,
                "at least two unique valid ARI reports",
            ):
                analytics.capacity_forecast()

    def test_capacity_forecast_is_immediate_when_full(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            first = sample_snapshot(
                "2026-07-20T12:00:00Z",
                900,
            )
            second = sample_snapshot(
                "2026-07-21T12:00:00Z",
                1000,
            )

            for payload in (first, second):
                payload["storage"]["capacity"] = "1000"
                payload["storage"]["capacity_bytes"] = 1000
                payload["storage"]["available"] = "0"
                payload["storage"]["available_bytes"] = 0

            (history / "first.json").write_text(
                json.dumps(first),
                encoding="utf-8",
            )
            (history / "second.json").write_text(
                json.dumps(second),
                encoding="utf-8",
            )

            forecast = ARIAnalytics(
                ARIService(directory),
            ).capacity_forecast()

            self.assertEqual(
                0,
                forecast.available_bytes,
            )
            self.assertEqual(
                0.0,
                forecast.days_until_full,
            )
            self.assertEqual(
                "2026-07-21T12:00:00+00:00",
                forecast.estimated_full_timestamp,
            )


if __name__ == "__main__":
    unittest.main()
