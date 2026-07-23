"""Tests for the ARI service."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas.ari import (
    ARIReport,
    ARIService,
)


def sample_snapshot() -> dict:
    return {
        "timestamp": "2026-07-22T20:30:00-04:00",
        "atlas": {
            "version": "0.9.0-rc.1",
            "hostname": "docker",
            "schema_version": 1,
        },
        "storage": {
            "media_root": "/mnt/storage/media",
            "capacity": "1T",
            "capacity_bytes": 1000,
            "used": "10G",
            "used_bytes": 10,
            "available": "990G",
            "available_bytes": 990,
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
            "movies": {"count": 0},
            "tv": {"count": 0},
            "anime_movies": {"count": 0},
            "anime_tv": {"count": 0},
        },
    }


class ARIServiceTests(unittest.TestCase):

    def test_load_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "latest.json"

            path.write_text(
                json.dumps(sample_snapshot()),
                encoding="utf-8",
            )

            report = ARIService(tmp).load(path)

            self.assertIsInstance(
                report,
                ARIReport,
            )

    def test_latest_path(self):
        service = ARIService("/tmp/test")

        self.assertEqual(
            Path("/tmp/test/latest.json"),
            service.latest_path(),
        )

    def test_list_snapshots(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)

            (directory / "a.json").write_text("{}")
            (directory / "b.json").write_text("{}")
            (directory / "ignore.txt").write_text("")

            snapshots = ARIService(directory).list_snapshots()

            self.assertEqual(
                2,
                len(snapshots),
            )

            self.assertTrue(
                all(
                    path.suffix == ".json"
                    for path in snapshots
                )
            )


if __name__ == "__main__":
    unittest.main()
