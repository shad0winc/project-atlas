"""Runtime composition of built-in and persistent custom Atlas roles.

The immutable built-in catalog remains authoritative for built-in names.
Custom roles are converted into the existing :class:`RoleDefinition` model
and appended only when their names do not collide with built-ins.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Iterable, Mapping

from atlas.custom_roles import CustomRoleDefinition, CustomRoleStore
from atlas_api.authorization.catalog import BUILT_IN_ROLES
from atlas_api.authorization.models import RoleDefinition
from atlas_api.authorization.service import AuthorizationService


class RuntimeRoleCatalogError(RuntimeError):
    """Runtime role catalog composition failed closed."""


def custom_role_definition(
    role: CustomRoleDefinition,
) -> RoleDefinition:
    """Convert one persisted custom role to the canonical API role model."""

    return RoleDefinition(
        name=role.name,
        display_name=role.display_name,
        description=role.description,
        permissions=frozenset(role.permissions),
        protected=False,
        assignable=role.assignable,
    )


def compose_role_catalog(
    custom_roles: Iterable[CustomRoleDefinition] = (),
) -> Mapping[str, RoleDefinition]:
    """Return an immutable built-in + custom role catalog.

    Built-in names are reserved and can never be replaced by persisted data.
    Duplicate custom names also fail closed rather than silently overriding a
    previous definition.
    """

    roles: dict[str, RoleDefinition] = dict(BUILT_IN_ROLES)
    seen_custom: set[str] = set()

    for custom in custom_roles:
        name = custom.name

        if name in BUILT_IN_ROLES:
            raise RuntimeRoleCatalogError(
                f"Custom role '{name}' conflicts with a built-in role."
            )

        if name in seen_custom:
            raise RuntimeRoleCatalogError(
                f"Duplicate custom role '{name}' was provided."
            )

        definition = custom_role_definition(custom)
        roles[name] = definition
        seen_custom.add(name)

    return MappingProxyType(roles)


def authorization_service_for_store(
    store: CustomRoleStore,
) -> AuthorizationService:
    """Build an authorization service from one persistent custom-role store."""

    return AuthorizationService(
        compose_role_catalog(store.list_roles())
    )
