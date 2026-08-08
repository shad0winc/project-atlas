"""Event-publication tests for MediaRequestService."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from atlas.media_requests import (
    JsonMediaRequestRepository,
    MediaRequest,
    MediaRequestProvider,
    MediaRequestService,
    MediaRequestStatus,
    MediaRequestType,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatusResult,
    ProviderSubmissionResult,
)


NOW = datetime(2026, 8, 3, 4, 0, tzinfo=timezone.utc)


def make_request(**overrides: object) -> MediaRequest:
    values: dict[str, object] = {
        "request_id": "request-001",
        "user_id": "user-001",
        "media_type": "movie",
        "provider": "example",
        "provider_media_id": "157336",
        "title": "Interstellar",
        "created_at": "2026-08-03T03:00:00Z",
    }
    values.update(overrides)
    return MediaRequest(**values)


class EventProvider(MediaRequestProvider):
    def __init__(self) -> None:
        self.status_result = ProviderStatusResult(
            provider="example",
            provider_request_id="provider-001",
            status="searching",
            updated_at="2026-08-03T04:30:00Z",
        )

    @property
    def name(self) -> str:
        return "example"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types=(MediaRequestType.MOVIE,),
            supports_cancellation=True,
        )

    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        return ProviderSubmissionResult(
            provider="example",
            provider_request_id="provider-001",
            status="approved",
            submitted_at="2026-08-03T03:00:00Z",
            updated_at="2026-08-03T04:00:00Z",
        )

    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        return self.status_result

    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        return ProviderStatusResult(
            provider="example",
            provider_request_id=provider_request_id,
            status="cancelled",
            updated_at="2026-08-03T05:00:00Z",
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider="example",
            status="healthy",
            checked_at="2026-08-03T04:00:00Z",
        )


@pytest.fixture
def repository(
    tmp_path: Path,
) -> JsonMediaRequestRepository:
    return JsonMediaRequestRepository(tmp_path / "requests")


def make_service(
    repository: JsonMediaRequestRepository,
    publisher: object = None,
) -> MediaRequestService:
    return MediaRequestService(
        repository,
        (EventProvider(),),
        event_publisher=publisher,  # type: ignore[arg-type]
        clock=lambda: NOW,
    )


def test_create_publishes_created_event(
    repository: JsonMediaRequestRepository,
) -> None:
    published: list[tuple[str, dict[str, object]]] = []
    service = make_service(
        repository,
        lambda name, payload: published.append((name, dict(payload))),
    )

    service.create_request(make_request())

    assert [name for name, _ in published] == ["request.created"]
    assert published[0][1]["request_id"] == "request-001"
    assert published[0][1]["status"] == "pending"


def test_submit_publishes_submitted_and_lifecycle_events(
    repository: JsonMediaRequestRepository,
) -> None:
    published: list[tuple[str, dict[str, object]]] = []
    service = make_service(
        repository,
        lambda name, payload: published.append((name, dict(payload))),
    )
    service.create_request(make_request())
    published.clear()

    service.submit_request("request-001")

    assert [name for name, _ in published] == [
        "request.submitted",
        "request.approved",
    ]
    assert published[0][1]["provider_request_id"] == "provider-001"


def test_refresh_publishes_only_when_status_changes(
    repository: JsonMediaRequestRepository,
) -> None:
    published: list[tuple[str, dict[str, object]]] = []
    service = make_service(
        repository,
        lambda name, payload: published.append((name, dict(payload))),
    )
    service.create_request(make_request())
    service.submit_request("request-001")
    published.clear()

    service.refresh_request("request-001")
    assert [name for name, _ in published] == ["request.searching"]

    published.clear()
    service.refresh_request("request-001")
    assert published == []


def test_cancel_publishes_cancelled_event(
    repository: JsonMediaRequestRepository,
) -> None:
    published: list[tuple[str, dict[str, object]]] = []
    service = make_service(
        repository,
        lambda name, payload: published.append((name, dict(payload))),
    )
    service.create_request(make_request())
    service.submit_request("request-001")
    published.clear()

    service.cancel_request("request-001")

    assert [name for name, _ in published] == ["request.cancelled"]


def test_operations_without_publisher_remain_supported(
    repository: JsonMediaRequestRepository,
) -> None:
    service = make_service(repository)

    request = service.create_request(make_request())

    assert request.request_id == "request-001"
    assert service.publication_errors == ()


def test_publication_failure_does_not_rollback_state(
    repository: JsonMediaRequestRepository,
) -> None:
    def fail(name: str, payload: object) -> None:
        raise RuntimeError("event bus unavailable")

    service = make_service(repository, fail)

    request = service.create_request(make_request())

    assert repository.get(request.request_id) == request
    assert len(service.publication_errors) == 1
    assert "request.created" in service.publication_errors[0]
    assert "event bus unavailable" in service.publication_errors[0]


def test_clear_publication_errors(
    repository: JsonMediaRequestRepository,
) -> None:
    service = make_service(
        repository,
        lambda name, payload: (_ for _ in ()).throw(
            RuntimeError("failure")
        ),
    )
    service.create_request(make_request())

    service.clear_publication_errors()

    assert service.publication_errors == ()


def test_service_rejects_non_callable_publisher(
    repository: JsonMediaRequestRepository,
) -> None:
    with pytest.raises(
        Exception,
        match="event_publisher",
    ):
        MediaRequestService(
            repository,
            (EventProvider(),),
            event_publisher=object(),  # type: ignore[arg-type]
        )


def test_service_rejects_non_callable_clock(
    repository: JsonMediaRequestRepository,
) -> None:
    with pytest.raises(Exception, match="clock"):
        MediaRequestService(
            repository,
            (EventProvider(),),
            clock=object(),  # type: ignore[arg-type]
        )


def test_invalid_clock_is_captured_as_publication_error(
    repository: JsonMediaRequestRepository,
) -> None:
    service = MediaRequestService(
        repository,
        (EventProvider(),),
        event_publisher=lambda name, payload: None,
        clock=lambda: datetime(2026, 8, 3, 4, 0),
    )

    request = service.create_request(make_request())

    assert repository.get(request.request_id) == request
    assert len(service.publication_errors) == 1
    assert "timezone-aware" in service.publication_errors[0]
