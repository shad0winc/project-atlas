"""Tests for persistent Atlas custom roles."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from atlas.custom_roles import (
    CustomRoleDefinition,
    CustomRoleError,
    CustomRoleStore,
)


class CustomRoleStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary_directory.name) / "identity" / "custom_roles.json"
        self.store = CustomRoleStore(
            self.path,
            reserved_names=("owner", "global_admin", "member"),
        )
        self.store.initialize()

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    @staticmethod
    def sports_role() -> CustomRoleDefinition:
        return CustomRoleDefinition(
            name="sports_coordinator",
            display_name="Sports Admin",
            description="Manage Atlas sports request access.",
            permissions=frozenset({"sports.read", "sports.events.request"}),
        )

    def test_initialize_creates_bounded_empty_store(self) -> None:
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(payload, {"roles": [], "schema_version": 1})
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o640)

    def test_create_round_trips_role(self) -> None:
        created = self.store.create(self.sports_role())
        loaded = self.store.get("SPORTS_COORDINATOR")
        self.assertEqual(loaded, created)
        self.assertEqual(self.store.list_roles(), (created,))

    def test_rejects_built_in_name_collision(self) -> None:
        with self.assertRaisesRegex(CustomRoleError, "built-in"):
            self.store.create(
                CustomRoleDefinition(
                    name="member",
                    display_name="Replacement Member",
                    description="Must never replace the built-in role.",
                    permissions=frozenset({"sports.read"}),
                )
            )

    def test_rejects_duplicate_custom_role(self) -> None:
        self.store.create(self.sports_role())
        with self.assertRaisesRegex(CustomRoleError, "already exists"):
            self.store.create(self.sports_role())

    def test_update_preserves_role_name(self) -> None:
        self.store.create(self.sports_role())
        updated = self.store.update(
            "sports_coordinator",
            display_name="Sports Operations",
            description="Updated sports access.",
            permissions=("sports.read",),
            assignable=False,
        )
        self.assertEqual(updated.name, "sports_coordinator")
        self.assertEqual(updated.permissions, frozenset({"sports.read"}))
        self.assertFalse(updated.assignable)

    def test_delete_rejects_assigned_role(self) -> None:
        self.store.create(self.sports_role())
        with self.assertRaisesRegex(CustomRoleError, "assigned"):
            self.store.delete("sports_coordinator", assigned_roles=("sports_coordinator",))
        self.assertIsNotNone(self.store.get("sports_coordinator"))

    def test_delete_unassigned_role(self) -> None:
        self.store.create(self.sports_role())
        self.store.delete("sports_coordinator", assigned_roles=("member",))
        self.assertIsNone(self.store.get("sports_coordinator"))

    def test_rejects_invalid_permission_pattern(self) -> None:
        with self.assertRaisesRegex(CustomRoleError, "namespace and action"):
            CustomRoleDefinition(
                name="bad_role",
                display_name="Bad Role",
                description="Invalid permission test.",
                permissions=frozenset({"invalid"}),
            )

    def test_rejects_unknown_store_fields(self) -> None:
        self.path.write_text(
            json.dumps({"schema_version": 1, "roles": [], "unexpected": True}),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(CustomRoleError, "schema is invalid"):
            self.store.list_roles()


if __name__ == "__main__":
    unittest.main()
