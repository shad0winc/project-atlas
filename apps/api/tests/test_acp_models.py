"""Tests for Atlas Access Control Platform domain primitives."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from atlas_api.acp import (
    ACPRole,
    ACPValidationError,
    AuditEvent,
    DuplicatePermissionError,
    OwnershipRecord,
    PermissionDefinition,
    PermissionGroup,
    PermissionRegistry,
    ResourceQuota,
    Visibility,
)


def _permission(
    identifier: str = "media.read",
) -> PermissionDefinition:
    return PermissionDefinition(
        identifier=identifier,
        display_name="Browse media",
        description="View items currently available in the library.",
        namespace="media",
        module="media",
    )


class PermissionDefinitionTests(unittest.TestCase):
    def test_normalizes_and_serializes_permission(self) -> None:
        permission = PermissionDefinition(
            identifier=" MEDIA.READ ",
            display_name=" Browse media ",
            description=" View the library. ",
            namespace=" MEDIA ",
            module=" MEDIA ",
        )

        self.assertEqual(permission.identifier, "media.read")
        self.assertEqual(permission.namespace, "media")
        self.assertEqual(
            permission.to_dict()["display_name"],
            "Browse media",
        )

    def test_rejects_wildcard_registration(self) -> None:
        with self.assertRaises(ACPValidationError):
            PermissionDefinition(
                identifier="media.*",
                display_name="All media",
                description="All media permissions.",
                namespace="media",
            )

    def test_requires_matching_namespace(self) -> None:
        with self.assertRaises(ACPValidationError):
            PermissionDefinition(
                identifier="sports.read",
                display_name="Browse sports",
                description="Browse sporting events.",
                namespace="media",
            )


class ACPRoleTests(unittest.TestCase):
    def test_role_normalizes_permissions_and_timestamps(self) -> None:
        role = ACPRole(
            name=" DEFAULT_USER ",
            display_name=" Default User ",
            description=" Standard Atlas user. ",
            permissions=frozenset(
                {"MEDIA.READ", "favorites.write"}
            ),
            system=True,
            created_at="2026-07-25T12:00:00Z",
        )

        self.assertEqual(role.name, "default_user")
        self.assertEqual(
            role.permissions,
            frozenset({"media.read", "favorites.write"}),
        )
        self.assertEqual(role.created_at.tzinfo, timezone.utc)
        self.assertEqual(
            role.to_dict()["created_at"],
            "2026-07-25T12:00:00Z",
        )

    def test_protected_role_must_be_system_role(self) -> None:
        with self.assertRaises(ACPValidationError):
            ACPRole(
                name="owner",
                display_name="Owner",
                description="Atlas owner.",
                protected=True,
                system=False,
            )

    def test_role_round_trip(self) -> None:
        original = ACPRole(
            name="media_sports_admin",
            display_name="Media & Sports Administrator",
            description="Administers media and sports workflows.",
            permissions=frozenset(
                {"media.delete", "sports.events.cancel"}
            ),
            system=True,
        )

        restored = ACPRole.from_dict(original.to_dict())
        self.assertEqual(restored, original)


class OwnershipRecordTests(unittest.TestCase):
    def test_public_resource_is_visible_to_everyone(self) -> None:
        ownership = OwnershipRecord(
            resource_type="gameserver",
            resource_id="minecraft-1",
            owner_user_id="usr_owner",
            visibility=Visibility.PUBLIC,
        )

        self.assertTrue(ownership.is_visible_to(None))
        self.assertTrue(ownership.is_visible_to("usr_other"))

    def test_private_resource_is_visible_only_to_owner(self) -> None:
        ownership = OwnershipRecord(
            resource_type="gameserver",
            resource_id="minecraft-1",
            owner_user_id="usr_owner",
        )

        self.assertTrue(ownership.is_visible_to("usr_owner"))
        self.assertFalse(ownership.is_visible_to("usr_other"))

    def test_shared_resource_honors_shared_user_list(self) -> None:
        ownership = OwnershipRecord(
            resource_type="gameserver",
            resource_id="minecraft-1",
            owner_user_id="usr_owner",
            visibility="shared",
            shared_with=frozenset({"usr_friend"}),
        )

        self.assertTrue(ownership.is_visible_to("usr_friend"))
        self.assertFalse(ownership.is_visible_to("usr_other"))

    def test_shared_users_require_shared_visibility(self) -> None:
        with self.assertRaises(ACPValidationError):
            OwnershipRecord(
                resource_type="gameserver",
                resource_id="minecraft-1",
                owner_user_id="usr_owner",
                visibility="private",
                shared_with=frozenset({"usr_friend"}),
            )


class ResourceQuotaTests(unittest.TestCase):
    def test_quota_allows_usage_within_limit(self) -> None:
        quota = ResourceQuota(
            subject_id="usr_builder",
            limits={
                "gameservers.count": 2,
                "gameservers.memory_gb": 12,
            },
        )

        self.assertTrue(
            quota.allows("gameservers.count", 2)
        )
        self.assertFalse(
            quota.allows("gameservers.count", 3)
        )
        self.assertFalse(
            quota.allows("gameservers.cpu_cores", 1)
        )

    def test_rejects_negative_quota(self) -> None:
        with self.assertRaises(ACPValidationError):
            ResourceQuota(
                subject_id="usr_builder",
                limits={"gameservers.count": -1},
            )


class AuditEventTests(unittest.TestCase):
    def test_audit_event_normalizes_utc_timestamp(self) -> None:
        event = AuditEvent(
            event_type="roles.created",
            actor_user_id="usr_admin",
            target_type="role",
            target_id="media_sports_admin",
            occurred_at=datetime(
                2026,
                7,
                25,
                12,
                0,
                tzinfo=timezone.utc,
            ),
            details={"permissions": 2},
        )

        self.assertEqual(
            event.to_dict()["occurred_at"],
            "2026-07-25T12:00:00Z",
        )
        self.assertEqual(event.details["permissions"], 2)


class PermissionRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.registry = PermissionRegistry()
        self.registry.register_group(
            PermissionGroup(
                namespace="media",
                display_name="Media",
                description="Media library and request permissions.",
                module="media",
            )
        )

    def test_registers_and_resolves_permission(self) -> None:
        permission = self.registry.register(_permission())

        self.assertIs(
            self.registry.require("MEDIA.READ"),
            permission,
        )
        self.assertEqual(
            self.registry.list_permissions("media"),
            (permission,),
        )

    def test_rejects_duplicate_permission(self) -> None:
        self.registry.register(_permission())

        with self.assertRaises(DuplicatePermissionError):
            self.registry.register(_permission())

    def test_requires_registered_namespace(self) -> None:
        with self.assertRaises(ACPValidationError):
            self.registry.register(
                PermissionDefinition(
                    identifier="sports.read",
                    display_name="Browse sports",
                    description="Browse live and scheduled events.",
                    namespace="sports",
                    module="sports",
                )
            )

    def test_rejects_module_mismatch(self) -> None:
        with self.assertRaises(ACPValidationError):
            self.registry.register(
                PermissionDefinition(
                    identifier="media.delete",
                    display_name="Delete media",
                    description="Delete an unprotected media item.",
                    namespace="media",
                    module="sports",
                    dangerous=True,
                )
            )


if __name__ == "__main__":
    unittest.main()
