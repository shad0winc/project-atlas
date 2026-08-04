"""End-to-end execution tests for scheduled Operations collection."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from atlas.operations_scheduler import (
    register_operations_collection,
)
from atlas.scheduler import TaskScheduler


def test_registered_operations_task_is_due_initially() -> None:
    with tempfile.TemporaryDirectory() as directory:
        state = Path(directory) / "tasks.json"

        scheduler = TaskScheduler(state)

        register_operations_collection(scheduler)

        task = scheduler.task_state(
            "operations.collect",
        )

        assert task["due"] is True
        assert task["status"] == "never_run"
        assert task["run_count"] == 0


def test_scheduler_state_round_trip() -> None:
    with tempfile.TemporaryDirectory() as directory:
        state = Path(directory) / "tasks.json"

        scheduler = TaskScheduler(state)

        register_operations_collection(scheduler)

        stored = json.loads(
            state.read_text(encoding="utf-8")
        )

        assert "operations.collect" in stored["tasks"]


def test_operations_task_has_no_optional_module_event_route() -> None:
    with tempfile.TemporaryDirectory() as directory:
        state = Path(directory) / "tasks.json"
        scheduler = TaskScheduler(state)

        register_operations_collection(scheduler)

        task = scheduler.task_state(
            "operations.collect",
        )

        assert task["module"] is None


def test_scheduler_executes_real_operations_callback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    operations_root = tmp_path / "operations"
    scheduler_state = (
        tmp_path
        / "scheduler"
        / "tasks.json"
    )

    monkeypatch.setenv(
        "ATLAS_OPERATIONS_DIRECTORY",
        str(operations_root),
    )

    scheduler = TaskScheduler(
        scheduler_state,
    )
    register_operations_collection(
        scheduler,
    )

    result = scheduler.run_task(
        "operations.collect",
    )

    assert result.task == "operations.collect"
    assert result.result == "success"
    assert result.return_code == 0
    assert result.error is None
    assert result.event_error is None

    latest_path = operations_root / "latest.json"
    history_directory = operations_root / "history"

    assert latest_path.is_file()
    assert history_directory.is_dir()

    snapshots = tuple(
        history_directory.glob("*.json")
    )

    assert len(snapshots) == 1

    latest = json.loads(
        latest_path.read_text(encoding="utf-8")
    )
    snapshot = json.loads(
        snapshots[0].read_text(encoding="utf-8")
    )

    assert latest == snapshot
    assert latest["schema_version"] == 1
    assert latest["status"] in {
        "healthy",
        "warning",
        "critical",
        "unknown",
    }
    assert isinstance(latest["score"], int)

    task = scheduler.task_state(
        "operations.collect",
    )

    assert task["status"] == "healthy"
    assert task["run_count"] == 1
    assert task["failure_count"] == 0
    assert task["last_success"] is not None
    assert task["module"] is None

    history = scheduler.history(
        limit=10,
    )

    assert len(history) == 1
    assert history[0]["task"] == "operations.collect"
    assert history[0]["result"] == "success"
    assert history[0]["event_error"] is None
