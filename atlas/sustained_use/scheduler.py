"""Scheduler registration contract for Q.6 sustained-use sampling."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol


SUSTAINED_USE_SAMPLE_TASK = "sustained-use.sample"

# Q.6 certification observations remain fixed at 15-minute slots.
SUSTAINED_USE_SAMPLE_INTERVAL_SECONDS = 900

# The generic Scheduler polls the gate frequently enough that bounded
# dispatcher jitter cannot accumulate into certification-clock drift.
SUSTAINED_USE_DISPATCH_INTERVAL_SECONDS = 60

SUSTAINED_USE_SAMPLE_CALLBACK = (
    "python3 -m atlas.sustained_use.scheduled_sample --json"
)

SUSTAINED_USE_SAMPLE_DESCRIPTION = (
    "Check the fixed Q.6 cadence and capture one due "
    "sustained-use sample"
)


class SchedulerRegistrar(Protocol):
    """Minimal Scheduler registration boundary used by sustained-use."""

    def register(
        self,
        name: str,
        interval_seconds: int,
        callback: str,
        *,
        description: str = "",
        enabled: bool = True,
        module: str | None = None,
    ) -> Mapping[str, Any]:
        """Register or update one Scheduler task."""


def register_sustained_use_sampling(
    scheduler: SchedulerRegistrar,
    *,
    interval_seconds: int = SUSTAINED_USE_DISPATCH_INTERVAL_SECONDS,
    enabled: bool = True,
) -> Mapping[str, Any]:
    """Register the canonical Q.6 fixed-cadence polling task.

    Scheduler execution cadence is intentionally shorter than the
    certification sampling interval. The scheduled callback determines
    whether a fixed T0-derived Q.6 slot is due.

    This function only defines Scheduler registration. It does not start a
    Q.6 session, collect a sample, finalize a session, or execute Scheduler
    work.
    """

    register = getattr(
        scheduler,
        "register",
        None,
    )

    if not callable(register):
        raise TypeError(
            "scheduler must provide a callable register method"
        )

    if isinstance(interval_seconds, bool) or not isinstance(
        interval_seconds,
        int,
    ):
        raise TypeError(
            "interval_seconds must be an integer"
        )

    if interval_seconds <= 0:
        raise ValueError(
            "interval_seconds must be greater than zero"
        )

    if not isinstance(enabled, bool):
        raise TypeError(
            "enabled must be a boolean"
        )

    registered = register(
        SUSTAINED_USE_SAMPLE_TASK,
        interval_seconds,
        SUSTAINED_USE_SAMPLE_CALLBACK,
        description=SUSTAINED_USE_SAMPLE_DESCRIPTION,
        enabled=enabled,
        module=None,
    )

    if not isinstance(
        registered,
        Mapping,
    ):
        raise TypeError(
            "scheduler register must return a mapping"
        )

    return registered
