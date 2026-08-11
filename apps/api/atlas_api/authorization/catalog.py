"""Built-in Atlas authorization roles and permission catalog."""

from __future__ import annotations

from types import MappingProxyType
from typing import Mapping

from atlas_api.authorization.models import RoleDefinition


OWNER_ROLE = "owner"
GLOBAL_ADMIN_ROLE = "global_admin"
ATLAS_ADMIN_ROLE = "atlas_admin"
GAME_SERVER_ADMIN_ROLE = "gameserver_admin"
MONITORING_ADMIN_ROLE = "monitoring_admin"
OPERATOR_ROLE = "operator"
CHECK_RUNNER_ROLE = "check_runner"
READ_ONLY_ROLE = "read_only"
MEMBER_ROLE = "member"

LEGACY_ROLE_ALIASES: Mapping[str, str] = MappingProxyType(
    {
        "admin": GLOBAL_ADMIN_ROLE,
        "user": MEMBER_ROLE,
        "games_admin": GAME_SERVER_ADMIN_ROLE,
        "readonly": READ_ONLY_ROLE,
    }
)


_BUILT_IN_ROLES: dict[str, RoleDefinition] = {
    OWNER_ROLE: RoleDefinition(
        name=OWNER_ROLE,
        display_name="Owner",
        description=(
            "Protected platform owner with unrestricted Atlas access."
        ),
        permissions=frozenset({"*"}),
        protected=True,
        assignable=False,
    ),
    GLOBAL_ADMIN_ROLE: RoleDefinition(
        name=GLOBAL_ADMIN_ROLE,
        display_name="Global Administrator",
        description=(
            "Administers all Atlas categories except protected Owner actions."
        ),
        permissions=frozenset(
            {
                "atlas.*",
                "audit.*",
                "cleanup.*",
                "favorites.*",
                "gameservers.*",
                "media.*",
                "modules.*",
                "monitoring.*",
                "requests.*",
                "retention.*",
                "roles.*",
                "scheduler.*",
                "system.*",
                "users.*",
            }
        ),
    ),
    ATLAS_ADMIN_ROLE: RoleDefinition(
        name=ATLAS_ADMIN_ROLE,
        display_name="Atlas Administrator",
        description=(
            "Administers core Atlas services without game-server or "
            "security administration."
        ),
        permissions=frozenset(
            {
                "atlas.*",
                "cleanup.*",
                "favorites.*",
                "media.*",
                "modules.read",
                "monitoring.read",
                "requests.*",
                "retention.*",
                "scheduler.*",
                "system.health.read",
                "system.logs.read",
            }
        ),
    ),
    GAME_SERVER_ADMIN_ROLE: RoleDefinition(
        name=GAME_SERVER_ADMIN_ROLE,
        display_name="Game Server Administrator",
        description=(
            "Creates, configures, operates, and backs up game servers."
        ),
        permissions=frozenset(
            {
                "gameservers.*",
                "monitoring.read",
                "system.health.read",
                "system.logs.read",
            }
        ),
    ),
    MONITORING_ADMIN_ROLE: RoleDefinition(
        name=MONITORING_ADMIN_ROLE,
        display_name="Monitoring Administrator",
        description=(
            "Administers monitoring, metrics, alerts, health, and log access."
        ),
        permissions=frozenset(
            {
                "monitoring.*",
                "system.checks.run",
                "system.health.read",
                "system.logs.read",
            }
        ),
    ),
    OPERATOR_ROLE: RoleDefinition(
        name=OPERATOR_ROLE,
        display_name="Operator",
        description=(
            "Runs approved operational actions without changing policy "
            "or security configuration."
        ),
        permissions=frozenset(
            {
                "cleanup.run",
                "gameservers.restart",
                "gameservers.start",
                "gameservers.stop",
                "monitoring.read",
                "scheduler.run",
                "system.checks.run",
                "system.health.read",
                "system.logs.read",
            }
        ),
    ),
    CHECK_RUNNER_ROLE: RoleDefinition(
        name=CHECK_RUNNER_ROLE,
        display_name="Check Runner",
        description=(
            "Runs health and verification checks without configuration access."
        ),
        permissions=frozenset(
            {
                "monitoring.read",
                "system.checks.run",
                "system.health.read",
            }
        ),
    ),
    READ_ONLY_ROLE: RoleDefinition(
        name=READ_ONLY_ROLE,
        display_name="Read Only",
        description=(
            "Reads Atlas resources without performing mutations."
        ),
        permissions=frozenset(
            {
                "*.read",
            }
        ),
    ),
    MEMBER_ROLE: RoleDefinition(
        name=MEMBER_ROLE,
        display_name="Member",
        description=(
            "Uses standard Atlas user-facing features."
        ),
        permissions=frozenset(
            {
                "atlas.dashboard.read",
                "favorites.read",
                "favorites.write",
                "media.read",
                "requests.cancel",
                "requests.create",
                "requests.read",
                "users.self.read",
                "users.self.update",
            }
        ),
    ),
}

BUILT_IN_ROLES: Mapping[str, RoleDefinition] = MappingProxyType(
    _BUILT_IN_ROLES
)


def normalize_role_name(role_name: str) -> str:
    """Normalize a role name and apply legacy compatibility aliases."""

    normalized = role_name.strip().lower()

    if not normalized:
        raise ValueError("Role name cannot be empty.")

    return LEGACY_ROLE_ALIASES.get(normalized, normalized)


def get_role(role_name: str) -> RoleDefinition | None:
    """Return one built-in role after alias resolution."""

    return BUILT_IN_ROLES.get(normalize_role_name(role_name))


def require_role(role_name: str) -> RoleDefinition:
    """Return one built-in role or raise when it is unknown."""

    normalized = normalize_role_name(role_name)
    role = BUILT_IN_ROLES.get(normalized)

    if role is None:
        raise KeyError(f"Unknown Atlas role: {normalized}")

    return role


def list_roles() -> tuple[RoleDefinition, ...]:
    """Return all built-in roles in catalog order."""

    return tuple(BUILT_IN_ROLES.values())


def is_protected_role(role_name: str) -> bool:
    """Return whether a role has protected platform semantics."""

    role = get_role(role_name)
    return role is not None and role.protected
