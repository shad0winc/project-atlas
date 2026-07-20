from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from atlas.favorite_cli import main
from atlas.media.provider import MediaItem
from atlas.favorites import FavoriteStore
from atlas.user_profiles import UserProfileStore


class FavoriteCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.users = UserProfileStore(self.root)
        self.profile = self.users.create_user("michael", display_name="Michael")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_cli(self, *arguments: str) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        provider = unittest.mock.Mock()
        provider.get_item.return_value = MediaItem("jellyfin", "movie-1", "movie", "The Matrix", {"year": 1999})
        with patch("atlas.favorite_cli.default_jellyfin_provider", return_value=provider), \
             patch("atlas.favorite_cli.publish_core_event"), \
             contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(("--identity-directory", str(self.root), *arguments))
        return code, stdout.getvalue(), stderr.getvalue()

    def test_add_show_list_and_remove_by_relationship(self) -> None:
        code, output, error = self.run_cli(
            "add", "--user", "michael", "--provider", "jellyfin",
            "--item-id", "movie-1",
            "--metadata-json", '{"year": 1999}', "--json",
        )
        self.assertEqual(0, code, error)
        record = json.loads(output)
        self.assertEqual(self.profile["user_id"], record["user_id"])
        self.assertEqual({"year": 1999}, record["metadata"])

        code, output, error = self.run_cli("show", record["favorite_id"])
        self.assertEqual(0, code, error)
        self.assertEqual("The Matrix", json.loads(output)["title"])

        code, output, error = self.run_cli("list", "--user", "michael", "--json")
        self.assertEqual(0, code, error)
        self.assertEqual([record], json.loads(output))

        code, output, error = self.run_cli(
            "remove", "--user", "michael", "--provider", "jellyfin",
            "--item-id", "movie-1",
        )
        self.assertEqual(0, code, error)
        self.assertIn("Removed favorite", output)
        self.assertEqual([], FavoriteStore(self.root).list())

    def test_list_filters_and_table_output(self) -> None:
        store = FavoriteStore(self.root)
        store.add(self.profile["user_id"], "jellyfin", "movie-1", media_type="movie", title="Movie")
        store.add(self.profile["user_id"], "plex", "show-1", media_type="tv", title="Show")
        code, output, error = self.run_cli("list", "--provider", "jellyfin")
        self.assertEqual(0, code, error)
        self.assertIn("FAVORITE ID", output)
        self.assertIn("Movie", output)
        self.assertNotIn("Show", output)

    def test_verify_reports_success_and_failure(self) -> None:
        code, output, error = self.run_cli("verify")
        self.assertEqual(0, code, error)
        self.assertEqual("PASS\tfavorites valid\n", output)

        store = FavoriteStore(self.root)
        record = store.add(self.profile["user_id"], "jellyfin", "movie-1", media_type="movie")
        (store.records_directory / f"{record['favorite_id']}.json").unlink()
        code, output, error = self.run_cli("verify")
        self.assertEqual(1, code)
        self.assertIn("FAIL", output)

    def test_invalid_user_and_metadata_return_nonzero(self) -> None:
        code, _, error = self.run_cli(
            "add", "--user", "missing", "--provider", "jellyfin",
            "--item-id", "movie-1",
        )
        self.assertEqual(1, code)
        self.assertIn("user not found", error)

        code, _, error = self.run_cli(
            "add", "--user", "michael", "--provider", "jellyfin",
            "--item-id", "movie-1", "--metadata-json", "[]",
        )
        self.assertEqual(1, code)
        self.assertIn("must be an object", error)

    def test_remove_requires_relationship_context(self) -> None:
        code, _, error = self.run_cli("remove", "--item-id", "movie-1")
        self.assertEqual(1, code)
        self.assertIn("--user and --provider", error)


if __name__ == "__main__":
    unittest.main()
