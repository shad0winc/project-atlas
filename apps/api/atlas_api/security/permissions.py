"""Pure authorization helpers used by Atlas API security dependencies."""

from __future__ import annotations

from typing import Any, Mapping

from atlas_api.authorization import (
    AuthorizationDecision,
    AuthorizationService,
    AuthorizationSubject,
    normalize_role_name,
)


def build_authorization_subject(
    profile: Mapping[str, Any],
) -> AuthorizationSubject:
    """Build an authorization subject from a validated Atlas profile."""

    overrides = profile.get("permission_overrides", {})
    if not isinstance(overrides, Mapping):
        raise ValueError("Profile permission overrides must be a mapping.")

    roles = profile.get("roles", ())
    if isinstance(roles, str):
        roles = (roles,)
    if not isinstance(roles, (list, tuple)):
        raise ValueError("Profile roles must be a list or tuple.")

    return AuthorizationSubject(
        user_id=_required_string(profile, "user_id"),
        roles=tuple(str(role) for role in roles),
        granted_permissions=frozenset(
            _permission_values(overrides.get("allow", ()), "allow")
        ),
        denied_permissions=frozenset(
            _permission_values(overrides.get("deny", ()), "deny")
        ),
        active=profile.get("status") == "active",
    )


def evaluate_permission(
    profile: Mapping[str, Any],
    permission: str,
    *,
    authorization: AuthorizationService | None = None,
) -> AuthorizationDecision:
    """Evaluate one permission against an Atlas profile."""

    service = authorization or AuthorizationService()
    return service.evaluate(
        build_authorization_subject(profile),
        permission,
    )


def subject_has_role(
    profile: Mapping[str, Any],
    role: str,
    *,
    authorization: AuthorizationService | None = None,
) -> bool:
    """Return whether an Atlas profile resolves to the requested role."""

    service = authorization or AuthorizationService()
    effective = service.resolve(build_authorization_subject(profile))
    return normalize_role_name(role) in effective.roles


def _permission_values(
    value: object,
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(
        value,
        (list, tuple, set, frozenset),
    ):
        raise ValueError(
            f"Permission override '{field_name}' must be a list."
        )

    return tuple(str(permission) for permission in value)


def _required_string(
    profile: Mapping[str, Any],
    field_name: str,
) -> str:
    value = profile.get(field_name)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Profile field '{field_name}' must be a non-empty string."
        )

    return value.strip()
