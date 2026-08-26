from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas.identity import IdentityPaths
from atlas.invitations import InvitationStore
from atlas.user_profiles import UserProfileStore
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.dependencies import (
    get_current_user,
    get_user_profile_store,
)
from atlas_api.main import create_app


class AdminInvitationAPIContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.identity_root = Path(self.temp.name) / "identity"

        self.paths = IdentityPaths(self.identity_root)
        self.profiles = UserProfileStore(self.identity_root)
        self.invitations = InvitationStore(self.paths)

        self.profiles.initialize()
        self.invitations.initialize()

        self.global_admin_profile = self.profiles.create_user(
            username="global-admin",
            display_name="Global Admin",
            roles=["global_admin"],
        )
        self.member_profile = self.profiles.create_user(
            username="member",
            display_name="Member",
            roles=["member"],
        )

        self.global_admin_id = self.global_admin_profile["user_id"]
        self.member_id = self.member_profile["user_id"]

        self.app = create_app()
        self.app.dependency_overrides[get_user_profile_store] = (
            lambda: self.profiles
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()
        self.temp.cleanup()

    @staticmethod
    def authenticated_user(
        profile: dict,
    ) -> AuthenticatedUser:
        return AuthenticatedUser(
            user_id=str(profile["user_id"]),
            username=str(profile["username"]),
            display_name=str(profile["display_name"]),
            roles=tuple(
                str(role)
                for role in profile["roles"]
            ),
            provider="atlas",
            metadata={},
        )

    def client_for(self, profile: dict) -> TestClient:
        user = self.authenticated_user(profile)

        self.app.dependency_overrides[get_current_user] = (
            lambda: user
        )

        return TestClient(self.app)

    def test_admin_invitation_routes_are_not_public(self) -> None:
        def unauthenticated_user():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        self.app.dependency_overrides[get_current_user] = (
            unauthenticated_user
        )

        client = TestClient(self.app)

        responses = (
            client.get("/api/v1/admin/invitations"),
            client.post(
                "/api/v1/admin/invitations",
                json={
                    "email": "friend@example.com",
                    "role": "user",
                    "days": 7,
                },
            ),
            client.get(
                "/api/v1/admin/invitations/"
                "inv_00000000000000000000000000000000"
            ),
            client.post(
                "/api/v1/admin/invitations/"
                "inv_00000000000000000000000000000000/revoke"
            ),
        )

        self.assertEqual(
            [response.status_code for response in responses],
            [401, 401, 401, 401],
        )

    def test_member_cannot_administer_invitations(self) -> None:
        client = self.client_for(self.member_profile)

        responses = (
            client.get("/api/v1/admin/invitations"),
            client.post(
                "/api/v1/admin/invitations",
                json={
                    "email": "friend@example.com",
                    "role": "user",
                    "days": 7,
                },
            ),
            client.get(
                "/api/v1/admin/invitations/"
                "inv_00000000000000000000000000000000"
            ),
            client.post(
                "/api/v1/admin/invitations/"
                "inv_00000000000000000000000000000000/revoke"
            ),
        )

        self.assertEqual(
            [response.status_code for response in responses],
            [403, 403, 403, 403],
        )

    def test_global_admin_can_create_invitation(self) -> None:
        client = self.client_for(self.global_admin_profile)

        response = client.post(
            "/api/v1/admin/invitations",
            json={
                "email": "FRIEND@EXAMPLE.COM",
                "role": "user",
                "days": 7,
            },
        )

        self.assertEqual(response.status_code, 201)

        body = response.json()

        self.assertEqual(body["email"], "friend@example.com")
        self.assertEqual(body["role"], "user")
        self.assertEqual(body["status"], "pending")
        self.assertEqual(
            body["created_by"],
            self.global_admin_id,
        )
        self.assertTrue(
            body["token"].startswith("atlas_inv_")
        )
        self.assertIn("invite_id", body)
        self.assertIn("expires_at", body)
        self.assertNotIn("token_hash", body)

    def test_create_token_is_returned_once_only(self) -> None:
        client = self.client_for(self.global_admin_profile)

        created = client.post(
            "/api/v1/admin/invitations",
            json={
                "email": "friend@example.com",
                "role": "user",
                "days": 7,
            },
        )

        self.assertEqual(created.status_code, 201)

        issue = created.json()
        invite_id = issue["invite_id"]

        detail = client.get(
            f"/api/v1/admin/invitations/{invite_id}"
        )

        self.assertEqual(detail.status_code, 200)

        detail_body = detail.json()

        self.assertNotIn("token", detail_body)
        self.assertNotIn("token_hash", detail_body)

        listing = client.get(
            "/api/v1/admin/invitations"
        )

        self.assertEqual(listing.status_code, 200)

        items = listing.json()["items"]
        record = next(
            item
            for item in items
            if item["invite_id"] == invite_id
        )

        self.assertNotIn("token", record)
        self.assertNotIn("token_hash", record)

    def test_global_admin_can_list_and_filter_invitations(
        self,
    ) -> None:
        first = self.invitations.create(
            email="first@example.com",
            created_by=self.global_admin_id,
        )
        second = self.invitations.create(
            email="second@example.com",
            created_by=self.global_admin_id,
        )

        self.invitations.revoke(
            second.invitation["invite_id"],
            revoked_by=self.global_admin_id,
        )

        client = self.client_for(self.global_admin_profile)

        response = client.get(
            "/api/v1/admin/invitations?status=pending"
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertIn("items", body)

        ids = {
            item["invite_id"]
            for item in body["items"]
        }

        self.assertIn(
            first.invitation["invite_id"],
            ids,
        )
        self.assertNotIn(
            second.invitation["invite_id"],
            ids,
        )

        for item in body["items"]:
            self.assertEqual(item["status"], "pending")
            self.assertNotIn("token", item)
            self.assertNotIn("token_hash", item)

    def test_global_admin_can_inspect_invitation(self) -> None:
        issue = self.invitations.create(
            email="friend@example.com",
            role="user",
            created_by=self.global_admin_id,
        )

        client = self.client_for(self.global_admin_profile)

        response = client.get(
            "/api/v1/admin/invitations/"
            f"{issue.invitation['invite_id']}"
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(
            body["invite_id"],
            issue.invitation["invite_id"],
        )
        self.assertEqual(
            body["email"],
            "friend@example.com",
        )
        self.assertEqual(body["status"], "pending")
        self.assertNotIn("token", body)
        self.assertNotIn("token_hash", body)

    def test_global_admin_can_revoke_pending_invitation(
        self,
    ) -> None:
        issue = self.invitations.create(
            email="friend@example.com",
            created_by=self.global_admin_id,
        )

        client = self.client_for(self.global_admin_profile)

        response = client.post(
            "/api/v1/admin/invitations/"
            f"{issue.invitation['invite_id']}/revoke"
        )

        self.assertEqual(response.status_code, 200)

        body = response.json()

        self.assertEqual(body["status"], "revoked")
        self.assertEqual(
            body["revoked_by"],
            self.global_admin_id,
        )
        self.assertNotIn("token", body)
        self.assertNotIn("token_hash", body)

    def test_invalid_status_filter_is_rejected(self) -> None:
        client = self.client_for(self.global_admin_profile)

        response = client.get(
            "/api/v1/admin/invitations?status=invalid"
        )

        self.assertEqual(response.status_code, 422)

    def test_invalid_expiration_is_rejected(self) -> None:
        client = self.client_for(self.global_admin_profile)

        response = client.post(
            "/api/v1/admin/invitations",
            json={
                "email": "friend@example.com",
                "role": "user",
                "days": 0,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_unknown_invitation_returns_not_found(self) -> None:
        client = self.client_for(self.global_admin_profile)

        response = client.get(
            "/api/v1/admin/invitations/"
            "inv_00000000000000000000000000000000"
        )

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
