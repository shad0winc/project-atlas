"""Tests for the credential-safe Atlas API security audit writer."""

from __future__ import annotations

import json
import os

import pytest

from atlas_api.security.audit import SecurityAuditError, SecurityAuditWriter


def private_journal(tmp_path):
    path = tmp_path / "events.jsonl"
    path.write_text("", encoding="utf-8")
    path.chmod(0o660)
    return path


def test_security_audit_appends_schema_two_event(tmp_path) -> None:
    path = private_journal(tmp_path)
    writer = SecurityAuditWriter(path)

    writer.publish(
        "security.authentication.succeeded",
        {"user_id": "user-123", "provider": "jellyfin"},
    )

    event = json.loads(path.read_text(encoding="utf-8"))
    assert event["schema"] == 2
    assert event["id"].startswith("evt-")
    assert event["source"] == "atlas-api"
    assert event["event"] == "security.authentication.succeeded"
    assert event["payload"] == {
        "provider": "jellyfin",
        "user_id": "user-123",
    }


def test_security_audit_appends_without_replacing_existing_events(tmp_path) -> None:
    path = private_journal(tmp_path)
    path.write_text('{"existing":true}\n', encoding="utf-8")
    path.chmod(0o660)

    SecurityAuditWriter(path).publish(
        "security.session.revoked",
        {"user_id": "user-123"},
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0]) == {"existing": True}
    assert json.loads(lines[1])["event"] == "security.session.revoked"


@pytest.mark.parametrize(
    "payload",
    [
        {"password": "never"},
        {"refresh_token": "never"},
        {"nested": {"jwt_secret": "never"}},
        {"items": [{"invitation-token": "never"}]},
    ],
)
def test_security_audit_rejects_sensitive_payload_keys(tmp_path, payload) -> None:
    path = private_journal(tmp_path)

    with pytest.raises(ValueError, match="sensitive key"):
        SecurityAuditWriter(path).publish(
            "security.authentication.failed",
            payload,
        )

    assert path.read_text(encoding="utf-8") == ""


def test_security_audit_requires_security_event_namespace(tmp_path) -> None:
    path = private_journal(tmp_path)

    with pytest.raises(ValueError, match="must start with 'security[.]'"):
        SecurityAuditWriter(path).publish("identity.registration.completed")


def test_security_audit_refuses_to_create_missing_journal(tmp_path) -> None:
    path = tmp_path / "missing.jsonl"

    with pytest.raises(SecurityAuditError, match="unavailable"):
        SecurityAuditWriter(path).publish("security.authentication.failed")

    assert not path.exists()


def test_security_audit_refuses_symlink_journal(tmp_path) -> None:
    target = private_journal(tmp_path)
    link = tmp_path / "events-link.jsonl"
    link.symlink_to(target)

    with pytest.raises(SecurityAuditError, match="unavailable"):
        SecurityAuditWriter(link).publish("security.authentication.failed")


def test_security_audit_refuses_world_accessible_journal(tmp_path) -> None:
    path = private_journal(tmp_path)
    path.chmod(0o664)

    with pytest.raises(SecurityAuditError, match="other permissions"):
        SecurityAuditWriter(path).publish("security.authentication.failed")


def test_security_audit_writer_uses_explicit_environment_path(
    tmp_path, monkeypatch
) -> None:
    path = private_journal(tmp_path)
    monkeypatch.setenv("ATLAS_SECURITY_AUDIT_PATH", str(path))

    writer = SecurityAuditWriter.from_environment()

    assert writer.path == path
