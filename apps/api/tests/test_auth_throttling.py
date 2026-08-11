"""Tests for account-scoped Atlas login throttling."""

from __future__ import annotations

import unittest

from atlas_api.auth.exceptions import (
    AuthenticationProviderError,
    AuthenticationRateLimitError,
    InvalidCredentialsError,
)
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.auth.service import AuthenticationService
from atlas_api.auth.throttling import LoginAttemptLimiter
from atlas_api.core.settings import AtlasAPISettings


class CountingAuthenticationProvider:
    def __init__(self) -> None:
        self.calls = 0
        self.unavailable = False

    def authenticate(
        self,
        username: str,
        password: str,
    ) -> AuthenticatedUser | None:
        self.calls += 1

        if self.unavailable:
            raise AuthenticationProviderError("provider unavailable")

        if username != "michael" or password != "atlas-password":
            return None

        return AuthenticatedUser(
            user_id="user-123",
            username="michael",
            display_name="Michael",
            roles=("member",),
        )


class LoginAttemptLimiterTests(unittest.TestCase):
    def test_limit_is_account_scoped_and_case_insensitive(self) -> None:
        limiter = LoginAttemptLimiter(
            max_failures=2,
            window_seconds=60,
            clock=lambda: 1000.0,
        )

        limiter.record_failure("Michael")
        limiter.record_failure(" michael ")

        self.assertEqual(limiter.retry_after("MICHAEL"), 60)
        self.assertIsNone(limiter.retry_after("friend"))

    def test_failures_expire_after_window(self) -> None:
        now = [1000.0]
        limiter = LoginAttemptLimiter(
            max_failures=1,
            window_seconds=60,
            clock=lambda: now[0],
        )

        limiter.record_failure("michael")
        self.assertEqual(limiter.retry_after("michael"), 60)

        now[0] = 1060.0

        self.assertIsNone(limiter.retry_after("michael"))

    def test_reset_clears_failures(self) -> None:
        limiter = LoginAttemptLimiter(
            max_failures=1,
            window_seconds=60,
            clock=lambda: 1000.0,
        )

        limiter.record_failure("michael")
        limiter.reset("michael")

        self.assertIsNone(limiter.retry_after("michael"))


class LoginAttemptAuthenticationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.now = [1000.0]
        self.provider = CountingAuthenticationProvider()
        self.limiter = LoginAttemptLimiter(
            max_failures=2,
            window_seconds=60,
            clock=lambda: self.now[0],
        )
        self.service = AuthenticationService(
            self.provider,
            JWTService(
                AtlasAPISettings(
                    jwt_secret="atlas-login-throttle-test-" + ("s" * 48),
                    jwt_issuer="atlas-test",
                    jwt_audience="atlas-test-client",
                )
            ),
            login_attempts=self.limiter,
        )

    def test_provider_is_not_called_after_failure_limit(self) -> None:
        for _ in range(2):
            with self.assertRaises(InvalidCredentialsError):
                self.service.login("michael", "wrong")

        with self.assertRaises(AuthenticationRateLimitError) as caught:
            self.service.login("michael", "wrong-again")

        self.assertEqual(caught.exception.retry_after_seconds, 60)
        self.assertEqual(self.provider.calls, 2)

    def test_successful_login_resets_failure_history(self) -> None:
        with self.assertRaises(InvalidCredentialsError):
            self.service.login("michael", "wrong")

        self.service.login("michael", "atlas-password")

        with self.assertRaises(InvalidCredentialsError):
            self.service.login("michael", "wrong-again")

        self.assertIsNone(self.limiter.retry_after("michael"))

    def test_provider_outage_does_not_count_as_bad_credentials(self) -> None:
        self.provider.unavailable = True

        for _ in range(3):
            with self.assertRaises(AuthenticationProviderError):
                self.service.login("michael", "atlas-password")

        self.assertIsNone(self.limiter.retry_after("michael"))

    def test_throttle_window_reopens_authentication(self) -> None:
        for _ in range(2):
            with self.assertRaises(InvalidCredentialsError):
                self.service.login("michael", "wrong")

        self.now[0] = 1060.0

        tokens = self.service.login("michael", "atlas-password")

        self.assertTrue(tokens.access_token)
        self.assertEqual(self.provider.calls, 3)


if __name__ == "__main__":
    unittest.main()
