from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from atlas.service_lifecycle import (
    ServiceLifecycleError,
)
from atlas.service_lifecycle.runtime_snapshot_publish import (
    RUNTIME_DIRECTORY_MODE,
    RUNTIME_FILE_MODE,
    RUNTIME_GROUP_GID,
    RUNTIME_OWNER_UID,
    publish_runtime_snapshot,
)


def _payload(
    generated_at: str = "2026-08-29T02:50:00Z",
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "generated_at": generated_at,
        "provider": "docker-compose",
        "services": [],
        "history": {
            "provider": "docker-compose",
            "generated_at": generated_at,
            "total_records": 0,
            "counts": {},
            "requires_attention": False,
            "records": [],
        },
    }


@pytest.fixture
def ownership_calls(monkeypatch):
    calls: list[tuple[str, int, int]] = []

    def fake_chown(path, uid, gid):
        calls.append(
            ("chown", uid, gid)
        )

    def fake_fchown(fd, uid, gid):
        calls.append(
            ("fchown", uid, gid)
        )

    monkeypatch.setattr(
        os,
        "chown",
        fake_chown,
    )
    monkeypatch.setattr(
        os,
        "fchown",
        fake_fchown,
    )

    return calls


def test_publish_runtime_snapshot_writes_atomic_json(
    tmp_path: Path,
    ownership_calls,
) -> None:
    directory = tmp_path / "services"
    destination = directory / "latest.json"

    result = publish_runtime_snapshot(
        _payload(),
        destination,
    )

    assert result == destination
    assert destination.is_file()

    payload = json.loads(
        destination.read_text(encoding="utf-8")
    )

    assert payload["schema_version"] == 1
    assert payload["provider"] == "docker-compose"

    assert (
        destination.stat().st_mode & 0o777
    ) == RUNTIME_FILE_MODE

    assert (
        directory.stat().st_mode & 0o777
    ) == RUNTIME_DIRECTORY_MODE

    assert (
        "chown",
        RUNTIME_OWNER_UID,
        RUNTIME_GROUP_GID,
    ) in ownership_calls

    assert (
        "fchown",
        RUNTIME_OWNER_UID,
        RUNTIME_GROUP_GID,
    ) in ownership_calls

    assert list(
        directory.glob(".latest.json.*")
    ) == []


def test_publish_runtime_snapshot_atomically_replaces_existing(
    tmp_path: Path,
    ownership_calls,
) -> None:
    directory = tmp_path / "services"
    destination = directory / "latest.json"

    publish_runtime_snapshot(
        _payload("2026-08-29T02:50:00Z"),
        destination,
    )

    publish_runtime_snapshot(
        _payload("2026-08-29T02:51:00Z"),
        destination,
    )

    payload = json.loads(
        destination.read_text(encoding="utf-8")
    )

    assert payload["generated_at"] == (
        "2026-08-29T02:51:00Z"
    )

    assert list(
        directory.glob(".latest.json.*")
    ) == []


def test_publish_runtime_snapshot_cleans_temporary_on_replace_failure(
    tmp_path: Path,
    monkeypatch,
    ownership_calls,
) -> None:
    directory = tmp_path / "services"
    destination = directory / "latest.json"

    def fail_replace(source, target):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(
        os,
        "replace",
        fail_replace,
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="unable to publish",
    ):
        publish_runtime_snapshot(
            _payload(),
            destination,
        )

    assert not destination.exists()

    assert list(
        directory.glob(".latest.json.*")
    ) == []


def test_publish_runtime_snapshot_does_not_create_parent_tree(
    tmp_path: Path,
    ownership_calls,
) -> None:
    destination = (
        tmp_path
        / "missing"
        / "services"
        / "latest.json"
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="unable to create",
    ):
        publish_runtime_snapshot(
            _payload(),
            destination,
        )

    assert not (
        tmp_path / "missing"
    ).exists()


def test_runtime_snapshot_permission_contract_is_bounded() -> None:
    assert RUNTIME_OWNER_UID == 0
    assert RUNTIME_GROUP_GID == 20000
    assert RUNTIME_DIRECTORY_MODE == 0o750
    assert RUNTIME_FILE_MODE == 0o640


def test_runtime_snapshot_publisher_has_no_recursive_permission_logic():
    source = Path(
        "atlas/service_lifecycle/"
        "runtime_snapshot_publish.py"
    ).read_text(encoding="utf-8")

    forbidden = (
        "chmod -R",
        "chown -R",
        ".rglob(",
        ".glob(\"**",
        "os.walk(",
    )

    for value in forbidden:
        assert value not in source
