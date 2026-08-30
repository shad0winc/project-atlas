from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path

import pytest

from atlas.downloads import (
    DownloadItem,
    DownloadsError,
    DownloadsSnapshot,
    DownloadState,
    publish_snapshot,
    read_snapshot,
)


def _snapshot(now: datetime) -> DownloadsSnapshot:
    return DownloadsSnapshot.build(
        (
            DownloadItem(
                name="Example",
                category="tv",
                state=DownloadState.DOWNLOADING,
                progress=0.5,
                total_bytes=1000,
                downloaded_bytes=500,
                download_rate=100,
                upload_rate=20,
                eta_seconds=5,
            ),
        ),
        total_download_rate=100,
        total_upload_rate=20,
        generated_at=now,
    )


def test_snapshot_contains_only_bounded_download_fields() -> None:
    payload = _snapshot(datetime.now(timezone.utc)).to_dict()
    assert set(payload) == {"schema_version", "generated_at", "summary", "downloads"}
    assert set(payload["downloads"][0]) == {
        "name",
        "category",
        "state",
        "progress",
        "total_bytes",
        "downloaded_bytes",
        "download_rate",
        "upload_rate",
        "eta_seconds",
    }
    serialized = json.dumps(payload).lower()
    for forbidden in (
        "hash",
        "magnet",
        "tracker",
        "peer",
        "save_path",
        "content_path",
        "password",
        "cookie",
    ):
        assert forbidden not in serialized


def test_publish_snapshot_uses_runtime_security_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("atlas.downloads.runtime.RUNTIME_OWNER_UID", os.getuid())
    monkeypatch.setattr("atlas.downloads.runtime.RUNTIME_GROUP_GID", os.getgid())
    destination = tmp_path / "downloads" / "latest.json"
    publish_snapshot(_snapshot(datetime.now(timezone.utc)).to_dict(), destination)
    assert destination.is_file()
    assert destination.parent.stat().st_mode & 0o777 == 0o750
    assert destination.stat().st_mode & 0o777 == 0o640


def test_read_snapshot_rejects_missing_snapshot(tmp_path: Path) -> None:
    with pytest.raises(DownloadsError, match="unavailable"):
        read_snapshot(tmp_path / "missing.json")


def test_read_snapshot_rejects_stale_snapshot(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    path = tmp_path / "latest.json"
    path.write_text(
        json.dumps(_snapshot(now - timedelta(minutes=10)).to_dict()),
        encoding="utf-8",
    )
    with pytest.raises(DownloadsError, match="stale"):
        read_snapshot(path, max_age_seconds=180, now=now)


def test_read_snapshot_accepts_valid_empty_activity(tmp_path: Path) -> None:
    now = datetime.now(timezone.utc)
    path = tmp_path / "latest.json"
    payload = DownloadsSnapshot.build(
        (),
        total_download_rate=0,
        total_upload_rate=0,
        generated_at=now,
    ).to_dict()
    path.write_text(json.dumps(payload), encoding="utf-8")
    snapshot = read_snapshot(path, now=now)
    assert snapshot.downloads == ()
    assert snapshot.summary.active == 0
    assert snapshot.summary.completed == 0
