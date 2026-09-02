import pytest

from atlas.media_requests.models import (
    MediaRequest,
    MediaRequestError,
    MediaRequestStatus,
    MediaRequestType,
)
from atlas.media_requests.provider import (
    MediaRequestProviderError,
    ProviderSubmissionResult,
)


def _request(**overrides):
    values = {
        "request_id": "req_0123456789abcdef0123456789abcdef",
        "user_id": "usr_0123456789abcdef0123456789abcdef",
        "media_type": MediaRequestType.MOVIE,
        "provider": "jellyseerr",
        "provider_media_id": "123",
        "title": "Example",
        "status": MediaRequestStatus.APPROVED,
        "provider_request_id": "456",
        "created_at": "2026-08-13T02:04:58.832861Z",
        "updated_at": "2026-08-13T02:04:58Z",
    }
    values.update(overrides)
    return MediaRequest(**values)


def test_request_repairs_same_second_provider_precision_loss():
    request = _request()
    assert request.updated_at == request.created_at


def test_request_rejects_genuinely_earlier_update():
    with pytest.raises(
        MediaRequestError,
        match="updated_at must not be earlier than created_at",
    ):
        _request(updated_at="2026-08-13T02:04:56Z")


def test_provider_submission_repairs_same_second_precision_loss():
    result = ProviderSubmissionResult(
        provider="jellyseerr",
        provider_request_id="456",
        status=MediaRequestStatus.APPROVED,
        submitted_at="2026-08-13T02:04:58.832861Z",
        updated_at="2026-08-13T02:04:58Z",
        context=None,
    )
    assert result.updated_at == result.submitted_at


def test_provider_submission_rejects_genuinely_earlier_update():
    with pytest.raises(
        MediaRequestProviderError,
        match="updated_at must not be earlier than submitted_at",
    ):
        ProviderSubmissionResult(
            provider="jellyseerr",
            provider_request_id="456",
            status=MediaRequestStatus.APPROVED,
            submitted_at="2026-08-13T02:04:58.832861Z",
            updated_at="2026-08-13T02:04:56Z",
            context=None,
        )
