"""Tests for normalized media-library detail contracts."""

from __future__ import annotations

import unittest

from atlas.media import (
    MEDIA_LIBRARY_IDS,
    MediaLibraryDetail,
    MediaLibraryFilesystem,
    MediaLibraryProvider,
    MediaLibraryValidation,
)


class MediaLibraryFilesystemTests(unittest.TestCase):
    """Validate media-library filesystem contracts."""

    def test_normalizes_and_serializes_filesystem(self) -> None:
        filesystem = MediaLibraryFilesystem(
            path=" /mnt/storage/media/Movies ",
            item_count=12,
        )

        self.assertEqual(
            {
                "path": "/mnt/storage/media/Movies",
                "item_count": 12,
            },
            filesystem.to_dict(),
        )

    def test_rejects_invalid_item_count(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "nonnegative integer",
        ):
            MediaLibraryFilesystem(
                path="/mnt/storage/media/Movies",
                item_count=-1,
            )


class MediaLibraryProviderTests(unittest.TestCase):
    """Validate media-library provider contracts."""

    def test_normalizes_and_serializes_provider(self) -> None:
        provider = MediaLibraryProvider(
            name=" Jellyfin ",
            library_name=" Movies ",
            library_type=" Movies ",
            path=" /media/Movies ",
            status=" Available ",
        )

        self.assertEqual(
            {
                "name": "jellyfin",
                "library_name": "Movies",
                "library_type": "movies",
                "path": "/media/Movies",
                "status": "available",
            },
            provider.to_dict(),
        )


class MediaLibraryValidationTests(unittest.TestCase):
    """Validate media-library validation contracts."""

    def test_normalizes_and_serializes_validation(self) -> None:
        validation = MediaLibraryValidation(
            configured=True,
            path_matches=True,
            synchronization="synchronized",
        )

        self.assertEqual(
            {
                "configured": True,
                "path_matches": True,
                "synchronization": "synchronized",
            },
            validation.to_dict(),
        )

    def test_rejects_invalid_boolean_values(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "configured must be a boolean",
        ):
            MediaLibraryValidation(
                configured=1,
                path_matches=None,
                synchronization="unknown",
            )

    def test_rejects_invalid_synchronization(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "synchronization must be",
        ):
            MediaLibraryValidation(
                configured=False,
                path_matches=None,
                synchronization="invalid",
            )


class MediaLibraryDetailTests(unittest.TestCase):
    """Validate complete media-library detail contracts."""

    def test_stable_library_identity_matches_summary_contract(self) -> None:
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
            MEDIA_LIBRARY_IDS,
        )

    def test_normalizes_children_timestamp_and_serialization(self) -> None:
        detail = MediaLibraryDetail(
            id=" MOVIES ",
            label=" Movies ",
            status="available",
            generated_at="2026-07-27T19:00:00-04:00",
            count=12,
            detail=" Filesystem library count ",
            filesystem=MediaLibraryFilesystem(
                path=" /mnt/storage/media/Movies ",
                item_count=12,
            ),
            provider=MediaLibraryProvider(
                name=" Jellyfin ",
                library_name=" Movies ",
                library_type=" Movies ",
                path=" /media/Movies ",
                status=" Available ",
            ),
            validation=MediaLibraryValidation(
                configured=True,
                path_matches=True,
                synchronization="synchronized",
            ),
        )

        self.assertEqual("movies", detail.id)
        self.assertEqual(
            "2026-07-27T23:00:00Z",
            detail.generated_at,
        )
        self.assertEqual(
            {
                "id": "movies",
                "label": "Movies",
                "status": "available",
                "generated_at": "2026-07-27T23:00:00Z",
                "count": 12,
                "detail": "Filesystem library count",
                "filesystem": {
                    "path": "/mnt/storage/media/Movies",
                    "item_count": 12,
                },
                "provider": {
                    "name": "jellyfin",
                    "library_name": "Movies",
                    "library_type": "movies",
                    "path": "/media/Movies",
                    "status": "available",
                },
                "validation": {
                    "configured": True,
                    "path_matches": True,
                    "synchronization": "synchronized",
                },
            },
            detail.to_dict(),
        )

    def test_from_dict_validates_child_contracts(self) -> None:
        detail = MediaLibraryDetail.from_dict(
            {
                "id": "photos",
                "label": "Photos",
                "status": "unavailable",
                "generated_at": "2026-07-27T23:00:00Z",
                "count": None,
                "detail": "Photo counts are unavailable",
                "filesystem": None,
                "provider": None,
                "validation": {
                    "configured": False,
                    "path_matches": None,
                    "synchronization": "unknown",
                },
            }
        )

        self.assertEqual("photos", detail.id)
        self.assertIsNone(detail.filesystem)
        self.assertIsNone(detail.provider)
        self.assertEqual(
            "unknown",
            detail.validation.synchronization,
        )

    def test_rejects_unknown_library_identity(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "unsupported media library ID",
        ):
            MediaLibraryDetail(
                id="games",
                label="Games",
                status="unavailable",
                generated_at="2026-07-27T23:00:00Z",
                count=None,
                validation=MediaLibraryValidation(
                    configured=False,
                    path_matches=None,
                    synchronization="unknown",
                ),
            )

    def test_rejects_inconsistent_availability(self) -> None:
        validation = MediaLibraryValidation(
            configured=False,
            path_matches=None,
            synchronization="unknown",
        )

        with self.assertRaisesRegex(
            ValueError,
            "require a count",
        ):
            MediaLibraryDetail(
                id="movies",
                label="Movies",
                status="available",
                generated_at="2026-07-27T23:00:00Z",
                count=None,
                validation=validation,
            )

        with self.assertRaisesRegex(
            ValueError,
            "cannot have a count",
        ):
            MediaLibraryDetail(
                id="photos",
                label="Photos",
                status="unavailable",
                generated_at="2026-07-27T23:00:00Z",
                count=1,
                validation=validation,
            )

    def test_rejects_unvalidated_child_values(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "filesystem must be",
        ):
            MediaLibraryDetail(
                id="movies",
                label="Movies",
                status="available",
                generated_at="2026-07-27T23:00:00Z",
                count=1,
                filesystem={
                    "path": "/mnt/storage/media/Movies",
                    "item_count": 1,
                },
                validation=MediaLibraryValidation(
                    configured=False,
                    path_matches=None,
                    synchronization="unknown",
                ),
            )


if __name__ == "__main__":
    unittest.main()
