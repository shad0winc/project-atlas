"""HTTP contract tests for Atlas authentication routes."""

from __future__ import annotations

import unittest

from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas_api.auth.exceptions import (
    AuthenticationProviderError,
    InvalidCredentialsError,
)
from atlas_api.auth.models import AuthenticatedUser, TokenPair
from atlas_api.dependencies import (
    get_authentication_service,
    get_user_profile_store,
)
from atlas_api.main import create_app
from atlas_api.routes.v1.auth import require_current_user_read


class SuccessfulAuthenticationService:
    """Authentication service double returning a stable token pair."""

    def login(self, username: str, password: str) -> TokenPair:
        self.username = username
        self.password = password

        return TokenPair(
            access_token="access-token",
            refresh_token="refresh-token",
        )


class InvalidAuthenticationService:
    """Authentication service double rejecting credentials."""

    def login(self, username: str, password: str) -> TokenPair:
        raise InvalidCredentialsError("invalid credentials")


class UnavailableAuthenticationService:
    """Authentication service double representing provider failure."""

    def login(self, username: str, password: str) -> TokenPair:
        raise AuthenticationProviderError("provider unavailable")


class ProfileStoreDouble:
    """Profile-store double exposing one controlled Atlas profile."""

    def __init__(self, profile: dict[str, object]) -> None:
        self.profile = profile
        self.requested_user_id: str | None = None

    def get_user(self, user_id: str) -> dict[str, object]:
        self.requested_user_id = user_id
        return self.profile


def authorization_profile(
    *,
    roles: tuple[str, ...] = ("member",),
    allow: tuple[str, ...] = (),
    deny: tuple[str, ...] = (),
) -> dict[str, object]:
    """Create one active profile for /auth/me authorization tests."""

    return {
        "schema_version": 2,
        "user_id": "usr_123",
        "username": "michael",
        "display_name": "Michael",
        "email": "",
        "status": "active",
        "roles": list(roles),
        "permission_overrides": {
            "allow": list(allow),
            "deny": list(deny),
        },
        "created_at": "2026-07-27T00:00:00Z",
        "updated_at": "2026-07-27T00:00:00Z",
    }


class AuthenticationRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.application = create_app()
        self.client = TestClient(self.application)

    def tearDown(self) -> None:
        self.application.dependency_overrides.clear()

    def test_login_returns_token_pair(self) -> None:
        service = SuccessfulAuthenticationService()
        self.application.dependency_overrides[
            get_authentication_service
        ] = lambda: service

        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "michael",
                "password": "secret",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "access_token": "access-token",
                "refresh_token": "refresh-token",
                "token_type": "bearer",
            },
        )
        self.assertEqual(service.username, "michael")
        self.assertEqual(service.password, "secret")

    def test_login_rejects_invalid_credentials(self) -> None:
        self.application.dependency_overrides[
            get_authentication_service
        ] = InvalidAuthenticationService

        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "michael",
                "password": "wrong",
            },
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json(),
            {"detail": "Username or password is incorrect."},
        )
        self.assertEqual(
            response.headers["www-authenticate"],
            "Bearer",
        )

    def test_login_reports_provider_unavailability(self) -> None:
        self.application.dependency_overrides[
            get_authentication_service
        ] = UnavailableAuthenticationService

        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "michael",
                "password": "secret",
            },
        )

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {
                "detail":
                    "The authentication provider is unavailable."
            },
        )

    def test_login_rejects_unknown_request_fields(self) -> None:
        self.application.dependency_overrides[
            get_authentication_service
        ] = SuccessfulAuthenticationService

        response = self.client.post(
            "/api/v1/auth/login",
            json={
                "username": "michael",
                "password": "secret",
                "admin": True,
            },
        )

        self.assertEqual(response.status_code, 422)

    def test_me_returns_effective_authorization_contract(self) -> None:
        user = AuthenticatedUser(
            user_id="usr_123",
            username="michael",
            display_name="Michael",
            roles=("admin",),
            provider="jellyfin",
        )
        profiles = ProfileStoreDouble(
            authorization_profile(
                roles=("admin",),
                allow=("system.checks.run",),
                deny=("users.delete",),
            )
        )

        self.application.dependency_overrides[
            require_current_user_read
        ] = lambda: user
        self.application.dependency_overrides[
            get_user_profile_store
        ] = lambda: profiles

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(
            payload,
            {
                "user_id": "usr_123",
                "username": "michael",
                "display_name": "Michael",
                "roles": ["global_admin"],
                "provider": "jellyfin",
                "granted_permission_patterns": sorted(
                    [
                        "atlas.*",
                        "audit.*",
                        "cleanup.*",
                        "favorites.*",
                        "gameservers.*",
                        "media.*",
                        "modules.*",
                        "monitoring.*",
                        "requests.*",
                        "retention.*",
                        "roles.*",
                        "scheduler.*",
                        "system.*",
                        "system.checks.run",
                        "users.*",
                    ]
                ),
                "denied_permission_patterns": ["users.delete"],
            },
        )
        self.assertEqual(profiles.requested_user_id, "usr_123")

    def test_me_merges_permissions_from_multiple_roles(self) -> None:
        user = AuthenticatedUser(
            user_id="usr_123",
            username="michael",
            display_name="Michael",
            roles=("atlas_admin", "monitoring_admin"),
            provider="jellyfin",
        )
        profiles = ProfileStoreDouble(
            authorization_profile(
                roles=("atlas_admin", "monitoring_admin"),
            )
        )

        self.application.dependency_overrides[
            require_current_user_read
        ] = lambda: user
        self.application.dependency_overrides[
            get_user_profile_store
        ] = lambda: profiles

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)

        payload = response.json()

        self.assertEqual(
            payload["roles"],
            ["atlas_admin", "monitoring_admin"],
        )
        self.assertIn(
            "atlas.*",
            payload["granted_permission_patterns"],
        )
        self.assertIn(
            "monitoring.*",
            payload["granted_permission_patterns"],
        )
        self.assertEqual(
            payload["denied_permission_patterns"],
            [],
        )

    def test_me_exposes_direct_grant_for_member(self) -> None:
        user = AuthenticatedUser(
            user_id="usr_123",
            username="michael",
            display_name="Michael",
            roles=("member",),
            provider="jellyfin",
        )
        profiles = ProfileStoreDouble(
            authorization_profile(
                allow=("system.health.read",),
            )
        )

        self.application.dependency_overrides[
            require_current_user_read
        ] = lambda: user
        self.application.dependency_overrides[
            get_user_profile_store
        ] = lambda: profiles

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "system.health.read",
            response.json()["granted_permission_patterns"],
        )

    def test_me_preserves_explicit_denial_separately(self) -> None:
        user = AuthenticatedUser(
            user_id="usr_123",
            username="michael",
            display_name="Michael",
            roles=("global_admin",),
            provider="jellyfin",
        )
        profiles = ProfileStoreDouble(
            authorization_profile(
                roles=("global_admin",),
                deny=("users.delete", "roles.assign"),
            )
        )

        self.application.dependency_overrides[
            require_current_user_read
        ] = lambda: user
        self.application.dependency_overrides[
            get_user_profile_store
        ] = lambda: profiles

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["denied_permission_patterns"],
            ["roles.assign", "users.delete"],
        )

    def test_me_returns_forbidden_when_permission_is_denied(self) -> None:
        def deny_current_user_read() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "No assigned role or direct grant provides the "
                    "requested permission."
                ),
            )

        self.application.dependency_overrides[
            require_current_user_read
        ] = deny_current_user_read

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(
            response.json(),
            {
                "detail": (
                    "No assigned role or direct grant provides the "
                    "requested permission."
                )
            },
        )


if __name__ == "__main__":
    unittest.main()
