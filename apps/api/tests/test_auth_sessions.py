"""Tests for single-use Atlas refresh-session state."""

from __future__ import annotations

import unittest

from atlas_api.auth.exceptions import InvalidCredentialsError
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import (
    AuthenticatedUser,
    TokenClaims,
    TokenType,
)
from atlas_api.auth.service import AuthenticationService
from atlas_api.auth.sessions import RefreshSessionRegistry
from atlas_api.core.settings import AtlasAPISettings


class AuthenticationProviderDouble:
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
            roles=("member",),
        )


def refresh_claims(
    token_id: str,
    *,
    expires_at: int = 2000,
) -> TokenClaims:
    return TokenClaims(
        subject="user-123",
        username="michael",
        roles=("member",),
        token_type=TokenType.REFRESH,
        token_id=token_id,
        issued_at=900,
        expires_at=expires_at,
    )


class RefreshSessionRegistryTests(unittest.TestCase):
    def test_registered_refresh_session_is_consumed_once(self) -> None:
        registry = RefreshSessionRegistry(clock=lambda: 1000)
        claims = refresh_claims("refresh-1")

        registry.register(claims)

        self.assertTrue(registry.consume(claims))
        self.assertFalse(registry.consume(claims))
        self.assertEqual(registry.active_count, 0)

    def test_revocation_is_idempotent(self) -> None:
        registry = RefreshSessionRegistry(clock=lambda: 1000)
        claims = refresh_claims("refresh-2")

        registry.register(claims)

        self.assertTrue(registry.revoke(claims))
        self.assertFalse(registry.revoke(claims))

    def test_expired_sessions_are_pruned(self) -> None:
        now = [1000]
        registry = RefreshSessionRegistry(clock=lambda: now[0])
        claims = refresh_claims("refresh-3", expires_at=1001)

        registry.register(claims)
        now[0] = 1001

        self.assertEqual(registry.active_count, 0)
        self.assertFalse(registry.consume(claims))

    def test_access_claims_cannot_be_registered(self) -> None:
        registry = RefreshSessionRegistry(clock=lambda: 1000)
        claims = TokenClaims(
            subject="user-123",
            username="michael",
            roles=("member",),
            token_type=TokenType.ACCESS,
            token_id="access-1",
            issued_at=900,
            expires_at=2000,
        )

        with self.assertRaisesRegex(ValueError, "refresh token"):
            registry.register(claims)


    def test_revoke_subject_removes_all_matching_sessions(self) -> None:
        registry = RefreshSessionRegistry(clock=lambda: 1000)
        first = refresh_claims("refresh-subject-1")
        second = refresh_claims("refresh-subject-2")

        other = TokenClaims(
            subject="other-user",
            username="friend",
            roles=("member",),
            token_type=TokenType.REFRESH,
            token_id="refresh-other",
            issued_at=900,
            expires_at=2000,
        )

        registry.register(first)
        registry.register(second)
        registry.register(other)

        self.assertEqual(
            registry.revoke_subject("user-123"),
            2,
        )
        self.assertEqual(registry.active_count, 1)
        self.assertFalse(registry.consume(first))
        self.assertFalse(registry.consume(second))
        self.assertTrue(registry.consume(other))

    def test_revoke_subject_rejects_blank_subject(self) -> None:
        registry = RefreshSessionRegistry(clock=lambda: 1000)

        with self.assertRaisesRegex(ValueError, "subject"):
            registry.revoke_subject("   ")


class RefreshSessionAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.provider = AuthenticationProviderDouble()
        self.jwt_service = JWTService(
            AtlasAPISettings(
                jwt_secret="atlas-refresh-session-test-" + ("s" * 48),
                jwt_issuer="atlas-test",
                jwt_audience="atlas-test-client",
            )
        )
        self.service = AuthenticationService(
            self.provider,
            self.jwt_service,
        )
        self.user = AuthenticatedUser(
            user_id="user-123",
            username="michael",
            display_name="Michael",
            roles=("member",),
        )

    def test_refresh_token_replay_is_rejected(self) -> None:
        original = self.service.login(
            "michael",
            "atlas-password",
        )

        self.service.refresh(original.refresh_token, self.user)

        with self.assertRaises(InvalidCredentialsError):
            self.service.refresh(
                original.refresh_token,
                self.user,
            )

    def test_rotated_refresh_token_is_registered(self) -> None:
        original = self.service.login(
            "michael",
            "atlas-password",
        )
        rotated = self.service.refresh(
            original.refresh_token,
            self.user,
        )

        replacement = self.service.refresh(
            rotated.refresh_token,
            self.user,
        )

        self.assertNotEqual(
            replacement.refresh_token,
            rotated.refresh_token,
        )

    def test_process_restart_invalidates_refresh_session(self) -> None:
        original = self.service.login(
            "michael",
            "atlas-password",
        )
        restarted = AuthenticationService(
            self.provider,
            self.jwt_service,
        )

        with self.assertRaises(InvalidCredentialsError):
            restarted.refresh(
                original.refresh_token,
                self.user,
            )

    def test_logout_revokes_current_refresh_session(self) -> None:
        tokens = self.service.login(
            "michael",
            "atlas-password",
        )

        self.service.logout(tokens.refresh_token, self.user)
        self.service.logout(tokens.refresh_token, self.user)

        with self.assertRaises(InvalidCredentialsError):
            self.service.refresh(
                tokens.refresh_token,
                self.user,
            )


if __name__ == "__main__":
    unittest.main()
