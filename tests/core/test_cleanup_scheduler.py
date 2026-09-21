"""Scheduler registration contracts for cleanup execution."""

from __future__ import annotations

from typing import Any

import pytest

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
        "enabled": True,
        "module": None,
    }

    assert scheduler.calls == [registered]


def test_register_cleanup_execution_accepts_overrides() -> None:
    scheduler = RecordingScheduler()

    registered = register_cleanup_execution(
        scheduler,
        interval_seconds=1800,
        enabled=False,
    )

    assert registered["interval_seconds"] == 1800
    assert registered["enabled"] is False
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
