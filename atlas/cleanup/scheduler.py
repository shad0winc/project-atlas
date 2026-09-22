"""Scheduler registration for production cleanup execution."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Protocol, runtime_checkable


CLEANUP_EXECUTION_TASK_NAME: Final = "cleanup.execute"

# Retention deadlines are measured in hours or days. Hourly dispatch gives
# bounded execution delay without turning destructive cleanup into a
# high-frequency polling loop.
CLEANUP_EXECUTION_INTERVAL_SECONDS: Final = 3600

CLEANUP_EXECUTION_CALLBACK: Final = (
    "python3 -m atlas.cleanup.scheduled_execution"
)

CLEANUP_EXECUTION_DESCRIPTION: Final = (
    "Execute eligible Atlas media cleanup with retention revalidation"
)

CLEANUP_EXECUTION_MODULE: Final[str | None] = None


@runtime_checkable
class CleanupTaskRegistrar(Protocol):
    """Minimal Scheduler registration boundary used by cleanup."""

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
        """Register or update one persistent Scheduler task."""


def register_cleanup_execution(
    scheduler: CleanupTaskRegistrar,
    *,
    interval_seconds: int = CLEANUP_EXECUTION_INTERVAL_SECONDS,
    enabled: bool = False,
) -> Mapping[str, Any]:
    """Register the canonical Core cleanup-execution task."""

    register = getattr(
        scheduler,
        "register",
        None,
    )

    if not callable(register):
        raise TypeError(
            "scheduler must provide a callable register method"
        )

    if (
        isinstance(interval_seconds, bool)
        or not isinstance(interval_seconds, int)
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
        CLEANUP_EXECUTION_TASK_NAME,
        interval_seconds,
        CLEANUP_EXECUTION_CALLBACK,
        description=CLEANUP_EXECUTION_DESCRIPTION,
        enabled=enabled,
        module=CLEANUP_EXECUTION_MODULE,
    )

    if not isinstance(registered, Mapping):
        raise TypeError(
            "scheduler register must return a mapping"
        )

    return registered
