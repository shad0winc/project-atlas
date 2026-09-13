"""Scheduled media-request reconciliation contracts."""

from __future__ import annotations

from dataclasses import dataclass

from atlas.media_requests.reconciler import (
    ReconciliationOutcome,
    reconcile_active_requests,
)


@dataclass(frozen=True)
class StubRequest:
    request_id: str
    provider_request_id: str | None
    status: str
    terminal: bool = False


class RecordingService:
    def __init__(
        self,
        requests: tuple[StubRequest, ...],
        *,
        failures: set[str] | None = None,
    ) -> None:
        self.requests = requests
        self.failures = set(failures or ())
        self.refreshes: list[str] = []

    def list_requests(self) -> tuple[StubRequest, ...]:
        return self.requests

    def refresh_request(self, request_id: object) -> StubRequest:
        normalized = str(request_id)
        self.refreshes.append(normalized)

        if normalized in self.failures:
            raise RuntimeError(f"refresh failed: {normalized}")

        for request in self.requests:
            if request.request_id == normalized:
                return request

        raise LookupError(normalized)


def test_reconcile_empty_repository_is_successful() -> None:
    service = RecordingService(())

    result = reconcile_active_requests(service)

    assert result == ReconciliationOutcome(
        considered=0,
        refreshed=0,
        skipped=0,
        failed=0,
        failures=(),
    )
    assert service.refreshes == []


def test_reconcile_refreshes_submitted_nonterminal_requests() -> None:
    service = RecordingService(
        (
            StubRequest(
                request_id="approved",
                provider_request_id="provider-1",
                status="approved",
            ),
            StubRequest(
                request_id="searching",
                provider_request_id="provider-2",
                status="searching",
            ),
            StubRequest(
                request_id="importing",
                provider_request_id="provider-3",
                status="importing",
            ),
        )
    )

    result = reconcile_active_requests(service)

    assert service.refreshes == [
        "approved",
        "searching",
        "importing",
    ]
    assert result.considered == 3
    assert result.refreshed == 3
    assert result.skipped == 0
    assert result.failed == 0
    assert result.failures == ()


def test_reconcile_skips_unsubmitted_terminal_and_recovery_requests() -> None:
    service = RecordingService(
        (
            StubRequest(
                request_id="pending",
                provider_request_id=None,
                status="pending",
            ),
            StubRequest(
                request_id="submitting",
                provider_request_id="provider-1",
                status="submitting",
            ),
            StubRequest(
                request_id="cancelling",
                provider_request_id="provider-2",
                status="cancelling",
            ),
            StubRequest(
                request_id="available",
                provider_request_id="provider-3",
                status="available",
                terminal=True,
            ),
            StubRequest(
                request_id="cancelled",
                provider_request_id="provider-4",
                status="cancelled",
                terminal=True,
            ),
        )
    )

    result = reconcile_active_requests(service)

    assert service.refreshes == []
    assert result.considered == 5
    assert result.refreshed == 0
    assert result.skipped == 5
    assert result.failed == 0
    assert result.failures == ()


def test_reconcile_isolates_one_refresh_failure() -> None:
    service = RecordingService(
        (
            StubRequest(
                request_id="first",
                provider_request_id="provider-1",
                status="approved",
            ),
            StubRequest(
                request_id="broken",
                provider_request_id="provider-2",
                status="searching",
            ),
            StubRequest(
                request_id="last",
                provider_request_id="provider-3",
                status="importing",
            ),
        ),
        failures={"broken"},
    )

    result = reconcile_active_requests(service)

    assert service.refreshes == [
        "first",
        "broken",
        "last",
    ]
    assert result.considered == 3
    assert result.refreshed == 2
    assert result.skipped == 0
    assert result.failed == 1
    assert len(result.failures) == 1
    assert result.failures[0].request_id == "broken"
    assert "refresh failed" in result.failures[0].error


class PromotionService:
    """Reconciler seam with service-owned AVAILABLE promotion."""

    def __init__(
        self,
        requests: tuple[StubRequest, ...],
        refreshed: dict[str, StubRequest],
    ) -> None:
        self.requests = requests
        self.refreshed = refreshed
        self.refreshes: list[str] = []
        self.promotions: list[str] = []

    def list_requests(
        self,
    ) -> tuple[StubRequest, ...]:
        return self.requests

    def refresh_request(
        self,
        request_id: object,
    ) -> StubRequest:
        normalized = str(request_id)
        self.refreshes.append(normalized)
        return self.refreshed[normalized]

    def mark_available(
        self,
        request_id: object,
    ) -> StubRequest:
        normalized = str(request_id)
        self.promotions.append(normalized)

        current = self.refreshed[normalized]

        return StubRequest(
            request_id=current.request_id,
            provider_request_id=(
                current.provider_request_id
            ),
            status="available",
            terminal=True,
        )


class RecordingReadiness:
    def __init__(
        self,
        ready: set[str] | None = None,
        failures: set[str] | None = None,
    ) -> None:
        self.ready = set(ready or ())
        self.failures = set(failures or ())
        self.checked: list[str] = []

    def is_ready(
        self,
        request: StubRequest,
    ) -> bool:
        self.checked.append(
            request.request_id
        )

        if request.request_id in self.failures:
            raise RuntimeError(
                "readiness failed: "
                f"{request.request_id}"
            )

        return (
            request.request_id
            in self.ready
        )


def test_reconcile_promotes_refreshed_processing_when_ready() -> None:
    original = StubRequest(
        request_id="movie",
        provider_request_id="provider-1",
        status="approved",
    )
    processing = StubRequest(
        request_id="movie",
        provider_request_id="provider-1",
        status="processing",
    )

    service = PromotionService(
        (original,),
        {
            "movie": processing,
        },
    )
    readiness = RecordingReadiness(
        ready={"movie"},
    )

    result = reconcile_active_requests(
        service,
        readiness=readiness,
    )

    assert service.refreshes == [
        "movie",
    ]
    assert readiness.checked == [
        "movie",
    ]
    assert service.promotions == [
        "movie",
    ]

    assert result.considered == 1
    assert result.refreshed == 1
    assert result.skipped == 0
    assert result.failed == 0
    assert result.failures == ()


def test_reconcile_leaves_processing_when_not_ready() -> None:
    processing = StubRequest(
        request_id="movie",
        provider_request_id="provider-1",
        status="processing",
    )

    service = PromotionService(
        (processing,),
        {
            "movie": processing,
        },
    )
    readiness = RecordingReadiness()

    result = reconcile_active_requests(
        service,
        readiness=readiness,
    )

    assert service.refreshes == [
        "movie",
    ]
    assert readiness.checked == [
        "movie",
    ]
    assert service.promotions == []

    assert result.refreshed == 1
    assert result.failed == 0


def test_reconcile_checks_readiness_only_after_processing() -> None:
    approved = StubRequest(
        request_id="approved",
        provider_request_id="provider-1",
        status="approved",
    )
    searching = StubRequest(
        request_id="approved",
        provider_request_id="provider-1",
        status="searching",
    )

    service = PromotionService(
        (approved,),
        {
            "approved": searching,
        },
    )
    readiness = RecordingReadiness(
        ready={"approved"},
    )

    reconcile_active_requests(
        service,
        readiness=readiness,
    )

    assert service.refreshes == [
        "approved",
    ]
    assert readiness.checked == []
    assert service.promotions == []


def test_reconcile_isolates_readiness_failure_and_continues() -> None:
    first = StubRequest(
        request_id="broken",
        provider_request_id="provider-1",
        status="processing",
    )
    last = StubRequest(
        request_id="ready",
        provider_request_id="provider-2",
        status="processing",
    )

    service = PromotionService(
        (
            first,
            last,
        ),
        {
            "broken": first,
            "ready": last,
        },
    )
    readiness = RecordingReadiness(
        ready={"ready"},
        failures={"broken"},
    )

    result = reconcile_active_requests(
        service,
        readiness=readiness,
    )

    assert service.refreshes == [
        "broken",
        "ready",
    ]
    assert readiness.checked == [
        "broken",
        "ready",
    ]
    assert service.promotions == [
        "ready",
    ]

    assert result.considered == 2
    assert result.refreshed == 1
    assert result.skipped == 0
    assert result.failed == 1
    assert (
        result.failures[0].request_id
        == "broken"
    )
    assert (
        "readiness failed"
        in result.failures[0].error
    )
