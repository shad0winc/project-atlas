"""User-profile assignment contracts for persistent Atlas custom roles."""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from atlas.custom_roles import (
    CustomRoleDefinition,
    CustomRoleStore,
)
from atlas.user_profiles import (
    UserProfileError,
    UserProfileStore,
    VALID_ROLES,
)


class UserProfileCustomRoleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        root = Path(self.temporary_directory.name)
        self.profile_root = root / "users"
        self.custom_role_path = root / "identity" / "custom_roles.json"
        self.environment = patch.dict(
            os.environ,
            {"ATLAS_CUSTOM_ROLES_PATH": str(self.custom_role_path)},
        )
        self.environment.start()

        self.custom_roles = CustomRoleStore(
            self.custom_role_path,
            reserved_names=VALID_ROLES,
        )
        self.custom_roles.initialize()
        self.custom_roles.create(
            CustomRoleDefinition(
                name="sports_coordinator",
                display_name="Sports Administrator",
                description="Administers Atlas sports services.",
                permissions=frozenset({"sports.*"}),
            )
        )
        self.profiles = UserProfileStore(self.profile_root)

    def tearDown(self) -> None:
        self.environment.stop()
        self.temporary_directory.cleanup()

    def test_create_user_accepts_persisted_custom_role(self) -> None:
        profile = self.profiles.create_user(
            "sportsuser",
            roles=("sports_coordinator",),
        )
        self.assertEqual(profile["roles"], ["sports_coordinator"])

    def test_read_user_accepts_persisted_custom_role(self) -> None:
        created = self.profiles.create_user(
            "sportsuser",
            roles=("sports_coordinator",),
        )
        loaded = self.profiles.get_user(created["user_id"])
        self.assertEqual(loaded["roles"], ["sports_coordinator"])

    def test_update_user_accepts_persisted_custom_role(self) -> None:
        created = self.profiles.create_user("sportsuser")
        updated = self.profiles.update_user(
            created["user_id"],
            {"roles": ["sports_coordinator"]},
        )
        self.assertEqual(updated["roles"], ["sports_coordinator"])

    def test_builtin_and_custom_roles_can_be_composed(self) -> None:
        profile = self.profiles.create_user(
            "sportsuser",
            roles=("member", "sports_coordinator"),
        )
        self.assertEqual(profile["roles"], ["member", "sports_coordinator"])

    def test_unknown_role_still_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            UserProfileError,
            "profile role must be one of",
        ):
            self.profiles.create_user(
                "sportsuser",
                roles=("does_not_exist",),
            )

    def test_removed_custom_role_is_not_accepted_for_new_assignment(self) -> None:
        self.custom_roles.delete("sports_coordinator")
        with self.assertRaisesRegex(
            UserProfileError,
            "profile role must be one of",
        ):
            self.profiles.create_user(
                "sportsuser",
                roles=("sports_coordinator",),
            )
