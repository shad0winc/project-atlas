"""Role-based authorization primitives for the Atlas API."""

from atlas_api.authorization.catalog import (
    ATLAS_ADMIN_ROLE,
    BUILT_IN_ROLES,
    CHECK_RUNNER_ROLE,
    GAME_SERVER_ADMIN_ROLE,
    GLOBAL_ADMIN_ROLE,
    MEDIA_ADMIN_ROLE,
    LEGACY_ROLE_ALIASES,
    MEMBER_ROLE,
    MONITORING_ADMIN_ROLE,
    OPERATOR_ROLE,
    OWNER_ROLE,
    READ_ONLY_ROLE,
    SPORTS_ADMIN_ROLE,
    get_role,
    is_protected_role,
    list_roles,
    normalize_role_name,
    require_role,
)
from atlas_api.authorization.models import (
    AuthorizationDecision,
    AuthorizationEffect,
    AuthorizationSubject,
    EffectivePermissions,
    RoleDefinition,
)
from atlas_api.authorization.runtime_catalog import (
    RuntimeRoleCatalogError,
    authorization_service_for_store,
    compose_role_catalog,
    custom_role_definition,
)
from atlas_api.authorization.service import AuthorizationService


__all__ = [
    "ATLAS_ADMIN_ROLE",
    "AuthorizationDecision",
    "AuthorizationEffect",
    "AuthorizationService",
    "AuthorizationSubject",
    "BUILT_IN_ROLES",
    "CHECK_RUNNER_ROLE",
    "EffectivePermissions",
    "GAME_SERVER_ADMIN_ROLE",
    "GLOBAL_ADMIN_ROLE",
    "MEDIA_ADMIN_ROLE",
    "LEGACY_ROLE_ALIASES",
    "MEMBER_ROLE",
    "MONITORING_ADMIN_ROLE",
    "OPERATOR_ROLE",
    "OWNER_ROLE",
    "READ_ONLY_ROLE",
    "SPORTS_ADMIN_ROLE",
    "RoleDefinition",
    "RuntimeRoleCatalogError",
    "authorization_service_for_store",
    "compose_role_catalog",
    "custom_role_definition",
    "get_role",
    "is_protected_role",
    "list_roles",
    "normalize_role_name",
    "require_role",
]
