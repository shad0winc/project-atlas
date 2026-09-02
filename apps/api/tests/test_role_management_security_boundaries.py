"""PR73 role-management security-boundary regressions."""
from __future__ import annotations
import os
from pathlib import Path
import pytest
os.environ.setdefault("ATLAS_IDENTITY_WRITER_TOKEN", "test-only-token")
from atlas.custom_roles import CustomRoleDefinition, CustomRoleStore
from atlas.user_profiles import VALID_ROLES
from atlas_api.identity_writer import _assert_role_assignable, _validate_custom_role_permissions
from atlas_api.security.dependencies import get_authorization_service


def test_custom_permissions_are_bounded() -> None:
    _validate_custom_role_permissions(frozenset({"sports.read", "sports.*"}))
    with pytest.raises(Exception): _validate_custom_role_permissions(frozenset({"*"}))
    with pytest.raises(Exception): _validate_custom_role_permissions(frozenset({"invented.permission"}))


def test_owner_is_not_assignable() -> None:
    with pytest.raises(Exception): _assert_role_assignable("owner")


def test_runtime_authorization_reads_custom_role(tmp_path: Path, monkeypatch) -> None:
    path=tmp_path / "custom_roles.json"
    monkeypatch.setenv("ATLAS_CUSTOM_ROLES_PATH", str(path))
    store=CustomRoleStore(path, reserved_names=VALID_ROLES)
    store.initialize()
    store.create(CustomRoleDefinition(name="sports_coordinator", display_name="Sports Coordinator", description="Coordinates sports.", permissions=frozenset({"sports.read"})))
    assert "sports_coordinator" in get_authorization_service()._roles
