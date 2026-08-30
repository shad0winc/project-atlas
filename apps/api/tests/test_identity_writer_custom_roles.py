"""Identity Writer profile-store wiring for persistent custom roles."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("ATLAS_IDENTITY_WRITER_TOKEN", "test-only-identity-writer-token")

from atlas.custom_roles import CustomRoleDefinition, CustomRoleStore
from atlas.user_profiles import UserProfileStore, VALID_ROLES
from atlas_api.identity_writer import _user_store


def test_identity_writer_store_accepts_persisted_custom_role() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        users = root / "users"
        custom_roles = root / "identity" / "custom_roles.json"

        environment = {
            "ATLAS_USERS_DIR": str(users),
            "ATLAS_CUSTOM_ROLES_PATH": str(custom_roles),
        }

        with patch.dict(os.environ, environment, clear=False):
            role_store = CustomRoleStore(
                custom_roles,
                reserved_names=VALID_ROLES,
            )
            role_store.initialize()
            role_store.create(
                CustomRoleDefinition(
                    name="support_operator",
                    display_name="Support Operator",
                    description="A persisted custom role used by writer wiring tests.",
                    permissions=frozenset({"monitoring.read"}),
                )
            )

            base_store = UserProfileStore(
                users,
                profile_directory_mode=0o2770,
            )
            created = base_store.create_user("supportuser")

            updated = _user_store().update_user(
                created["user_id"],
                {"roles": ["support_operator"]},
            )

            assert updated["roles"] == ["support_operator"]
