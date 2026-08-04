"""Tests for Atlas Operations scheduler registration."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from atlas.operations_scheduler import (
    OPERATIONS_COLLECTION_CALLBACK,
    OPERATIONS_COLLECTION_DESCRIPTION,
    OPERATIONS_COLLECTION_INTERVAL_SECONDS,
    OPERATIONS_COLLECTION_TASK_NAME,
    OPERATIONS_SCHEDULER_MODULE,
    register_operations_collection,
)


class FakeScheduler:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def register(
        self,
        task_name: str,
        interval_seconds: int,
        callback: str,
        *,
        description: str = "",
        enabled: bool = True,
        module: str | None = None,
    ) -> Mapping[str, Any]:
        call = {
            "name": task_name,
            "interval_seconds": interval_seconds,
            "callback": callback,
            "description": description,
            "enabled": enabled,
            "module": module,
        }
        self.calls.append(call)
        return call


def test_operations_scheduler_constants_are_stable() -> None:
    assert OPERATIONS_COLLECTION_TASK_NAME == (
        "operations.collect"
    )
    assert OPERATIONS_COLLECTION_INTERVAL_SECONDS == 3600
    assert OPERATIONS_COLLECTION_CALLBACK == (
        "python3 -m atlas.operations_scheduled_collection"
    )
    assert OPERATIONS_COLLECTION_DESCRIPTION == (
        "Persist an Atlas Operations report"
    )
    assert OPERATIONS_SCHEDULER_MODULE is None


def test_register_operations_collection_uses_defaults() -> None:
    scheduler = FakeScheduler()

    registered = register_operations_collection(
        scheduler,
    )

    assert scheduler.calls == [
        {
            "name": "operations.collect",
            "interval_seconds": 3600,
            "callback": (
                "python3 -m "
                "atlas.operations_scheduled_collection"
            ),
            "description": (
                "Persist an Atlas Operations report"
            ),
            "enabled": True,
            "module": None,
        }
    ]
    assert registered == scheduler.calls[0]


def test_register_operations_collection_accepts_overrides() -> None:
    scheduler = FakeScheduler()

    registered = register_operations_collection(
        scheduler,
        interval_seconds=900,
        enabled=False,
    )

    assert registered["interval_seconds"] == 900
    assert registered["enabled"] is False


def test_register_operations_collection_is_repeatable() -> None:
    scheduler = FakeScheduler()

    first = register_operations_collection(
        scheduler,
    )
    second = register_operations_collection(
        scheduler,
        interval_seconds=7200,
    )

    assert first["interval_seconds"] == 3600
    assert second["interval_seconds"] == 7200
    assert len(scheduler.calls) == 2


def test_register_operations_collection_validates_scheduler() -> None:
    with pytest.raises(
        TypeError,
        match="scheduler must support task registration",
    ):
        register_operations_collection(
            object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    (
        True,
        False,
        1.5,
        "3600",
        None,
    ),
)
def test_register_operations_collection_validates_interval_type(
    value: object,
) -> None:
    with pytest.raises(
        TypeError,
        match="interval_seconds must be an integer",
    ):
        register_operations_collection(
            FakeScheduler(),
            interval_seconds=value,  # type: ignore[arg-type]
        )


def test_register_operations_collection_rejects_negative_interval() -> None:
    with pytest.raises(
        ValueError,
        match="interval_seconds cannot be negative",
    ):
        register_operations_collection(
            FakeScheduler(),
            interval_seconds=-1,
        )


def test_register_operations_collection_validates_enabled() -> None:
    with pytest.raises(
        TypeError,
        match="enabled must be boolean",
    ):
        register_operations_collection(
            FakeScheduler(),
            enabled=1,  # type: ignore[arg-type]
        )


def test_register_operations_collection_validates_result() -> None:
    class InvalidScheduler(FakeScheduler):
        def register(
            self,
            task_name: str,
            interval_seconds: int,
            callback: str,
            *,
            description: str = "",
            enabled: bool = True,
            module: str | None = None,
        ) -> object:
            del (
                task_name,
                interval_seconds,
                callback,
                description,
                enabled,
                module,
            )
            return object()

    with pytest.raises(
        TypeError,
        match="scheduler register must return a mapping",
    ):
        register_operations_collection(
            InvalidScheduler(),
        )
