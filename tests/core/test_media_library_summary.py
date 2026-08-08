"""Tests for normalized media-library summary contracts."""

from __future__ import annotations

import unittest

from atlas.ari import (
    ARIReport,
    AtlasMetadata,
    FilesystemLibraries,
    FilesystemLibrary,
    JellyfinCounts,
    JellyfinSnapshot,
    StorageSnapshot,
)
from atlas.media import (
    MediaLibraryCount,
    MediaLibrarySummary,
)


class MediaLibraryCountTests(unittest.TestCase):
    """Validate individual media-library counts."""

    def test_normalizes_and_serializes_count(self) -> None:
        library = MediaLibraryCount(
            id=" MOVIES ",
            label=" Movies ",
            count=12,
            status="available",
            detail=" Filesystem library count ",
        )

        self.assertEqual("movies", library.id)
        self.assertEqual("Movies", library.label)
        self.assertEqual(
            {
                "id": "movies",
                "label": "Movies",
                "count": 12,
                "status": "available",
                "detail": "Filesystem library count",
            },
            library.to_dict(),
        )

    def test_rejects_inconsistent_availability(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "require a count",
        ):
            MediaLibraryCount(
                id="movies",
                label="Movies",
                count=None,
                status="available",
            )

        with self.assertRaisesRegex(
            ValueError,
            "cannot have a count",
        ):
            MediaLibraryCount(
                id="photos",
                label="Photos",
                count=1,
                status="unavailable",
            )


class MediaLibrarySummaryTests(unittest.TestCase):
    """Validate complete media-library summaries."""

    def test_builds_summary_from_ari_report(self) -> None:
        summary = MediaLibrarySummary.from_ari_report(
            _report()
        )

        self.assertEqual(
            "2026-07-26T18:00:00Z",
            summary.generated_at,
        )
        self.assertEqual(
            tuple(
                library.id
                for library in summary.libraries
            ),
            (
                "movies",
                "television",
                "anime-movies",
                "anime-television",
                "music",
                "books",
                "photos",
            ),
        )

        counts = {
            library.id: library.count
            for library in summary.libraries
        }

        self.assertEqual(10, counts["movies"])
        self.assertEqual(20, counts["television"])
        self.assertEqual(30, counts["anime-movies"])
        self.assertEqual(40, counts["anime-television"])
        self.assertEqual(50, counts["music"])
        self.assertEqual(60, counts["books"])
        self.assertIsNone(counts["photos"])

    def test_rejects_duplicate_library_ids(self) -> None:
        library = MediaLibraryCount(
            id="movies",
            label="Movies",
            count=1,
            status="available",
        )

        with self.assertRaisesRegex(
            ValueError,
            "IDs must be unique",
        ):
            MediaLibrarySummary(
                generated_at="2026-07-26T18:00:00Z",
                libraries=(
                    library,
                    library,
                ),
            )

    def test_unavailable_summary_has_stable_contract(self) -> None:
        summary = MediaLibrarySummary.unavailable(
            generated_at="2026-07-26T18:00:00Z",
            detail="Snapshot missing",
        )

        self.assertEqual(7, len(summary.libraries))
        self.assertTrue(
            all(
                library.count is None
                for library in summary.libraries
            )
        )
        self.assertTrue(
            all(
                library.status == "unavailable"
                for library in summary.libraries
            )
        )


def _report() -> ARIReport:
    return ARIReport(
        timestamp="2026-07-26T18:00:00Z",
        atlas=AtlasMetadata(
            version="0.9.0-rc.1",
            hostname="docker",
            schema_version=1,
        ),
        storage=StorageSnapshot(
            media_root="/mnt/storage/media",
            capacity="1T",
            capacity_bytes=1_000,
            used="100B",
            used_bytes=100,
            available="900B",
            available_bytes=900,
            utilization_percent=10,
        ),
        jellyfin=JellyfinSnapshot(
            server_name="Atlas",
            version="10.10.0",
            id="server-1",
            libraries=(),
            users=(),
            counts=JellyfinCounts(
                movies=100,
                series=200,
                episodes=300,
                songs=50,
                albums=5,
                books=60,
                total_items=715,
            ),
        ),
        libraries=FilesystemLibraries(
            movies=FilesystemLibrary(10),
            tv=FilesystemLibrary(20),
            anime_movies=FilesystemLibrary(30),
            anime_tv=FilesystemLibrary(40),
        ),
    )


if __name__ == "__main__":
    unittest.main()
