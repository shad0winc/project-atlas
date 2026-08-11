"""FastAPI authorization dependencies for the Atlas HTTP API."""

from __future__ import annotations

from functools import lru_cache
from typing import Callable

from fastapi import Depends, HTTPException, status

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.authorization import (
    AuthorizationService,
    AuthorizationSubject,
)
from atlas_api.dependencies import (
    get_current_user,
    get_security_audit_writer,
    get_user_profile_store,
)
from atlas_api.security.permissions import (
    evaluate_permission,
    subject_has_role,
)

SecurityDependency = Callable[..., AuthenticatedUser]


@lru_cache(maxsize=1)
def get_authorization_service() -> AuthorizationService:
    """Return the process-wide Atlas authorization service."""

    return AuthorizationService()


def require_permission(permission: str) -> SecurityDependency:
    """Return a dependency requiring one concrete Atlas permission."""

    AuthorizationService().evaluate(
        AuthorizationSubject(user_id="dependency-validation"),
        permission,
    )

    def dependency(
        user: AuthenticatedUser = Depends(get_current_user),
        profiles: UserProfileStore = Depends(get_user_profile_store),
        authorization: AuthorizationService = Depends(
            get_authorization_service
        ),
        audit_writer=Depends(get_security_audit_writer),
    ) -> AuthenticatedUser:
        try:
            profile = _load_current_profile(user, profiles)
        except HTTPException:
            _publish_authorization_denial(
                audit_writer,
                user,
                reason="profile_unavailable_or_inactive",
                permission=permission,
            )
            raise

        decision = evaluate_permission(
            profile,
            permission,
            authorization=authorization,
        )

        if not decision.allowed:
            reason = (
                "explicit_denial"
                if decision.matched_denial is not None
                else "missing_grant"
            )
            _publish_authorization_denial(
                audit_writer,
                user,
                reason=reason,
                permission=decision.permission,
            )
            raise _forbidden(decision.reason)

        return user

    return dependency


def require_role(role: str) -> SecurityDependency:
    """Return a dependency requiring one resolved Atlas role."""

    normalized_role = role.strip().lower()
    if not normalized_role:
        raise ValueError("Required role cannot be empty.")

    def dependency(
        user: AuthenticatedUser = Depends(get_current_user),
        profiles: UserProfileStore = Depends(get_user_profile_store),
        authorization: AuthorizationService = Depends(
            get_authorization_service
        ),
        audit_writer=Depends(get_security_audit_writer),
    ) -> AuthenticatedUser:
        try:
            profile = _load_current_profile(user, profiles)
        except HTTPException:
            _publish_authorization_denial(
                audit_writer,
                user,
                reason="profile_unavailable_or_inactive",
                required_role=normalized_role,
            )
            raise

        if not subject_has_role(
            profile,
            normalized_role,
            authorization=authorization,
        ):
            _publish_authorization_denial(
                audit_writer,
                user,
                reason="missing_role",
                required_role=normalized_role,
            )
            raise _forbidden(
                f"The Atlas role '{normalized_role}' is required."
            )

        return user

    return dependency


def _publish_authorization_denial(
    audit_writer,
    user: AuthenticatedUser,
    *,
    reason: str,
    permission: str | None = None,
    required_role: str | None = None,
) -> None:
    # Direct unit calls may leave FastAPI's Depends marker unresolved. Runtime
    # requests always receive the composed SecurityAuditWriter instance.
    if not hasattr(audit_writer, "publish"):
        return

    payload = {
        "user_id": user.user_id,
        "username": user.username,
        "provider": user.provider,
        "reason": reason,
    }
    if permission is not None:
        payload["permission"] = permission
    if required_role is not None:
        payload["required_role"] = required_role

    audit_writer.publish(
        "security.authorization.denied",
        payload,
    )


def clear_security_dependency_caches() -> None:
    """Clear cached security dependencies for controlled reconfiguration."""

    get_authorization_service.cache_clear()


def _load_current_profile(
    user: AuthenticatedUser,
    profiles: UserProfileStore,
) -> dict[str, object]:
    try:
        profile = profiles.get_user(user.user_id)
    except UserProfileError as error:
        raise _unauthorized(
            "Authenticated Atlas user was not found."
        ) from error

    if profile["status"] != "active":
        raise _unauthorized("Authenticated Atlas user is disabled.")

    return profile


def _unauthorized(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=message,
        headers={"WWW-Authenticate": "Bearer"},
    )


def _forbidden(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=message,
    )
