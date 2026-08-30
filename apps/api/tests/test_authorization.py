"""Tests for the Atlas role-based authorization engine."""

from __future__ import annotations

import unittest

from atlas_api.authorization import (
    AuthorizationEffect,
    AuthorizationService,
    AuthorizationSubject,
    BUILT_IN_ROLES,
    GLOBAL_ADMIN_ROLE,
    OWNER_ROLE,
    get_role,
    is_protected_role,
)


class AuthorizationCatalogTests(unittest.TestCase):
    """Validate built-in role definitions and compatibility aliases."""

    def test_owner_is_protected_and_unrestricted(self) -> None:
        owner = BUILT_IN_ROLES[OWNER_ROLE]

        self.assertTrue(owner.protected)
        self.assertFalse(owner.assignable)
        self.assertEqual(owner.permissions, frozenset({"*"}))
        self.assertTrue(is_protected_role(OWNER_ROLE))

    def test_global_admin_is_not_owner(self) -> None:
        global_admin = BUILT_IN_ROLES[GLOBAL_ADMIN_ROLE]

        self.assertFalse(global_admin.protected)
        self.assertNotIn("*", global_admin.permissions)

    def test_legacy_admin_maps_to_global_admin(self) -> None:
        role = get_role("admin")

        self.assertIsNotNone(role)
        self.assertEqual(role.name, GLOBAL_ADMIN_ROLE)

    def test_legacy_user_maps_to_member(self) -> None:
        role = get_role("user")

        self.assertIsNotNone(role)
        self.assertEqual(role.name, "member")


class AuthorizationServiceTests(unittest.TestCase):
    """Validate role merging and permission decisions."""

    def setUp(self) -> None:
        self.service = AuthorizationService()

    def subject(
        self,
        *roles: str,
        grants: frozenset[str] = frozenset(),
        denials: frozenset[str] = frozenset(),
        active: bool = True,
    ) -> AuthorizationSubject:
        return AuthorizationSubject(
            user_id="atlas-user-1",
            roles=roles,
            granted_permissions=grants,
            denied_permissions=denials,
            active=active,
        )

    def test_owner_has_unrestricted_access(self) -> None:
        subject = self.subject("owner")

        self.assertTrue(
            self.service.is_allowed(
                subject,
                "users.delete",
            )
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "gameservers.console",
            )
        )

    def test_global_admin_can_administer_all_categories(self) -> None:
        subject = self.subject("global_admin")

        required_permissions = (
            "atlas.settings.update",
            "gameservers.create",
            "monitoring.alerts.update",
            "roles.assign",
            "users.disable",
        )

        for permission in required_permissions:
            with self.subTest(permission=permission):
                self.assertTrue(
                    self.service.is_allowed(
                        subject,
                        permission,
                    )
                )

    def test_atlas_admin_cannot_administer_game_servers(self) -> None:
        subject = self.subject("atlas_admin")

        self.assertTrue(
            self.service.is_allowed(
                subject,
                "retention.policy.update",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "gameservers.create",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "roles.assign",
            )
        )

    def test_game_server_admin_is_scoped_to_game_servers(self) -> None:
        subject = self.subject("gameserver_admin")

        self.assertTrue(
            self.service.is_allowed(
                subject,
                "gameservers.create",
            )
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "gameservers.console",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "users.delete",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "retention.policy.update",
            )
        )

    def test_monitoring_admin_can_manage_monitoring(self) -> None:
        subject = self.subject("monitoring_admin")

        self.assertTrue(
            self.service.is_allowed(
                subject,
                "monitoring.alerts.update",
            )
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "system.logs.read",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "system.settings.update",
            )
        )

    def test_read_only_role_matches_read_actions(self) -> None:
        subject = self.subject("read_only")

        self.assertTrue(
            self.service.is_allowed(
                subject,
                "users.read",
            )
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "gameservers.read",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "users.update",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "gameservers.start",
            )
        )

    def test_check_runner_can_run_checks_without_configuration(self) -> None:
        subject = self.subject("check_runner")

        self.assertTrue(
            self.service.is_allowed(
                subject,
                "system.checks.run",
            )
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "system.health.read",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "system.checks.configure",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "monitoring.alerts.update",
            )
        )

    def test_multiple_roles_merge_permissions(self) -> None:
        subject = self.subject(
            "atlas_admin",
            "gameserver_admin",
            "monitoring_admin",
        )

        self.assertTrue(
            self.service.is_allowed(
                subject,
                "retention.policy.update",
            )
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "gameservers.create",
            )
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "monitoring.alerts.update",
            )
        )

    def test_member_can_use_standard_sports_experience_without_sports_admin_wildcard(self) -> None:
        subject = self.subject("member")

        self.assertTrue(
            self.service.is_allowed(
                subject,
                "sports.read",
            )
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "sports.events.request",
            )
        )
        self.assertFalse(
            self.service.is_allowed(
                subject,
                "sports.configuration.update",
            )
        )

    def test_direct_grant_adds_permission(self) -> None:
        subject = self.subject(
            "member",
            grants=frozenset({"system.checks.run"}),
        )

        decision = self.service.evaluate(
            subject,
            "system.checks.run",
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(
            decision.matched_grant,
            "system.checks.run",
        )

    def test_explicit_denial_overrides_role_grant(self) -> None:
        subject = self.subject(
            "global_admin",
            denials=frozenset({"users.delete"}),
        )

        decision = self.service.evaluate(
            subject,
            "users.delete",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.effect,
            AuthorizationEffect.DENY,
        )
        self.assertEqual(
            decision.matched_denial,
            "users.delete",
        )

    def test_explicit_wildcard_denial_overrides_owner(self) -> None:
        subject = self.subject(
            "owner",
            denials=frozenset({"gameservers.*"}),
        )

        decision = self.service.evaluate(
            subject,
            "gameservers.delete",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.matched_denial,
            "gameservers.*",
        )

    def test_inactive_user_is_always_denied(self) -> None:
        subject = self.subject(
            "owner",
            active=False,
        )

        decision = self.service.evaluate(
            subject,
            "atlas.settings.update",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.reason,
            "The Atlas user is not active.",
        )

    def test_unknown_role_is_recorded_and_denied(self) -> None:
        subject = self.subject("not_a_real_role")

        effective = self.service.resolve(subject)
        decision = self.service.evaluate(
            subject,
            "system.health.read",
        )

        self.assertEqual(
            effective.unknown_roles,
            ("not_a_real_role",),
        )
        self.assertFalse(decision.allowed)

    def test_legacy_admin_remains_compatible(self) -> None:
        subject = self.subject("admin")

        effective = self.service.resolve(subject)

        self.assertEqual(
            effective.roles,
            ("global_admin",),
        )
        self.assertTrue(
            self.service.is_allowed(
                subject,
                "users.update",
            )
        )


if __name__ == "__main__":
    unittest.main()
