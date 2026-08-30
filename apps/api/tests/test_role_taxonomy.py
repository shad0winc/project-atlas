"""Built-in Atlas service-administrator role taxonomy contracts."""

from atlas_api.authorization import (
    BUILT_IN_ROLES,
    GLOBAL_ADMIN_ROLE,
    MEDIA_ADMIN_ROLE,
    MEMBER_ROLE,
    SPORTS_ADMIN_ROLE,
)


def test_global_administrator_spans_all_current_service_domains() -> None:
    permissions = BUILT_IN_ROLES[GLOBAL_ADMIN_ROLE].permissions

    assert {
        "atlas.*",
        "audit.*",
        "cleanup.*",
        "downloads.*",
        "favorites.*",
        "gameservers.*",
        "media.*",
        "modules.*",
        "monitoring.*",
        "requests.*",
        "retention.*",
        "roles.*",
        "scheduler.*",
        "sports.*",
        "system.*",
        "users.*",
    } <= permissions


def test_media_administrator_is_focused_to_media_operations() -> None:
    role = BUILT_IN_ROLES[MEDIA_ADMIN_ROLE]

    assert role.display_name == "Media Administrator"
    assert role.assignable is True
    assert role.protected is False
    assert role.permissions == frozenset(
        {
            "cleanup.*",
            "downloads.*",
            "favorites.*",
            "media.*",
            "monitoring.read",
            "requests.*",
            "retention.*",
            "system.health.read",
            "system.logs.read",
        }
    )
    assert "roles.*" not in role.permissions
    assert "users.*" not in role.permissions
    assert "gameservers.*" not in role.permissions
    assert "sports.*" not in role.permissions


def test_member_includes_standard_sports_consumer_permissions() -> None:
    role = BUILT_IN_ROLES[MEMBER_ROLE]

    assert "sports.read" in role.permissions
    assert "sports.events.request" in role.permissions
    assert "sports.*" not in role.permissions


def test_sports_administrator_matches_current_sports_contract_only() -> None:
    role = BUILT_IN_ROLES[SPORTS_ADMIN_ROLE]

    assert role.display_name == "Sports Administrator"
    assert role.assignable is True
    assert role.protected is False
    assert role.permissions == frozenset(
        {
            "sports.events.request",
            "sports.read",
        }
    )
