"""Permission resolution and authorization evaluation for Atlas."""

from __future__ import annotations

from fnmatch import fnmatchcase
from typing import Mapping

from atlas_api.authorization.catalog import (
    BUILT_IN_ROLES,
    normalize_role_name,
)
from atlas_api.authorization.models import (
    AuthorizationDecision,
    AuthorizationEffect,
    AuthorizationSubject,
    EffectivePermissions,
    RoleDefinition,
    normalize_permission,
    normalize_permission_patterns,
    normalize_role_names,
)


class AuthorizationService:
    """Resolve roles and evaluate Atlas permissions."""

    def __init__(
        self,
        roles: Mapping[str, RoleDefinition] | None = None,
    ) -> None:
        self._roles = roles if roles is not None else BUILT_IN_ROLES

    def resolve(
        self,
        subject: AuthorizationSubject,
    ) -> EffectivePermissions:
        """Resolve effective permission patterns for a subject."""

        normalized_input_roles = normalize_role_names(subject.roles)
        resolved_roles: list[str] = []
        unknown_roles: list[str] = []
        permissions_by_role: dict[str, frozenset[str]] = {}
        grants: set[str] = set()

        for input_role in normalized_input_roles:
            normalized_role = normalize_role_name(input_role)

            if normalized_role not in resolved_roles:
                resolved_roles.append(normalized_role)

            definition = self._roles.get(normalized_role)

            if definition is None:
                unknown_roles.append(normalized_role)
                continue

            permissions_by_role[normalized_role] = definition.permissions
            grants.update(definition.permissions)

        direct_grants = normalize_permission_patterns(
            subject.granted_permissions
        )
        denials = normalize_permission_patterns(
            subject.denied_permissions
        )

        grants.update(direct_grants)

        return EffectivePermissions(
            user_id=subject.user_id,
            roles=tuple(resolved_roles),
            granted_permissions=frozenset(grants),
            denied_permissions=denials,
            permissions_by_role=permissions_by_role,
            unknown_roles=tuple(unknown_roles),
        )

    def evaluate(
        self,
        subject: AuthorizationSubject,
        permission: str,
    ) -> AuthorizationDecision:
        """Evaluate one concrete permission for a subject."""

        required_permission = normalize_permission(permission)
        effective = self.resolve(subject)

        if not subject.active:
            return AuthorizationDecision(
                effect=AuthorizationEffect.DENY,
                permission=required_permission,
                subject_id=subject.user_id,
                roles=effective.roles,
                reason="The Atlas user is not active.",
            )

        matched_denial = self._best_match(
            effective.denied_permissions,
            required_permission,
        )

        if matched_denial is not None:
            return AuthorizationDecision(
                effect=AuthorizationEffect.DENY,
                permission=required_permission,
                subject_id=subject.user_id,
                matched_denial=matched_denial,
                roles=effective.roles,
                reason=(
                    "The requested permission is explicitly denied."
                ),
            )

        matched_grant = self._best_match(
            effective.granted_permissions,
            required_permission,
        )

        if matched_grant is None:
            return AuthorizationDecision(
                effect=AuthorizationEffect.DENY,
                permission=required_permission,
                subject_id=subject.user_id,
                roles=effective.roles,
                reason=(
                    "No assigned role or direct grant provides the "
                    "requested permission."
                ),
            )

        return AuthorizationDecision(
            effect=AuthorizationEffect.ALLOW,
            permission=required_permission,
            subject_id=subject.user_id,
            matched_grant=matched_grant,
            roles=effective.roles,
            reason="The requested permission is granted.",
        )

    def is_allowed(
        self,
        subject: AuthorizationSubject,
        permission: str,
    ) -> bool:
        """Return whether a subject has one concrete permission."""

        return self.evaluate(subject, permission).allowed

    @staticmethod
    def _best_match(
        patterns: frozenset[str],
        permission: str,
    ) -> str | None:
        matches = [
            pattern
            for pattern in patterns
            if _permission_matches(pattern, permission)
        ]

        if not matches:
            return None

        return max(
            matches,
            key=_permission_specificity,
        )


def _permission_matches(pattern: str, permission: str) -> bool:
    if pattern == "*":
        return True

    return fnmatchcase(permission, pattern)


def _permission_specificity(pattern: str) -> tuple[int, int]:
    if pattern == "*":
        return (0, 0)

    concrete_components = sum(
        component != "*"
        for component in pattern.split(".")
    )

    return (
        concrete_components,
        len(pattern),
    )
