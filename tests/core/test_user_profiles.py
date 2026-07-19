from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas.user_cli import main as user_cli_main
from atlas.user_profiles import UserProfileError, UserProfileStore


class UserProfileStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "users"
        self.store = UserProfileStore(self.root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_initializes_empty_registry(self) -> None:
        self.store.initialize()
        registry = json.loads((self.root / "users.json").read_text())
        self.assertEqual(registry, {"schema_version": 1, "users": {}})

    def test_creates_and_reads_normalized_profile(self) -> None:
        profile = self.store.create_user(
            "  Michael  ",
            display_name="Michael",
            email="MICHAEL@EXAMPLE.COM",
            birthday="1990-01-01",
            role="admin",
        )
        self.assertTrue(profile["user_id"].startswith("usr_"))
        self.assertEqual(profile["username"], "michael")
        self.assertEqual(profile["email"], "michael@example.com")
        self.assertEqual(self.store.get_user("michael"), profile)
        self.assertEqual(self.store.get_user(profile["user_id"]), profile)

    def test_rejects_duplicate_username(self) -> None:
        self.store.create_user("michael")
        with self.assertRaisesRegex(UserProfileError, "username already exists"):
            self.store.create_user("MICHAEL")

    def test_rejects_duplicate_email(self) -> None:
        self.store.create_user("michael", email="family@example.com")
        with self.assertRaisesRegex(UserProfileError, "email already exists"):
            self.store.create_user("sarah", email="FAMILY@example.com")

    def test_rejects_invalid_username_role_birthday_and_jellyfin_id(self) -> None:
        invalid = (
            ("ab", {}, "username must"),
            ("valid", {"role": "owner"}, "role must"),
            ("valid", {"birthday": "not-a-date"}, "birthday must"),
            ("valid", {"jellyfin_user_id": "short"}, "Jellyfin user ID"),
        )
        for username, arguments, message in invalid:
            with self.subTest(message=message):
                with self.assertRaisesRegex(UserProfileError, message):
                    self.store.create_user(username, **arguments)

    def test_updates_profile_and_registry(self) -> None:
        profile = self.store.create_user("michael")
        updated = self.store.update_user(
            profile["user_id"],
            {
                "username": "mike",
                "status": "disabled",
                "jellyfin_user_id": "a" * 32,
            },
        )
        self.assertEqual(updated["username"], "mike")
        self.assertEqual(updated["status"], "disabled")
        self.assertEqual(updated["jellyfin_user_id"], "a" * 32)
        registry = json.loads((self.root / "users.json").read_text())
        self.assertEqual(registry["users"][profile["user_id"]]["username"], "mike")
        self.assertEqual(registry["users"][profile["user_id"]]["status"], "disabled")

    def test_lists_users_in_username_order(self) -> None:
        self.store.create_user("zach")
        self.store.create_user("alice")
        self.assertEqual(
            [profile["username"] for profile in self.store.list_users()],
            ["alice", "zach"],
        )

    def test_verify_detects_registry_mismatch(self) -> None:
        profile = self.store.create_user("michael")
        registry_file = self.root / "users.json"
        registry = json.loads(registry_file.read_text())
        registry["users"][profile["user_id"]]["status"] = "disabled"
        registry_file.write_text(json.dumps(registry), encoding="utf-8")
        errors = self.store.verify()
        self.assertEqual(len(errors), 1)
        self.assertIn("registry status does not match profile", errors[0])


class UserProfileCliTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "users"

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def invoke(self, *arguments: str) -> int:
        return user_cli_main(["--users-directory", str(self.root), *arguments])

    def test_create_list_disable_enable_and_verify(self) -> None:
        self.assertEqual(self.invoke("create", "michael", "--role", "admin"), 0)
        self.assertEqual(self.invoke("list"), 0)
        self.assertEqual(self.invoke("disable", "michael"), 0)
        self.assertEqual(self.invoke("enable", "michael"), 0)
        self.assertEqual(self.invoke("verify"), 0)

    def test_update_requires_changes(self) -> None:
        self.assertEqual(self.invoke("create", "michael"), 0)
        self.assertEqual(self.invoke("update", "michael"), 1)


if __name__ == "__main__":
    unittest.main()
