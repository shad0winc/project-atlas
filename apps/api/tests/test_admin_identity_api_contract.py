"""Test-first contract for the v1 administrator identity API.

This contract intentionally precedes implementation.

The first slice defines read-only administrator user-management behavior:

* global administrators can list users;
* global administrators can inspect one user;
* ordinary members cannot access administrator user data;
* anonymous requests cannot access administrator user data.

Mutation and invitation contracts are intentionally deferred until this
read-side vertical slice is implemented and green.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas.user_profiles import UserProfileError, UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_current_user,
    get_identity_writer_client,
    get_security_audit_writer,
    get_user_profile_store,
)
from atlas_api.services.identity_writer import IdentityWriterError
from atlas_api.main import create_app


class _ProfileBackedIdentityWriter:
    """Test adapter preserving user-domain mutation behavior."""

    def __init__(
        self,
        profiles: UserProfileStore,
    ) -> None:
        self.profiles = profiles

    def update_user(
        self,
        identifier: str,
        updates: dict[str, object],
    ) -> dict[str, object]:
        try:
            return self.profiles.update_user(
                identifier,
                updates,
            )
        except UserProfileError as error:
            message = str(error)

            if "not found" in message.lower():
                code = 404
            else:
                code = 400

            raise IdentityWriterError(
                message,
                status_code=code,
            ) from error


class _NoopSecurityAuditWriter:
    """Test-only audit sink for authorization-denial events."""

    def publish(
        self,
        event_name: str,
        payload=None,
    ) -> None:
        return None


class AdminIdentityAPIContractTests(unittest.TestCase):
    """Minimum read-side HTTP contract for administrator identity management."""

    def setUp(self) -> None:
        self.temporary_directory = TemporaryDirectory()
        self.identity_root = Path(self.temporary_directory.name)

        self.profiles = UserProfileStore(self.identity_root)

        self.global_admin_profile = self.profiles.create_user(
            "atlas-admin",
            display_name="Atlas Administrator",
            roles=("global_admin",),
        )

        self.member_profile = self.profiles.create_user(
            "atlas-member",
            display_name="Atlas Member",
            roles=("member",),
        )

        self.owner_profile = self.profiles.create_user(
            "atlas-owner",
            display_name="Atlas Owner",
            roles=("owner",),
        )

        self.global_admin_id = str(
            self.global_admin_profile["user_id"]
        )
        self.member_id = str(
            self.member_profile["user_id"]
        )
        self.owner_id = str(
            self.owner_profile["user_id"]
        )

        self.app = create_app()
        self.app.dependency_overrides[get_user_profile_store] = (
            lambda: self.profiles
        )
        self.app.dependency_overrides[get_identity_writer_client] = (
            lambda: _ProfileBackedIdentityWriter(
                self.profiles
            )
        )
        self.app.dependency_overrides[get_security_audit_writer] = (
            lambda: _NoopSecurityAuditWriter()
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.temporary_directory.cleanup()

    @staticmethod
    def authenticated_user(
        profile: dict[str, object],
    ) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=str(profile["user_id"]),
            username=str(profile["username"]),
            display_name=str(profile["display_name"]),
            roles=tuple(str(role) for role in profile["roles"]),
            provider="atlas",
            metadata={},
        )

    def client_for(
        self,
        profile: dict[str, object],
    ) -> TestClient:
        user = self.authenticated_user(profile)

        self.app.dependency_overrides[get_current_user] = (
            lambda: user
        )

        return TestClient(self.app)

    def test_global_admin_can_list_users(self) -> None:
        client = self.client_for(
            self.global_admin_profile
        )

        response = client.get("/api/v1/admin/users")

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertIn("users", payload)
        self.assertIsInstance(payload["users"], list)

        users_by_name = {
            user["username"]: user
            for user in payload["users"]
        }

        self.assertIn("atlas-admin", users_by_name)
        self.assertIn("atlas-member", users_by_name)

        member = users_by_name["atlas-member"]

        self.assertEqual(
            member["user_id"],
            self.member_id,
        )
        self.assertEqual(member["status"], "active")
        self.assertEqual(member["roles"], ["member"])

    def test_global_admin_can_inspect_user(self) -> None:
        client = self.client_for(
            self.global_admin_profile
        )

        response = client.get(
            f"/api/v1/admin/users/{self.member_id}"
        )

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(payload["user_id"], self.member_id)
        self.assertEqual(payload["username"], "atlas-member")
        self.assertEqual(payload["display_name"], "Atlas Member")
        self.assertEqual(payload["status"], "active")
        self.assertEqual(payload["roles"], ["member"])

    def test_member_cannot_list_users(self) -> None:
        client = self.client_for(
            self.member_profile
        )

        response = client.get("/api/v1/admin/users")

        self.assertEqual(response.status_code, 403)

    def test_member_cannot_inspect_another_user(self) -> None:
        client = self.client_for(
            self.member_profile
        )

        response = client.get(
            f"/api/v1/admin/users/{self.global_admin_id}"
        )

        self.assertEqual(response.status_code, 403)

    def test_admin_identity_routes_are_not_public(self) -> None:
        def unauthenticated_user() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        self.app.dependency_overrides[get_current_user] = (
            unauthenticated_user
        )

        client = TestClient(self.app)

        list_response = client.get("/api/v1/admin/users")
        detail_response = client.get(
            f"/api/v1/admin/users/{self.member_id}"
        )

        self.assertEqual(list_response.status_code, 401)
        self.assertEqual(detail_response.status_code, 401)
        self.assertEqual(
            list_response.headers.get("www-authenticate"),
            "Bearer",
        )
        self.assertEqual(
            detail_response.headers.get("www-authenticate"),
            "Bearer",
        )


    def test_global_admin_can_disable_and_reenable_member(self) -> None:
        client = self.client_for(
            self.global_admin_profile
        )

        disabled = client.patch(
            f"/api/v1/admin/users/{self.member_id}",
            json={"status": "disabled"},
        )

        self.assertEqual(disabled.status_code, 200)
        self.assertEqual(disabled.json()["status"], "disabled")
        self.assertEqual(
            self.profiles.get_user(self.member_id)["status"],
            "disabled",
        )

        enabled = client.patch(
            f"/api/v1/admin/users/{self.member_id}",
            json={"status": "active"},
        )

        self.assertEqual(enabled.status_code, 200)
        self.assertEqual(enabled.json()["status"], "active")
        self.assertEqual(
            self.profiles.get_user(self.member_id)["status"],
            "active",
        )

    def test_global_admin_can_assign_member_roles(self) -> None:
        client = self.client_for(
            self.global_admin_profile
        )

        response = client.patch(
            f"/api/v1/admin/users/{self.member_id}",
            json={
                "roles": [
                    "atlas_admin",
                    "monitoring_admin",
                ]
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["roles"],
            [
                "atlas_admin",
                "monitoring_admin",
            ],
        )
        self.assertEqual(
            self.profiles.get_user(self.member_id)["roles"],
            [
                "atlas_admin",
                "monitoring_admin",
            ],
        )

    def test_member_cannot_mutate_user(self) -> None:
        client = self.client_for(
            self.member_profile
        )

        response = client.patch(
            f"/api/v1/admin/users/{self.global_admin_id}",
            json={"status": "disabled"},
        )

        self.assertEqual(response.status_code, 403)

    def test_anonymous_request_cannot_mutate_user(self) -> None:
        def unauthenticated_user() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        self.app.dependency_overrides[get_current_user] = (
            unauthenticated_user
        )

        client = TestClient(self.app)

        response = client.patch(
            f"/api/v1/admin/users/{self.member_id}",
            json={"status": "disabled"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.headers.get("www-authenticate"),
            "Bearer",
        )

    def test_owner_cannot_be_disabled_through_admin_api(self) -> None:
        client = self.client_for(
            self.global_admin_profile
        )

        response = client.patch(
            f"/api/v1/admin/users/{self.owner_id}",
            json={"status": "disabled"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.profiles.get_user(self.owner_id)["status"],
            "active",
        )

    def test_owner_role_cannot_be_removed_through_admin_api(self) -> None:
        client = self.client_for(
            self.global_admin_profile
        )

        response = client.patch(
            f"/api/v1/admin/users/{self.owner_id}",
            json={"roles": ["global_admin"]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "owner",
            self.profiles.get_user(self.owner_id)["roles"],
        )

    def test_invalid_status_is_rejected(self) -> None:
        client = self.client_for(
            self.global_admin_profile
        )

        response = client.patch(
            f"/api/v1/admin/users/{self.member_id}",
            json={"status": "suspended"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.profiles.get_user(self.member_id)["status"],
            "active",
        )

    def test_invalid_role_is_rejected(self) -> None:
        client = self.client_for(
            self.global_admin_profile
        )

        response = client.patch(
            f"/api/v1/admin/users/{self.member_id}",
            json={"roles": ["not_a_role"]},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.profiles.get_user(self.member_id)["roles"],
            ["member"],
        )


if __name__ == "__main__":
    unittest.main()
