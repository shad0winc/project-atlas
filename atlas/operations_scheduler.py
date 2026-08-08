"""Scheduler registration for Atlas Operations collection."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Protocol, runtime_checkable


OPERATIONS_COLLECTION_TASK_NAME: Final = (
    "operations.collect"
)
OPERATIONS_COLLECTION_INTERVAL_SECONDS: Final = 3600
OPERATIONS_COLLECTION_CALLBACK: Final = (
    "python3 -m atlas.operations_scheduled_collection"
)
OPERATIONS_COLLECTION_DESCRIPTION: Final = (
    "Persist an Atlas Operations report"
)
OPERATIONS_SCHEDULER_MODULE: Final[str | None] = None


@runtime_checkable
class OperationsTaskRegistrar(Protocol):
    """Behavior required to register an Operations task."""

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
        """Register or update one persistent scheduler task."""

        ...


def register_operations_collection(
    scheduler: OperationsTaskRegistrar,
    *,
    interval_seconds: int = (
        OPERATIONS_COLLECTION_INTERVAL_SECONDS
    ),
    enabled: bool = True,
) -> dict[str, Any]:
    """Register or update scheduled Operations collection."""

    if not isinstance(
        scheduler,
        OperationsTaskRegistrar,
    ):
        raise TypeError(
            "scheduler must support task registration",
        )

    if (
        not isinstance(interval_seconds, int)
        or isinstance(interval_seconds, bool)
    ):
        raise TypeError(
            "interval_seconds must be an integer",
        )

    if interval_seconds < 0:
        raise ValueError(
            "interval_seconds cannot be negative",
        )

    if not isinstance(enabled, bool):
        raise TypeError(
            "enabled must be boolean",
        )

    registered = scheduler.register(
        OPERATIONS_COLLECTION_TASK_NAME,
        interval_seconds,
        OPERATIONS_COLLECTION_CALLBACK,
        description=OPERATIONS_COLLECTION_DESCRIPTION,
        enabled=enabled,
        module=OPERATIONS_SCHEDULER_MODULE,
    )

    if not isinstance(registered, Mapping):
        raise TypeError(
            "scheduler register must return a mapping",
        )

    return dict(registered)
