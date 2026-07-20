from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from atlas.favorites import FavoriteError, FavoriteStore

USER_A = "usr_" + "a" * 32
USER_B = "usr_" + "b" * 32
NOW = datetime(2026, 7, 19, 22, 0, tzinfo=timezone.utc)


class FavoriteStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = FavoriteStore(self.root, clock=lambda: NOW)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_initializes_empty_registry(self) -> None:
        self.store.initialize()
        self.assertTrue(self.store.records_directory.is_dir())
        data = json.loads(self.store.registry_file.read_text())
        self.assertEqual(data, {"schema_version": 1, "favorites": {}})

    def test_add_persists_metadata_relationship(self) -> None:
        record = self.store.add(
            USER_A, "jellyfin", "abc123", media_type="movie", title="Arrival",
            metadata={"library": "Movies"},
        )
        self.assertEqual(record["created_at"], "2026-07-19T22:00:00Z")
        self.assertEqual(self.store.get(record["favorite_id"]), record)
        self.assertEqual(self.store.find(USER_A, "jellyfin", "abc123"), record)
        self.assertFalse(any(path.is_symlink() for path in self.root.rglob("*")))

    def test_duplicate_relationship_is_rejected(self) -> None:
        self.store.add(USER_A, "jellyfin", "item-1", media_type="tv")
        with self.assertRaisesRegex(FavoriteError, "already exists"):
            self.store.add(USER_A, "jellyfin", "item-1", media_type="tv")
        self.store.add(USER_B, "jellyfin", "item-1", media_type="tv")

    def test_list_filters_by_user_provider_and_type(self) -> None:
        first = self.store.add(USER_A, "jellyfin", "1", media_type="movie")
        self.store.add(USER_A, "sports", "2", media_type="sports")
        self.store.add(USER_B, "jellyfin", "3", media_type="movie")
        self.assertEqual(self.store.list(user_id=USER_A, provider="jellyfin"), [first])
        self.assertEqual(len(self.store.list(media_type="movie")), 2)

    def test_remove_updates_registry_and_deletes_record(self) -> None:
        record = self.store.add(USER_A, "jellyfin", "1", media_type="anime")
        path = self.store._record_file(record["favorite_id"])
        removed = self.store.remove(record["favorite_id"])
        self.assertEqual(removed, record)
        self.assertFalse(path.exists())
        self.assertIsNone(self.store.find(USER_A, "jellyfin", "1"))

    def test_validation_rejects_bad_values_and_large_metadata(self) -> None:
        with self.assertRaises(FavoriteError):
            self.store.add("not-a-user", "jellyfin", "1", media_type="movie")
        with self.assertRaises(FavoriteError):
            self.store.add(USER_A, "Bad Provider!", "1", media_type="movie")
        with self.assertRaises(FavoriteError):
            self.store.add(USER_A, "jellyfin", "1", media_type="book")
        with self.assertRaises(FavoriteError):
            self.store.add(USER_A, "jellyfin", "1", media_type="movie", metadata={"x": "y" * 9000})

    def test_verify_detects_registry_mismatch_orphan_and_escape(self) -> None:
        record = self.store.add(USER_A, "jellyfin", "1", media_type="movie")
        registry = json.loads(self.store.registry_file.read_text())
        registry["favorites"][record["favorite_id"]]["item_id"] = "wrong"
        self.store.registry_file.write_text(json.dumps(registry))
        orphan = self.store.records_directory / ("fav_" + "f" * 32 + ".json")
        orphan.write_text("{}")
        errors = self.store.verify()
        self.assertTrue(any("item_id does not match" in error for error in errors))
        self.assertTrue(any("unregistered favorite record" in error for error in errors))

        registry["favorites"][record["favorite_id"]]["path"] = "../../escape.json"
        self.store.registry_file.write_text(json.dumps(registry))
        self.assertTrue(any("escapes favorites directory" in error for error in self.store.verify()))


if __name__ == "__main__":
    unittest.main()
