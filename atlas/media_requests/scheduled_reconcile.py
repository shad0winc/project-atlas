"""Scheduler callback for Atlas media-request reconciliation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
import json
import os
from pathlib import Path
import sys
from typing import TextIO

from atlas.events import publish_core_event
from atlas.media.jellyfin import default_jellyfin_provider

from .provider import MediaRequestProvider
from .readiness import JellyfinRequestReadiness
from .providers import default_jellyseerr_media_request_provider
from .reconciler import (
    ReconciliationOutcome,
    reconcile_active_requests,
)
from .repository import JsonMediaRequestRepository
from .service import MediaRequestService


DEFAULT_REQUESTS_ROOT = Path(
    "/mnt/storage/configs/atlas/runtime/requests"
)

REQUEST_EVENT_SOURCE = "atlas-requests"

RequestServiceFactory = Callable[
    [],
    MediaRequestService,
]


def _publish_request_event(
    event_name: str,
    payload: Mapping[str, object] | None = None,
) -> None:
    """Publish one request lifecycle event through the core event stream."""

    publish_core_event(
        event_name,
        payload,
        source=REQUEST_EVENT_SOURCE,
    )


def build_default_service() -> MediaRequestService:
    """Build the production media-request reconciliation service."""

    root_value = os.getenv(
        "ATLAS_REQUESTS_DIR",
        str(DEFAULT_REQUESTS_ROOT),
    ).strip()

    if not root_value:
        raise ValueError(
            "ATLAS_REQUESTS_DIR is required"
        )

    repository = JsonMediaRequestRepository(
        root_value,
    )

    provider: MediaRequestProvider = (
        default_jellyseerr_media_request_provider()
    )

    return MediaRequestService(
        repository,
        (provider,),
        event_publisher=_publish_request_event,
    )


def run_reconciliation(
    *,
    service_factory: RequestServiceFactory = build_default_service,
) -> ReconciliationOutcome:
    """Execute one bounded request reconciliation pass."""

    service = service_factory()

    jellyfin = default_jellyfin_provider()
    readiness = JellyfinRequestReadiness(
        jellyfin
    )

    return reconcile_active_requests(
        service,
        readiness=readiness,
    )


def render_result(
    outcome: ReconciliationOutcome,
) -> str:
    """Render one deterministic reconciliation summary."""

    if not isinstance(
        outcome,
        ReconciliationOutcome,
    ):
        raise TypeError(
            "outcome must be a ReconciliationOutcome"
        )

    payload = {
        "considered": outcome.considered,
        "failed": outcome.failed,
        "failures": [
            {
                "error": failure.error,
                "request_id": failure.request_id,
            }
            for failure in outcome.failures
        ],
        "refreshed": outcome.refreshed,
        "skipped": outcome.skipped,
    }

    return json.dumps(
        payload,
        indent=2,
        sort_keys=True,
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    service_factory: RequestServiceFactory = build_default_service,
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Execute one Scheduler-driven media-request reconciliation."""

    arguments = tuple(
        sys.argv[1:]
        if argv is None
        else argv
    )
    output = stdout or sys.stdout
    errors = stderr or sys.stderr

    if arguments:
        print(
            "Request reconciliation failed: "
            "arguments are not supported",
            file=errors,
        )
        return 2

    try:
        outcome = run_reconciliation(
            service_factory=service_factory,
        )
    except Exception as exc:
        detail = (
            str(exc).strip()
            or exc.__class__.__name__
        )
        print(
            "Request reconciliation failed: "
            f"{detail}",
            file=errors,
        )
        return 1

    print(
        render_result(outcome),
        file=output,
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
