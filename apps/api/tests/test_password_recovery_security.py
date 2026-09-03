"""Security integration tests for Atlas password recovery."""

from __future__ import annotations

import unittest
from types import SimpleNamespace

from atlas_api.auth.models import TokenClaims, TokenType
from atlas_api.auth.sessions import RefreshSessionRegistry
from atlas_api.auth.throttling import PasswordRecoveryRequestLimiter
from atlas_api.services.password_recovery import PasswordRecoveryService


class UsersDouble:
    def list_users(self):
        return [
            {
                "user_id": "user-123",
                "email": "member@example.test",
                "status": "active",
            }
        ]

    def get_user(self, user_id):
        if user_id != "user-123":
            raise KeyError(user_id)

        return {
            "user_id": "user-123",
            "email": "member@example.test",
            "status": "active",
        }


class RecoveriesDouble:
    def __init__(self):
        self.created = 0
        self.completed = []
        self.revoked = []

    def create(self, *, user_id, expires_in):
        self.created += 1
        return SimpleNamespace(
            recovery={
                "recovery_id": "pwd_test",
                "user_id": user_id,
            },
            token="atlas_reset_test",
        )

    def verify_token(self, token):
        if token != "atlas_reset_test":
            raise AssertionError("unexpected token")

        return {
            "recovery_id": "pwd_test",
            "user_id": "user-123",
        }

    def complete(self, recovery_id):
        self.completed.append(recovery_id)
        return {
            "recovery_id": recovery_id,
            "user_id": "user-123",
            "status": "completed",
        }

    def revoke(self, recovery_id):
        self.revoked.append(recovery_id)
        return {
            "recovery_id": recovery_id,
            "status": "revoked",
        }


class WriterDouble:
    def __init__(self):
        self.calls = []

    def set_user_password(self, user_id, password):
        self.calls.append((user_id, password))


class EmailDouble:
    def __init__(self):
        self.calls = []

    def send_password_reset(
        self,
        *,
        recipient,
        reset_url,
        expires_minutes,
    ):
        self.calls.append(
            {
                "recipient": recipient,
                "reset_url": reset_url,
                "expires_minutes": expires_minutes,
            }
        )


def refresh_claims(token_id, subject="user-123"):
    return TokenClaims(
        subject=subject,
        username="member",
        roles=("member",),
        token_type=TokenType.REFRESH,
        token_id=token_id,
        issued_at=900,
        expires_at=2000,
    )


class PasswordRecoveryRequestLimiterTests(unittest.TestCase):
    def test_request_limit_is_email_scoped_and_case_insensitive(self):
        limiter = PasswordRecoveryRequestLimiter(
            max_requests=2,
            window_seconds=60,
            clock=lambda: 1000.0,
        )

        limiter.record("Member@Example.test")
        limiter.record(" member@example.test ")

        self.assertEqual(
            limiter.retry_after("MEMBER@example.test"),
            60,
        )
        self.assertIsNone(
            limiter.retry_after("friend@example.test")
        )

    def test_request_window_expires(self):
        now = [1000.0]
        limiter = PasswordRecoveryRequestLimiter(
            max_requests=1,
            window_seconds=60,
            clock=lambda: now[0],
        )

        limiter.record("member@example.test")
        self.assertEqual(
            limiter.retry_after("member@example.test"),
            60,
        )

        now[0] = 1060.0

        self.assertIsNone(
            limiter.retry_after("member@example.test")
        )


class PasswordRecoverySecurityIntegrationTests(unittest.TestCase):
    def test_throttled_request_does_not_send_second_email(self):
        limiter = PasswordRecoveryRequestLimiter(
            max_requests=1,
            window_seconds=60,
            clock=lambda: 1000.0,
        )
        recoveries = RecoveriesDouble()
        email = EmailDouble()

        service = PasswordRecoveryService(
            users=UsersDouble(),
            recoveries=recoveries,
            identity_writer=WriterDouble(),
            email_sender=email,
            base_url="https://atlas.example.test",
            request_limiter=limiter,
        )

        service.request_reset("member@example.test")
        service.request_reset("MEMBER@example.test")

        self.assertEqual(recoveries.created, 1)
        self.assertEqual(len(email.calls), 1)

    def test_successful_reset_revokes_all_user_refresh_sessions(self):
        registry = RefreshSessionRegistry(clock=lambda: 1000)
        registry.register(refresh_claims("refresh-1"))
        registry.register(refresh_claims("refresh-2"))
        registry.register(
            refresh_claims(
                "refresh-other",
                subject="other-user",
            )
        )

        recoveries = RecoveriesDouble()
        writer = WriterDouble()

        service = PasswordRecoveryService(
            users=UsersDouble(),
            recoveries=recoveries,
            identity_writer=writer,
            email_sender=EmailDouble(),
            base_url="https://atlas.example.test",
            refresh_sessions=registry,
        )

        service.reset_password(
            token="atlas_reset_test",
            new_password="new-password",
        )

        self.assertEqual(
            writer.calls,
            [("user-123", "new-password")],
        )
        self.assertEqual(
            recoveries.completed,
            ["pwd_test"],
        )
        self.assertEqual(registry.active_count, 1)
        self.assertFalse(
            registry.consume(refresh_claims("refresh-1"))
        )
        self.assertFalse(
            registry.consume(refresh_claims("refresh-2"))
        )
        self.assertTrue(
            registry.consume(
                refresh_claims(
                    "refresh-other",
                    subject="other-user",
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
