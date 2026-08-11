"""Tests for the API-native Atlas runtime event publisher."""

from __future__ import annotations

import inspect
import json

import pytest

import atlas_api.events as runtime_events
from atlas_api.events import (
    DEFAULT_EVENT_JOURNAL_PATH,
    RuntimeEventJournalError,
    RuntimeEventJournalPublisher,
)


def private_journal(tmp_path):
    path = tmp_path / "events.jsonl"

    path.write_text(
        "",
        encoding="utf-8",
    )

    path.chmod(
        0o660
    )

    return path


def test_runtime_event_publisher_appends_schema_two_event(
    tmp_path,
) -> None:
    path = private_journal(
        tmp_path
    )

    path.write_text(
        '{"existing":true}\n',
        encoding="utf-8",
    )

    path.chmod(
        0o660
    )

    publisher = RuntimeEventJournalPublisher(
        path
    )

    publisher.publish(
        "request.created",
        {
            "request_id": "req_test",
            "user_id": "usr_test",
        },
    )

    lines = path.read_text(
        encoding="utf-8"
    ).splitlines()

    assert json.loads(
        lines[0]
    ) == {
        "existing": True,
    }

    event = json.loads(
        lines[1]
    )

    assert event["schema"] == 2
    assert event["id"].startswith(
        "evt-"
    )
    assert event["source"] == "atlas-api"
    assert event["event"] == "request.created"
    assert event["payload"] == {
        "request_id": "req_test",
        "user_id": "usr_test",
    }


def test_runtime_event_publisher_uses_explicit_event_log(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = private_journal(
        tmp_path
    )

    monkeypatch.setenv(
        "ATLAS_EVENT_LOG",
        str(path),
    )

    publisher = (
        RuntimeEventJournalPublisher.from_environment()
    )

    assert publisher.path == path


def test_runtime_event_publisher_uses_default_mounted_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(
        "ATLAS_EVENT_LOG",
        raising=False,
    )

    publisher = (
        RuntimeEventJournalPublisher.from_environment()
    )

    assert (
        publisher.path
        == DEFAULT_EVENT_JOURNAL_PATH
    )


def test_runtime_event_publisher_refuses_missing_journal(
    tmp_path,
) -> None:
    publisher = RuntimeEventJournalPublisher(
        tmp_path / "missing.jsonl"
    )

    with pytest.raises(
        RuntimeEventJournalError,
        match="unavailable",
    ):
        publisher.publish(
            "request.created"
        )


def test_runtime_event_publisher_refuses_symlink_journal(
    tmp_path,
) -> None:
    target = private_journal(
        tmp_path
    )

    link = (
        tmp_path
        / "events-link.jsonl"
    )

    link.symlink_to(
        target
    )

    publisher = RuntimeEventJournalPublisher(
        link
    )

    with pytest.raises(
        RuntimeEventJournalError,
        match="unavailable",
    ):
        publisher.publish(
            "request.created"
        )


def test_runtime_event_publisher_refuses_world_accessible_journal(
    tmp_path,
) -> None:
    path = private_journal(
        tmp_path
    )

    path.chmod(
        0o664
    )

    publisher = RuntimeEventJournalPublisher(
        path
    )

    with pytest.raises(
        RuntimeEventJournalError,
        match="other permissions",
    ):
        publisher.publish(
            "request.created"
        )


def test_runtime_event_publisher_has_no_atlas_cli_dependency() -> None:
    source = inspect.getsource(
        runtime_events
    )

    assert "subprocess" not in source
    assert "/bin/atlas" not in source
    assert "scripts/atlas" not in source
