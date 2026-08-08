"""Tests for media-library detail service assembly."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from atlas.media import MediaLibraryDetail
from atlas_api.services.media_library import (
    MEDIA_LIBRARY_DEFINITIONS,
    MediaLibraryDetailService,
)


class MediaLibraryDetailServiceTests(
    unittest.TestCase
):
    """Verify ARI-to-domain media-library mapping."""

    def test_definitions_cover_stable_domain_ids(
        self,
    ) -> None:
        self.assertEqual(
            {
                "movies",
                "television",
                "anime-movies",
                "anime-television",
                "music",
                "books",
                "photos",
            },
            {
                definition.id
                for definition in MEDIA_LIBRARY_DEFINITIONS
            },
        )

    def test_reads_filesystem_and_provider_detail(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "latest.json"
            snapshot.write_text(
                json.dumps(_snapshot_payload()),
                encoding="utf-8",
            )

            detail = MediaLibraryDetailService(
                snapshot
            ).read_detail(" Movies ")

        self.assertIsInstance(
            detail,
            MediaLibraryDetail,
        )
        self.assertEqual("movies", detail.id)
        self.assertEqual("available", detail.status)
        self.assertEqual(10, detail.count)
        self.assertEqual(
            "/mnt/storage/media/Movies",
            detail.filesystem.path,
        )
        self.assertEqual(
            "Movies",
            detail.provider.library_name,
        )
        self.assertTrue(
            detail.validation.configured
        )
        self.assertTrue(
            detail.validation.path_matches
        )
        self.assertEqual(
            "synchronized",
            detail.validation.synchronization,
        )

    def test_maps_all_supported_count_sources(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "latest.json"
            snapshot.write_text(
                json.dumps(_snapshot_payload()),
                encoding="utf-8",
            )
            service = MediaLibraryDetailService(
                snapshot
            )

            counts = {
                library_id: service.read_detail(
                    library_id
                ).count
                for library_id in (
                    "movies",
                    "television",
                    "anime-movies",
                    "anime-television",
                    "music",
                    "books",
                    "photos",
                )
            }

        self.assertEqual(
            {
                "movies": 10,
                "television": 20,
                "anime-movies": 30,
                "anime-television": 40,
                "music": 50,
                "books": 60,
                "photos": None,
            },
            counts,
        )

    def test_photos_return_stable_unavailable_contract(
        self,
    ) -> None:
        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "latest.json"
            snapshot.write_text(
                json.dumps(_snapshot_payload()),
                encoding="utf-8",
            )

            detail = MediaLibraryDetailService(
                snapshot
            ).read_detail("photos")

        self.assertEqual(
            "unavailable",
            detail.status,
        )
        self.assertIsNone(detail.count)
        self.assertIsNone(detail.filesystem)
        self.assertIn(
            "not yet collected",
            detail.detail,
        )

    def test_missing_provider_returns_unknown_validation(
        self,
    ) -> None:
        payload = _snapshot_payload()
        payload["jellyfin"]["libraries"] = []

        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "latest.json"
            snapshot.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            detail = MediaLibraryDetailService(
                snapshot
            ).read_detail("movies")

        self.assertIsNone(detail.provider)
        self.assertFalse(
            detail.validation.configured
        )
        self.assertIsNone(
            detail.validation.path_matches
        )
        self.assertEqual(
            "unknown",
            detail.validation.synchronization,
        )

    def test_detects_provider_path_mismatch(
        self,
    ) -> None:
        payload = _snapshot_payload()
        payload["jellyfin"]["libraries"][0]["path"] = (
            "/media/Films"
        )

        with TemporaryDirectory() as directory:
            snapshot = Path(directory) / "latest.json"
            snapshot.write_text(
                json.dumps(payload),
                encoding="utf-8",
            )

            detail = MediaLibraryDetailService(
                snapshot
            ).read_detail("movies")

        self.assertFalse(
            detail.validation.path_matches
        )
        self.assertEqual(
            "out_of_sync",
            detail.validation.synchronization,
        )

    def test_missing_snapshot_returns_unavailable_contract(
        self,
    ) -> None:
        detail = MediaLibraryDetailService(
            Path("/missing/atlas/latest.json"),
            clock=lambda: datetime(
                2026,
                7,
                28,
                1,
                0,
                tzinfo=timezone.utc,
            ),
        ).read_detail("movies")

        self.assertEqual(
            "unavailable",
            detail.status,
        )
        self.assertEqual(
            "2026-07-28T01:00:00Z",
            detail.generated_at,
        )
        self.assertIsNone(detail.count)
        self.assertIsNone(detail.filesystem)
        self.assertIsNone(detail.provider)
        self.assertEqual(
            "unknown",
            detail.validation.synchronization,
        )
        self.assertIn(
            "FileNotFoundError",
            detail.detail,
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

            detail = MediaLibraryDetailService(
                snapshot,
                clock=lambda: datetime(
                    2026,
                    7,
                    28,
                    1,
                    0,
                    tzinfo=timezone.utc,
                ),
            ).read_detail("books")

        self.assertEqual(
            "unavailable",
            detail.status,
        )
        self.assertIn(
            "JSONDecodeError",
            detail.detail,
        )

    def test_rejects_unknown_library_identity(
        self,
    ) -> None:
        service = MediaLibraryDetailService(
            Path("/unused/latest.json")
        )

        with self.assertRaisesRegex(
            KeyError,
            "unsupported media library ID",
        ):
            service.read_detail("games")


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
            "libraries": [
                {
                    "name": "Movies",
                    "type": "movies",
                    "path": "/media/Movies",
                    "status": "available",
                },
                {
                    "name": "Television",
                    "type": "tvshows",
                    "path": "/media/TV",
                    "status": "available",
                },
                {
                    "name": "Anime Movies",
                    "type": "movies",
                    "path": "/media/Anime Movies",
                    "status": "available",
                },
                {
                    "name": "Anime Television",
                    "type": "tvshows",
                    "path": "/media/Anime TV",
                    "status": "available",
                },
                {
                    "name": "Music",
                    "type": "music",
                    "path": "/media/Music",
                    "status": "available",
                },
                {
                    "name": "Books",
                    "type": "books",
                    "path": "/media/Books",
                    "status": "available",
                },
                {
                    "name": "Photos",
                    "type": "photos",
                    "path": "/media/Photos",
                    "status": "available",
                },
            ],
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
