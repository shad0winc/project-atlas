"""Tests for the Atlas ARI snapshot reader."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas.analytics import (
    ARISnapshot,
    SnapshotReader,
    SnapshotReaderError,
)


def _snapshot_document() -> dict[str, object]:
    return {
        "timestamp": "2026-07-26T08:00:10-04:00",
        "atlas": {
            "version": "0.9.0-rc.1",
            "hostname": "docker",
            "schema_version": 1,
        },
        "storage": {
            "media_root": "/mnt/storage/media",
            "capacity": "1.8T",
            "capacity_bytes": 1_967_846_068_224,
            "used": "1.4G",
            "used_bytes": 1_493_508_096,
            "available": "1.7T",
            "available_bytes": 1_866_315_890_688,
            "utilization_percent": 1,
        },
        "jellyfin": {
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
                "count": 12,
            },
            "tv": {
                "count": 8,
            },
            "anime_movies": {
                "count": 3,
            },
            "anime_tv": {
                "count": 5,
            },
        },
    }


class ARISnapshotTests(unittest.TestCase):
    """Verify the validated ARI source contract."""

    def test_snapshot_normalizes_library_names(self) -> None:
        snapshot = ARISnapshot(
            timestamp="2026-07-26T08:00:10-04:00",
            schema_version=1,
            storage=SnapshotReader()
            .read_document(_snapshot_document())
            .storage,
            library_counts=(
                (" Movies ", 12),
                ("TV", 8),
            ),
        )

        self.assertEqual(
            snapshot.library_counts,
            (
                ("movies", 12),
                ("tv", 8),
            ),
        )

    def test_snapshot_rejects_duplicate_library_names(self) -> None:
        storage = SnapshotReader().read_document(
            _snapshot_document()
        ).storage

        with self.assertRaises(SnapshotReaderError):
            ARISnapshot(
                timestamp="2026-07-26T08:00:10-04:00",
                schema_version=1,
                storage=storage,
                library_counts=(
                    ("movies", 12),
                    (" MOVIES ", 13),
                ),
            )

    def test_library_count_returns_named_count(self) -> None:
        snapshot = SnapshotReader().read_document(
            _snapshot_document()
        )

        self.assertEqual(
            snapshot.library_count(" Movies "),
            12,
        )

        with self.assertRaises(KeyError):
            snapshot.library_count("music")

    def test_snapshot_serializes_stable_contract(self) -> None:
        snapshot = SnapshotReader().read_document(
            _snapshot_document()
        )
        payload = snapshot.to_dict()

        self.assertEqual(
            set(payload),
            {
                "timestamp",
                "schema_version",
                "storage",
                "libraries",
            },
        )
        self.assertEqual(
            payload["libraries"],
            {
                "anime_movies": {
                    "count": 3,
                },
                "anime_tv": {
                    "count": 5,
                },
                "movies": {
                    "count": 12,
                },
                "tv": {
                    "count": 8,
                },
            },
        )


class SnapshotReaderTests(unittest.TestCase):
    """Verify ARI JSON parsing and validation."""

    def setUp(self) -> None:
        self.reader = SnapshotReader()

    def test_read_document_maps_real_ari_contract(self) -> None:
        snapshot = self.reader.read_document(
            _snapshot_document()
        )

        self.assertEqual(
            snapshot.timestamp,
            "2026-07-26T08:00:10-04:00",
        )
        self.assertEqual(snapshot.schema_version, 1)
        self.assertEqual(
            snapshot.library_counts,
            (
                ("anime_movies", 3),
                ("anime_tv", 5),
                ("movies", 12),
                ("tv", 8),
            ),
        )

    def test_reader_calculates_utilization_from_bytes(self) -> None:
        document = _snapshot_document()
        storage = document["storage"]
        self.assertIsInstance(storage, dict)
        storage["utilization_percent"] = 99

        snapshot = self.reader.read_document(document)

        self.assertEqual(
            snapshot.storage.utilization_percent,
            0.08,
        )

    def test_reader_derives_reserved_filesystem_space(self) -> None:
        snapshot = self.reader.read_document(
            _snapshot_document()
        )

        self.assertEqual(
            snapshot.storage.reserved_bytes,
            100_036_669_440,
        )

    def test_read_loads_snapshot_from_disk(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text(
                json.dumps(_snapshot_document()),
                encoding="utf-8",
            )

            snapshot = self.reader.read(path)

        self.assertEqual(snapshot.library_count("movies"), 12)

    def test_read_rejects_missing_file(self) -> None:
        with self.assertRaisesRegex(
            SnapshotReaderError,
            "does not exist",
        ):
            self.reader.read("/tmp/missing-atlas-ari.json")

    def test_read_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "snapshot.json"
            path.write_text("{invalid", encoding="utf-8")

            with self.assertRaisesRegex(
                SnapshotReaderError,
                "invalid JSON",
            ):
                self.reader.read(path)

    def test_reader_rejects_missing_timestamp(self) -> None:
        document = _snapshot_document()
        document.pop("timestamp")

        with self.assertRaisesRegex(
            SnapshotReaderError,
            "timestamp",
        ):
            self.reader.read_document(document)

    def test_reader_rejects_missing_schema_version(self) -> None:
        document = _snapshot_document()
        atlas = document["atlas"]
        self.assertIsInstance(atlas, dict)
        atlas.pop("schema_version")

        with self.assertRaisesRegex(
            SnapshotReaderError,
            "schema_version",
        ):
            self.reader.read_document(document)

    def test_reader_rejects_missing_storage_bytes(self) -> None:
        document = _snapshot_document()
        storage = document["storage"]
        self.assertIsInstance(storage, dict)
        storage.pop("capacity_bytes")

        with self.assertRaisesRegex(
            SnapshotReaderError,
            "capacity_bytes",
        ):
            self.reader.read_document(document)

    def test_reader_rejects_invalid_library_count(self) -> None:
        document = _snapshot_document()
        libraries = document["libraries"]
        self.assertIsInstance(libraries, dict)
        libraries["movies"] = {
            "count": -1,
        }

        with self.assertRaisesRegex(
            SnapshotReaderError,
            "libraries.movies.count",
        ):
            self.reader.read_document(document)

    def test_reader_rejects_non_object_document(self) -> None:
        with self.assertRaisesRegex(
            SnapshotReaderError,
            "snapshot must be an object",
        ):
            self.reader.read_document([])


class AnalyticsSnapshotReaderPublicApiTests(unittest.TestCase):
    """Verify the reader is exported through atlas.analytics."""

    def test_public_package_exports_reader_contracts(self) -> None:
        from atlas import analytics

        self.assertIs(
            analytics.ARISnapshot,
            ARISnapshot,
        )
        self.assertIs(
            analytics.SnapshotReader,
            SnapshotReader,
        )
        self.assertIs(
            analytics.SnapshotReaderError,
            SnapshotReaderError,
        )


if __name__ == "__main__":
    unittest.main()
