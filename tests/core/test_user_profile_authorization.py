"""Tests for user-profile roles, overrides, and schema migration."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas.user_cli import main as user_cli_main
from atlas.user_profiles import (
    PROFILE_SCHEMA_VERSION,
    UserProfileError,
    UserProfileStore,
)


class UserProfileAuthorizationTests(unittest.TestCase):
    """Validate current role and permission-override behavior."""

    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )
        self.root = (
            Path(self.temporary_directory.name)
            / "users"
        )
        self.store = UserProfileStore(self.root)

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def test_new_profile_uses_schema_two(self) -> None:
        profile = self.store.create_user("michael")

        self.assertEqual(
            profile["schema_version"],
            PROFILE_SCHEMA_VERSION,
        )
        self.assertEqual(
            profile["roles"],
            ["member"],
        )
        self.assertEqual(
            profile["permission_overrides"],
            {
                "allow": [],
                "deny": [],
            },
        )
        self.assertNotIn("role", profile)

    def test_legacy_role_argument_is_mapped(self) -> None:
        admin = self.store.create_user(
            "michael",
            role="admin",
        )
        member = self.store.create_user(
            "friend",
            role="user",
        )

        self.assertEqual(
            admin["roles"],
            ["global_admin"],
        )
        self.assertEqual(
            member["roles"],
            ["member"],
        )

    def test_multiple_roles_are_persisted(self) -> None:
        profile = self.store.create_user(
            "michael",
            roles=(
                "atlas_admin",
                "monitoring_admin",
            ),
        )

        loaded = self.store.get_user(
            profile["user_id"]
        )

        self.assertEqual(
            loaded["roles"],
            [
                "atlas_admin",
                "monitoring_admin",
            ],
        )

    def test_duplicate_roles_are_removed(self) -> None:
        profile = self.store.create_user(
            "michael",
            roles=(
                "operator",
                "operator",
                "monitoring_admin",
            ),
        )

        self.assertEqual(
            profile["roles"],
            [
                "operator",
                "monitoring_admin",
            ],
        )

    def test_permission_overrides_are_persisted(self) -> None:
        profile = self.store.create_user(
            "michael",
            permission_overrides={
                "allow": [
                    "system.checks.run",
                    "system.checks.run",
                ],
                "deny": [
                    "users.delete",
                ],
            },
        )

        self.assertEqual(
            profile["permission_overrides"],
            {
                "allow": [
                    "system.checks.run",
                ],
                "deny": [
                    "users.delete",
                ],
            },
        )

    def test_updates_roles_and_permission_overrides(self) -> None:
        profile = self.store.create_user("michael")

        updated = self.store.update_user(
            profile["user_id"],
            {
                "roles": [
                    "atlas_admin",
                    "monitoring_admin",
                ],
                "granted_permissions": [
                    "system.checks.run",
                ],
                "denied_permissions": [
                    "users.delete",
                ],
            },
        )

        self.assertEqual(
            updated["roles"],
            [
                "atlas_admin",
                "monitoring_admin",
            ],
        )
        self.assertEqual(
            updated["permission_overrides"],
            {
                "allow": [
                    "system.checks.run",
                ],
                "deny": [
                    "users.delete",
                ],
            },
        )

    def test_rejects_role_and_roles_together(self) -> None:
        with self.assertRaisesRegex(
            UserProfileError,
            "cannot be provided together",
        ):
            self.store.create_user(
                "michael",
                role="admin",
                roles=("member",),
            )

    def test_rejects_invalid_profile_role(self) -> None:
        with self.assertRaisesRegex(
            UserProfileError,
            "profile role must be one of",
        ):
            self.store.create_user(
                "michael",
                roles=("invalid_role",),
            )

    def test_rejects_invalid_permission_pattern(self) -> None:
        with self.assertRaisesRegex(
            UserProfileError,
            "namespace and action",
        ):
            self.store.create_user(
                "michael",
                permission_overrides={
                    "allow": ["invalid"],
                    "deny": [],
                },
            )

    def test_owner_cannot_be_disabled(self) -> None:
        owner = self.store.create_user(
            "michael",
            roles=("owner",),
        )

        with self.assertRaisesRegex(
            UserProfileError,
            "cannot be disabled",
        ):
            self.store.update_user(
                owner["user_id"],
                {"status": "disabled"},
            )

    def test_owner_role_cannot_be_removed(self) -> None:
        owner = self.store.create_user(
            "michael",
            roles=("owner",),
        )

        with self.assertRaisesRegex(
            UserProfileError,
            "cannot be removed",
        ):
            self.store.update_user(
                owner["user_id"],
                {"roles": ["global_admin"]},
            )

    def test_owner_cannot_be_deleted(self) -> None:
        owner = self.store.create_user(
            "michael",
            roles=("owner",),
        )

        with self.assertRaisesRegex(
            UserProfileError,
            "cannot be deleted",
        ):
            self.store.delete_user(
                owner["user_id"]
            )


class LegacyProfileMigrationTests(unittest.TestCase):
    """Validate transparent profile schema migration."""

    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )
        self.root = (
            Path(self.temporary_directory.name)
            / "users"
        )
        self.store = UserProfileStore(self.root)
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def write_legacy_profile(
        self,
        *,
        role: str,
    ) -> tuple[str, Path]:
        user_id = (
            "usr_0123456789abcdef"
            "0123456789abcdef"
        )
        profile_path = (
            self.root
            / "profiles"
            / user_id
            / "profile.json"
        )
        profile_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        legacy = {
            "schema_version": 1,
            "user_id": user_id,
            "username": "michael",
            "display_name": "Michael",
            "first_name": None,
            "last_name": None,
            "email": None,
            "birthday": None,
            "role": role,
            "status": "active",
            "jellyfin_user_id": None,
            "created_at": "2026-07-25T19:22:15Z",
            "updated_at": "2026-07-25T19:22:15Z",
        }

        profile_path.write_text(
            json.dumps(legacy),
            encoding="utf-8",
        )

        registry = {
            "schema_version": 1,
            "users": {
                user_id: {
                    "username": "michael",
                    "status": "active",
                    "profile": (
                        f"profiles/{user_id}/profile.json"
                    ),
                }
            },
        }

        self.store.registry_file.write_text(
            json.dumps(registry),
            encoding="utf-8",
        )

        return user_id, profile_path

    def test_admin_profile_migrates_to_global_admin(
        self,
    ) -> None:
        user_id, profile_path = (
            self.write_legacy_profile(role="admin")
        )

        profile = self.store.get_user(user_id)
        persisted = json.loads(
            profile_path.read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(
            profile["roles"],
            ["global_admin"],
        )
        self.assertEqual(
            persisted["schema_version"],
            PROFILE_SCHEMA_VERSION,
        )
        self.assertEqual(
            persisted["roles"],
            ["global_admin"],
        )
        self.assertNotIn("role", persisted)

    def test_user_profile_migrates_to_member(
        self,
    ) -> None:
        user_id, _ = self.write_legacy_profile(
            role="user"
        )

        profile = self.store.get_user(user_id)

        self.assertEqual(
            profile["roles"],
            ["member"],
        )
        self.assertEqual(
            profile["permission_overrides"],
            {
                "allow": [],
                "deny": [],
            },
        )


class UserProfileAuthorizationCliTests(
    unittest.TestCase
):
    """Validate CLI support for role assignments and overrides."""

    def setUp(self) -> None:
        self.temporary_directory = (
            tempfile.TemporaryDirectory()
        )
        self.root = (
            Path(self.temporary_directory.name)
            / "users"
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def invoke(self, *arguments: str) -> int:
        return user_cli_main(
            [
                "--users-directory",
                str(self.root),
                *arguments,
            ]
        )

    def test_cli_creates_multi_role_profile(self) -> None:
        result = self.invoke(
            "create",
            "michael",
            "--roles",
            "atlas_admin",
            "monitoring_admin",
            "--grant",
            "system.checks.run",
            "--deny",
            "users.delete",
        )

        self.assertEqual(result, 0)

        profile = UserProfileStore(
            self.root
        ).get_user("michael")

        self.assertEqual(
            profile["roles"],
            [
                "atlas_admin",
                "monitoring_admin",
            ],
        )
        self.assertEqual(
            profile["permission_overrides"],
            {
                "allow": [
                    "system.checks.run",
                ],
                "deny": [
                    "users.delete",
                ],
            },
        )

    def test_cli_preserves_legacy_role_alias(self) -> None:
        result = self.invoke(
            "create",
            "michael",
            "--role",
            "admin",
        )

        self.assertEqual(result, 0)

        profile = UserProfileStore(
            self.root
        ).get_user("michael")

        self.assertEqual(
            profile["roles"],
            ["global_admin"],
        )


if __name__ == "__main__":
    unittest.main()
