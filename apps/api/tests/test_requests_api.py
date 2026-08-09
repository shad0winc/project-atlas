"""Contract tests for the self-scoped Atlas media-request API."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tempfile
import unittest

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from atlas.media_requests import (
    JsonMediaRequestRepository,
    MediaRequest,
    MediaRequestProvider,
    MediaRequestProviderOperationError,
    MediaRequestRepositoryError,
    MediaRequestService,
    MediaRequestStatus,
    MediaRequestType,
    ProviderCapabilities,
    ProviderHealth,
    ProviderStatusResult,
    ProviderSubmissionResult,
)
from atlas_api.auth.models import AuthenticatedUser
from atlas_api.main import create_app
from atlas_api.routes.v1.requests import (
    get_media_requests_api_service,
    require_requests_cancel,
    require_requests_create,
    require_requests_read,
)
from atlas_api.services.requests import (
    MediaRequestNotFoundError,
    MediaRequestReconciliationRequiredError,
    MediaRequestValidationError,
    MediaRequestsAPIService,
    MediaRequestsUnavailableError,
)


USER_ID = "usr_" + ("a" * 32)
OTHER_USER_ID = "usr_" + ("b" * 32)
REQUEST_ID = "req_" + ("c" * 32)
OTHER_REQUEST_ID = "req_" + ("d" * 32)
TIMESTAMP = "2026-08-09T19:30:00Z"
UPDATED = "2026-08-09T19:31:00Z"


def authenticated_user() -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id=USER_ID,
        username="michael",
        display_name="Michael",
        roles=("member",),
        provider="jellyfin",
        metadata={},
    )


def request_record(
    *,
    request_id: str = REQUEST_ID,
    user_id: str = USER_ID,
    status_value: str = "approved",
    provider_request_id: str | None = "42",
) -> MediaRequest:
    return MediaRequest(
        request_id=request_id,
        user_id=user_id,
        media_type="movie",
        provider="jellyseerr",
        provider_media_id="157336",
        title="Interstellar",
        year=2014,
        status=status_value,
        provider_request_id=provider_request_id,
        created_at=TIMESTAMP,
        updated_at=UPDATED,
    )


class StubMediaRequestsAPIService:
    """Record route calls without touching persistent state."""

    def __init__(self) -> None:
        self.records = (
            request_record(),
        )
        self.list_user_ids: list[str] = []
        self.create_calls: list[
            tuple[
                str,
                str,
                str,
                str,
                int | None,
                int | None,
            ]
        ] = []
        self.cancel_calls: list[
            tuple[str, str]
        ] = []

    def list_for_user(
        self,
        user_id: str,
    ) -> tuple[MediaRequest, ...]:
        self.list_user_ids.append(
            user_id
        )
        return self.records

    def create_for_user(
        self,
        user_id: str,
        *,
        media_type: str,
        provider_media_id: str,
        title: str,
        year: int | None = None,
        season_number: int | None = None,
    ) -> MediaRequest:
        self.create_calls.append(
            (
                user_id,
                media_type,
                provider_media_id,
                title,
                year,
                season_number,
            )
        )

        return request_record()

    def cancel_for_user(
        self,
        user_id: str,
        request_id: str,
    ) -> MediaRequest:
        self.cancel_calls.append(
            (
                user_id,
                request_id,
            )
        )

        return request_record(
            request_id=request_id,
            status_value="cancelled",
        )


class MediaRequestsEndpointTests(unittest.TestCase):
    """Verify authentication, permissions, and self-scope at HTTP boundary."""

    def setUp(self) -> None:
        self.app = create_app()
        self.service = StubMediaRequestsAPIService()

        self.app.dependency_overrides[
            require_requests_read
        ] = authenticated_user

        self.app.dependency_overrides[
            require_requests_create
        ] = authenticated_user

        self.app.dependency_overrides[
            require_requests_cancel
        ] = authenticated_user

        self.app.dependency_overrides[
            get_media_requests_api_service
        ] = lambda: self.service

        self.client = TestClient(
            self.app
        )

    def tearDown(self) -> None:
        self.app.dependency_overrides.clear()

    def test_list_uses_authenticated_user_scope(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/requests"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            [USER_ID],
            self.service.list_user_ids,
        )

        payload = response.json()

        self.assertEqual(
            USER_ID,
            payload["requests"][0]["user_id"],
        )

        self.assertNotIn(
            "provider_request_id",
            payload["requests"][0],
        )

        self.assertTrue(
            payload["requests"][0]["can_cancel"]
        )

        self.assertFalse(
            payload["requests"][0]["recovery_required"]
        )

    def test_list_ignores_caller_user_id_selection(
        self,
    ) -> None:
        response = self.client.get(
            "/api/v1/requests",
            params={
                "user_id": OTHER_USER_ID,
            },
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            [USER_ID],
            self.service.list_user_ids,
        )

    def test_create_uses_authenticated_user_scope(
        self,
    ) -> None:
        response = self.client.post(
            "/api/v1/requests",
            json={
                "media_type": "movie",
                "provider_media_id": "157336",
                "title": "Interstellar",
                "year": 2014,
            },
        )

        self.assertEqual(
            201,
            response.status_code,
        )

        self.assertEqual(
            [
                (
                    USER_ID,
                    "movie",
                    "157336",
                    "Interstellar",
                    2014,
                    None,
                )
            ],
            self.service.create_calls,
        )

    def test_create_rejects_caller_owned_fields(
        self,
    ) -> None:
        forbidden_fields = (
            ("user_id", OTHER_USER_ID),
            ("provider", "other-provider"),
            ("request_id", OTHER_REQUEST_ID),
            ("provider_request_id", "999"),
            ("status", "approved"),
            ("created_at", TIMESTAMP),
            ("updated_at", UPDATED),
        )

        for field_name, field_value in forbidden_fields:
            with self.subTest(
                field_name=field_name
            ):
                response = self.client.post(
                    "/api/v1/requests",
                    json={
                        "media_type": "movie",
                                "provider_media_id": "157336",
                        "title": "Interstellar",
                        field_name: field_value,
                    },
                )

                self.assertEqual(
                    422,
                    response.status_code,
                )

        self.assertEqual(
            [],
            self.service.create_calls,
        )

    def test_cancel_uses_authenticated_user_scope(
        self,
    ) -> None:
        response = self.client.post(
            f"/api/v1/requests/{REQUEST_ID}/cancel"
        )

        self.assertEqual(
            200,
            response.status_code,
        )

        self.assertEqual(
            [
                (
                    USER_ID,
                    REQUEST_ID,
                )
            ],
            self.service.cancel_calls,
        )

    def test_read_requires_authentication(
        self,
    ) -> None:
        def unauthenticated() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Bearer authentication is required.",
                headers={
                    "WWW-Authenticate": "Bearer",
                },
            )

        self.app.dependency_overrides[
            require_requests_read
        ] = unauthenticated

        response = self.client.get(
            "/api/v1/requests"
        )

        self.assertEqual(
            401,
            response.status_code,
        )

    def test_create_requires_permission(
        self,
    ) -> None:
        def forbidden() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden.",
            )

        self.app.dependency_overrides[
            require_requests_create
        ] = forbidden

        response = self.client.post(
            "/api/v1/requests",
            json={
                "media_type": "movie",
                "provider_media_id": "157336",
                "title": "Interstellar",
            },
        )

        self.assertEqual(
            403,
            response.status_code,
        )

    def test_cancel_requires_permission(
        self,
    ) -> None:
        def forbidden() -> AuthenticatedUser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden.",
            )

        self.app.dependency_overrides[
            require_requests_cancel
        ] = forbidden

        response = self.client.post(
            f"/api/v1/requests/{REQUEST_ID}/cancel"
        )

        self.assertEqual(
            403,
            response.status_code,
        )

        self.assertEqual(
            [],
            self.service.cancel_calls,
        )

    def test_openapi_registers_request_routes(
        self,
    ) -> None:
        schema = self.client.app.openapi()

        self.assertIn(
            "/api/v1/requests",
            schema["paths"],
        )

        self.assertIn(
            "/api/v1/requests/{request_id}/cancel",
            schema["paths"],
        )


class FakeProvider(MediaRequestProvider):
    """Deterministic provider for application-service tests."""

    def __init__(self) -> None:
        self.submissions: list[MediaRequest] = []
        self.cancellations: list[str] = []
        self.submission_error: Exception | None = None
        self.cancel_error: Exception | None = None

    @property
    def name(self) -> str:
        return "jellyseerr"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types=(
                MediaRequestType.MOVIE,
                MediaRequestType.TV,
                MediaRequestType.ANIME_MOVIE,
                MediaRequestType.ANIME_TV,
            ),
            supports_submission=True,
            supports_status=True,
            supports_cancellation=True,
        )

    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        self.submissions.append(
            request
        )

        if self.submission_error is not None:
            raise self.submission_error

        provider_timestamp = (
            request.updated_at
            or request.created_at
        )

        return ProviderSubmissionResult(
            provider=self.name,
            provider_request_id="42",
            status="approved",
            submitted_at=provider_timestamp,
            updated_at=provider_timestamp,
        )

    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        return ProviderStatusResult(
            provider=self.name,
            provider_request_id=provider_request_id,
            status="approved",
            updated_at=UPDATED,
        )

    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        self.cancellations.append(
            provider_request_id
        )

        if self.cancel_error is not None:
            raise self.cancel_error

        return ProviderStatusResult(
            provider=self.name,
            provider_request_id=provider_request_id,
            status="cancelled",
            updated_at=UPDATED,
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="healthy",
            checked_at=TIMESTAMP,
        )


@dataclass
class ServiceFixture:
    repository: JsonMediaRequestRepository
    provider: FakeProvider
    api: MediaRequestsAPIService


def make_service_fixture() -> ServiceFixture:
    temporary = tempfile.TemporaryDirectory()

    # Keep the directory alive for the fixture lifetime by attaching
    # it to the repository object used only within this test process.
    repository = JsonMediaRequestRepository(
        Path(temporary.name) / "requests"
    )
    setattr(
        repository,
        "_test_temporary_directory",
        temporary,
    )

    provider = FakeProvider()

    core = MediaRequestService(
        repository,
        (provider,),
    )

    api = MediaRequestsAPIService(
        repository=repository,
        requests=core,
        request_id_factory=lambda: REQUEST_ID,
    )

    return ServiceFixture(
        repository=repository,
        provider=provider,
        api=api,
    )


def test_application_create_binds_authenticated_owner_and_id() -> None:
    fixture = make_service_fixture()

    result = fixture.api.create_for_user(
        USER_ID,
        media_type="movie",
        provider_media_id="157336",
        title="Interstellar",
        year=2014,
    )

    assert result.request_id == REQUEST_ID
    assert result.user_id == USER_ID
    assert result.provider == "jellyseerr"
    assert result.status is MediaRequestStatus.APPROVED

    assert len(fixture.provider.submissions) == 1

    submitted = fixture.provider.submissions[0]

    assert submitted.request_id == REQUEST_ID
    assert submitted.user_id == USER_ID
    assert submitted.status is MediaRequestStatus.SUBMITTING


def test_application_rejects_non_numeric_jellyseerr_id_before_persistence(
) -> None:
    fixture = make_service_fixture()

    with pytest.raises(
        MediaRequestValidationError,
        match="numeric",
    ):
        fixture.api.create_for_user(
            USER_ID,
            media_type="movie",
            provider_media_id="tmdb:157336",
            title="Interstellar",
        )

    assert fixture.repository.list() == ()
    assert fixture.provider.submissions == []


def test_application_list_is_self_scoped() -> None:
    fixture = make_service_fixture()

    fixture.repository.save(
        MediaRequest(
            request_id=REQUEST_ID,
            user_id=USER_ID,
            media_type="movie",
            provider="jellyseerr",
            provider_media_id="157336",
            title="Interstellar",
            created_at=TIMESTAMP,
        )
    )

    fixture.repository.save(
        MediaRequest(
            request_id=OTHER_REQUEST_ID,
            user_id=OTHER_USER_ID,
            media_type="movie",
            provider="jellyseerr",
            provider_media_id="603",
            title="The Matrix",
            created_at=TIMESTAMP,
        )
    )

    assert tuple(
        request.request_id
        for request in fixture.api.list_for_user(
            USER_ID
        )
    ) == (
        REQUEST_ID,
    )


def test_cross_user_cancel_is_hidden_and_does_not_mutate() -> None:
    fixture = make_service_fixture()

    fixture.repository.save(
        request_record(
            request_id=OTHER_REQUEST_ID,
            user_id=OTHER_USER_ID,
        )
    )

    with pytest.raises(
        MediaRequestNotFoundError
    ):
        fixture.api.cancel_for_user(
            USER_ID,
            OTHER_REQUEST_ID,
        )

    assert fixture.provider.cancellations == []


def test_submission_final_persistence_failure_requires_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = make_service_fixture()

    original_replace = fixture.repository.replace
    replace_calls = 0

    def replace_with_final_failure(
        request: MediaRequest,
    ) -> MediaRequest:
        nonlocal replace_calls

        replace_calls += 1

        if replace_calls == 2:
            raise MediaRequestRepositoryError(
                "simulated final persistence failure"
            )

        return original_replace(
            request
        )

    monkeypatch.setattr(
        fixture.repository,
        "replace",
        replace_with_final_failure,
    )

    with pytest.raises(
        MediaRequestReconciliationRequiredError
    ):
        fixture.api.create_for_user(
            USER_ID,
            media_type="movie",
            provider_media_id="157336",
            title="Interstellar",
        )

    persisted = fixture.repository.get(
        REQUEST_ID
    )

    assert persisted.status is MediaRequestStatus.SUBMITTING
    assert len(fixture.provider.submissions) == 1


def test_cancellation_final_persistence_failure_requires_reconciliation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = make_service_fixture()

    fixture.repository.save(
        request_record()
    )

    original_replace = fixture.repository.replace
    replace_calls = 0

    def replace_with_final_failure(
        request: MediaRequest,
    ) -> MediaRequest:
        nonlocal replace_calls

        replace_calls += 1

        if replace_calls == 2:
            raise MediaRequestRepositoryError(
                "simulated final persistence failure"
            )

        return original_replace(
            request
        )

    monkeypatch.setattr(
        fixture.repository,
        "replace",
        replace_with_final_failure,
    )

    with pytest.raises(
        MediaRequestReconciliationRequiredError
    ):
        fixture.api.cancel_for_user(
            USER_ID,
            REQUEST_ID,
        )

    persisted = fixture.repository.get(
        REQUEST_ID
    )

    assert persisted.status is MediaRequestStatus.CANCELLING
    assert fixture.provider.cancellations == ["42"]


def test_repository_corruption_is_not_hidden_as_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = make_service_fixture()

    def corrupt_get(
        request_id: object,
    ) -> MediaRequest:
        del request_id

        raise MediaRequestRepositoryError(
            "media-request registry key does not match "
            "record request_id: corrupted"
        )

    monkeypatch.setattr(
        fixture.repository,
        "get",
        corrupt_get,
    )

    with pytest.raises(
        MediaRequestsUnavailableError
    ):
        fixture.api.cancel_for_user(
            USER_ID,
            REQUEST_ID,
        )


def test_submission_failure_surfaces_reconciliation_and_keeps_intent(
) -> None:
    fixture = make_service_fixture()

    fixture.provider.submission_error = (
        MediaRequestProviderOperationError(
            "ambiguous"
        )
    )

    with pytest.raises(
        MediaRequestReconciliationRequiredError
    ):
        fixture.api.create_for_user(
            USER_ID,
            media_type="movie",
            provider_media_id="157336",
            title="Interstellar",
        )

    persisted = fixture.repository.get(
        REQUEST_ID
    )

    assert persisted.status is MediaRequestStatus.SUBMITTING
    assert persisted.provider_request_id is None


def test_cancellation_failure_surfaces_reconciliation_and_keeps_intent(
) -> None:
    fixture = make_service_fixture()

    fixture.repository.save(
        request_record()
    )

    fixture.provider.cancel_error = (
        MediaRequestProviderOperationError(
            "ambiguous"
        )
    )

    with pytest.raises(
        MediaRequestReconciliationRequiredError
    ):
        fixture.api.cancel_for_user(
            USER_ID,
            REQUEST_ID,
        )

    persisted = fixture.repository.get(
        REQUEST_ID
    )

    assert persisted.status is MediaRequestStatus.CANCELLING
    assert persisted.provider_request_id == "42"
