"""Tests for the Atlas authentication service."""

import unittest

from atlas_api.auth.exceptions import InvalidCredentialsError
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import (
    AuthenticatedUser,
    TokenType,
)
from atlas_api.auth.service import AuthenticationService
from atlas_api.core.settings import AtlasAPISettings


class FakeAuthenticationProvider:
    def authenticate(
        self,
        username: str,
        password: str,
    ) -> AuthenticatedUser | None:
        if username != "michael" or password != "atlas-password":
            return None

        return AuthenticatedUser(
            user_id="user-123",
            username="michael",
            display_name="Michael",
            roles=("admin",),
        )


class AuthenticationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.jwt_service = JWTService(
            AtlasAPISettings(
                jwt_secret="atlas-service-test-" + ("s" * 48),
                jwt_issuer="atlas-test",
                jwt_audience="atlas-test-client",
            )
        )
        self.service = AuthenticationService(
            FakeAuthenticationProvider(),
            self.jwt_service,
        )

    def test_login_returns_access_and_refresh_tokens(self) -> None:
        tokens = self.service.login(
            "michael",
            "atlas-password",
        )

        access_claims = self.jwt_service.decode_token(
            tokens.access_token,
            expected_type=TokenType.ACCESS,
        )
        refresh_claims = self.jwt_service.decode_token(
            tokens.refresh_token,
            expected_type=TokenType.REFRESH,
        )

        self.assertEqual(access_claims.subject, "user-123")
        self.assertEqual(refresh_claims.subject, "user-123")
        self.assertEqual(tokens.token_type, "bearer")

    def test_login_rejects_invalid_credentials(self) -> None:
        with self.assertRaises(InvalidCredentialsError):
            self.service.login(
                "michael",
                "wrong-password",
            )

    def test_login_rejects_empty_credentials(self) -> None:
        with self.assertRaises(InvalidCredentialsError):
            self.service.login("", "")

    def test_refresh_rotates_token_pair(self) -> None:
        user = AuthenticatedUser(
            user_id="user-123",
            username="michael",
            display_name="Michael",
            roles=("admin",),
        )
        original = self.service.login(
            "michael",
            "atlas-password",
        )

        replacement = self.service.refresh(
            original.refresh_token,
            user,
        )

        self.assertNotEqual(
            original.access_token,
            replacement.access_token,
        )
        self.assertNotEqual(
            original.refresh_token,
            replacement.refresh_token,
        )


if __name__ == "__main__":
    unittest.main()
