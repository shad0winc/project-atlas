from __future__ import annotations

import json
from pathlib import Path

import pytest

from atlas.dashboard_runtime import (
    DashboardRuntimeError,
    health_report_from_payload,
    publish_snapshot,
    read_health_snapshot,
)
from atlas.health import HealthCheck, HealthReport, HealthStatus


def _payload() -> dict[str, object]:
    return HealthReport(
        checks=[
            HealthCheck(
                name="Docker Engine",
                category="infrastructure",
                status=HealthStatus.HEALTHY,
                message="Docker daemon is available",
            )
        ],
        generated_at="2026-08-29T16:00:00Z",
    ).to_dict()


def test_health_report_from_payload_round_trips() -> None:
    report = health_report_from_payload(_payload())
    assert report.generated_at == "2026-08-29T16:00:00Z"
    assert report.status is HealthStatus.HEALTHY
    assert report.score == 100
    assert report.checks[0].category == "infrastructure"


def test_read_health_snapshot_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(DashboardRuntimeError, match="unavailable"):
        read_health_snapshot(tmp_path / "missing.json")


def test_read_health_snapshot_rejects_schema(tmp_path: Path) -> None:
    path = tmp_path / "health.json"
    payload = _payload()
    payload["schema_version"] = 999
    path.write_text(json.dumps(payload))
    with pytest.raises(DashboardRuntimeError, match="schema"):
        read_health_snapshot(path)


def test_publish_snapshot_is_readable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Filesystem ownership changes require root in production. Keep the unit
    # test focused on serialization/atomic replacement behavior.
    monkeypatch.setattr("atlas.dashboard_runtime.os.chown", lambda *args: None)
    monkeypatch.setattr("atlas.dashboard_runtime.os.fchown", lambda *args: None)
    destination = tmp_path / "runtime" / "health.json"
    publish_snapshot(_payload(), destination)
    report = read_health_snapshot(destination)
    assert report.score == 100
    assert destination.stat().st_mode & 0o777 == 0o640
