"""Tests for the ARI service."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas.ari import (
    ARIReport,
    ARIService,
    ARIServiceError,
)


def sample_snapshot() -> dict:
    """Return a valid ARI snapshot payload."""

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
    """Validate ARI snapshot loading and discovery."""

    def test_load_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "latest.json"
            path.write_text(
                json.dumps(sample_snapshot()),
                encoding="utf-8",
            )

            report = ARIService(temporary).load(path)

            self.assertIsInstance(
                report,
                ARIReport,
            )
            self.assertEqual(
                "2026-07-23T00:30:00Z",
                report.timestamp,
            )

    def test_latest_loads_configured_latest_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "latest.json"
            path.write_text(
                json.dumps(sample_snapshot()),
                encoding="utf-8",
            )

            report = ARIService(temporary).latest()

            self.assertEqual(
                "docker",
                report.atlas.hostname,
            )

    def test_latest_path(
        self,
    ) -> None:
        service = ARIService("/tmp/test")

        self.assertEqual(
            Path("/tmp/test/latest.json"),
            service.latest_path(),
        )

    def test_list_snapshots(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.mkdir()

            latest = directory / "latest.json"
            first = history / "20260722-120000.json"
            second = history / "20260723-120000.json"

            latest.write_text(
                "{}",
                encoding="utf-8",
            )
            first.write_text(
                "{}",
                encoding="utf-8",
            )
            second.write_text(
                "{}",
                encoding="utf-8",
            )

            snapshots = ARIService(
                directory,
            ).list_snapshots()

            self.assertEqual(
                [
                    latest,
                    first,
                    second,
                ],
                snapshots,
            )

    def test_list_snapshots_excludes_state_files(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)

            latest = directory / "latest.json"
            latest.write_text(
                "{}",
                encoding="utf-8",
            )
            (directory / "health-state.json").write_text(
                "{}",
                encoding="utf-8",
            )
            (directory / "storage-state.json").write_text(
                "{}",
                encoding="utf-8",
            )

            self.assertEqual(
                [latest],
                ARIService(directory).list_snapshots(),
            )

    def test_list_snapshots_returns_empty_for_missing_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            missing = Path(temporary) / "missing"

            self.assertEqual(
                [],
                ARIService(missing).list_snapshots(),
            )

    def test_list_snapshots_rejects_file_as_history_directory(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            history = directory / "snapshots"
            history.write_text(
                "",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ARIServiceError,
                "ARI snapshot history path is not a directory",
            ):
                ARIService(directory).list_snapshots()

    def test_load_rejects_missing_snapshot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "missing.json"

            with self.assertRaisesRegex(
                ARIServiceError,
                "ARI snapshot not found",
            ) as context:
                ARIService(temporary).load(path)

            self.assertIsInstance(
                context.exception.__cause__,
                FileNotFoundError,
            )

    def test_load_rejects_invalid_json(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid.json"
            path.write_text(
                "{invalid",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ARIServiceError,
                "ARI snapshot contains invalid JSON",
            ) as context:
                ARIService(temporary).load(path)

            self.assertIsInstance(
                context.exception.__cause__,
                json.JSONDecodeError,
            )

    def test_load_rejects_invalid_report_contract(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "invalid-report.json"
            path.write_text(
                json.dumps(
                    {
                        "timestamp": (
                            "2026-07-22T20:30:00-04:00"
                        ),
                    },
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ARIServiceError,
                "ARI snapshot is invalid",
            ):
                ARIService(temporary).load(path)


if __name__ == "__main__":
    unittest.main()
