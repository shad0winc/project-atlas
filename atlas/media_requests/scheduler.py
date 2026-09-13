"""Scheduler registration for media-request reconciliation."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Final, Protocol, runtime_checkable


MEDIA_REQUEST_RECONCILE_TASK_NAME: Final = (
    "requests.reconcile"
)
MEDIA_REQUEST_RECONCILE_INTERVAL_SECONDS: Final = 60
MEDIA_REQUEST_RECONCILE_CALLBACK: Final = (
    "python3 -m atlas.media_requests.scheduled_reconcile"
)
MEDIA_REQUEST_RECONCILE_DESCRIPTION: Final = (
    "Reconcile active media requests with provider status"
)
MEDIA_REQUEST_RECONCILE_MODULE: Final[str | None] = None


@runtime_checkable
class MediaRequestTaskRegistrar(Protocol):
    """Behavior required to register the reconciliation task."""

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
        ...


def register_media_request_reconciliation(
    scheduler: MediaRequestTaskRegistrar,
    *,
    interval_seconds: int = (
        MEDIA_REQUEST_RECONCILE_INTERVAL_SECONDS
    ),
    enabled: bool = True,
) -> Mapping[str, Any]:
    """Register the core media-request reconciliation task."""

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
        MEDIA_REQUEST_RECONCILE_TASK_NAME,
        interval_seconds,
        MEDIA_REQUEST_RECONCILE_CALLBACK,
        description=MEDIA_REQUEST_RECONCILE_DESCRIPTION,
        enabled=enabled,
        module=MEDIA_REQUEST_RECONCILE_MODULE,
    )

    if not isinstance(registered, Mapping):
        raise TypeError(
            "scheduler register must return a mapping"
        )

    return registered
