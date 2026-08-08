"""Tests for Atlas analytics domain models."""

from __future__ import annotations

import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from atlas.analytics import (
    AnalyticsSnapshot,
    ForecastHealth,
    ForecastSummary,
    LibraryGrowth,
    StorageSummary,
)


class StorageSummaryTests(unittest.TestCase):
    """Verify storage summary normalization and validation."""

    def test_from_bytes_calculates_utilization(self) -> None:
        summary = StorageSummary.from_bytes(
            total_bytes=1_000,
            used_bytes=375,
            free_bytes=625,
        )

        self.assertEqual(summary.total_bytes, 1_000)
        self.assertEqual(summary.used_bytes, 375)
        self.assertEqual(summary.free_bytes, 625)
        self.assertEqual(summary.utilization_percent, 37.5)

    def test_storage_summary_serializes_stable_contract(self) -> None:
        summary = StorageSummary.from_bytes(
            total_bytes=2_000,
            used_bytes=500,
            free_bytes=1_500,
        )

        self.assertEqual(
            summary.to_dict(),
            {
                "total_bytes": 2_000,
                "used_bytes": 500,
                "free_bytes": 1_500,
                "reserved_bytes": 0,
                "utilization_percent": 25.0,
            },
        )

    def test_storage_summary_derives_reserved_bytes(self) -> None:
        summary = StorageSummary(
            total_bytes=1_000,
            used_bytes=100,
            free_bytes=850,
            utilization_percent=10,
        )

        self.assertEqual(summary.reserved_bytes, 50)
        self.assertEqual(
            summary.to_dict(),
            {
                "total_bytes": 1_000,
                "used_bytes": 100,
                "free_bytes": 850,
                "reserved_bytes": 50,
                "utilization_percent": 10.0,
            },
        )

    def test_storage_summary_rejects_overallocated_bytes(self) -> None:
        with self.assertRaises(ValueError):
            StorageSummary(
                total_bytes=1_000,
                used_bytes=400,
                free_bytes=700,
                utilization_percent=40,
            )

    def test_storage_summary_rejects_incorrect_utilization(self) -> None:
        with self.assertRaises(ValueError):
            StorageSummary(
                total_bytes=1_000,
                used_bytes=400,
                free_bytes=600,
                utilization_percent=50,
            )

    def test_storage_summary_is_immutable(self) -> None:
        summary = StorageSummary.from_bytes(
            total_bytes=1_000,
            used_bytes=400,
            free_bytes=600,
        )

        with self.assertRaises(FrozenInstanceError):
            summary.used_bytes = 500  # type: ignore[misc]


class LibraryGrowthTests(unittest.TestCase):
    """Verify normalized media-library growth calculations."""

    def test_library_growth_normalizes_and_calculates_delta(self) -> None:
        growth = LibraryGrowth(
            library=" Movies ",
            current_count=120,
            previous_count=100,
        )

        self.assertEqual(growth.library, "movies")
        self.assertEqual(growth.delta, 20)
        self.assertEqual(growth.percent_change, 20.0)

    def test_library_growth_supports_decrease(self) -> None:
        growth = LibraryGrowth(
            library="tv",
            current_count=80,
            previous_count=100,
        )

        self.assertEqual(growth.delta, -20)
        self.assertEqual(growth.percent_change, -20.0)

    def test_library_growth_uses_none_without_baseline(self) -> None:
        growth = LibraryGrowth(
            library="books",
            current_count=12,
            previous_count=0,
        )

        self.assertEqual(growth.delta, 12)
        self.assertIsNone(growth.percent_change)

    def test_library_growth_serializes_stable_contract(self) -> None:
        growth = LibraryGrowth(
            library="anime_tv",
            current_count=15,
            previous_count=10,
        )

        self.assertEqual(
            growth.to_dict(),
            {
                "library": "anime_tv",
                "current_count": 15,
                "previous_count": 10,
                "delta": 5,
                "percent_change": 50.0,
            },
        )

    def test_library_growth_rejects_blank_identity(self) -> None:
        with self.assertRaises(ValueError):
            LibraryGrowth(
                library=" ",
                current_count=1,
                previous_count=0,
            )


class ForecastSummaryTests(unittest.TestCase):
    """Verify capacity forecast contracts."""

    def test_forecast_normalizes_health(self) -> None:
        forecast = ForecastSummary(
            daily_growth_bytes=1_024.5,
            remaining_bytes=10_000,
            estimated_days_remaining=9,
            health=" WARNING ",  # type: ignore[arg-type]
        )

        self.assertIs(
            forecast.health,
            ForecastHealth.WARNING,
        )

    def test_forecast_serializes_stable_contract(self) -> None:
        forecast = ForecastSummary(
            daily_growth_bytes=500,
            remaining_bytes=5_000,
            estimated_days_remaining=10,
            health=ForecastHealth.HEALTHY,
        )

        self.assertEqual(
            forecast.to_dict(),
            {
                "daily_growth_bytes": 500.0,
                "remaining_bytes": 5_000,
                "estimated_days_remaining": 10,
                "health": "healthy",
            },
        )

    def test_nonpositive_growth_requires_unknown_forecast(self) -> None:
        forecast = ForecastSummary(
            daily_growth_bytes=0,
            remaining_bytes=5_000,
            estimated_days_remaining=None,
            health=ForecastHealth.UNKNOWN,
        )

        self.assertEqual(
            forecast.health,
            ForecastHealth.UNKNOWN,
        )

    def test_positive_growth_requires_days_remaining(self) -> None:
        with self.assertRaises(ValueError):
            ForecastSummary(
                daily_growth_bytes=500,
                remaining_bytes=5_000,
                estimated_days_remaining=None,
                health=ForecastHealth.HEALTHY,
            )


class AnalyticsSnapshotTests(unittest.TestCase):
    """Verify the complete analytics child contract."""

    def setUp(self) -> None:
        self.storage = StorageSummary.from_bytes(
            total_bytes=10_000,
            used_bytes=4_000,
            free_bytes=6_000,
        )

        self.growth = LibraryGrowth(
            library="movies",
            current_count=120,
            previous_count=110,
        )

        self.forecast = ForecastSummary(
            daily_growth_bytes=100,
            remaining_bytes=6_000,
            estimated_days_remaining=60,
            health=ForecastHealth.HEALTHY,
        )

    def test_snapshot_normalizes_timestamp_and_children(self) -> None:
        snapshot = AnalyticsSnapshot(
            generated_at=datetime(
                2026,
                7,
                26,
                18,
                0,
                tzinfo=timezone.utc,
            ),
            storage=self.storage,
            libraries=[self.growth],  # type: ignore[arg-type]
            forecast=self.forecast,
        )

        self.assertEqual(
            snapshot.generated_at,
            "2026-07-26T18:00:00Z",
        )
        self.assertEqual(
            snapshot.libraries,
            (self.growth,),
        )

    def test_snapshot_rejects_invalid_storage_child(self) -> None:
        with self.assertRaises(TypeError):
            AnalyticsSnapshot(
                generated_at="2026-07-26T18:00:00Z",
                storage=object(),  # type: ignore[arg-type]
            )

    def test_snapshot_rejects_invalid_library_child(self) -> None:
        with self.assertRaises(TypeError):
            AnalyticsSnapshot(
                generated_at="2026-07-26T18:00:00Z",
                storage=self.storage,
                libraries=(object(),),  # type: ignore[arg-type]
            )

    def test_snapshot_rejects_duplicate_library_identity(self) -> None:
        duplicate = LibraryGrowth(
            library=" MOVIES ",
            current_count=130,
            previous_count=120,
        )

        with self.assertRaises(ValueError):
            AnalyticsSnapshot(
                generated_at="2026-07-26T18:00:00Z",
                storage=self.storage,
                libraries=(
                    self.growth,
                    duplicate,
                ),
            )

    def test_snapshot_serializes_complete_contract(self) -> None:
        snapshot = AnalyticsSnapshot(
            generated_at="2026-07-26T14:00:00-04:00",
            storage=self.storage,
            libraries=(self.growth,),
            forecast=self.forecast,
        )

        self.assertEqual(
            snapshot.to_dict(),
            {
                "generated_at": "2026-07-26T18:00:00Z",
                "storage": {
                    "total_bytes": 10_000,
                    "used_bytes": 4_000,
                    "free_bytes": 6_000,
                    "reserved_bytes": 0,
                    "utilization_percent": 40.0,
                },
                "libraries": [
                    {
                        "library": "movies",
                        "current_count": 120,
                        "previous_count": 110,
                        "delta": 10,
                        "percent_change": 9.09,
                    }
                ],
                "forecast": {
                    "daily_growth_bytes": 100.0,
                    "remaining_bytes": 6_000,
                    "estimated_days_remaining": 60,
                    "health": "healthy",
                },
            },
        )


class AnalyticsPublicApiTests(unittest.TestCase):
    """Verify analytics contracts are exported publicly."""

    def test_public_package_exports_models(self) -> None:
        from atlas import analytics

        self.assertIs(
            analytics.StorageSummary,
            StorageSummary,
        )
        self.assertIs(
            analytics.LibraryGrowth,
            LibraryGrowth,
        )
        self.assertIs(
            analytics.ForecastSummary,
            ForecastSummary,
        )
        self.assertIs(
            analytics.AnalyticsSnapshot,
            AnalyticsSnapshot,
        )


if __name__ == "__main__":
    unittest.main()
