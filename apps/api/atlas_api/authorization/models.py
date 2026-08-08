"""Core models for Atlas role-based authorization."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Iterable, Mapping


class AuthorizationEffect(StrEnum):
    """Possible outcomes of an Atlas authorization evaluation."""

    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True, slots=True)
class RoleDefinition:
    """Immutable definition of an Atlas authorization role."""

    name: str
    display_name: str
    description: str
    permissions: frozenset[str]
    protected: bool = False
    assignable: bool = True

    def __post_init__(self) -> None:
        normalized_name = self.name.strip().lower()

        if not normalized_name:
            raise ValueError("Role name cannot be empty.")

        if normalized_name != self.name:
            raise ValueError(
                "Role names must already be normalized lowercase values."
            )

        if not self.display_name.strip():
            raise ValueError("Role display name cannot be empty.")

        if not self.description.strip():
            raise ValueError("Role description cannot be empty.")

        for permission in self.permissions:
            _validate_permission_pattern(permission)


@dataclass(frozen=True, slots=True)
class AuthorizationSubject:
    """Authorization inputs associated with one Atlas user."""

    user_id: str
    roles: tuple[str, ...] = ()
    granted_permissions: frozenset[str] = frozenset()
    denied_permissions: frozenset[str] = frozenset()
    active: bool = True

    def __post_init__(self) -> None:
        if not self.user_id.strip():
            raise ValueError("Authorization subject user ID cannot be empty.")

        for role in self.roles:
            if not role.strip():
                raise ValueError("Authorization role names cannot be empty.")

        for permission in self.granted_permissions:
            _validate_permission_pattern(permission)

        for permission in self.denied_permissions:
            _validate_permission_pattern(permission)


@dataclass(frozen=True, slots=True)
class EffectivePermissions:
    """Resolved permissions and provenance for an authorization subject."""

    user_id: str
    roles: tuple[str, ...]
    granted_permissions: frozenset[str]
    denied_permissions: frozenset[str]
    permissions_by_role: Mapping[str, frozenset[str]]
    unknown_roles: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        immutable_mapping = MappingProxyType(
            {
                role: frozenset(permissions)
                for role, permissions in self.permissions_by_role.items()
            }
        )

        object.__setattr__(
            self,
            "permissions_by_role",
            immutable_mapping,
        )


@dataclass(frozen=True, slots=True)
class AuthorizationDecision:
    """Result of evaluating one required Atlas permission."""

    effect: AuthorizationEffect
    permission: str
    subject_id: str
    matched_grant: str | None = None
    matched_denial: str | None = None
    roles: tuple[str, ...] = ()
    reason: str = ""

    @property
    def allowed(self) -> bool:
        """Return whether access was granted."""

        return self.effect is AuthorizationEffect.ALLOW


def normalize_role_names(roles: Iterable[str]) -> tuple[str, ...]:
    """Normalize and deduplicate role names while preserving order."""

    normalized: list[str] = []
    seen: set[str] = set()

    for role in roles:
        value = role.strip().lower()

        if not value:
            raise ValueError("Authorization role names cannot be empty.")

        if value not in seen:
            normalized.append(value)
            seen.add(value)

    return tuple(normalized)


def normalize_permission(permission: str) -> str:
    """Normalize and validate one concrete permission name."""

    normalized = permission.strip().lower()
    _validate_concrete_permission(normalized)
    return normalized


def normalize_permission_patterns(
    permissions: Iterable[str],
) -> frozenset[str]:
    """Normalize and validate permission patterns."""

    normalized: set[str] = set()

    for permission in permissions:
        value = permission.strip().lower()
        _validate_permission_pattern(value)
        normalized.add(value)

    return frozenset(normalized)


def _validate_concrete_permission(permission: str) -> None:
    if not permission:
        raise ValueError("Permission cannot be empty.")

    if "*" in permission:
        raise ValueError(
            "A requested permission must be concrete and cannot contain '*'."
        )

    _validate_permission_components(permission)


def _validate_permission_pattern(permission: str) -> None:
    if not permission:
        raise ValueError("Permission pattern cannot be empty.")

    if permission == "*":
        return

    if permission.count("*") > 1:
        raise ValueError(
            "Permission patterns may contain at most one wildcard."
        )

    if "*" in permission:
        components = permission.split(".")

        if "*" not in components:
            raise ValueError(
                "Permission wildcards must occupy a complete namespace component."
            )

        if components.count("*") != 1:
            raise ValueError(
                "Permission patterns may contain only one wildcard component."
            )

        non_wildcard_components = [
            component
            for component in components
            if component != "*"
        ]

        if not non_wildcard_components:
            raise ValueError(
                "Use '*' for unrestricted access."
            )

        for component in non_wildcard_components:
            _validate_permission_component(component)

        return

    _validate_permission_components(permission)


def _validate_permission_components(permission: str) -> None:
    components = permission.split(".")

    if len(components) < 2:
        raise ValueError(
            "Permissions must contain a namespace and action."
        )

    for component in components:
        _validate_permission_component(component)


def _validate_permission_component(component: str) -> None:
    if not component:
        raise ValueError(
            "Permission components cannot be empty."
        )

    if not component.replace("_", "").replace("-", "").isalnum():
        raise ValueError(
            "Permission components may contain only letters, numbers, "
            "underscores, and hyphens."
        )
