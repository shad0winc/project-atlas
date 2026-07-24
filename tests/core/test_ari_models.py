"""Tests for normalized Atlas Retention Intelligence models."""

from __future__ import annotations

import unittest

from atlas.ari import (
    ARIError,
    ARIReport,
    AtlasMetadata,
    FilesystemLibraries,
    FilesystemLibrary,
    JellyfinCounts,
    JellyfinLibrary,
    JellyfinSnapshot,
    JellyfinUser,
    StorageSnapshot,
)


class AtlasMetadataTests(unittest.TestCase):
    """Validate Atlas snapshot metadata."""

    def test_normalizes_and_serializes_metadata(
        self,
    ) -> None:
        metadata = AtlasMetadata(
            version=" 0.9.0-rc.1 ",
            hostname=" docker ",
            schema_version=1,
        )

        self.assertEqual(
            "0.9.0-rc.1",
            metadata.version,
        )
        self.assertEqual(
            "docker",
            metadata.hostname,
        )
        self.assertEqual(
            {
                "version": "0.9.0-rc.1",
                "hostname": "docker",
                "schema_version": 1,
            },
            metadata.to_dict(),
        )

    def test_creates_metadata_from_snapshot_mapping(
        self,
    ) -> None:
        metadata = AtlasMetadata.from_dict(
            {
                "version": "0.9.0-rc.1",
                "hostname": "docker",
                "schema_version": 1,
            },
        )

        self.assertEqual(
            "0.9.0-rc.1",
            metadata.version,
        )
        self.assertEqual(
            1,
            metadata.schema_version,
        )

    def test_rejects_invalid_metadata(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ARIError,
            "version is required",
        ):
            AtlasMetadata(
                version="",
                hostname="docker",
                schema_version=1,
            )

        with self.assertRaisesRegex(
            ARIError,
            "schema_version must be a positive integer",
        ):
            AtlasMetadata(
                version="0.9.0-rc.1",
                hostname="docker",
                schema_version=0,
            )

        with self.assertRaisesRegex(
            ARIError,
            "atlas must be an object",
        ):
            AtlasMetadata.from_dict(
                [],  # type: ignore[arg-type]
            )


class StorageSnapshotTests(unittest.TestCase):
    """Validate ARI storage metrics."""

    def test_normalizes_and_serializes_storage(
        self,
    ) -> None:
        storage = StorageSnapshot(
            media_root=" /mnt/storage/media ",
            capacity="1.8T",
            capacity_bytes=1967846068224,
            used="1.4G",
            used_bytes=1473740800,
            available="1.7T",
            available_bytes=1866335657984,
            utilization_percent=1,
        )

        self.assertEqual(
            "/mnt/storage/media",
            storage.media_root,
        )
        self.assertEqual(
            {
                "media_root": "/mnt/storage/media",
                "capacity": "1.8T",
                "capacity_bytes": 1967846068224,
                "used": "1.4G",
                "used_bytes": 1473740800,
                "available": "1.7T",
                "available_bytes": 1866335657984,
                "utilization_percent": 1,
            },
            storage.to_dict(),
        )

    def test_creates_storage_from_snapshot_mapping(
        self,
    ) -> None:
        payload = {
            "media_root": "/mnt/storage/media",
            "capacity": "1.8T",
            "capacity_bytes": 1967846068224,
            "used": "1.4G",
            "used_bytes": 1473740800,
            "available": "1.7T",
            "available_bytes": 1866335657984,
            "utilization_percent": 1,
        }

        storage = StorageSnapshot.from_dict(payload)

        self.assertEqual(
            payload,
            storage.to_dict(),
        )

    def test_rejects_invalid_byte_metrics(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ARIError,
            "used_bytes must be a nonnegative integer",
        ):
            StorageSnapshot(
                media_root="/mnt/storage/media",
                capacity="1.8T",
                capacity_bytes=100,
                used="unknown",
                used_bytes=-1,
                available="unknown",
                available_bytes=100,
                utilization_percent=0,
            )

        with self.assertRaisesRegex(
            ARIError,
            "used_bytes cannot exceed capacity_bytes",
        ):
            StorageSnapshot(
                media_root="/mnt/storage/media",
                capacity="100B",
                capacity_bytes=100,
                used="101B",
                used_bytes=101,
                available="0B",
                available_bytes=0,
                utilization_percent=100,
            )

    def test_rejects_invalid_utilization(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ARIError,
            "utilization_percent must be between 0 and 100",
        ):
            StorageSnapshot(
                media_root="/mnt/storage/media",
                capacity="1.8T",
                capacity_bytes=100,
                used="unknown",
                used_bytes=0,
                available="unknown",
                available_bytes=100,
                utilization_percent=101,
            )

        with self.assertRaisesRegex(
            ARIError,
            "utilization_percent must be a nonnegative integer",
        ):
            StorageSnapshot(
                media_root="/mnt/storage/media",
                capacity="1.8T",
                capacity_bytes=100,
                used="unknown",
                used_bytes=0,
                available="unknown",
                available_bytes=100,
                utilization_percent=True,
            )

    def test_rejects_nonobject_storage_payload(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ARIError,
            "storage must be an object",
        ):
            StorageSnapshot.from_dict(
                "invalid",
            )


class JellyfinLibraryTests(unittest.TestCase):
    """Validate Jellyfin library snapshot contracts."""

    def test_normalizes_and_serializes_library(
        self,
    ) -> None:
        library = JellyfinLibrary(
            name=" Movies ",
            type=" MOVIES ",
            path=" /media/Movies ",
            status=" Idle ",
        )

        self.assertEqual("Movies", library.name)
        self.assertEqual("movies", library.type)
        self.assertEqual(
            {
                "name": "Movies",
                "type": "movies",
                "path": "/media/Movies",
                "status": "Idle",
            },
            library.to_dict(),
        )

    def test_creates_library_from_mapping(
        self,
    ) -> None:
        payload = {
            "name": "TV",
            "type": "tvshows",
            "path": "/media/TV",
            "status": "Idle",
        }

        self.assertEqual(
            payload,
            JellyfinLibrary.from_dict(payload).to_dict(),
        )

    def test_rejects_invalid_library(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ARIError,
            "name is required",
        ):
            JellyfinLibrary(
                name="",
                type="movies",
                path="/media/Movies",
                status="Idle",
            )

        with self.assertRaisesRegex(
            ARIError,
            "jellyfin library must be an object",
        ):
            JellyfinLibrary.from_dict([])


class JellyfinUserTests(unittest.TestCase):
    """Validate Jellyfin user snapshot contracts."""

    def test_normalizes_user_and_activity_timestamp(
        self,
    ) -> None:
        user = JellyfinUser(
            name=" root ",
            id=" user-123 ",
            administrator=True,
            disabled=False,
            hidden=True,
            last_activity="2026-07-13T08:58:23-04:00",
        )

        self.assertEqual("root", user.name)
        self.assertEqual("user-123", user.id)
        self.assertEqual(
            "2026-07-13T12:58:23Z",
            user.last_activity,
        )
        self.assertEqual(
            {
                "name": "root",
                "id": "user-123",
                "administrator": True,
                "disabled": False,
                "hidden": True,
                "last_activity": "2026-07-13T12:58:23Z",
            },
            user.to_dict(),
        )

    def test_preserves_null_last_activity(
        self,
    ) -> None:
        user = JellyfinUser.from_dict(
            {
                "name": "admin",
                "id": "user-456",
                "administrator": False,
                "disabled": False,
                "hidden": True,
                "last_activity": None,
            },
        )

        self.assertIsNone(user.last_activity)

    def test_rejects_invalid_user_values(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ARIError,
            "administrator must be a boolean",
        ):
            JellyfinUser(
                name="root",
                id="user-123",
                administrator=1,  # type: ignore[arg-type]
                disabled=False,
                hidden=True,
            )

        with self.assertRaisesRegex(
            ARIError,
            "last_activity must include a timezone",
        ):
            JellyfinUser(
                name="root",
                id="user-123",
                administrator=True,
                disabled=False,
                hidden=True,
                last_activity="2026-07-13T12:58:23",
            )


class JellyfinCountsTests(unittest.TestCase):
    """Validate Jellyfin media-count contracts."""

    def test_serializes_media_counts(
        self,
    ) -> None:
        counts = JellyfinCounts(
            movies=4,
            series=3,
            episodes=25,
            songs=10,
            albums=2,
            books=1,
            total_items=45,
        )

        self.assertEqual(
            {
                "movies": 4,
                "series": 3,
                "episodes": 25,
                "songs": 10,
                "albums": 2,
                "books": 1,
                "total_items": 45,
            },
            counts.to_dict(),
        )

    def test_creates_counts_from_mapping(
        self,
    ) -> None:
        payload = {
            "movies": 0,
            "series": 0,
            "episodes": 0,
            "songs": 0,
            "albums": 0,
            "books": 0,
            "total_items": 0,
        }

        self.assertEqual(
            payload,
            JellyfinCounts.from_dict(payload).to_dict(),
        )

    def test_rejects_invalid_count(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ARIError,
            "movies must be a nonnegative integer",
        ):
            JellyfinCounts(
                movies=-1,
                series=0,
                episodes=0,
                songs=0,
                albums=0,
                books=0,
                total_items=0,
            )

        with self.assertRaisesRegex(
            ARIError,
            "total_items must be a nonnegative integer",
        ):
            JellyfinCounts(
                movies=0,
                series=0,
                episodes=0,
                songs=0,
                albums=0,
                books=0,
                total_items=True,  # type: ignore[arg-type]
            )

class FilesystemLibraryTests(unittest.TestCase):
    def test_serializes_library(self):
        library = FilesystemLibrary(count=42)

        self.assertEqual(
            {"count": 42},
            library.to_dict(),
        )

    def test_rejects_invalid_count(self):
        with self.assertRaisesRegex(
            ARIError,
            "count must be a nonnegative integer",
        ):
            FilesystemLibrary(count=-1)


class FilesystemLibrariesTests(unittest.TestCase):
    def test_serializes_collection(self):
        libraries = FilesystemLibraries(
            movies=FilesystemLibrary(1),
            tv=FilesystemLibrary(2),
            anime_movies=FilesystemLibrary(3),
            anime_tv=FilesystemLibrary(4),
        )

        self.assertEqual(
            {
                "movies": {"count": 1},
                "tv": {"count": 2},
                "anime_movies": {"count": 3},
                "anime_tv": {"count": 4},
            },
            libraries.to_dict(),
        )

    def test_builds_from_mapping(self):
        payload = {
            "movies": {"count": 1},
            "tv": {"count": 2},
            "anime_movies": {"count": 3},
            "anime_tv": {"count": 4},
        }

        self.assertEqual(
            payload,
            FilesystemLibraries.from_dict(payload).to_dict(),
        )

    def test_rejects_invalid_member(self):
        with self.assertRaisesRegex(
            ARIError,
            "movies must be a FilesystemLibrary",
        ):
            FilesystemLibraries(
                movies="invalid",
                tv=FilesystemLibrary(0),
                anime_movies=FilesystemLibrary(0),
                anime_tv=FilesystemLibrary(0),
            )

class JellyfinSnapshotTests(unittest.TestCase):
    """Validate the composite Jellyfin snapshot contract."""

    def test_builds_and_serializes_snapshot(
        self,
    ) -> None:
        payload = {
            "server_name": "Atlas Jellyfin",
            "version": "10.10.7",
            "id": "server-123",
            "libraries": [
                {
                    "name": "Movies",
                    "type": "movies",
                    "path": "/media/Movies",
                    "status": "Idle",
                },
                {
                    "name": "TV",
                    "type": "tvshows",
                    "path": "/media/TV",
                    "status": "Idle",
                },
            ],
            "users": [
                {
                    "name": "admin",
                    "id": "user-123",
                    "administrator": True,
                    "disabled": False,
                    "hidden": False,
                    "last_activity": "2026-07-22T20:00:00-04:00",
                },
            ],
            "counts": {
                "movies": 4,
                "series": 3,
                "episodes": 25,
                "songs": 0,
                "albums": 0,
                "books": 0,
                "total_items": 32,
            },
        }

        snapshot = JellyfinSnapshot.from_dict(payload)

        self.assertIsInstance(
            snapshot.libraries,
            tuple,
        )
        self.assertIsInstance(
            snapshot.users,
            tuple,
        )
        self.assertEqual(
            "2026-07-23T00:00:00Z",
            snapshot.users[0].last_activity,
        )

        expected = {
            **payload,
            "users": [
                {
                    **payload["users"][0],
                    "last_activity": "2026-07-23T00:00:00Z",
                },
            ],
        }

        self.assertEqual(
            expected,
            snapshot.to_dict(),
        )

    def test_accepts_empty_library_and_user_arrays(
        self,
    ) -> None:
        snapshot = JellyfinSnapshot.from_dict(
            {
                "server_name": "Atlas Jellyfin",
                "version": "10.10.7",
                "id": "server-123",
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
        )

        self.assertEqual((), snapshot.libraries)
        self.assertEqual((), snapshot.users)

    def test_rejects_invalid_snapshot_members(
        self,
    ) -> None:
        counts = JellyfinCounts(
            movies=0,
            series=0,
            episodes=0,
            songs=0,
            albums=0,
            books=0,
            total_items=0,
        )

        with self.assertRaisesRegex(
            ARIError,
            "libraries must contain JellyfinLibrary",
        ):
            JellyfinSnapshot(
                server_name="Atlas Jellyfin",
                version="10.10.7",
                id="server-123",
                libraries=("invalid",),
                users=(),
                counts=counts,
            )

        with self.assertRaisesRegex(
            ARIError,
            "jellyfin users must be an array",
        ):
            JellyfinSnapshot.from_dict(
                {
                    "server_name": "Atlas Jellyfin",
                    "version": "10.10.7",
                    "id": "server-123",
                    "libraries": [],
                    "users": {},
                    "counts": counts.to_dict(),
                },
            )


class ARIReportTests(unittest.TestCase):
    """Validate the complete ARI snapshot contract."""

    @staticmethod
    def _payload(
        *,
        schema_version: int = 1,
    ) -> dict:
        return {
            "timestamp": "2026-07-22T20:30:00-04:00",
            "atlas": {
                "version": "0.9.0-rc.1",
                "hostname": "docker",
                "schema_version": schema_version,
            },
            "storage": {
                "media_root": "/mnt/storage/media",
                "capacity": "1.8T",
                "capacity_bytes": 1967846068224,
                "used": "1.4G",
                "used_bytes": 1473740800,
                "available": "1.7T",
                "available_bytes": 1866335657984,
                "utilization_percent": 1,
            },
            "jellyfin": {
                "server_name": "Atlas Jellyfin",
                "version": "10.10.7",
                "id": "server-123",
                "libraries": [
                    {
                        "name": "Movies",
                        "type": "movies",
                        "path": "/media/Movies",
                        "status": "Idle",
                    },
                ],
                "users": [
                    {
                        "name": "admin",
                        "id": "user-123",
                        "administrator": True,
                        "disabled": False,
                        "hidden": False,
                        "last_activity": None,
                    },
                ],
                "counts": {
                    "movies": 4,
                    "series": 3,
                    "episodes": 25,
                    "songs": 0,
                    "albums": 0,
                    "books": 0,
                    "total_items": 32,
                },
            },
            "libraries": {
                "movies": {"count": 4},
                "tv": {"count": 3},
                "anime_movies": {"count": 0},
                "anime_tv": {"count": 0},
            },
        }

    def test_builds_complete_report(
        self,
    ) -> None:
        report = ARIReport.from_dict(
            self._payload(),
        )

        self.assertEqual(
            "2026-07-23T00:30:00Z",
            report.timestamp,
        )
        self.assertEqual(
            "docker",
            report.atlas.hostname,
        )
        self.assertEqual(
            1473740800,
            report.storage.used_bytes,
        )
        self.assertEqual(
            "Movies",
            report.jellyfin.libraries[0].name,
        )
        self.assertEqual(
            4,
            report.jellyfin.counts.movies,
        )
        self.assertEqual(
            4,
            report.libraries.movies.count,
        )

    def test_round_trip_preserves_snapshot_contract(
        self,
    ) -> None:
        payload = self._payload()

        expected = {
            **payload,
            "timestamp": "2026-07-23T00:30:00Z",
        }

        report = ARIReport.from_dict(payload)

        self.assertEqual(
            expected,
            report.to_dict(),
        )

    def test_rejects_unsupported_schema_version(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            ARIError,
            "unsupported ARI schema_version: 2",
        ):
            ARIReport.from_dict(
                self._payload(
                    schema_version=2,
                ),
            )

    def test_rejects_naive_report_timestamp(
        self,
    ) -> None:
        payload = self._payload()
        payload["timestamp"] = "2026-07-23T00:30:00"

        with self.assertRaisesRegex(
            ARIError,
            "timestamp must include a timezone",
        ):
            ARIReport.from_dict(payload)

    def test_rejects_invalid_nested_model(
        self,
    ) -> None:
        payload = self._payload()
        payload["storage"] = []

        with self.assertRaisesRegex(
            ARIError,
            "storage must be an object",
        ):
            ARIReport.from_dict(payload)


if __name__ == "__main__":
    unittest.main()
