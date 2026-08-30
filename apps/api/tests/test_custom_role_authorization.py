"""Authorization composition tests for persistent Atlas custom roles."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from atlas.custom_roles import (
    CustomRoleDefinition,
    CustomRoleStore,
)
from atlas_api.authorization import (
    AuthorizationSubject,
    BUILT_IN_ROLES,
)
from atlas_api.authorization.runtime_catalog import (
    RuntimeRoleCatalogError,
    authorization_service_for_store,
    compose_role_catalog,
    custom_role_definition,
)


class CustomRoleAuthorizationTests(unittest.TestCase):
    @staticmethod
    def sports_role() -> CustomRoleDefinition:
        return CustomRoleDefinition(
            name="sports_coordinator",
            display_name="Sports Administrator",
            description=(
                "Read Atlas sports data and submit sports event requests."
            ),
            permissions=frozenset(
                {
                    "sports.read",
                    "sports.events.request",
                }
            ),
        )

    def test_empty_custom_catalog_preserves_built_ins(self) -> None:
        catalog = compose_role_catalog()
        self.assertEqual(dict(catalog), dict(BUILT_IN_ROLES))

    def test_custom_role_uses_canonical_role_definition(self) -> None:
        definition = custom_role_definition(self.sports_role())
        self.assertEqual(definition.name, "sports_coordinator")
        self.assertEqual(
            definition.permissions,
            frozenset(
                {
                    "sports.read",
                    "sports.events.request",
                }
            ),
        )
        self.assertFalse(definition.protected)
        self.assertTrue(definition.assignable)

    def test_custom_sports_role_authorizes_existing_permissions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = CustomRoleStore(
                Path(temporary) / "custom_roles.json",
                reserved_names=BUILT_IN_ROLES,
            )
            store.initialize()
            store.create(self.sports_role())

            authorization = authorization_service_for_store(store)
            subject = AuthorizationSubject(
                user_id="usr_sports",
                roles=("sports_coordinator",),
            )

            self.assertTrue(
                authorization.is_allowed(subject, "sports.read")
            )
            self.assertTrue(
                authorization.is_allowed(
                    subject,
                    "sports.events.request",
                )
            )
            self.assertFalse(
                authorization.is_allowed(subject, "users.read")
            )

    def test_explicit_denial_still_overrides_custom_role_grant(self) -> None:
        catalog = compose_role_catalog((self.sports_role(),))
        from atlas_api.authorization import AuthorizationService

        authorization = AuthorizationService(catalog)
        subject = AuthorizationSubject(
            user_id="usr_sports",
            roles=("sports_coordinator",),
            denied_permissions=frozenset({"sports.events.request"}),
        )

        self.assertTrue(
            authorization.is_allowed(subject, "sports.read")
        )
        self.assertFalse(
            authorization.is_allowed(
                subject,
                "sports.events.request",
            )
        )

    def test_unknown_role_remains_unknown(self) -> None:
        catalog = compose_role_catalog((self.sports_role(),))
        from atlas_api.authorization import AuthorizationService

        effective = AuthorizationService(catalog).resolve(
            AuthorizationSubject(
                user_id="usr_unknown",
                roles=("missing_custom_role",),
            )
        )

        self.assertEqual(
            effective.unknown_roles,
            ("missing_custom_role",),
        )
        self.assertEqual(effective.granted_permissions, frozenset())

    def test_built_in_name_collision_fails_closed(self) -> None:
        replacement = CustomRoleDefinition(
            name="member",
            display_name="Replacement Member",
            description="Must never replace the built-in member role.",
            permissions=frozenset({"sports.read"}),
        )

        with self.assertRaisesRegex(
            RuntimeRoleCatalogError,
            "conflicts with a built-in role",
        ):
            compose_role_catalog((replacement,))

    def test_duplicate_custom_names_fail_closed(self) -> None:
        role = self.sports_role()

        with self.assertRaisesRegex(
            RuntimeRoleCatalogError,
            "Duplicate custom role",
        ):
            compose_role_catalog((role, role))

    def test_composed_catalog_is_immutable(self) -> None:
        catalog = compose_role_catalog((self.sports_role(),))

        with self.assertRaises(TypeError):
            catalog["replacement"] = catalog["sports_coordinator"]  # type: ignore[index]


if __name__ == "__main__":
    unittest.main()
