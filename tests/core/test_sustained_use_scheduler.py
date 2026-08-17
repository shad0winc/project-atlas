from __future__ import annotations

from typing import Any

import pytest

from atlas.sustained_use.scheduler import (
    SUSTAINED_USE_SAMPLE_CALLBACK,
    SUSTAINED_USE_SAMPLE_DESCRIPTION,
    SUSTAINED_USE_SAMPLE_INTERVAL_SECONDS,
    SUSTAINED_USE_SAMPLE_TASK,
    register_sustained_use_sampling,
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


def test_register_sustained_use_sampling_uses_canonical_contract() -> None:
    scheduler = RecordingScheduler()

    registered = register_sustained_use_sampling(
        scheduler,
    )

    assert registered == {
        "name": SUSTAINED_USE_SAMPLE_TASK,
        "interval_seconds": (
            SUSTAINED_USE_SAMPLE_INTERVAL_SECONDS
        ),
        "callback": SUSTAINED_USE_SAMPLE_CALLBACK,
        "description": SUSTAINED_USE_SAMPLE_DESCRIPTION,
        "enabled": True,
        "module": None,
    }

    assert scheduler.calls == [registered]


def test_canonical_scheduler_values_are_frozen() -> None:
    assert SUSTAINED_USE_SAMPLE_TASK == (
        "sustained-use.sample"
    )
    assert SUSTAINED_USE_SAMPLE_INTERVAL_SECONDS == 900
    assert SUSTAINED_USE_SAMPLE_CALLBACK == (
        "python3 -m atlas.sustained_use.scheduled_sample --json"
    )
    assert SUSTAINED_USE_SAMPLE_DESCRIPTION == (
        "Capture one sample for the active Q.6 "
        "sustained-use session"
    )


def test_register_sustained_use_sampling_accepts_test_overrides() -> None:
    scheduler = RecordingScheduler()

    registered = register_sustained_use_sampling(
        scheduler,
        interval_seconds=60,
        enabled=False,
    )

    assert registered["interval_seconds"] == 60
    assert registered["enabled"] is False
    assert registered["module"] is None


def test_register_sustained_use_sampling_is_repeatable() -> None:
    scheduler = RecordingScheduler()

    first = register_sustained_use_sampling(
        scheduler,
    )
    second = register_sustained_use_sampling(
        scheduler,
        interval_seconds=1800,
    )

    assert first["interval_seconds"] == 900
    assert second["interval_seconds"] == 1800
    assert len(scheduler.calls) == 2


def test_register_sustained_use_sampling_requires_register() -> None:
    with pytest.raises(
        TypeError,
        match="scheduler must provide a callable register method",
    ):
        register_sustained_use_sampling(
            object(),  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        True,
        False,
        900.0,
        "900",
        None,
    ],
)
def test_register_sustained_use_sampling_validates_interval_type(
    value: object,
) -> None:
    scheduler = RecordingScheduler()

    with pytest.raises(
        TypeError,
        match="interval_seconds must be an integer",
    ):
        register_sustained_use_sampling(
            scheduler,
            interval_seconds=value,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "value",
    [
        0,
        -1,
    ],
)
def test_register_sustained_use_sampling_rejects_nonpositive_interval(
    value: int,
) -> None:
    scheduler = RecordingScheduler()

    with pytest.raises(
        ValueError,
        match="interval_seconds must be greater than zero",
    ):
        register_sustained_use_sampling(
            scheduler,
            interval_seconds=value,
        )


@pytest.mark.parametrize(
    "value",
    [
        1,
        0,
        "true",
        None,
    ],
)
def test_register_sustained_use_sampling_validates_enabled(
    value: object,
) -> None:
    scheduler = RecordingScheduler()

    with pytest.raises(
        TypeError,
        match="enabled must be a boolean",
    ):
        register_sustained_use_sampling(
            scheduler,
            enabled=value,  # type: ignore[arg-type]
        )


def test_register_sustained_use_sampling_validates_result() -> None:
    class InvalidScheduler:
        def register(
            self,
            name: str,
            interval_seconds: int,
            callback: str,
            *,
            description: str = "",
            enabled: bool = True,
            module: str | None = None,
        ) -> object:
            return [
                name,
                interval_seconds,
                callback,
                description,
                enabled,
                module,
            ]

    with pytest.raises(
        TypeError,
        match="scheduler register must return a mapping",
    ):
        register_sustained_use_sampling(
            InvalidScheduler(),  # type: ignore[arg-type]
        )
