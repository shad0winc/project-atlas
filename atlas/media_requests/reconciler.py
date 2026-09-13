"""Scheduled reconciliation of active Atlas media requests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


_RECOVERY_REQUIRED_STATUSES = frozenset({
    "submitting",
    "cancelling",
})


@dataclass(frozen=True)
class ReconciliationFailure:
    """One isolated request-refresh failure."""

    request_id: str
    error: str


@dataclass(frozen=True)
class ReconciliationOutcome:
    """Stable summary of one reconciliation pass."""

    considered: int
    refreshed: int
    skipped: int
    failed: int
    failures: tuple[ReconciliationFailure, ...]


@runtime_checkable
class ReconciliationRequest(Protocol):
    """Request fields required by the reconciliation loop."""

    @property
    def request_id(self) -> object:
        ...

    @property
    def provider_request_id(self) -> object | None:
        ...

    @property
    def status(self) -> object:
        ...

    @property
    def terminal(self) -> bool:
        ...


@runtime_checkable
class ReconciliationService(Protocol):
    """Base media-request behavior required by every reconciliation pass."""

    def list_requests(
        self,
    ) -> tuple[ReconciliationRequest, ...]:
        ...

    def refresh_request(
        self,
        request_id: object,
    ) -> ReconciliationRequest:
        ...


@runtime_checkable
class AvailabilityPromotionService(Protocol):
    """Additional service behavior required only for readiness promotion."""

    def mark_available(
        self,
        request_id: object,
    ) -> ReconciliationRequest:
        ...


@runtime_checkable
class RequestReadiness(Protocol):
    """Readiness behavior required for PROCESSING requests."""

    def is_ready(
        self,
        request: ReconciliationRequest,
    ) -> bool:
        ...


def _status_value(status: object) -> str:
    value = getattr(
        status,
        "value",
        status,
    )

    return str(value).strip().lower()


def _is_refreshable(
    request: ReconciliationRequest,
) -> bool:
    if bool(request.terminal):
        return False

    if request.provider_request_id is None:
        return False

    if _status_value(request.status) in _RECOVERY_REQUIRED_STATUSES:
        return False

    return True


def reconcile_active_requests(
    service: ReconciliationService,
    *,
    readiness: RequestReadiness | None = None,
) -> ReconciliationOutcome:
    """Refresh every eligible request while isolating failures."""

    if not isinstance(
        service,
        ReconciliationService,
    ):
        raise TypeError(
            "service must provide media-request reconciliation behavior"
        )

    if (
        readiness is not None
        and not isinstance(
            readiness,
            RequestReadiness,
        )
    ):
        raise TypeError(
            "readiness must provide request-readiness behavior"
        )

    if (
        readiness is not None
        and not isinstance(
            service,
            AvailabilityPromotionService,
        )
    ):
        raise TypeError(
            "service must provide availability-promotion behavior "
            "when readiness is enabled"
        )

    requests = service.list_requests()

    failures: list[ReconciliationFailure] = []
    refreshed = 0
    skipped = 0

    for request in requests:
        if not _is_refreshable(request):
            skipped += 1
            continue

        try:
            updated = service.refresh_request(
                request.request_id,
            )

            if (
                readiness is not None
                and _status_value(
                    updated.status
                ) == "processing"
                and readiness.is_ready(
                    updated
                )
            ):
                service.mark_available(
                    updated.request_id,
                )

        except Exception as exc:
            detail = (
                str(exc).strip()
                or exc.__class__.__name__
            )
            failures.append(
                ReconciliationFailure(
                    request_id=str(request.request_id),
                    error=detail,
                )
            )
            continue

        refreshed += 1

    return ReconciliationOutcome(
        considered=len(requests),
        refreshed=refreshed,
        skipped=skipped,
        failed=len(failures),
        failures=tuple(failures),
    )
