"""Contract tests for the Atlas media-request service."""

from __future__ import annotations

import errno
from pathlib import Path

import pytest

from atlas.media_requests import (
    JsonMediaRequestRepository,
    MediaRequest,
    MediaRequestProvider,
    MediaRequestProviderError,
    MediaRequestProviderOperationError,
    MediaRequestRepositoryError,
    MediaRequestService,
    MediaRequestServiceConflictError,
    MediaRequestServiceError,
    MediaRequestStatus,
    MediaRequestType,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatusResult,
    ProviderSubmissionResult,
)


TIMESTAMP = "2026-08-02T20:00:00Z"
UPDATED = "2026-08-02T20:30:00Z"
AVAILABLE = "2026-08-02T21:00:00Z"


def make_request(**overrides: object) -> MediaRequest:
    values: dict[str, object] = {
        "request_id": "request-001",
        "user_id": "user-001",
        "media_type": "movie",
        "provider": "example",
        "provider_media_id": "tmdb:157336",
        "title": "Interstellar",
        "year": 2014,
        "created_at": TIMESTAMP,
    }
    values.update(overrides)
    return MediaRequest(**values)


class FakeProvider(MediaRequestProvider):
    def __init__(
        self,
        *,
        name: str = "example",
        media_types: tuple[MediaRequestType, ...] = (
            MediaRequestType.MOVIE,
        ),
        supports_submission: bool = True,
        supports_status: bool = True,
        supports_cancellation: bool = True,
    ) -> None:
        self._name = name
        self._capabilities = ProviderCapabilities(
            media_types=media_types,
            supports_submission=supports_submission,
            supports_status=supports_status,
            supports_cancellation=supports_cancellation,
        )
        self.preflight_requests: list[
            MediaRequest
        ] = []
        self.submissions: list[MediaRequest] = []
        self.status_requests: list[str] = []
        self.cancellations: list[str] = []
        self.submission_result: object = ProviderSubmissionResult(
            provider=name,
            provider_request_id="provider-001",
            status="approved",
            submitted_at=TIMESTAMP,
            updated_at=UPDATED,
        )
        self.status_result: object = ProviderStatusResult(
            provider=name,
            provider_request_id="provider-001",
            status="downloading",
            updated_at=UPDATED,
        )
        self.cancel_result: object = ProviderStatusResult(
            provider=name,
            provider_request_id="provider-001",
            status="cancelled",
            updated_at=UPDATED,
        )
        self.preflight_error: Exception | None = None
        self.submission_error: Exception | None = None
        self.status_error: Exception | None = None
        self.cancel_error: Exception | None = None
        self.capabilities_error: Exception | None = None

    @property
    def name(self) -> str:
        return self._name

    def capabilities(self) -> ProviderCapabilities:
        if self.capabilities_error is not None:
            raise self.capabilities_error
        return self._capabilities

    def validate_submission(
        self,
        request: MediaRequest,
    ) -> None:
        self.preflight_requests.append(
            request
        )

        if self.preflight_error is not None:
            raise self.preflight_error

    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        self.submissions.append(request)
        if self.submission_error is not None:
            raise self.submission_error
        return self.submission_result  # type: ignore[return-value]

    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        self.status_requests.append(provider_request_id)
        if self.status_error is not None:
            raise self.status_error
        return self.status_result  # type: ignore[return-value]

    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        self.cancellations.append(provider_request_id)
        if self.cancel_error is not None:
            raise self.cancel_error
        return self.cancel_result  # type: ignore[return-value]

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="healthy",
            checked_at=TIMESTAMP,
        )


@pytest.fixture
def repository(
    tmp_path: Path,
) -> JsonMediaRequestRepository:
    return JsonMediaRequestRepository(tmp_path / "requests")


@pytest.fixture
def provider() -> FakeProvider:
    return FakeProvider()


@pytest.fixture
def service(
    repository: JsonMediaRequestRepository,
    provider: FakeProvider,
) -> MediaRequestService:
    return MediaRequestService(repository, (provider,))


def test_service_requires_repository() -> None:
    with pytest.raises(
        MediaRequestServiceError,
        match="repository",
    ):
        MediaRequestService(object(), (FakeProvider(),))  # type: ignore[arg-type]


@pytest.mark.parametrize("providers", [(), [], None, [object()]])
def test_service_requires_provider_collection(providers: object) -> None:
    repository = JsonMediaRequestRepository("/tmp/unused")

    with pytest.raises(MediaRequestServiceError, match="provider"):
        MediaRequestService(
            repository,
            providers,  # type: ignore[arg-type]
        )


def test_service_rejects_duplicate_provider_names(
    repository: JsonMediaRequestRepository,
) -> None:
    with pytest.raises(
        MediaRequestServiceError,
        match="duplicate",
    ):
        MediaRequestService(
            repository,
            (FakeProvider(), FakeProvider(name=" Example ")),
        )


def test_provider_names_are_deterministic(
    repository: JsonMediaRequestRepository,
) -> None:
    service = MediaRequestService(
        repository,
        (
            FakeProvider(name="zeta"),
            FakeProvider(name="alpha"),
        ),
    )

    assert service.provider_names == ("alpha", "zeta")


def test_create_request_persists_pending_request(
    service: MediaRequestService,
) -> None:
    request = make_request()

    assert service.create_request(request) == request
    assert service.get_request(request.request_id) == request


def test_create_request_rejects_active_target_conflict(
    service: MediaRequestService,
) -> None:
    first = make_request()
    second = make_request(
        request_id="request-002",
        user_id="user-002",
    )

    service.create_request(first)

    with pytest.raises(
        MediaRequestServiceConflictError,
        match="active media request conflicts",
    ):
        service.create_request(second)

    assert service.list_requests() == (first,)


def test_create_request_requires_media_request(
    service: MediaRequestService,
) -> None:
    with pytest.raises(
        MediaRequestServiceError,
        match="MediaRequest",
    ):
        service.create_request(object())  # type: ignore[arg-type]


def test_create_request_requires_pending_status(
    service: MediaRequestService,
) -> None:
    with pytest.raises(
        MediaRequestServiceError,
        match="pending",
    ):
        service.create_request(
            make_request(
                status="approved",
                updated_at=UPDATED,
            )
        )


def test_create_request_rejects_provider_request_identity(
    service: MediaRequestService,
) -> None:
    with pytest.raises(
        MediaRequestServiceError,
        match="provider_request_id",
    ):
        service.create_request(
            make_request(provider_request_id="provider-001")
        )


def test_create_request_rejects_unregistered_provider(
    service: MediaRequestService,
) -> None:
    with pytest.raises(
        MediaRequestServiceError,
        match="not registered",
    ):
        service.create_request(make_request(provider="missing"))


def test_create_request_rejects_unsupported_media_type(
    service: MediaRequestService,
) -> None:
    with pytest.raises(
        MediaRequestServiceError,
        match="does not support media type",
    ):
        service.create_request(
            make_request(
                media_type="tv",
                season_number=1,
            )
        )


def test_create_request_rejects_provider_without_submission(
    repository: JsonMediaRequestRepository,
) -> None:
    service = MediaRequestService(
        repository,
        (FakeProvider(supports_submission=False),),
    )

    with pytest.raises(
        MediaRequestServiceError,
        match="does not support submission",
    ):
        service.create_request(make_request())


def test_create_request_preflight_failure_blocks_persistence(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    provider.preflight_error = MediaRequestProviderError(
        "routing is not configured"
    )

    request = make_request()

    with pytest.raises(
        MediaRequestServiceError,
        match="preflight",
    ):
        service.create_request(
            request
        )

    assert provider.preflight_requests == [
        request
    ]
    assert provider.submissions == []
    assert service.list_requests() == ()


def test_create_request_wraps_repository_failure(
    service: MediaRequestService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service.repository,
        "save_if_no_active_conflict",
        lambda request: (_ for _ in ()).throw(
            MediaRequestRepositoryError("failure")
        ),
    )

    with pytest.raises(
        MediaRequestServiceError,
        match="persist",
    ):
        service.create_request(make_request())


def test_submit_request_calls_provider_and_replaces_record(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    request = service.create_request(make_request())

    updated = service.submit_request(request.request_id)

    assert len(provider.submissions) == 1
    assert provider.submissions[0].request_id == request.request_id
    assert provider.submissions[0].status is MediaRequestStatus.SUBMITTING
    assert provider.submissions[0].provider_request_id is None
    assert updated.provider_request_id == "provider-001"
    assert updated.status is MediaRequestStatus.APPROVED
    assert updated.updated_at == UPDATED
    assert service.get_request(request.request_id) == updated


def test_submit_request_rejects_already_submitted_request(
    service: MediaRequestService,
) -> None:
    service.create_request(make_request())
    service.submit_request("request-001")

    with pytest.raises(
        MediaRequestServiceError,
        match="already submitted",
    ):
        service.submit_request("request-001")


def test_submit_request_revalidates_before_submitting_intent(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    request = service.create_request(
        make_request()
    )

    provider.preflight_error = (
        MediaRequestProviderError(
            "routing changed"
        )
    )

    with pytest.raises(
        MediaRequestServiceError,
        match="preflight",
    ):
        service.submit_request(
            request.request_id
        )

    assert len(
        provider.preflight_requests
    ) == 2
    assert provider.submissions == []
    assert (
        service
        .get_request(
            request.request_id
        )
        .status
        is MediaRequestStatus.PENDING
    )


def test_submit_request_wraps_provider_failure(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    provider.submission_error = MediaRequestProviderOperationError(
        "unavailable"
    )
    service.create_request(make_request())

    with pytest.raises(
        MediaRequestServiceError,
        match="submission failed",
    ):
        service.submit_request("request-001")

    persisted = service.get_request("request-001")
    assert persisted.status is MediaRequestStatus.SUBMITTING
    assert persisted.provider_request_id is None


def test_submit_request_requires_submission_result(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    provider.submission_result = object()
    service.create_request(make_request())

    with pytest.raises(
        MediaRequestServiceError,
        match="ProviderSubmissionResult",
    ):
        service.submit_request("request-001")


def test_submit_request_rejects_provider_mismatch(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    provider.submission_result = ProviderSubmissionResult(
        provider="other",
        provider_request_id="provider-001",
        status="approved",
        submitted_at=TIMESTAMP,
        updated_at=UPDATED,
    )
    service.create_request(make_request())

    with pytest.raises(
        MediaRequestServiceError,
        match="does not match",
    ):
        service.submit_request("request-001")


def submitted_request(
    service: MediaRequestService,
) -> MediaRequest:
    service.create_request(make_request())
    return service.submit_request("request-001")


def test_refresh_request_updates_status(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)

    refreshed = service.refresh_request("request-001")

    assert provider.status_requests == ["provider-001"]
    assert refreshed.status is MediaRequestStatus.DOWNLOADING
    assert refreshed.updated_at == UPDATED


def test_refresh_request_can_mark_available(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.status_result = ProviderStatusResult(
        provider="example",
        provider_request_id="provider-001",
        status="available",
        updated_at=AVAILABLE,
        available_at=AVAILABLE,
    )

    refreshed = service.refresh_request("request-001")

    assert refreshed.status is MediaRequestStatus.AVAILABLE
    assert refreshed.available_at == AVAILABLE
    assert refreshed.terminal is True


def test_refresh_requires_submitted_request(
    service: MediaRequestService,
) -> None:
    service.create_request(make_request())

    with pytest.raises(
        MediaRequestServiceError,
        match="not submitted",
    ):
        service.refresh_request("request-001")


def test_refresh_requires_status_capability(
    repository: JsonMediaRequestRepository,
) -> None:
    provider = FakeProvider(supports_status=False)
    service = MediaRequestService(repository, (provider,))
    submitted_request(service)

    with pytest.raises(
        MediaRequestServiceError,
        match="does not support status",
    ):
        service.refresh_request("request-001")


def test_refresh_wraps_provider_failure(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.status_error = MediaRequestProviderOperationError("failed")

    with pytest.raises(
        MediaRequestServiceError,
        match="status refresh failed",
    ):
        service.refresh_request("request-001")


def test_refresh_requires_status_result(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.status_result = object()

    with pytest.raises(
        MediaRequestServiceError,
        match="ProviderStatusResult",
    ):
        service.refresh_request("request-001")


def test_refresh_rejects_provider_request_identity_mismatch(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.status_result = ProviderStatusResult(
        provider="example",
        provider_request_id="different",
        status="downloading",
        updated_at=UPDATED,
    )

    with pytest.raises(
        MediaRequestServiceError,
        match="identity does not match",
    ):
        service.refresh_request("request-001")


def test_refresh_rejects_invalid_lifecycle_regression(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.status_result = ProviderStatusResult(
        provider="example",
        provider_request_id="provider-001",
        status="downloading",
        updated_at=UPDATED,
    )
    service.refresh_request("request-001")

    provider.status_result = ProviderStatusResult(
        provider="example",
        provider_request_id="provider-001",
        status="approved",
        updated_at=AVAILABLE,
    )

    with pytest.raises(
        MediaRequestServiceError,
        match="invalid media-request status transition",
    ):
        service.refresh_request("request-001")


def test_same_status_refresh_is_idempotent(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted = submitted_request(service)
    provider.status_result = ProviderStatusResult(
        provider="example",
        provider_request_id="provider-001",
        status="approved",
        updated_at=AVAILABLE,
    )

    refreshed = service.refresh_request("request-001")

    assert submitted.status is refreshed.status
    assert refreshed.updated_at == AVAILABLE


def test_cancel_request_updates_cancelled_status(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)

    cancelled = service.cancel_request("request-001")

    assert provider.cancellations == ["provider-001"]
    assert cancelled.status is MediaRequestStatus.CANCELLED
    assert cancelled.terminal is True


def test_cancel_requires_submitted_request(
    service: MediaRequestService,
) -> None:
    service.create_request(make_request())

    with pytest.raises(
        MediaRequestServiceError,
        match="not submitted",
    ):
        service.cancel_request("request-001")


def test_cancel_rejects_terminal_request(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.status_result = ProviderStatusResult(
        provider="example",
        provider_request_id="provider-001",
        status="available",
        updated_at=AVAILABLE,
        available_at=AVAILABLE,
    )
    service.refresh_request("request-001")

    with pytest.raises(
        MediaRequestServiceError,
        match="terminal",
    ):
        service.cancel_request("request-001")


def test_cancel_requires_provider_capability(
    repository: JsonMediaRequestRepository,
) -> None:
    provider = FakeProvider(supports_cancellation=False)
    service = MediaRequestService(repository, (provider,))
    submitted_request(service)

    with pytest.raises(
        MediaRequestServiceError,
        match="does not support cancellation",
    ):
        service.cancel_request("request-001")


def test_cancel_wraps_provider_failure(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.cancel_error = MediaRequestProviderOperationError("failed")

    with pytest.raises(
        MediaRequestServiceError,
        match="cancellation failed",
    ):
        service.cancel_request("request-001")

    persisted = service.get_request("request-001")
    assert persisted.status is MediaRequestStatus.CANCELLING
    assert persisted.provider_request_id == "provider-001"


def test_cancel_requires_cancelled_result(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.cancel_result = ProviderStatusResult(
        provider="example",
        provider_request_id="provider-001",
        status="approved",
        updated_at=UPDATED,
    )

    with pytest.raises(
        MediaRequestServiceError,
        match="must return cancelled",
    ):
        service.cancel_request("request-001")

    assert service.get_request("request-001").status is MediaRequestStatus.CANCELLING


def test_list_recovery_required_requests_is_read_only(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    service.create_request(make_request())
    submitting = service.repository.save(
        make_request(
            request_id="request-002",
            provider_media_id="tmdb:603",
            status="submitting",
        )
    )
    cancelling = service.repository.save(
        make_request(
            request_id="request-003",
            provider_request_id="provider-003",
            provider_media_id="tmdb:27205",
            status="cancelling",
        )
    )

    assert service.list_recovery_required_requests() == (
        submitting,
        cancelling,
    )
    assert provider.submissions == []
    assert provider.status_requests == []
    assert provider.cancellations == []


def test_list_recovery_required_requests_excludes_normal_states(
    service: MediaRequestService,
) -> None:
    service.create_request(make_request())

    assert service.list_recovery_required_requests() == ()


def test_list_recovery_required_requests_wraps_repository_failure(
    service: MediaRequestService,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        service.repository,
        "list",
        lambda: (_ for _ in ()).throw(
            MediaRequestRepositoryError("failure")
        ),
    )

    with pytest.raises(
        MediaRequestServiceError,
        match="requiring reconciliation",
    ):
        service.list_recovery_required_requests()


def test_list_and_user_lookup_delegate_to_repository(
    service: MediaRequestService,
) -> None:
    first = service.create_request(make_request())
    second = service.create_request(
        make_request(
            request_id="request-002",
            user_id="user-002",
            provider_media_id="tmdb:603",
        )
    )

    assert service.list_requests() == (first, second)
    assert service.list_user_requests("user-002") == (second,)


def test_find_provider_request_returns_submitted_record(
    service: MediaRequestService,
) -> None:
    submitted = submitted_request(service)

    assert service.find_provider_request(
        "example",
        "provider-001",
    ) == submitted


def test_get_wraps_repository_failure(
    service: MediaRequestService,
) -> None:
    with pytest.raises(MediaRequestServiceError, match="read"):
        service.get_request("missing")


def test_submit_intent_persistence_failure_blocks_provider(
    service: MediaRequestService,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service.create_request(make_request())
    monkeypatch.setattr(
        service.repository,
        "replace",
        lambda request: (_ for _ in ()).throw(
            MediaRequestRepositoryError("failure")
        ),
    )

    with pytest.raises(MediaRequestServiceError, match="update"):
        service.submit_request("request-001")

    assert provider.submissions == []
    assert service.get_request("request-001").status is MediaRequestStatus.PENDING


def test_provider_observes_durable_submitting_intent(
    service: MediaRequestService,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service.create_request(make_request())
    real_submit = provider.submit

    def observe(request: MediaRequest) -> ProviderSubmissionResult:
        persisted = service.get_request(request.request_id)
        assert persisted.status is MediaRequestStatus.SUBMITTING
        assert persisted == request
        return real_submit(request)

    monkeypatch.setattr(provider, "submit", observe)

    result = service.submit_request("request-001")

    assert result.status is MediaRequestStatus.APPROVED


def test_submit_final_persistence_failure_keeps_intent(
    service: MediaRequestService,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service.create_request(make_request())
    real_replace = service.repository.replace
    calls = 0

    def fail_final(request: MediaRequest) -> MediaRequest:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise MediaRequestRepositoryError("failure")
        return real_replace(request)

    monkeypatch.setattr(service.repository, "replace", fail_final)

    with pytest.raises(MediaRequestServiceError, match="update"):
        service.submit_request("request-001")

    assert len(provider.submissions) == 1
    persisted = service.get_request("request-001")
    assert persisted.status is MediaRequestStatus.SUBMITTING
    assert persisted.provider_request_id is None


def test_submit_invalid_result_keeps_intent(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    provider.submission_result = object()
    service.create_request(make_request())

    with pytest.raises(MediaRequestServiceError, match="ProviderSubmissionResult"):
        service.submit_request("request-001")

    assert service.get_request("request-001").status is MediaRequestStatus.SUBMITTING


def test_submit_replay_is_blocked_from_recovery_intent(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    provider.submission_error = MediaRequestProviderOperationError("ambiguous")
    service.create_request(make_request())

    with pytest.raises(MediaRequestServiceError, match="submission failed"):
        service.submit_request("request-001")

    provider.submission_error = None
    with pytest.raises(MediaRequestServiceError, match="requires reconciliation"):
        service.submit_request("request-001")

    assert len(provider.submissions) == 1


def test_cancel_intent_persistence_failure_blocks_provider(
    service: MediaRequestService,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted = submitted_request(service)
    monkeypatch.setattr(
        service.repository,
        "replace",
        lambda request: (_ for _ in ()).throw(
            MediaRequestRepositoryError("failure")
        ),
    )

    with pytest.raises(MediaRequestServiceError, match="update"):
        service.cancel_request("request-001")

    assert provider.cancellations == []
    assert service.get_request("request-001") == submitted


def test_provider_observes_durable_cancelling_intent(
    service: MediaRequestService,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted_request(service)
    real_cancel = provider.cancel

    def observe(provider_request_id: str) -> ProviderStatusResult:
        persisted = service.get_request("request-001")
        assert persisted.status is MediaRequestStatus.CANCELLING
        assert persisted.provider_request_id == provider_request_id
        return real_cancel(provider_request_id)

    monkeypatch.setattr(provider, "cancel", observe)

    result = service.cancel_request("request-001")

    assert result.status is MediaRequestStatus.CANCELLED


def test_cancel_final_persistence_failure_keeps_intent(
    service: MediaRequestService,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    submitted_request(service)
    real_replace = service.repository.replace
    calls = 0

    def fail_final(request: MediaRequest) -> MediaRequest:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise MediaRequestRepositoryError("failure")
        return real_replace(request)

    monkeypatch.setattr(service.repository, "replace", fail_final)

    with pytest.raises(MediaRequestServiceError, match="update"):
        service.cancel_request("request-001")

    assert provider.cancellations == ["provider-001"]
    persisted = service.get_request("request-001")
    assert persisted.status is MediaRequestStatus.CANCELLING
    assert persisted.provider_request_id == "provider-001"


def test_cancel_replay_is_blocked_from_recovery_intent(
    service: MediaRequestService,
    provider: FakeProvider,
) -> None:
    submitted_request(service)
    provider.cancel_error = MediaRequestProviderOperationError("ambiguous")

    with pytest.raises(MediaRequestServiceError, match="cancellation failed"):
        service.cancel_request("request-001")

    provider.cancel_error = None
    with pytest.raises(MediaRequestServiceError, match="requires reconciliation"):
        service.cancel_request("request-001")

    assert provider.cancellations == ["provider-001"]

def test_submit_enospc_blocks_provider_and_preserves_pending_state(
    service: MediaRequestService,
    provider: FakeProvider,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = service.create_request(make_request())

    def fail_write(path: Path, value: object) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(
        "atlas.media_requests.repository.write_json_atomic",
        fail_write,
    )

    with pytest.raises(MediaRequestServiceError, match="update") as captured:
        service.submit_request(original.request_id)

    repository_error = captured.value.__cause__
    assert isinstance(repository_error, MediaRequestRepositoryError)
    assert isinstance(repository_error.__cause__, OSError)
    assert repository_error.__cause__.errno == errno.ENOSPC
    assert provider.submissions == []
    assert service.get_request(original.request_id) == original
