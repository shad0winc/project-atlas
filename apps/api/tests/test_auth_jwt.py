"""Tests for Atlas JWT creation and validation."""

from datetime import datetime, timedelta, timezone
import unittest

from atlas_api.auth.exceptions import (
    ExpiredTokenError,
    InvalidTokenError,
    UnexpectedTokenTypeError,
)
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser, TokenType
from atlas_api.core.settings import AtlasAPISettings


class JWTServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = datetime.now(timezone.utc)

        self.settings = AtlasAPISettings(
            jwt_secret="atlas-test-secret-" + ("x" * 48),
            jwt_issuer="atlas-test",
            jwt_audience="atlas-test-client",
            access_token_minutes=15,
            refresh_token_days=30,
        )

        self.user = AuthenticatedUser(
            user_id="user-123",
            username="michael",
            display_name="Michael",
            roles=("admin", "member"),
        )

    def test_creates_and_decodes_access_token(self) -> None:
        service = JWTService(
            self.settings,
            clock=lambda: self.now,
        )

        token = service.create_access_token(self.user)

        claims = service.decode_token(
            token,
            expected_type=TokenType.ACCESS,
        )

        self.assertEqual(claims.subject, "user-123")
        self.assertEqual(claims.username, "michael")
        self.assertEqual(claims.roles, ("admin", "member"))
        self.assertEqual(claims.token_type, TokenType.ACCESS)

    def test_creates_refresh_token(self) -> None:
        service = JWTService(
            self.settings,
            clock=lambda: self.now,
        )

        token = service.create_refresh_token(self.user)

        claims = service.decode_token(
            token,
            expected_type=TokenType.REFRESH,
        )

        self.assertEqual(claims.token_type, TokenType.REFRESH)

    def test_rejects_unexpected_token_type(self) -> None:
        service = JWTService(
            self.settings,
            clock=lambda: self.now,
        )

        token = service.create_access_token(self.user)

        with self.assertRaises(UnexpectedTokenTypeError):
            service.decode_token(
                token,
                expected_type=TokenType.REFRESH,
            )

    def test_rejects_wrong_signing_secret(self) -> None:
        issuing_service = JWTService(
            self.settings,
            clock=lambda: self.now,
        )

        validating_service = JWTService(
            AtlasAPISettings(
                jwt_secret="different-secret-" + ("y" * 48),
                jwt_issuer="atlas-test",
                jwt_audience="atlas-test-client",
            )
        )

        token = issuing_service.create_access_token(self.user)

        with self.assertRaises(InvalidTokenError):
            validating_service.decode_token(token)

    def test_rejects_expired_token(self) -> None:
        expired_now = datetime.now(timezone.utc) - timedelta(hours=1)

        service = JWTService(
            AtlasAPISettings(
                jwt_secret="atlas-expired-secret-" + ("z" * 48),
                jwt_issuer="atlas-test",
                jwt_audience="atlas-test-client",
                access_token_minutes=1,
            ),
            clock=lambda: expired_now,
        )

        token = service.create_access_token(self.user)

        with self.assertRaises(ExpiredTokenError):
            service.decode_token(token)


if __name__ == "__main__":
    unittest.main()
