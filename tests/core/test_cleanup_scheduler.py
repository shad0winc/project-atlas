"""Scheduler registration contracts for cleanup execution."""

from __future__ import annotations

from typing import Any

import pytest

from atlas.scheduler import TaskScheduler

from atlas.cleanup.scheduler import (
    CLEANUP_EXECUTION_CALLBACK,
    CLEANUP_EXECUTION_DESCRIPTION,
    CLEANUP_EXECUTION_INTERVAL_SECONDS,
    CLEANUP_EXECUTION_MODULE,
    CLEANUP_EXECUTION_TASK_NAME,
    register_cleanup_execution,
)


class RecordingScheduler:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def register(
        self,
        name: str,
        interval_seconds: int,
        callback: str,
        *,
        description: str = "",
        enabled: bool = True,
        module: str | None = None,
    ) -> dict[str, Any]:
        value = {
            "name": name,
            "interval_seconds": interval_seconds,
            "callback": callback,
            "description": description,
            "enabled": enabled,
            "module": module,
        }
        self.calls.append(value)
        return value


def test_cleanup_scheduler_constants_are_stable() -> None:
    assert CLEANUP_EXECUTION_TASK_NAME == "cleanup.execute"
    assert CLEANUP_EXECUTION_INTERVAL_SECONDS == 3600
    assert CLEANUP_EXECUTION_CALLBACK == (
        "python3 -m atlas.cleanup.scheduled_execution"
    )
    assert CLEANUP_EXECUTION_DESCRIPTION == (
        "Execute eligible Atlas media cleanup with "
        "retention revalidation"
    )
    assert CLEANUP_EXECUTION_MODULE is None


def test_register_cleanup_execution_uses_core_scheduler() -> None:
    scheduler = RecordingScheduler()

    registered = register_cleanup_execution(
        scheduler,
    )

    assert registered == {
        "name": "cleanup.execute",
        "interval_seconds": 3600,
        "callback": (
            "python3 -m atlas.cleanup.scheduled_execution"
        ),
        "description": (
            "Execute eligible Atlas media cleanup with "
            "retention revalidation"
        ),
        "enabled": False,
        "module": None,
    }

    assert scheduler.calls == [registered]


def test_register_cleanup_execution_accepts_overrides() -> None:
    scheduler = RecordingScheduler()

    registered = register_cleanup_execution(
        scheduler,
        interval_seconds=1800,
        enabled=True,
    )

    assert registered["interval_seconds"] == 1800
    assert registered["enabled"] is True
    assert registered["module"] is None


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        3600.0,
        "3600",
        None,
    ],
)
def test_register_cleanup_execution_validates_interval_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="interval_seconds must be an integer",
    ):
        register_cleanup_execution(
            RecordingScheduler(),
            interval_seconds=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_register_cleanup_execution_rejects_nonpositive_interval(
    value: int,
) -> None:
    with pytest.raises(
        ValueError,
        match="interval_seconds must be greater than zero",
    ):
        register_cleanup_execution(
            RecordingScheduler(),
            interval_seconds=value,
        )


def test_register_cleanup_execution_validates_enabled() -> None:
    with pytest.raises(
        TypeError,
        match="enabled must be a boolean",
    ):
        register_cleanup_execution(
            RecordingScheduler(),
            enabled="true",  # type: ignore[arg-type]
        )


def test_register_cleanup_execution_requires_register() -> None:
    with pytest.raises(
        TypeError,
        match="scheduler must provide a callable register method",
    ):
        register_cleanup_execution(
            object(),  # type: ignore[arg-type]
        )


def test_routine_registration_disables_previously_enabled_task() -> None:
    """An ordinary sync must not preserve accidental live activation."""

    scheduler = RecordingScheduler()

    explicitly_enabled = register_cleanup_execution(
        scheduler,
        enabled=True,
    )

    assert explicitly_enabled["enabled"] is True

    routine_registration = register_cleanup_execution(
        scheduler,
    )

    assert routine_registration["enabled"] is False

    assert scheduler.calls[0]["enabled"] is True
    assert scheduler.calls[1]["enabled"] is False

    assert scheduler.calls[0]["name"] == scheduler.calls[1]["name"]
    assert scheduler.calls[0]["callback"] == scheduler.calls[1]["callback"]


def test_real_scheduler_resync_disables_persisted_cleanup_task(
    tmp_path,
) -> None:
    """Routine registration must disable a persisted live task."""

    state_file = tmp_path / "scheduler.json"

    scheduler = TaskScheduler(state_file=state_file)

    enabled_task = register_cleanup_execution(
        scheduler,
        enabled=True,
    )

    assert enabled_task["enabled"] is True

    enabled_state = scheduler.task_state(
        CLEANUP_EXECUTION_TASK_NAME,
    )

    assert enabled_state["enabled"] is True

    # Reopen the same isolated state through a new scheduler instance.
    scheduler = TaskScheduler(state_file=state_file)

    disabled_task = register_cleanup_execution(scheduler)

    assert disabled_task["enabled"] is False

    disabled_state = scheduler.task_state(
        CLEANUP_EXECUTION_TASK_NAME,
    )

    assert disabled_state["enabled"] is False
    assert disabled_state["due"] is False
    assert disabled_state["next_run"] is None

    assert (
        disabled_state["callback"]
        == enabled_state["callback"]
    )

    scheduler = TaskScheduler(state_file=state_file)

    register_cleanup_execution(scheduler)

    final_state = scheduler.task_state(
        CLEANUP_EXECUTION_TASK_NAME,
    )

    assert final_state["enabled"] is False
    assert final_state["due"] is False
    assert final_state["next_run"] is None
