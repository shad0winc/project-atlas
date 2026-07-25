"""HTTP contract tests for Atlas authentication routes."""

from __future__ import annotations

import unittest

from fastapi.testclient import TestClient

from atlas_api.auth.exceptions import (
    AuthenticationProviderError,
    InvalidCredentialsError,
)
from atlas_api.auth.models import AuthenticatedUser, TokenPair
from atlas_api.dependencies import (
    get_authentication_service,
    get_current_user,
)
from atlas_api.main import create_app


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

    def test_me_returns_authenticated_user(self) -> None:
        user = AuthenticatedUser(
            user_id="usr_123",
            username="michael",
            display_name="Michael",
            roles=("admin",),
            provider="jellyfin",
        )

        self.application.dependency_overrides[
            get_current_user
        ] = lambda: user

        response = self.client.get("/api/v1/auth/me")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "user_id": "usr_123",
                "username": "michael",
                "display_name": "Michael",
                "roles": ["admin"],
                "provider": "jellyfin",
            },
        )


if __name__ == "__main__":
    unittest.main()
