"""Scheduler callback for Atlas media-request reconciliation."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
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
from .service import MediaRequestService
from .construction import build_request_service, open_request_repository, validate_default_acquisition_activation
from .submission_recovery import SubmissionRecoveryService
from .submission_reconciler import SubmissionRecoveryOutcome, reconcile_submission_receipts


@dataclass(frozen=True)
class ScheduledRecoveryOutcome:
    reconciliation: ReconciliationOutcome
    receipts: SubmissionRecoveryOutcome
    events_attempted: int
    events_delivered: int
    events_pending: int


def _submission_recovery_enabled():
    value = os.getenv("ATLAS_SUBMISSION_RECOVERY_ENABLED", "0").strip()
    if value not in {"0", "1"}:
        raise ValueError("Submission recovery opt-in must be 0 or 1")
    return value == "1"


DEFAULT_REQUESTS_ROOT = Path(
    "/mnt/storage/configs/atlas/runtime/requests"
)

REQUEST_EVENT_SOURCE = "atlas-requests"
SUBMISSION_RECEIPT_LIMIT = 10
SUBMISSION_EVENT_LIMIT = 25

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

    repository = open_request_repository(root_value)
    validate_default_acquisition_activation(repository)

    provider: MediaRequestProvider = (
        default_jellyseerr_media_request_provider()
    )

    return build_request_service(
        repository,
        (provider,),
        event_publisher=_publish_request_event,
    )


def run_reconciliation(
    *,
    service_factory: RequestServiceFactory = build_default_service,
) -> ReconciliationOutcome | ScheduledRecoveryOutcome:
    """Execute reconciliation with explicit, default-off submission recovery."""

    enabled = _submission_recovery_enabled()
    service = service_factory()
    if enabled and not isinstance(service, SubmissionRecoveryService):
        raise ValueError("Submission recovery opt-in requires an explicitly migrated schema-2 service")

    jellyfin = default_jellyfin_provider()
    readiness = JellyfinRequestReadiness(
        jellyfin
    )

    if not enabled:
        return reconcile_active_requests(service, readiness=readiness)

    # Minute-based rotation covers a stable backlog without rewriting journals
    # or leaving permanently unverified items at the front of every pass.
    minute = int(datetime.now(timezone.utc).timestamp()) // 60
    try:
        receipts = reconcile_submission_receipts(service, limit=SUBMISSION_RECEIPT_LIMIT, offset=minute * SUBMISSION_RECEIPT_LIMIT)
        delivered = service.drain_submission_events(limit=SUBMISSION_EVENT_LIMIT, offset=minute * SUBMISSION_EVENT_LIMIT)
        pending_after = len(service.repository.pending_submission_events())
    except Exception:
        raise RuntimeError("Scheduled submission recovery remains unverified") from None
    reconciliation = reconcile_active_requests(service, readiness=readiness)
    return ScheduledRecoveryOutcome(reconciliation, receipts, service.submission_event_attempts, delivered, pending_after)


def render_result(
    outcome: ReconciliationOutcome | ScheduledRecoveryOutcome,
) -> str:
    """Render legacy summaries unchanged; opt-in passes include recovery counts."""

    if isinstance(outcome, ScheduledRecoveryOutcome):
        payload = json.loads(render_result(outcome.reconciliation))
        payload["submission_recovery"] = {
            "receipts": asdict(outcome.receipts),
            "events_attempted": outcome.events_attempted,
            "events_delivered": outcome.events_delivered,
            "events_pending": outcome.events_pending,
        }
        return json.dumps(payload, indent=2, sort_keys=True)

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
