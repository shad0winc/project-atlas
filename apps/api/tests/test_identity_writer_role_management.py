"""Private Identity Writer custom-role mutation contracts."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi import HTTPException

os.environ.setdefault("ATLAS_IDENTITY_WRITER_TOKEN", "test-only-identity-writer-token")

from atlas.user_profiles import UserProfileStore
from atlas_api.identity_writer import (
    CustomRoleCreateRequest,
    CustomRoleUpdateRequest,
    create_custom_role,
    delete_custom_role,
    update_custom_role,
)


def test_writer_custom_role_crud_and_assigned_delete_guard() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        env = {
            "ATLAS_USERS_DIR": str(root / "users"),
            "ATLAS_CUSTOM_ROLES_PATH": str(root / "identity" / "custom_roles.json"),
        }
        with patch.dict(os.environ, env, clear=False):
            created = create_custom_role(CustomRoleCreateRequest(
                name="sports_coordinator",
                display_name="Sports Coordinator",
                description="Coordinates sports requests.",
                permissions=["sports.read", "sports.events.request"],
            ))
            assert created["name"] == "sports_coordinator"

            updated = update_custom_role(
                "sports_coordinator",
                CustomRoleUpdateRequest(display_name="Sports Operations Coordinator"),
            )
            assert updated["display_name"] == "Sports Operations Coordinator"

            profiles = UserProfileStore(root / "users")
            profiles.create_user("coordinator", roles=("sports_coordinator",))
            with pytest.raises(HTTPException) as error:
                delete_custom_role("sports_coordinator")
            assert error.value.status_code == 409
