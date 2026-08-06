"""Contract tests for Atlas media-request models."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.media_requests import (
    MediaRequest,
    MediaRequestError,
    MediaRequestStatus,
    MediaRequestType,
)


def make_request(**overrides: object) -> MediaRequest:
    values: dict[str, object] = {
        "request_id": "request-001",
        "user_id": "user-001",
        "media_type": MediaRequestType.MOVIE,
        "provider": "jellyseerr",
        "provider_media_id": "tmdb:157336",
        "title": "Interstellar",
        "year": 2014,
        "created_at": "2026-08-02T20:00:00Z",
    }
    values.update(overrides)
    return MediaRequest(**values)


def test_media_request_normalizes_core_fields() -> None:
    request = MediaRequest(
        request_id=" request-001 ",
        user_id=" user-001 ",
        media_type=" Anime Movie ",
        provider=" Jellyseerr ",
        provider_request_id=" 42 ",
        provider_media_id=" tmdb:372058 ",
        title="  Your Name  ",
        year=2016,
        created_at="2026-08-02T16:00:00-04:00",
    )

    assert request.request_id == "request-001"
    assert request.user_id == "user-001"
    assert request.media_type is MediaRequestType.ANIME_MOVIE
    assert request.provider == "jellyseerr"
    assert request.provider_request_id == "42"
    assert request.provider_media_id == "tmdb:372058"
    assert request.title == "Your Name"
    assert request.created_at == "2026-08-02T20:00:00Z"
    assert request.updated_at == request.created_at


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("movie", MediaRequestType.MOVIE),
        ("TV", MediaRequestType.TV),
        ("anime-movie", MediaRequestType.ANIME_MOVIE),
        ("anime tv", MediaRequestType.ANIME_TV),
        ("sports", MediaRequestType.SPORTS),
    ],
)
def test_media_request_normalizes_supported_media_types(
    value: str,
    expected: MediaRequestType,
) -> None:
    assert make_request(media_type=value).media_type is expected


@pytest.mark.parametrize(
    "value",
    ["", "music", None, True, object()],
)
def test_media_request_rejects_invalid_media_types(value: object) -> None:
    with pytest.raises(MediaRequestError, match="media_type"):
        make_request(media_type=value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("pending", MediaRequestStatus.PENDING),
        ("SUBMITTING", MediaRequestStatus.SUBMITTING),
        ("APPROVED", MediaRequestStatus.APPROVED),
        ("downloading", MediaRequestStatus.DOWNLOADING),
        ("cancelling", MediaRequestStatus.CANCELLING),
        ("cancelled", MediaRequestStatus.CANCELLED),
    ],
)
def test_media_request_normalizes_supported_statuses(
    value: str,
    expected: MediaRequestStatus,
) -> None:
    overrides: dict[str, object] = {"status": value}

    if expected is MediaRequestStatus.CANCELLING:
        overrides["provider_request_id"] = "provider-request-001"

    assert make_request(**overrides).status is expected


@pytest.mark.parametrize(
    "field_name",
    [
        "request_id",
        "user_id",
        "provider_media_id",
        "title",
    ],
)
@pytest.mark.parametrize("value", ["", "   ", None, True, object()])
def test_media_request_requires_core_identity_and_text(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(MediaRequestError, match=field_name):
        make_request(**{field_name: value})


@pytest.mark.parametrize(
    "value",
    ["-request", "request-", "request value", "request/value", "@request"],
)
def test_media_request_rejects_invalid_request_identity(value: str) -> None:
    with pytest.raises(MediaRequestError, match="request_id"):
        make_request(request_id=value)


def test_media_request_normalizes_provider() -> None:
    request = make_request(provider=" Jellyseerr API ")
    assert request.provider == "jellyseerr-api"


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, True, "jellyseerr/api", "-jellyseerr"],
)
def test_media_request_rejects_invalid_provider(value: object) -> None:
    with pytest.raises(MediaRequestError, match="provider"):
        make_request(provider=value)


def test_media_request_accepts_optional_provider_request_id() -> None:
    assert make_request(provider_request_id=None).provider_request_id is None
    assert make_request(provider_request_id=42).provider_request_id == "42"


@pytest.mark.parametrize("value", ["", "   ", True, object()])
def test_media_request_rejects_invalid_provider_request_id(
    value: object,
) -> None:
    with pytest.raises(MediaRequestError, match="provider_request_id"):
        make_request(provider_request_id=value)


@pytest.mark.parametrize("value", [1887, 99999, True, "2014"])
def test_media_request_rejects_invalid_year(value: object) -> None:
    with pytest.raises(MediaRequestError, match="year"):
        make_request(year=value)


def test_media_request_accepts_season_for_tv() -> None:
    request = make_request(
        media_type="tv",
        season_number=2,
    )
    assert request.season_number == 2


@pytest.mark.parametrize("media_type", ["movie", "anime_movie", "sports"])
def test_media_request_rejects_season_for_non_tv(
    media_type: str,
) -> None:
    with pytest.raises(MediaRequestError, match="season_number"):
        make_request(
            media_type=media_type,
            season_number=1,
        )


@pytest.mark.parametrize("value", [-1, True, "1"])
def test_media_request_rejects_invalid_season_number(value: object) -> None:
    with pytest.raises(MediaRequestError, match="season_number"):
        make_request(
            media_type="tv",
            season_number=value,
        )


def test_available_request_requires_available_timestamp() -> None:
    with pytest.raises(MediaRequestError, match="available_at is required"):
        make_request(status="available")


def test_non_available_request_rejects_available_timestamp() -> None:
    with pytest.raises(
        MediaRequestError,
        match="available_at is only valid",
    ):
        make_request(
            status="pending",
            available_at="2026-08-02T21:00:00Z",
        )


def test_available_request_normalizes_timestamp() -> None:
    request = make_request(
        status="available",
        updated_at="2026-08-02T17:00:00-04:00",
        available_at="2026-08-02T17:00:00-04:00",
    )

    assert request.available_at == "2026-08-02T21:00:00Z"
    assert request.updated_at == "2026-08-02T21:00:00Z"
    assert request.terminal is True
    assert request.active is False


@pytest.mark.parametrize(
    "field_name",
    ["created_at", "updated_at", "available_at"],
)
@pytest.mark.parametrize(
    "value",
    ["not-a-timestamp", "2026-08-02T20:00:00"],
)
def test_media_request_rejects_invalid_timestamps(
    field_name: str,
    value: str,
) -> None:
    overrides: dict[str, object] = {field_name: value}

    if field_name == "available_at":
        overrides["status"] = "available"

    with pytest.raises(MediaRequestError, match=field_name):
        make_request(**overrides)


def test_media_request_rejects_updated_at_before_created_at() -> None:
    with pytest.raises(MediaRequestError, match="updated_at"):
        make_request(updated_at="2026-08-02T19:59:59Z")


def test_media_request_rejects_available_at_before_created_at() -> None:
    with pytest.raises(MediaRequestError, match="available_at"):
        make_request(
            status="available",
            available_at="2026-08-02T19:59:59Z",
        )


@pytest.mark.parametrize(
    ("status", "terminal"),
    [
        (MediaRequestStatus.PENDING, False),
        (MediaRequestStatus.SUBMITTING, False),
        (MediaRequestStatus.APPROVED, False),
        (MediaRequestStatus.SEARCHING, False),
        (MediaRequestStatus.DOWNLOADING, False),
        (MediaRequestStatus.IMPORTING, False),
        (MediaRequestStatus.CANCELLING, False),
        (MediaRequestStatus.AVAILABLE, True),
        (MediaRequestStatus.REJECTED, True),
        (MediaRequestStatus.FAILED, True),
        (MediaRequestStatus.CANCELLED, True),
    ],
)
def test_media_request_terminal_contract(
    status: MediaRequestStatus,
    terminal: bool,
) -> None:
    overrides: dict[str, object] = {"status": status}

    if status is MediaRequestStatus.AVAILABLE:
        overrides["available_at"] = "2026-08-02T21:00:00Z"
    elif status is MediaRequestStatus.CANCELLING:
        overrides["provider_request_id"] = "provider-request-001"

    request = make_request(**overrides)

    assert request.terminal is terminal
    assert request.active is not terminal


def test_submitting_request_is_recovery_intent_without_provider_id() -> None:
    request = make_request(
        status=" submitting ",
        provider_request_id=None,
        updated_at="2026-08-02T20:30:00Z",
    )

    assert request.status is MediaRequestStatus.SUBMITTING
    assert request.provider_request_id is None
    assert request.terminal is False
    assert request.active is True
    assert request.to_dict()["status"] == "submitting"


def test_submitting_request_rejects_provider_request_id() -> None:
    with pytest.raises(
        MediaRequestError,
        match="provider_request_id must be null when status is submitting",
    ):
        make_request(
            status="submitting",
            provider_request_id="provider-request-001",
        )


def test_cancelling_request_requires_provider_request_id() -> None:
    with pytest.raises(
        MediaRequestError,
        match="provider_request_id is required when status is cancelling",
    ):
        make_request(
            status="cancelling",
            provider_request_id=None,
        )


def test_cancelling_request_is_recovery_intent_with_provider_id() -> None:
    request = make_request(
        status=" cancelling ",
        provider_request_id=" provider-request-001 ",
        updated_at="2026-08-02T20:30:00Z",
    )

    assert request.status is MediaRequestStatus.CANCELLING
    assert request.provider_request_id == "provider-request-001"
    assert request.terminal is False
    assert request.active is True
    assert request.to_dict()["status"] == "cancelling"


def test_recovery_intent_statuses_are_publicly_exported() -> None:
    assert MediaRequestStatus.SUBMITTING.value == "submitting"
    assert MediaRequestStatus.CANCELLING.value == "cancelling"


def test_media_request_is_immutable() -> None:
    request = make_request()

    with pytest.raises(FrozenInstanceError):
        request.title = "Changed"  # type: ignore[misc]


def test_media_request_serializes_normalized_contract() -> None:
    request = make_request(
        media_type="tv",
        provider_request_id=42,
        provider_media_id=1399,
        season_number=1,
        status="approved",
        updated_at="2026-08-02T20:30:00Z",
    )

    assert request.to_dict() == {
        "request_id": "request-001",
        "user_id": "user-001",
        "media_type": "tv",
        "provider": "jellyseerr",
        "provider_request_id": "42",
        "provider_media_id": "1399",
        "title": "Interstellar",
        "year": 2014,
        "season_number": 1,
        "status": "approved",
        "terminal": False,
        "active": True,
        "created_at": "2026-08-02T20:00:00Z",
        "updated_at": "2026-08-02T20:30:00Z",
        "available_at": None,
    }
