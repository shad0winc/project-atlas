"""Tests for Atlas analytics timelines."""

from __future__ import annotations

import unittest

from atlas.analytics import (
    ARISnapshot,
    AnalyticsTimeline,
    AnalyticsTimelineBuilder,
    AnalyticsTimelineError,
    StorageSummary,
    TimelineGap,
)


def _storage(
    *,
    total_bytes: int = 10_000,
    used_bytes: int = 4_000,
    free_bytes: int = 5_500,
) -> StorageSummary:
    return StorageSummary(
        total_bytes=total_bytes,
        used_bytes=used_bytes,
        free_bytes=free_bytes,
        utilization_percent=(
            used_bytes / total_bytes * 100
            if total_bytes
            else 0
        ),
    )


def _snapshot(
    timestamp: str,
    *,
    schema_version: int = 1,
    movies: int = 0,
    used_bytes: int = 4_000,
) -> ARISnapshot:
    return ARISnapshot(
        timestamp=timestamp,
        schema_version=schema_version,
        storage=_storage(
            used_bytes=used_bytes,
            free_bytes=10_000 - used_bytes - 500,
        ),
        library_counts=(
            ("movies", movies),
            ("tv", 0),
        ),
    )


class TimelineGapTests(unittest.TestCase):
    """Verify timeline gap contracts."""

    def test_gap_calculates_excess_seconds(self) -> None:
        gap = TimelineGap(
            previous_timestamp="2026-07-24T08:00:00Z",
            current_timestamp="2026-07-26T08:00:00Z",
            interval_seconds=172_800,
            expected_interval_seconds=86_400,
        )

        self.assertEqual(gap.excess_seconds, 86_400.0)

    def test_gap_serializes_stable_contract(self) -> None:
        gap = TimelineGap(
            previous_timestamp="2026-07-24T08:00:00Z",
            current_timestamp="2026-07-26T08:00:00Z",
            interval_seconds=172_800,
            expected_interval_seconds=86_400,
        )

        self.assertEqual(
            gap.to_dict(),
            {
                "previous_timestamp": (
                    "2026-07-24T08:00:00Z"
                ),
                "current_timestamp": (
                    "2026-07-26T08:00:00Z"
                ),
                "interval_seconds": 172_800.0,
                "expected_interval_seconds": 86_400.0,
                "excess_seconds": 86_400.0,
            },
        )

    def test_gap_rejects_reversed_timestamps(self) -> None:
        with self.assertRaisesRegex(
            AnalyticsTimelineError,
            "must follow",
        ):
            TimelineGap(
                previous_timestamp="2026-07-26T08:00:00Z",
                current_timestamp="2026-07-25T08:00:00Z",
                interval_seconds=86_400,
                expected_interval_seconds=86_400,
            )


class AnalyticsTimelineBuilderTests(unittest.TestCase):
    """Verify timeline construction and normalization."""

    def setUp(self) -> None:
        self.builder = AnalyticsTimelineBuilder()

    def test_build_returns_timeline(self) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-25T08:00:00Z"),
                _snapshot("2026-07-26T08:00:00Z"),
            )
        )

        self.assertIsInstance(
            result,
            AnalyticsTimeline,
        )

    def test_build_orders_snapshots_chronologically(self) -> None:
        newest = _snapshot(
            "2026-07-26T08:00:00Z",
            movies=20,
        )
        oldest = _snapshot(
            "2026-07-24T08:00:00Z",
            movies=10,
        )
        middle = _snapshot(
            "2026-07-25T08:00:00Z",
            movies=15,
        )

        result = self.builder.build(
            (newest, oldest, middle)
        )

        self.assertEqual(result.first, oldest)
        self.assertEqual(result.previous, middle)
        self.assertEqual(result.latest, newest)

    def test_timeline_exposes_snapshot_count(self) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-24T08:00:00Z"),
                _snapshot("2026-07-25T08:00:00Z"),
                _snapshot("2026-07-26T08:00:00Z"),
            )
        )

        self.assertEqual(result.snapshot_count, 3)

    def test_timeline_exposes_duration(self) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-24T08:00:00Z"),
                _snapshot("2026-07-26T08:00:00Z"),
            )
        )

        self.assertEqual(
            result.duration_seconds,
            172_800.0,
        )

    def test_timeline_exposes_intervals(self) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-24T08:00:00Z"),
                _snapshot("2026-07-25T08:00:00Z"),
                _snapshot("2026-07-26T08:00:00Z"),
            )
        )

        self.assertEqual(
            result.interval_seconds,
            (86_400.0, 86_400.0),
        )
        self.assertEqual(
            result.median_interval_seconds,
            86_400.0,
        )

    def test_builder_derives_expected_interval_from_median(
        self,
    ) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-23T08:00:00Z"),
                _snapshot("2026-07-24T08:00:00Z"),
                _snapshot("2026-07-25T08:00:00Z"),
                _snapshot("2026-07-27T08:00:00Z"),
            )
        )

        self.assertEqual(
            result.expected_interval_seconds,
            86_400.0,
        )

    def test_builder_accepts_explicit_expected_interval(
        self,
    ) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-24T08:00:00Z"),
                _snapshot("2026-07-26T08:00:00Z"),
            ),
            expected_interval_seconds=43_200,
        )

        self.assertEqual(
            result.expected_interval_seconds,
            43_200.0,
        )

    def test_builder_detects_large_gap(self) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-23T08:00:00Z"),
                _snapshot("2026-07-24T08:00:00Z"),
                _snapshot("2026-07-25T08:00:00Z"),
                _snapshot("2026-07-28T08:00:00Z"),
            ),
            expected_interval_seconds=86_400,
        )

        self.assertTrue(result.has_gaps)
        self.assertEqual(len(result.gaps), 1)
        self.assertEqual(
            result.gaps[0].interval_seconds,
            259_200.0,
        )

    def test_builder_does_not_mark_normal_interval_as_gap(
        self,
    ) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-24T08:00:00Z"),
                _snapshot("2026-07-25T08:00:00Z"),
                _snapshot("2026-07-26T08:00:00Z"),
            ),
            expected_interval_seconds=86_400,
        )

        self.assertFalse(result.has_gaps)
        self.assertEqual(result.gaps, ())

    def test_builder_uses_configurable_gap_multiplier(
        self,
    ) -> None:
        result = self.builder.build(
            (
                _snapshot("2026-07-24T08:00:00Z"),
                _snapshot("2026-07-25T12:00:00Z"),
            ),
            expected_interval_seconds=86_400,
            gap_multiplier=1.1,
        )

        self.assertTrue(result.has_gaps)

    def test_builder_rejects_duplicate_timestamps(self) -> None:
        with self.assertRaisesRegex(
            AnalyticsTimelineError,
            "unique timestamps",
        ):
            self.builder.build(
                (
                    _snapshot("2026-07-25T08:00:00Z"),
                    _snapshot("2026-07-25T04:00:00-04:00"),
                )
            )

    def test_builder_rejects_mixed_schema_versions(self) -> None:
        with self.assertRaisesRegex(
            AnalyticsTimelineError,
            "same schema_version",
        ):
            self.builder.build(
                (
                    _snapshot(
                        "2026-07-25T08:00:00Z",
                        schema_version=1,
                    ),
                    _snapshot(
                        "2026-07-26T08:00:00Z",
                        schema_version=2,
                    ),
                )
            )

    def test_builder_rejects_one_snapshot(self) -> None:
        with self.assertRaisesRegex(
            AnalyticsTimelineError,
            "At least two",
        ):
            self.builder.build(
                (
                    _snapshot(
                        "2026-07-25T08:00:00Z"
                    ),
                )
            )

    def test_builder_rejects_invalid_snapshot_type(self) -> None:
        with self.assertRaisesRegex(
            TypeError,
            r"snapshots\[1\] must be an ARISnapshot",
        ):
            self.builder.build(
                (
                    _snapshot("2026-07-25T08:00:00Z"),
                    object(),
                )
            )

    def test_builder_rejects_nonpositive_expected_interval(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            AnalyticsTimelineError,
            "greater than zero",
        ):
            self.builder.build(
                (
                    _snapshot("2026-07-25T08:00:00Z"),
                    _snapshot("2026-07-26T08:00:00Z"),
                ),
                expected_interval_seconds=0,
            )

    def test_builder_rejects_invalid_gap_multiplier(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            AnalyticsTimelineError,
            "greater than 1",
        ):
            self.builder.build(
                (
                    _snapshot("2026-07-25T08:00:00Z"),
                    _snapshot("2026-07-26T08:00:00Z"),
                ),
                gap_multiplier=1,
            )

    def test_timeline_serializes_stable_contract(self) -> None:
        result = self.builder.build(
            (
                _snapshot(
                    "2026-07-25T08:00:00Z",
                    movies=10,
                    used_bytes=4_000,
                ),
                _snapshot(
                    "2026-07-26T08:00:00Z",
                    movies=12,
                    used_bytes=4_500,
                ),
            ),
            expected_interval_seconds=86_400,
        )

        payload = result.to_dict()

        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["snapshot_count"], 2)
        self.assertEqual(
            payload["first_timestamp"],
            "2026-07-25T08:00:00Z",
        )
        self.assertEqual(
            payload["latest_timestamp"],
            "2026-07-26T08:00:00Z",
        )
        self.assertEqual(
            payload["duration_seconds"],
            86_400.0,
        )
        self.assertEqual(
            payload["expected_interval_seconds"],
            86_400.0,
        )
        self.assertEqual(
            payload["median_interval_seconds"],
            86_400.0,
        )
        self.assertFalse(payload["has_gaps"])
        self.assertEqual(payload["gaps"], [])
        self.assertEqual(len(payload["snapshots"]), 2)


class AnalyticsTimelinePublicApiTests(unittest.TestCase):
    """Verify timeline contracts are publicly exported."""

    def test_package_exports_timeline_contracts(self) -> None:
        from atlas import analytics

        self.assertIs(
            analytics.AnalyticsTimeline,
            AnalyticsTimeline,
        )
        self.assertIs(
            analytics.AnalyticsTimelineBuilder,
            AnalyticsTimelineBuilder,
        )
        self.assertIs(
            analytics.AnalyticsTimelineError,
            AnalyticsTimelineError,
        )
        self.assertIs(
            analytics.TimelineGap,
            TimelineGap,
        )


if __name__ == "__main__":
    unittest.main()
