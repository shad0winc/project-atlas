"""Core identity contracts for built-in service administrator roles."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from atlas.custom_roles import CustomRoleDefinition, CustomRoleError, CustomRoleStore
from atlas.user_profiles import UserProfileStore, VALID_ROLES


def test_media_and_sports_administrator_roles_are_profile_assignable() -> None:
    with tempfile.TemporaryDirectory() as directory:
        store = UserProfileStore(Path(directory) / "users")

        media = store.create_user("mediaadmin", roles=("media_admin",))
        sports = store.create_user("sportsadmin", roles=("sports_admin",))

        assert media["roles"] == ["media_admin"]
        assert sports["roles"] == ["sports_admin"]


def test_service_admin_names_are_reserved_from_custom_roles() -> None:
    assert "media_admin" in VALID_ROLES
    assert "sports_admin" in VALID_ROLES

    with tempfile.TemporaryDirectory() as directory:
        store = CustomRoleStore(
            Path(directory) / "custom_roles.json",
            reserved_names=VALID_ROLES,
        )
        store.initialize()

        with pytest.raises(CustomRoleError, match="conflicts with a built-in role"):
            store.create(
                CustomRoleDefinition(
                    name="sports_admin",
                    display_name="Shadow Sports Admin",
                    description="Must never shadow the built-in role.",
                    permissions=frozenset({"sports.read"}),
                )
            )
