"""Tests for the Atlas analytics comparison service."""

from __future__ import annotations

import unittest

from atlas.analytics import (
    ARISnapshot,
    AnalyticsComparisonError,
    AnalyticsComparisonService,
    AnalyticsSnapshot,
    ForecastHealth,
    StorageSummary,
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
    *,
    timestamp: str,
    libraries: tuple[tuple[str, int], ...],
    storage: StorageSummary | None = None,
) -> ARISnapshot:
    return ARISnapshot(
        timestamp=timestamp,
        schema_version=1,
        storage=storage or _storage(),
        library_counts=libraries,
    )


class AnalyticsComparisonServiceTests(unittest.TestCase):
    """Verify analytics generation from two source snapshots."""

    def setUp(self) -> None:
        self.service = AnalyticsComparisonService()

    def test_compare_returns_analytics_snapshot(self) -> None:
        previous = _snapshot(
            timestamp="2026-07-25T08:00:00-04:00",
            libraries=(
                ("movies", 10),
                ("tv", 20),
            ),
        )
        current = _snapshot(
            timestamp="2026-07-26T08:00:00-04:00",
            libraries=(
                ("movies", 15),
                ("tv", 22),
            ),
        )

        result = self.service.compare(
            current=current,
            previous=previous,
        )

        self.assertIsInstance(result, AnalyticsSnapshot)

    def test_compare_uses_current_snapshot_timestamp(self) -> None:
        result = self.service.compare(
            current=_snapshot(
                timestamp="2026-07-26T08:00:00-04:00",
                libraries=(("movies", 15),),
            ),
            previous=_snapshot(
                timestamp="2026-07-25T08:00:00-04:00",
                libraries=(("movies", 10),),
            ),
        )

        self.assertEqual(
            result.generated_at,
            "2026-07-26T12:00:00Z",
        )

    def test_compare_preserves_current_storage(self) -> None:
        current_storage = _storage(
            total_bytes=20_000,
            used_bytes=7_000,
            free_bytes=12_000,
        )

        result = self.service.compare(
            current=_snapshot(
                timestamp="2026-07-26T08:00:00-04:00",
                libraries=(("movies", 15),),
                storage=current_storage,
            ),
            previous=_snapshot(
                timestamp="2026-07-25T08:00:00-04:00",
                libraries=(("movies", 10),),
            ),
        )

        self.assertIs(result.storage, current_storage)

    def test_compare_calculates_library_growth(self) -> None:
        result = self.service.compare(
            current=_snapshot(
                timestamp="2026-07-26T08:00:00-04:00",
                libraries=(
                    ("movies", 15),
                    ("tv", 18),
                ),
            ),
            previous=_snapshot(
                timestamp="2026-07-25T08:00:00-04:00",
                libraries=(
                    ("movies", 10),
                    ("tv", 20),
                ),
            ),
        )

        growth = {
            entry.library: entry
            for entry in result.libraries
        }

        self.assertEqual(growth["movies"].delta, 5)
        self.assertEqual(
            growth["movies"].percent_change,
            50.0,
        )
        self.assertEqual(growth["tv"].delta, -2)
        self.assertEqual(
            growth["tv"].percent_change,
            -10.0,
        )

    def test_compare_sorts_libraries_by_normalized_name(self) -> None:
        result = self.service.compare(
            current=_snapshot(
                timestamp="2026-07-26T08:00:00Z",
                libraries=(
                    ("tv", 20),
                    ("anime_movies", 5),
                    ("movies", 10),
                ),
            ),
            previous=_snapshot(
                timestamp="2026-07-25T08:00:00Z",
                libraries=(
                    ("movies", 9),
                    ("tv", 19),
                    ("anime_movies", 4),
                ),
            ),
        )

        self.assertEqual(
            tuple(entry.library for entry in result.libraries),
            (
                "anime_movies",
                "movies",
                "tv",
            ),
        )

    def test_compare_adds_new_library_with_zero_baseline(self) -> None:
        result = self.service.compare(
            current=_snapshot(
                timestamp="2026-07-26T08:00:00Z",
                libraries=(
                    ("movies", 10),
                    ("music", 4),
                ),
            ),
            previous=_snapshot(
                timestamp="2026-07-25T08:00:00Z",
                libraries=(("movies", 8),),
            ),
        )

        growth = {
            entry.library: entry
            for entry in result.libraries
        }

        self.assertEqual(
            growth["music"].previous_count,
            0,
        )
        self.assertEqual(
            growth["music"].current_count,
            4,
        )
        self.assertEqual(growth["music"].delta, 4)
        self.assertIsNone(
            growth["music"].percent_change,
        )

    def test_compare_retains_removed_library_with_zero_current_count(
        self,
    ) -> None:
        result = self.service.compare(
            current=_snapshot(
                timestamp="2026-07-26T08:00:00Z",
                libraries=(("movies", 10),),
            ),
            previous=_snapshot(
                timestamp="2026-07-25T08:00:00Z",
                libraries=(
                    ("movies", 8),
                    ("music", 4),
                ),
            ),
        )

        growth = {
            entry.library: entry
            for entry in result.libraries
        }

        self.assertEqual(
            growth["music"].current_count,
            0,
        )
        self.assertEqual(
            growth["music"].previous_count,
            4,
        )
        self.assertEqual(growth["music"].delta, -4)
        self.assertEqual(
            growth["music"].percent_change,
            -100.0,
        )

    def test_compare_creates_unknown_forecast_placeholder(self) -> None:
        current_storage = _storage(
            total_bytes=10_000,
            used_bytes=4_000,
            free_bytes=5_500,
        )

        result = self.service.compare(
            current=_snapshot(
                timestamp="2026-07-26T08:00:00Z",
                libraries=(("movies", 10),),
                storage=current_storage,
            ),
            previous=_snapshot(
                timestamp="2026-07-25T08:00:00Z",
                libraries=(("movies", 8),),
            ),
        )

        self.assertEqual(
            result.forecast.health,
            ForecastHealth.UNKNOWN,
        )
        self.assertEqual(
            result.forecast.daily_growth_bytes,
            0.0,
        )
        self.assertEqual(
            result.forecast.remaining_bytes,
            5_500,
        )
        self.assertIsNone(
            result.forecast.estimated_days_remaining,
        )

    def test_compare_rejects_equal_timestamps(self) -> None:
        current = _snapshot(
            timestamp="2026-07-26T08:00:00Z",
            libraries=(("movies", 10),),
        )
        previous = _snapshot(
            timestamp="2026-07-26T08:00:00Z",
            libraries=(("movies", 8),),
        )

        with self.assertRaisesRegex(
            AnalyticsComparisonError,
            "must precede",
        ):
            self.service.compare(
                current=current,
                previous=previous,
            )

    def test_compare_rejects_reversed_timestamps(self) -> None:
        current = _snapshot(
            timestamp="2026-07-25T08:00:00Z",
            libraries=(("movies", 10),),
        )
        previous = _snapshot(
            timestamp="2026-07-26T08:00:00Z",
            libraries=(("movies", 8),),
        )

        with self.assertRaisesRegex(
            AnalyticsComparisonError,
            "must precede",
        ):
            self.service.compare(
                current=current,
                previous=previous,
            )

    def test_compare_rejects_naive_timestamp(self) -> None:
        current = _snapshot(
            timestamp="2026-07-26T08:00:00",
            libraries=(("movies", 10),),
        )
        previous = _snapshot(
            timestamp="2026-07-25T08:00:00Z",
            libraries=(("movies", 8),),
        )

        with self.assertRaisesRegex(
            AnalyticsComparisonError,
            "must include a timezone",
        ):
            self.service.compare(
                current=current,
                previous=previous,
            )

    def test_compare_rejects_invalid_snapshot_type(self) -> None:
        previous = _snapshot(
            timestamp="2026-07-25T08:00:00Z",
            libraries=(("movies", 8),),
        )

        with self.assertRaisesRegex(
            TypeError,
            "current must be an ARISnapshot",
        ):
            self.service.compare(
                current=object(),  # type: ignore[arg-type]
                previous=previous,
            )

    def test_compare_many_uses_two_newest_snapshots(self) -> None:
        oldest = _snapshot(
            timestamp="2026-07-23T08:00:00Z",
            libraries=(("movies", 2),),
        )
        newest = _snapshot(
            timestamp="2026-07-26T08:00:00Z",
            libraries=(("movies", 10),),
        )
        middle = _snapshot(
            timestamp="2026-07-25T08:00:00Z",
            libraries=(("movies", 7),),
        )

        result = self.service.compare_many(
            (
                newest,
                oldest,
                middle,
            )
        )

        self.assertEqual(
            result.libraries[0].current_count,
            10,
        )
        self.assertEqual(
            result.libraries[0].previous_count,
            7,
        )
        self.assertEqual(
            result.libraries[0].delta,
            3,
        )

    def test_compare_many_rejects_single_snapshot(self) -> None:
        snapshot = _snapshot(
            timestamp="2026-07-26T08:00:00Z",
            libraries=(("movies", 10),),
        )

        with self.assertRaisesRegex(
            AnalyticsComparisonError,
            "At least two",
        ):
            self.service.compare_many((snapshot,))

    def test_result_serializes_stable_contract(self) -> None:
        result = self.service.compare(
            current=_snapshot(
                timestamp="2026-07-26T08:00:00Z",
                libraries=(("movies", 12),),
            ),
            previous=_snapshot(
                timestamp="2026-07-25T08:00:00Z",
                libraries=(("movies", 10),),
            ),
        )

        payload = result.to_dict()

        self.assertEqual(
            payload["generated_at"],
            "2026-07-26T08:00:00Z",
        )
        self.assertEqual(
            payload["libraries"],
            [
                {
                    "library": "movies",
                    "current_count": 12,
                    "previous_count": 10,
                    "delta": 2,
                    "percent_change": 20.0,
                }
            ],
        )
        self.assertEqual(
            payload["forecast"],
            {
                "daily_growth_bytes": 0.0,
                "remaining_bytes": 5_500,
                "estimated_days_remaining": None,
                "health": "unknown",
            },
        )


class AnalyticsComparisonPublicApiTests(unittest.TestCase):
    """Verify comparison contracts are publicly exported."""

    def test_public_package_exports_comparison_contracts(
        self,
    ) -> None:
        from atlas import analytics

        self.assertIs(
            analytics.AnalyticsComparisonService,
            AnalyticsComparisonService,
        )
        self.assertIs(
            analytics.AnalyticsComparisonError,
            AnalyticsComparisonError,
        )


if __name__ == "__main__":
    unittest.main()
