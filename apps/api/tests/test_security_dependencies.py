from __future__ import annotations

import unittest
from unittest.mock import Mock

from fastapi import HTTPException

from atlas.user_profiles import UserProfileError
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.authorization import AuthorizationService
from atlas_api.security.dependencies import (
    require_permission,
    require_role,
)
from atlas_api.security.permissions import (
    build_authorization_subject,
    evaluate_permission,
    subject_has_role,
)


def _profile(
    *,
    roles: list[str] | None = None,
    allow: list[str] | None = None,
    deny: list[str] | None = None,
    status: str = "active",
) -> dict[str, object]:
    return {
        "user_id": "usr_test",
        "roles": roles or ["member"],
        "permission_overrides": {
            "allow": allow or [],
            "deny": deny or [],
        },
        "status": status,
    }


def _user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="usr_test",
        username="michael",
        display_name="Michael",
        roles=("member",),
        provider="jellyfin",
        metadata={},
    )


class SecurityPermissionTests(unittest.TestCase):
    def test_builds_subject_from_profile(self) -> None:
        subject = build_authorization_subject(
            _profile(
                roles=["atlas_admin", "monitoring_admin"],
                allow=["system.checks.run"],
                deny=["users.delete"],
            )
        )

        self.assertEqual(subject.user_id, "usr_test")
        self.assertEqual(
            subject.roles,
            ("atlas_admin", "monitoring_admin"),
        )
        self.assertEqual(
            subject.granted_permissions,
            frozenset({"system.checks.run"}),
        )
        self.assertEqual(
            subject.denied_permissions,
            frozenset({"users.delete"}),
        )
        self.assertTrue(subject.active)

    def test_evaluates_role_permission(self) -> None:
        decision = evaluate_permission(
            _profile(roles=["global_admin"]),
            "users.read",
        )
        self.assertTrue(decision.allowed)

    def test_explicit_denial_overrides_role_grant(self) -> None:
        decision = evaluate_permission(
            _profile(
                roles=["global_admin"],
                deny=["users.delete"],
            ),
            "users.delete",
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.matched_denial, "users.delete")

    def test_resolves_legacy_role_alias(self) -> None:
        self.assertTrue(
            subject_has_role(
                _profile(roles=["admin"]),
                "global_admin",
            )
        )


class SecurityDependencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.user = _user()
        self.profiles = Mock()
        self.authorization = AuthorizationService()

    def test_permission_dependency_returns_user_when_allowed(self) -> None:
        self.profiles.get_user.return_value = _profile(
            roles=["global_admin"]
        )
        dependency = require_permission("users.read")

        result = dependency(
            self.user,
            self.profiles,
            self.authorization,
        )
        self.assertIs(result, self.user)

    def test_permission_dependency_returns_403_when_denied(self) -> None:
        self.profiles.get_user.return_value = _profile(roles=["member"])
        dependency = require_permission("users.delete")

        with self.assertRaises(HTTPException) as context:
            dependency(
                self.user,
                self.profiles,
                self.authorization,
            )

        self.assertEqual(context.exception.status_code, 403)

    def test_permission_dependency_honors_explicit_denial(self) -> None:
        self.profiles.get_user.return_value = _profile(
            roles=["owner"],
            deny=["users.delete"],
        )
        dependency = require_permission("users.delete")

        with self.assertRaises(HTTPException) as context:
            dependency(
                self.user,
                self.profiles,
                self.authorization,
            )

        self.assertEqual(context.exception.status_code, 403)

    def test_role_dependency_returns_user_for_matching_role(self) -> None:
        self.profiles.get_user.return_value = _profile(
            roles=["monitoring_admin"]
        )
        dependency = require_role("monitoring_admin")

        result = dependency(
            self.user,
            self.profiles,
            self.authorization,
        )
        self.assertIs(result, self.user)

    def test_role_dependency_returns_403_for_missing_role(self) -> None:
        self.profiles.get_user.return_value = _profile(roles=["member"])
        dependency = require_role("owner")

        with self.assertRaises(HTTPException) as context:
            dependency(
                self.user,
                self.profiles,
                self.authorization,
            )

        self.assertEqual(context.exception.status_code, 403)

    def test_missing_profile_returns_401(self) -> None:
        self.profiles.get_user.side_effect = UserProfileError(
            "user profile not found"
        )
        dependency = require_permission("users.read")

        with self.assertRaises(HTTPException) as context:
            dependency(
                self.user,
                self.profiles,
                self.authorization,
            )

        self.assertEqual(context.exception.status_code, 401)
        self.assertEqual(
            context.exception.headers,
            {"WWW-Authenticate": "Bearer"},
        )

    def test_disabled_profile_returns_401(self) -> None:
        self.profiles.get_user.return_value = _profile(
            roles=["global_admin"],
            status="disabled",
        )
        dependency = require_permission("users.read")

        with self.assertRaises(HTTPException) as context:
            dependency(
                self.user,
                self.profiles,
                self.authorization,
            )

        self.assertEqual(context.exception.status_code, 401)


if __name__ == "__main__":
    unittest.main()
