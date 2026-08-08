"""Tests for the Atlas media dashboard service."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlas_api.services.dashboard_media import (
    DashboardMediaSummaryService,
)


class DashboardMediaSummaryServiceTests(
    unittest.TestCase
):
    """Verify ARI-to-media-dashboard adaptation."""

    def test_reads_valid_ari_snapshot(self) -> None:
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "latest.json"
            snapshot.write_text(
                json.dumps(_snapshot_payload()),
                encoding="utf-8",
            )

            summary = DashboardMediaSummaryService(
                snapshot
            ).read_summary()

        self.assertEqual(
            "2026-07-26T18:00:00Z",
            summary.generated_at,
        )

        libraries = {
            library.id: library
            for library in summary.libraries
        }

        self.assertEqual(
            10,
            libraries["movies"].count,
        )
        self.assertEqual(
            20,
            libraries["television"].count,
        )
        self.assertEqual(
            30,
            libraries["anime-movies"].count,
        )
        self.assertEqual(
            40,
            libraries["anime-television"].count,
        )
        self.assertEqual(
            50,
            libraries["music"].count,
        )
        self.assertEqual(
            60,
            libraries["books"].count,
        )
        self.assertIsNone(
            libraries["photos"].count
        )

    def test_missing_snapshot_returns_unavailable_contract(
        self,
    ) -> None:
        summary = DashboardMediaSummaryService(
            Path("/missing/atlas/latest.json")
        ).read_summary()

        self.assertEqual(
            7,
            len(summary.libraries),
        )
        self.assertTrue(
            all(
                library.status == "unavailable"
                for library in summary.libraries
            )
        )

    def test_invalid_snapshot_returns_unavailable_contract(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "latest.json"
            snapshot.write_text(
                "{invalid",
                encoding="utf-8",
            )

            summary = DashboardMediaSummaryService(
                snapshot
            ).read_summary()

        self.assertTrue(
            all(
                library.status == "unavailable"
                for library in summary.libraries
            )
        )


def _snapshot_payload() -> dict[str, object]:
    return {
        "timestamp": "2026-07-26T18:00:00Z",
        "atlas": {
            "version": "0.9.0-rc.1",
            "hostname": "docker",
            "schema_version": 1,
        },
        "storage": {
            "media_root": "/mnt/storage/media",
            "capacity": "1T",
            "capacity_bytes": 1_000,
            "used": "100B",
            "used_bytes": 100,
            "available": "900B",
            "available_bytes": 900,
            "utilization_percent": 10,
        },
        "jellyfin": {
            "server_name": "Atlas",
            "version": "10.10.0",
            "id": "server-1",
            "libraries": [],
            "users": [],
            "counts": {
                "movies": 100,
                "series": 200,
                "episodes": 300,
                "songs": 50,
                "albums": 5,
                "books": 60,
                "total_items": 715,
            },
        },
        "libraries": {
            "movies": {"count": 10},
            "tv": {"count": 20},
            "anime_movies": {"count": 30},
            "anime_tv": {"count": 40},
        },
    }


if __name__ == "__main__":
    unittest.main()
