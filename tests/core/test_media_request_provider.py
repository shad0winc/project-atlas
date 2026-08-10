"""Contract tests for Atlas media-request providers."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas.media_requests import (
    MediaRequest,
    MediaRequestProvider,
    MediaRequestProviderError,
    MediaRequestStatus,
    MediaRequestType,
    ProviderCapabilities,
    ProviderEventContext,
    ProviderHealth,
    ProviderHealthStatus,
    ProviderStatusResult,
    ProviderSubmissionResult,
)


TIMESTAMP = "2026-08-02T20:00:00Z"


def make_request(**overrides: object) -> MediaRequest:
    values: dict[str, object] = {
        "request_id": "request-001",
        "user_id": "user-001",
        "media_type": "movie",
        "provider": "jellyseerr",
        "provider_media_id": "tmdb:157336",
        "title": "Interstellar",
        "created_at": TIMESTAMP,
    }
    values.update(overrides)
    return MediaRequest(**values)


class CompleteProvider(MediaRequestProvider):
    @property
    def name(self) -> str:
        return "example"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            media_types=(MediaRequestType.MOVIE,),
        )

    def submit(
        self,
        request: MediaRequest,
    ) -> ProviderSubmissionResult:
        return ProviderSubmissionResult(
            provider=self.name,
            provider_request_id="1",
            status="pending",
            submitted_at=TIMESTAMP,
        )

    def get_status(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        return ProviderStatusResult(
            provider=self.name,
            provider_request_id=provider_request_id,
            status="pending",
            updated_at=TIMESTAMP,
        )

    def cancel(
        self,
        provider_request_id: str,
    ) -> ProviderStatusResult:
        return ProviderStatusResult(
            provider=self.name,
            provider_request_id=provider_request_id,
            status="cancelled",
            updated_at=TIMESTAMP,
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            provider=self.name,
            status="healthy",
            checked_at=TIMESTAMP,
        )


def test_abstract_provider_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        MediaRequestProvider()  # type: ignore[abstract]


def test_complete_provider_satisfies_contract() -> None:
    provider = CompleteProvider()

    assert provider.name == "example"
    assert provider.capabilities().supports("movie") is True
    assert provider.validate_submission(
        make_request()
    ) is None
    assert provider.submit(make_request()).provider_request_id == "1"
    assert provider.get_status("1").status is MediaRequestStatus.PENDING
    assert provider.cancel("1").status is MediaRequestStatus.CANCELLED
    assert provider.health().available is True


def test_capabilities_normalize_and_sort_media_types() -> None:
    capabilities = ProviderCapabilities(
        media_types=("tv", "movie", "anime-movie"),
        supports_cancellation=True,
        supports_webhooks=True,
    )

    assert capabilities.media_types == (
        MediaRequestType.ANIME_MOVIE,
        MediaRequestType.MOVIE,
        MediaRequestType.TV,
    )
    assert capabilities.supports(" anime movie ") is True
    assert capabilities.supports("sports") is False
    assert capabilities.to_dict() == {
        "media_types": ["anime_movie", "movie", "tv"],
        "supports_submission": True,
        "supports_status": True,
        "supports_cancellation": True,
        "supports_webhooks": True,
    }


@pytest.mark.parametrize(
    "value",
    [[], (), "movie", ("movie", "movie"), ("unsupported",)],
)
def test_capabilities_reject_invalid_media_types(value: object) -> None:
    with pytest.raises(MediaRequestProviderError):
        ProviderCapabilities(media_types=value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field_name",
    [
        "supports_submission",
        "supports_status",
        "supports_cancellation",
        "supports_webhooks",
    ],
)
def test_capabilities_require_boolean_flags(field_name: str) -> None:
    with pytest.raises(MediaRequestProviderError, match=field_name):
        ProviderCapabilities(
            media_types=(MediaRequestType.MOVIE,),
            **{field_name: 1},
        )


def test_event_context_normalizes_contract() -> None:
    context = ProviderEventContext(
        provider=" Jellyseerr API ",
        provider_media_id=157336,
        media_type="movie",
        title=" Interstellar ",
        year=2014,
        metadata={"library": "Movies", "quality": "4K"},
    )

    assert context.provider == "jellyseerr-api"
    assert context.provider_media_id == "157336"
    assert context.metadata == (
        ("library", "Movies"),
        ("quality", "4K"),
    )
    assert context.to_dict()["metadata"] == {
        "library": "Movies",
        "quality": "4K",
    }


def test_event_context_accepts_tv_season() -> None:
    context = ProviderEventContext(
        provider="jellyseerr",
        provider_media_id="1399",
        media_type="tv",
        title="Game of Thrones",
        season_number=1,
    )
    assert context.season_number == 1


@pytest.mark.parametrize("media_type", ["movie", "anime_movie", "sports"])
def test_event_context_rejects_season_for_non_tv(
    media_type: str,
) -> None:
    with pytest.raises(MediaRequestProviderError, match="season_number"):
        ProviderEventContext(
            provider="example",
            provider_media_id="1",
            media_type=media_type,
            title="Title",
            season_number=1,
        )


def test_submission_result_normalizes_and_serializes() -> None:
    context = ProviderEventContext(
        provider="jellyseerr",
        provider_media_id="157336",
        media_type="movie",
        title="Interstellar",
    )
    result = ProviderSubmissionResult(
        provider=" Jellyseerr ",
        provider_request_id=42,
        status="approved",
        submitted_at="2026-08-02T16:00:00-04:00",
        context=context,
    )

    assert result.provider == "jellyseerr"
    assert result.provider_request_id == "42"
    assert result.status is MediaRequestStatus.APPROVED
    assert result.submitted_at == TIMESTAMP
    assert result.updated_at == TIMESTAMP
    assert result.to_dict()["context"] == context.to_dict()


def test_submission_result_rejects_earlier_update() -> None:
    with pytest.raises(MediaRequestProviderError, match="updated_at"):
        ProviderSubmissionResult(
            provider="example",
            provider_request_id="1",
            status="pending",
            submitted_at=TIMESTAMP,
            updated_at="2026-08-02T19:59:59Z",
        )


def test_status_result_available_contract() -> None:
    result = ProviderStatusResult(
        provider="example",
        provider_request_id="1",
        status="available",
        updated_at=TIMESTAMP,
        available_at=TIMESTAMP,
    )

    assert result.terminal is True
    assert result.to_dict()["status"] == "available"


def test_available_status_requires_available_at() -> None:
    with pytest.raises(MediaRequestProviderError, match="available_at"):
        ProviderStatusResult(
            provider="example",
            provider_request_id="1",
            status="available",
            updated_at=TIMESTAMP,
        )


def test_non_available_status_rejects_available_at() -> None:
    with pytest.raises(MediaRequestProviderError, match="available_at"):
        ProviderStatusResult(
            provider="example",
            provider_request_id="1",
            status="pending",
            updated_at=TIMESTAMP,
            available_at=TIMESTAMP,
        )


def test_failed_status_requires_error() -> None:
    with pytest.raises(MediaRequestProviderError, match="error"):
        ProviderStatusResult(
            provider="example",
            provider_request_id="1",
            status="failed",
            updated_at=TIMESTAMP,
        )


def test_non_failed_status_rejects_error() -> None:
    with pytest.raises(MediaRequestProviderError, match="error"):
        ProviderStatusResult(
            provider="example",
            provider_request_id="1",
            status="pending",
            updated_at=TIMESTAMP,
            error="failure",
        )


@pytest.mark.parametrize(
    ("status", "terminal"),
    [
        ("pending", False),
        ("approved", False),
        ("searching", False),
        ("downloading", False),
        ("importing", False),
        ("available", True),
        ("rejected", True),
        ("failed", True),
        ("cancelled", True),
    ],
)
def test_status_result_terminal_contract(
    status: str,
    terminal: bool,
) -> None:
    values: dict[str, object] = {
        "provider": "example",
        "provider_request_id": "1",
        "status": status,
        "updated_at": TIMESTAMP,
    }
    if status == "available":
        values["available_at"] = TIMESTAMP
    if status == "failed":
        values["error"] = "provider failure"

    result = ProviderStatusResult(**values)

    assert result.terminal is terminal


@pytest.mark.parametrize(
    ("status", "available"),
    [
        ("healthy", True),
        ("degraded", True),
        ("unavailable", False),
        ("unknown", False),
    ],
)
def test_provider_health_contract(
    status: str,
    available: bool,
) -> None:
    health = ProviderHealth(
        provider=" Example ",
        status=status,
        checked_at="2026-08-02T16:00:00-04:00",
        message=" status message ",
    )

    assert health.provider == "example"
    assert health.status is ProviderHealthStatus(status)
    assert health.checked_at == TIMESTAMP
    assert health.message == "status message"
    assert health.available is available
    assert health.to_dict()["available"] is available


@pytest.mark.parametrize(
    "value",
    ["", "unsupported", None, True],
)
def test_provider_health_rejects_invalid_status(value: object) -> None:
    with pytest.raises(MediaRequestProviderError, match="status"):
        ProviderHealth(
            provider="example",
            status=value,
            checked_at=TIMESTAMP,
        )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ProviderCapabilities(
            media_types=(MediaRequestType.MOVIE,),
        ),
        lambda: ProviderEventContext(
            provider="example",
            provider_media_id="1",
            media_type="movie",
            title="Title",
        ),
        lambda: ProviderSubmissionResult(
            provider="example",
            provider_request_id="1",
            status="pending",
            submitted_at=TIMESTAMP,
        ),
        lambda: ProviderStatusResult(
            provider="example",
            provider_request_id="1",
            status="pending",
            updated_at=TIMESTAMP,
        ),
        lambda: ProviderHealth(
            provider="example",
            status="healthy",
            checked_at=TIMESTAMP,
        ),
    ],
)
def test_provider_contract_models_are_immutable(factory: object) -> None:
    value = factory()  # type: ignore[operator]

    with pytest.raises(FrozenInstanceError):
        value.provider = "changed"  # type: ignore[misc,union-attr]


@pytest.mark.parametrize(
    "timestamp_field",
    ["submitted_at", "updated_at"],
)
def test_submission_result_rejects_naive_timestamps(
    timestamp_field: str,
) -> None:
    values: dict[str, object] = {
        "provider": "example",
        "provider_request_id": "1",
        "status": "pending",
        "submitted_at": TIMESTAMP,
    }
    values[timestamp_field] = "2026-08-02T20:00:00"

    with pytest.raises(
        MediaRequestProviderError,
        match=timestamp_field,
    ):
        ProviderSubmissionResult(**values)
