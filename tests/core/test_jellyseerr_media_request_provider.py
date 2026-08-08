"""Contract tests for the Jellyseerr media-request provider."""

from __future__ import annotations

from datetime import datetime, timezone
import os
from unittest.mock import patch

import pytest

from atlas.media_requests import (
    JellyseerrMediaRequestProvider,
    MediaRequest,
    MediaRequestHTTPError,
    MediaRequestProviderError,
    MediaRequestStatus,
    MediaRequestType,
    ProviderHealthStatus,
    default_jellyseerr_media_request_provider,
)


CREATED = "2026-08-02T20:00:00Z"
UPDATED = "2026-08-02T20:30:00Z"


def make_request(**overrides: object) -> MediaRequest:
    values: dict[str, object] = {
        "request_id": "request-001",
        "user_id": "user-001",
        "media_type": "movie",
        "provider": "jellyseerr",
        "provider_media_id": "157336",
        "title": "Interstellar",
        "year": 2014,
        "created_at": CREATED,
    }
    values.update(overrides)
    return MediaRequest(**values)


def make_provider() -> JellyseerrMediaRequestProvider:
    return JellyseerrMediaRequestProvider(
        base_url="http://127.0.0.1:5055",
        api_key="secret",
        clock=lambda: datetime(
            2026,
            8,
            2,
            21,
            0,
            tzinfo=timezone.utc,
        ),
    )


def response(
    *,
    request_id: int = 42,
    request_status: int = 1,
    media_status: int = 2,
    media_type: str = "movie",
    title: str = "Interstellar",
) -> dict[str, object]:
    return {
        "id": request_id,
        "status": request_status,
        "type": media_type,
        "createdAt": CREATED,
        "updatedAt": UPDATED,
        "media": {
            "tmdbId": 157336,
            "status": media_status,
            "title": title,
        },
    }


def test_name_and_capabilities() -> None:
    provider = make_provider()

    assert provider.name == "jellyseerr"
    assert provider.capabilities().media_types == (
        MediaRequestType.ANIME_MOVIE,
        MediaRequestType.ANIME_TV,
        MediaRequestType.MOVIE,
        MediaRequestType.TV,
    )
    assert provider.capabilities().supports_submission is True
    assert provider.capabilities().supports_status is True
    assert provider.capabilities().supports_cancellation is True
    assert provider.capabilities().supports_webhooks is True


def test_submit_movie_payload_and_result() -> None:
    provider = make_provider()
    request = make_request()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_post_json",
        return_value=response(
            request_status=2,
            media_status=2,
        ),
    ) as post:
        result = provider.submit(request)

    post.assert_called_once_with(
        "/api/v1/request",
        {
            "mediaType": "movie",
            "mediaId": 157336,
        },
    )
    assert result.provider == "jellyseerr"
    assert result.provider_request_id == "42"
    assert result.status is MediaRequestStatus.APPROVED
    assert result.submitted_at == CREATED
    assert result.updated_at == UPDATED
    assert result.context is not None
    assert result.context.provider_media_id == "157336"
    assert result.context.metadata == (
        ("atlas_request_id", "request-001"),
        ("atlas_user_id", "user-001"),
    )


@pytest.mark.parametrize(
    ("media_type", "expected_type"),
    [
        ("movie", "movie"),
        ("anime_movie", "movie"),
        ("tv", "tv"),
        ("anime_tv", "tv"),
    ],
)
def test_submit_maps_media_types(
    media_type: str,
    expected_type: str,
) -> None:
    values: dict[str, object] = {
        "media_type": media_type,
    }
    if media_type in {"tv", "anime_tv"}:
        values["season_number"] = 2

    provider = make_provider()
    with patch.object(
        JellyseerrMediaRequestProvider,
        "_post_json",
        return_value=response(
            request_status=1,
            media_status=2,
            media_type=expected_type,
        ),
    ) as post:
        provider.submit(make_request(**values))

    payload = post.call_args.args[1]
    assert payload["mediaType"] == expected_type


def test_submit_tv_specific_season() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_post_json",
        return_value=response(media_type="tv"),
    ) as post:
        provider.submit(
            make_request(
                media_type="tv",
                season_number=3,
            )
        )

    assert post.call_args.args[1]["seasons"] == [3]


def test_submit_tv_all_seasons() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_post_json",
        return_value=response(media_type="tv"),
    ) as post:
        provider.submit(make_request(media_type="tv"))

    assert post.call_args.args[1]["seasons"] == "all"


def test_submit_requires_media_request() -> None:
    with pytest.raises(
        MediaRequestProviderError,
        match="MediaRequest",
    ):
        make_provider().submit(object())  # type: ignore[arg-type]


def test_submit_requires_matching_provider() -> None:
    with pytest.raises(
        MediaRequestProviderError,
        match="provider",
    ):
        make_provider().submit(
            make_request(provider="other")
        )


@pytest.mark.parametrize(
    "provider_media_id",
    ["tmdb:157336", "", "abc"],
)
def test_submit_requires_numeric_tmdb_id(
    provider_media_id: str,
) -> None:
    with pytest.raises(
        (MediaRequestProviderError, ValueError),
        match="provider_media_id",
    ):
        make_provider().submit(
            make_request(provider_media_id=provider_media_id)
        )


@pytest.mark.parametrize(
    ("request_status", "media_status", "expected"),
    [
        (1, 1, MediaRequestStatus.PENDING),
        (1, 2, MediaRequestStatus.PENDING),
        (2, 1, MediaRequestStatus.APPROVED),
        (2, 2, MediaRequestStatus.APPROVED),
        (2, 3, MediaRequestStatus.SEARCHING),
        (2, 4, MediaRequestStatus.IMPORTING),
        (2, 5, MediaRequestStatus.AVAILABLE),
        (2, 6, MediaRequestStatus.FAILED),
        (3, 2, MediaRequestStatus.REJECTED),
    ],
)
def test_submit_status_mapping(
    request_status: int,
    media_status: int,
    expected: MediaRequestStatus,
) -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_post_json",
        return_value=response(
            request_status=request_status,
            media_status=media_status,
        ),
    ):
        result = provider.submit(make_request())

    assert result.status is expected


def test_submit_rejects_invalid_response_shape() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_post_json",
        return_value=[],
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="must be an object",
        ):
            provider.submit(make_request())


@pytest.mark.parametrize(
    "payload",
    [
        {"status": 1, "createdAt": CREATED},
        {"id": 1, "createdAt": CREATED},
        {"id": 1, "status": 99, "createdAt": CREATED},
        {"id": 1, "status": 1, "createdAt": "not-time"},
    ],
)
def test_submit_rejects_invalid_contract(
    payload: dict[str, object],
) -> None:
    provider = make_provider()

    with patch.object(JellyseerrMediaRequestProvider, "_post_json", return_value=payload):
        with pytest.raises(MediaRequestProviderError):
            provider.submit(make_request())


def test_get_status_reads_request_resource() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=response(
            request_status=2,
            media_status=3,
        ),
    ) as get:
        result = provider.get_status("42")

    get.assert_called_once_with("/api/v1/request/42")
    assert result.provider_request_id == "42"
    assert result.status is MediaRequestStatus.SEARCHING
    assert result.updated_at == UPDATED
    assert result.available_at is None
    assert result.context is not None


def test_get_status_marks_available_at() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=response(
            request_status=2,
            media_status=5,
        ),
    ):
        result = provider.get_status("42")

    assert result.status is MediaRequestStatus.AVAILABLE
    assert result.available_at == UPDATED


def test_get_status_rejects_mismatched_id() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value=response(request_id=99),
    ):
        with pytest.raises(
            MediaRequestProviderError,
            match="mismatched",
        ):
            provider.get_status("42")


@pytest.mark.parametrize("request_id", ["", "   ", None, True])
def test_get_status_requires_request_id(request_id: object) -> None:
    with pytest.raises(MediaRequestProviderError):
        make_provider().get_status(request_id)  # type: ignore[arg-type]


def test_cancel_deletes_request_and_returns_cancelled() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_delete_json",
        return_value=None,
    ) as delete:
        result = provider.cancel("42")

    delete.assert_called_once_with("/api/v1/request/42")
    assert result.status is MediaRequestStatus.CANCELLED
    assert result.updated_at == "2026-08-02T21:00:00Z"


def test_cancel_propagates_http_failure() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_delete_json",
        side_effect=MediaRequestHTTPError("failure"),
    ):
        with pytest.raises(MediaRequestHTTPError):
            provider.cancel("42")


def test_health_healthy_with_version() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={"version": "2.7.3"},
    ):
        health = provider.health()

    assert health.status is ProviderHealthStatus.HEALTHY
    assert health.available is True
    assert health.message == "Jellyseerr 2.7.3"
    assert health.checked_at == "2026-08-02T21:00:00Z"


def test_health_healthy_without_version() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        return_value={},
    ):
        health = provider.health()

    assert health.status is ProviderHealthStatus.HEALTHY
    assert health.message == "Jellyseerr API is reachable"


def test_health_unavailable_on_http_failure() -> None:
    provider = make_provider()

    with patch.object(
        JellyseerrMediaRequestProvider,
        "_get_json",
        side_effect=MediaRequestHTTPError("unreachable"),
    ):
        health = provider.health()

    assert health.status is ProviderHealthStatus.UNAVAILABLE
    assert health.available is False
    assert health.message == "unreachable"


def test_health_unavailable_on_invalid_payload() -> None:
    provider = make_provider()

    with patch.object(JellyseerrMediaRequestProvider, "_get_json", return_value=[]):
        health = provider.health()

    assert health.status is ProviderHealthStatus.UNAVAILABLE


def test_clock_must_return_datetime() -> None:
    provider = JellyseerrMediaRequestProvider(
        base_url="http://127.0.0.1:5055",
        api_key="secret",
        clock=lambda: "not-time",  # type: ignore[return-value]
    )

    with patch.object(JellyseerrMediaRequestProvider, "_delete_json", return_value=None):
        with pytest.raises(
            MediaRequestProviderError,
            match="clock",
        ):
            provider.cancel("42")


def test_clock_must_be_timezone_aware() -> None:
    provider = JellyseerrMediaRequestProvider(
        base_url="http://127.0.0.1:5055",
        api_key="secret",
        clock=lambda: datetime(2026, 8, 2, 21, 0),
    )

    with patch.object(JellyseerrMediaRequestProvider, "_delete_json", return_value=None):
        with pytest.raises(
            MediaRequestProviderError,
            match="timezone-aware",
        ):
            provider.cancel("42")


def test_default_provider_uses_explicit_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "ATLAS_JELLYSEERR_URL",
        "https://requests.example.test",
    )
    monkeypatch.setenv("ATLAS_JELLYSEERR_API_KEY", "secret")

    provider = default_jellyseerr_media_request_provider()

    assert provider.base_url == "https://requests.example.test"
    assert provider.api_key == "secret"


def test_default_provider_derives_internal_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_JELLYSEERR_URL", raising=False)
    monkeypatch.setenv("LXC_IP", "10.0.0.25")
    monkeypatch.setenv("JELLYSEERR_PORT", "5055")
    monkeypatch.setenv("ATLAS_JELLYSEERR_API_KEY", "secret")

    provider = default_jellyseerr_media_request_provider()

    assert provider.base_url == "http://10.0.0.25:5055"


def test_default_provider_requires_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ATLAS_JELLYSEERR_URL", raising=False)
    monkeypatch.delenv("ATLAS_JELLYSEERR_API_KEY", raising=False)
    monkeypatch.delenv("LXC_IP", raising=False)
    monkeypatch.delenv("JELLYSEERR_PORT", raising=False)

    with pytest.raises(MediaRequestHTTPError, match="api_key"):
        default_jellyseerr_media_request_provider()
