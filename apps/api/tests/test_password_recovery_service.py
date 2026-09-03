"""Security behavior for Atlas password-recovery orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from atlas.password_recovery import PasswordRecoveryError
from atlas_api.services.email_sender import EmailDeliveryError
from atlas_api.services.identity_writer import IdentityWriterError
from atlas_api.services.password_recovery import (
    PasswordRecoveryService,
    PasswordRecoveryServiceError,
)


class FakeUsers:
    def __init__(
        self,
        profiles: list[dict[str, Any]],
    ) -> None:
        self.profiles = profiles

    def list_users(self) -> list[dict[str, Any]]:
        return list(self.profiles)

    def get_user(
        self,
        identifier: str,
    ) -> dict[str, Any]:
        for profile in self.profiles:
            if profile["user_id"] == identifier:
                return dict(profile)
        raise ValueError("user not found")


@dataclass
class FakeIssue:
    recovery: dict[str, Any]
    token: str


class FakeRecoveries:
    def __init__(self) -> None:
        self.created: list[str] = []
        self.revoked: list[str] = []
        self.completed: list[str] = []
        self.record = {
            "recovery_id": "pwd_123",
            "user_id": "user-1",
        }
        self.fail_verify = False

    def create(
        self,
        *,
        user_id: str,
        expires_in: Any,
    ) -> FakeIssue:
        self.created.append(user_id)
        self.record = {
            "recovery_id": "pwd_123",
            "user_id": user_id,
        }
        return FakeIssue(
            recovery=dict(self.record),
            token="atlas_reset_secret",
        )

    def revoke(
        self,
        recovery_id: str,
    ) -> None:
        self.revoked.append(recovery_id)

    def verify_token(
        self,
        token: str,
    ) -> dict[str, Any]:
        if self.fail_verify:
            raise PasswordRecoveryError("invalid token")
        return dict(self.record)

    def complete(
        self,
        recovery_id: str,
    ) -> None:
        self.completed.append(recovery_id)


class FakeWriter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []
        self.fail = False

    def set_user_password(
        self,
        identifier: str,
        new_password: str,
    ) -> None:
        if self.fail:
            raise IdentityWriterError(
                "writer unavailable"
            )
        self.calls.append(
            (identifier, new_password)
        )


class FakeEmail:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = False

    def send_password_reset(
        self,
        *,
        recipient: str,
        reset_url: str,
        expires_minutes: int,
    ) -> None:
        if self.fail:
            raise EmailDeliveryError(
                "delivery failed"
            )

        self.calls.append(
            {
                "recipient": recipient,
                "reset_url": reset_url,
                "expires_minutes": expires_minutes,
            }
        )


def _service(
    *,
    profiles: list[dict[str, Any]],
) -> tuple[
    PasswordRecoveryService,
    FakeRecoveries,
    FakeWriter,
    FakeEmail,
    list[tuple[str, dict[str, object]]],
]:
    recoveries = FakeRecoveries()
    writer = FakeWriter()
    email = FakeEmail()
    audit: list[
        tuple[str, dict[str, object]]
    ] = []

    service = PasswordRecoveryService(
        users=FakeUsers(profiles),
        recoveries=recoveries,
        identity_writer=writer,
        email_sender=email,
        base_url="https://atlas.example.test",
        expires_minutes=60,
        audit_publisher=lambda event, payload: audit.append(
            (event, payload)
        ),
    )

    return service, recoveries, writer, email, audit


def test_request_existing_active_user_sends_email() -> None:
    (
        service,
        recoveries,
        _writer,
        email,
        _audit,
    ) = _service(
        profiles=[
            {
                "user_id": "user-1",
                "email": "member@example.test",
                "status": "active",
            }
        ]
    )

    service.request_reset(" MEMBER@example.test ")

    assert recoveries.created == ["user-1"]
    assert len(email.calls) == 1
    assert (
        email.calls[0]["recipient"]
        == "member@example.test"
    )
    assert (
        email.calls[0]["reset_url"]
        == (
            "https://atlas.example.test/reset-password"
            "#token=atlas_reset_secret"
        )
    )


def test_request_unknown_user_does_not_issue_token() -> None:
    (
        service,
        recoveries,
        _writer,
        email,
        _audit,
    ) = _service(profiles=[])

    service.request_reset("unknown@example.test")

    assert recoveries.created == []
    assert email.calls == []


def test_request_disabled_user_does_not_issue_token() -> None:
    (
        service,
        recoveries,
        _writer,
        email,
        _audit,
    ) = _service(
        profiles=[
            {
                "user_id": "user-1",
                "email": "member@example.test",
                "status": "disabled",
            }
        ]
    )

    service.request_reset("member@example.test")

    assert recoveries.created == []
    assert email.calls == []


def test_delivery_failure_revokes_new_token() -> None:
    (
        service,
        recoveries,
        _writer,
        email,
        _audit,
    ) = _service(
        profiles=[
            {
                "user_id": "user-1",
                "email": "member@example.test",
                "status": "active",
            }
        ]
    )

    email.fail = True

    service.request_reset("member@example.test")

    assert recoveries.revoked == ["pwd_123"]


def test_reset_changes_password_then_consumes_token() -> None:
    (
        service,
        recoveries,
        writer,
        _email,
        _audit,
    ) = _service(
        profiles=[
            {
                "user_id": "user-1",
                "email": "member@example.test",
                "status": "active",
            }
        ]
    )

    service.reset_password(
        token="atlas_reset_secret",
        new_password="new-secret",
    )

    assert writer.calls == [
        ("user-1", "new-secret")
    ]
    assert recoveries.completed == ["pwd_123"]


def test_writer_failure_does_not_consume_token() -> None:
    (
        service,
        recoveries,
        writer,
        _email,
        _audit,
    ) = _service(
        profiles=[
            {
                "user_id": "user-1",
                "email": "member@example.test",
                "status": "active",
            }
        ]
    )

    writer.fail = True

    with pytest.raises(
        PasswordRecoveryServiceError
    ):
        service.reset_password(
            token="atlas_reset_secret",
            new_password="new-secret",
        )

    assert recoveries.completed == []


def test_invalid_token_never_reaches_writer() -> None:
    (
        service,
        recoveries,
        writer,
        _email,
        _audit,
    ) = _service(
        profiles=[
            {
                "user_id": "user-1",
                "email": "member@example.test",
                "status": "active",
            }
        ]
    )

    recoveries.fail_verify = True

    with pytest.raises(
        PasswordRecoveryServiceError,
        match="invalid or expired",
    ):
        service.reset_password(
            token="atlas_reset_invalid",
            new_password="new-secret",
        )

    assert writer.calls == []
