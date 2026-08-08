"""Security audit contracts for authentication and refresh sessions."""

from __future__ import annotations

import pytest

from atlas_api.auth.exceptions import (
    AuthenticationRateLimitError,
    InvalidCredentialsError,
)
from atlas_api.auth.jwt import JWTService
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.auth.service import AuthenticationService
from atlas_api.core.settings import AtlasAPISettings


USER = AuthenticatedUser(
    user_id="user-123",
    username="michael",
    display_name="Michael",
    roles=("admin",),
    provider="jellyfin",
)


class FakeProvider:
    def authenticate(self, username: str, password: str):
        if username == "michael" and password == "atlas-password":
            return USER
        return None


class AlwaysThrottledLimiter:
    def retry_after(self, username: str):
        return 47

    def record_failure(self, username: str) -> None:
        raise AssertionError("throttled login must not record another failure")

    def reset(self, username: str) -> None:
        raise AssertionError("throttled login must not reset state")


def build_service(events, *, login_attempts=None):
    jwt_service = JWTService(
        AtlasAPISettings(
            jwt_secret="atlas-security-audit-test-" + ("s" * 48),
            jwt_issuer="atlas-test",
            jwt_audience="atlas-test-client",
        )
    )
    service = AuthenticationService(
        FakeProvider(),
        jwt_service,
        login_attempts=login_attempts,
        audit_publisher=lambda name, payload: events.append(
            (name, dict(payload))
        ),
    )
    return service


def test_successful_login_is_audited_without_credentials() -> None:
    events = []
    service = build_service(events)

    service.login("michael", "atlas-password")

    assert events == [
        (
            "security.authentication.succeeded",
            {
                "user_id": "user-123",
                "username": "michael",
                "provider": "jellyfin",
            },
        )
    ]


def test_failed_login_is_audited_without_password() -> None:
    events = []
    service = build_service(events)

    with pytest.raises(InvalidCredentialsError):
        service.login("michael", "wrong-password")

    assert events == [
        (
            "security.authentication.failed",
            {
                "username": "michael",
                "reason": "invalid_credentials",
            },
        )
    ]


def test_throttled_login_is_audited() -> None:
    events = []
    service = build_service(
        events,
        login_attempts=AlwaysThrottledLimiter(),
    )

    with pytest.raises(AuthenticationRateLimitError):
        service.login("michael", "anything")

    assert events == [
        (
            "security.authentication.throttled",
            {
                "username": "michael",
                "retry_after_seconds": 47,
            },
        )
    ]


def test_refresh_success_and_replay_rejection_are_audited() -> None:
    events = []
    service = build_service(events)
    original = service.login("michael", "atlas-password")
    events.clear()

    service.refresh(original.refresh_token, USER)

    assert events == [
        (
            "security.session.refreshed",
            {
                "user_id": "user-123",
                "username": "michael",
                "provider": "jellyfin",
            },
        )
    ]

    events.clear()
    with pytest.raises(InvalidCredentialsError):
        service.refresh(original.refresh_token, USER)

    assert events == [
        (
            "security.session.refresh_rejected",
            {
                "user_id": "user-123",
                "username": "michael",
                "provider": "jellyfin",
                "reason": "inactive_or_replayed",
            },
        )
    ]


def test_logout_revocation_is_audited() -> None:
    events = []
    service = build_service(events)
    tokens = service.login("michael", "atlas-password")
    events.clear()

    service.logout(tokens.refresh_token, USER)

    assert events == [
        (
            "security.session.revoked",
            {
                "user_id": "user-123",
                "username": "michael",
                "provider": "jellyfin",
            },
        )
    ]


def test_audit_delivery_failure_fails_closed() -> None:
    jwt_service = JWTService(
        AtlasAPISettings(
            jwt_secret="atlas-security-audit-failure-" + ("s" * 48),
            jwt_issuer="atlas-test",
            jwt_audience="atlas-test-client",
        )
    )

    def fail_audit(_name, _payload):
        raise RuntimeError("audit unavailable")

    service = AuthenticationService(
        FakeProvider(),
        jwt_service,
        audit_publisher=fail_audit,
    )

    with pytest.raises(RuntimeError, match="audit unavailable"):
        service.login("michael", "atlas-password")


def test_emitted_payloads_never_use_credential_key_names() -> None:
    events = []
    service = build_service(events)
    tokens = service.login("michael", "atlas-password")
    service.refresh(tokens.refresh_token, USER)

    forbidden = ("credential", "jwt", "password", "secret", "token")
    for _event_name, payload in events:
        for key in payload:
            lowered = key.lower()
            assert not any(component in lowered for component in forbidden)
