"""Public administrator role-management contract tests."""
from atlas_api.routes.v1.admin_roles import _permission_catalog


def test_permission_catalog_is_bounded_and_excludes_owner_wildcard() -> None:
    permissions = _permission_catalog()
    assert permissions == sorted(set(permissions))
    assert "*" not in permissions
    assert "roles.*" in permissions
    assert "media.*" in permissions
    assert "sports.read" in permissions
    assert "sports.events.request" in permissions
