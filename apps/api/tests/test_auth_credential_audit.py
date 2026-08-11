"""Audit contracts for pre-service authentication credential rejection."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from atlas.user_profiles import UserProfileError
from atlas_api.auth.exceptions import InvalidTokenError
from atlas_api.dependencies import (
    clear_dependency_caches,
    get_current_user,
    get_login_attempt_limiter,
    get_refresh_session_registry,
    get_security_audit_writer,
    resolve_refresh_user,
)
from atlas_api.security.audit import SecurityAuditError


class RecordingAuditWriter:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []

    def publish(self, name, payload) -> None:
        self.events.append((name, dict(payload)))


class FailingAuditWriter:
    def publish(self, name, payload) -> None:
        raise SecurityAuditError("audit unavailable")


def bearer(value: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=value,
    )


def active_profile(user_id: str = "usr_test") -> dict[str, object]:
    return {
        "user_id": user_id,
        "username": "michael",
        "display_name": "Michael",
        "roles": ["member"],
        "status": "active",
        "jellyfin_user_id": "jellyfin-test",
    }


def test_missing_bearer_emits_access_rejection() -> None:
    audit = RecordingAuditWriter()

    with pytest.raises(HTTPException) as caught:
        get_current_user(
            credentials=None,
            jwt_service=Mock(),
            profiles=Mock(),
            audit_writer=audit,
        )

    assert caught.value.status_code == 401
    assert audit.events == [
        (
            "security.authentication.access_rejected",
            {"reason": "missing_bearer"},
        )
    ]


def test_invalid_access_value_is_never_audited() -> None:
    jwt_service = Mock()
    jwt_service.decode_token.side_effect = InvalidTokenError("invalid")
    audit = RecordingAuditWriter()
    supplied_value = "never-record-this-access-value"

    with pytest.raises(HTTPException) as caught:
        get_current_user(
            credentials=bearer(supplied_value),
            jwt_service=jwt_service,
            profiles=Mock(),
            audit_writer=audit,
        )

    assert caught.value.status_code == 401
    assert audit.events == [
        (
            "security.authentication.access_rejected",
            {"reason": "invalid_or_expired"},
        )
    ]
    assert supplied_value not in repr(audit.events)


def test_missing_access_profile_records_verified_subject() -> None:
    jwt_service = Mock()
    jwt_service.decode_token.return_value = SimpleNamespace(
        subject="usr_missing"
    )
    profiles = Mock()
    profiles.get_user.side_effect = UserProfileError("not found")
    audit = RecordingAuditWriter()

    with pytest.raises(HTTPException) as caught:
        get_current_user(
            credentials=bearer("access-value"),
            jwt_service=jwt_service,
            profiles=profiles,
            audit_writer=audit,
        )

    assert caught.value.status_code == 401
    assert audit.events == [
        (
            "security.authentication.access_rejected",
            {
                "reason": "profile_unavailable",
                "user_id": "usr_missing",
            },
        )
    ]


def test_inactive_access_profile_is_audited() -> None:
    jwt_service = Mock()
    jwt_service.decode_token.return_value = SimpleNamespace(
        subject="usr_disabled"
    )
    profiles = Mock()
    profiles.get_user.return_value = {"status": "disabled"}
    audit = RecordingAuditWriter()

    with pytest.raises(HTTPException):
        get_current_user(
            credentials=bearer("access-value"),
            jwt_service=jwt_service,
            profiles=profiles,
            audit_writer=audit,
        )

    assert audit.events == [
        (
            "security.authentication.access_rejected",
            {
                "reason": "profile_inactive",
                "user_id": "usr_disabled",
            },
        )
    ]


def test_valid_access_identity_emits_no_rejection() -> None:
    jwt_service = Mock()
    jwt_service.decode_token.return_value = SimpleNamespace(subject="usr_test")
    profiles = Mock()
    profiles.get_user.return_value = active_profile()
    audit = RecordingAuditWriter()

    user = get_current_user(
        credentials=bearer("valid-access-value"),
        jwt_service=jwt_service,
        profiles=profiles,
        audit_writer=audit,
    )

    assert user.user_id == "usr_test"
    assert audit.events == []


def test_missing_refresh_value_emits_session_credential_rejection() -> None:
    audit = RecordingAuditWriter()

    with pytest.raises(HTTPException) as caught:
        resolve_refresh_user(
            "   ",
            jwt_service=Mock(),
            profiles=Mock(),
            audit_writer=audit,
        )

    assert caught.value.status_code == 401
    assert audit.events == [
        (
            "security.session.credential_rejected",
            {"reason": "missing_value"},
        )
    ]


def test_invalid_refresh_value_is_never_audited() -> None:
    jwt_service = Mock()
    jwt_service.decode_token.side_effect = InvalidTokenError("invalid")
    audit = RecordingAuditWriter()
    supplied_value = "never-record-this-refresh-value"

    with pytest.raises(HTTPException):
        resolve_refresh_user(
            supplied_value,
            jwt_service=jwt_service,
            profiles=Mock(),
            audit_writer=audit,
        )

    assert audit.events == [
        (
            "security.session.credential_rejected",
            {"reason": "invalid_or_expired"},
        )
    ]
    assert supplied_value not in repr(audit.events)


def test_valid_refresh_identity_emits_no_pre_service_rejection() -> None:
    jwt_service = Mock()
    jwt_service.decode_token.return_value = SimpleNamespace(subject="usr_test")
    profiles = Mock()
    profiles.get_user.return_value = active_profile()
    audit = RecordingAuditWriter()

    user = resolve_refresh_user(
        "valid-refresh-value",
        jwt_service=jwt_service,
        profiles=profiles,
        audit_writer=audit,
    )

    assert user.user_id == "usr_test"
    assert audit.events == []


def test_audit_delivery_failure_fails_closed_before_401() -> None:
    jwt_service = Mock()
    jwt_service.decode_token.side_effect = InvalidTokenError("invalid")

    with pytest.raises(SecurityAuditError, match="audit unavailable"):
        get_current_user(
            credentials=bearer("access-value"),
            jwt_service=jwt_service,
            profiles=Mock(),
            audit_writer=FailingAuditWriter(),
        )


def test_dependency_cache_clear_resets_security_state(
    tmp_path,
    monkeypatch,
) -> None:
    first_path = tmp_path / "first-events.jsonl"
    second_path = tmp_path / "second-events.jsonl"

    clear_dependency_caches()
    monkeypatch.setenv("ATLAS_SECURITY_AUDIT_PATH", str(first_path))

    first_sessions = get_refresh_session_registry()
    first_limiter = get_login_attempt_limiter()
    first_writer = get_security_audit_writer()

    monkeypatch.setenv("ATLAS_SECURITY_AUDIT_PATH", str(second_path))
    assert get_security_audit_writer() is first_writer

    try:
        clear_dependency_caches()

        assert get_refresh_session_registry() is not first_sessions
        assert get_login_attempt_limiter() is not first_limiter
        assert get_security_audit_writer() is not first_writer
        assert get_security_audit_writer().path == second_path
    finally:
        clear_dependency_caches()
