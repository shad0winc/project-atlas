"""Authorization contracts for user-facing Atlas media requests."""

from atlas_api.authorization.catalog import require_role


def test_member_can_read_create_and_cancel_own_requests() -> None:
    permissions = require_role("member").permissions

    assert "requests.read" in permissions
    assert "requests.create" in permissions
    assert "requests.cancel" in permissions


def test_read_only_role_does_not_receive_request_mutations() -> None:
    permissions = require_role("read_only").permissions

    assert "*.read" in permissions
    assert "requests.create" not in permissions
    assert "requests.cancel" not in permissions


def test_request_administrators_continue_to_use_namespace_wildcard() -> None:
    assert "requests.*" in require_role("global_admin").permissions
    assert "requests.*" in require_role("atlas_admin").permissions
