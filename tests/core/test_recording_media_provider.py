"""Tests for the safe recording media provider."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from atlas.media import (
    MediaItem,
    MediaProviderError,
    ProviderOperation,
    RecordingMediaProvider,
)


FIXED_TIME = datetime(
    2026,
    7,
    20,
    18,
    30,
    tzinfo=timezone.utc,
)


def _item(
    *,
    provider: str = "jellyfin",
    item_id: str = "movie-123",
) -> MediaItem:
    return MediaItem(
        provider=provider,
        item_id=item_id,
        media_type="movie",
        title="Example Movie",
    )


def test_provider_name_is_normalized() -> None:
    provider = RecordingMediaProvider(
        "  Jellyfin  ",
    )

    assert provider.name == "jellyfin"


def test_get_item_returns_seeded_item() -> None:
    item = _item()
    provider = RecordingMediaProvider(
        "jellyfin",
        items={item.item_id: item},
    )

    assert provider.get_item("movie-123") is item


def test_get_item_rejects_unknown_item() -> None:
    provider = RecordingMediaProvider(
        "jellyfin",
    )

    with pytest.raises(
        MediaProviderError,
        match="media item not found",
    ):
        provider.get_item("missing")


def test_seeded_item_provider_must_match() -> None:
    item = _item(provider="plex")

    with pytest.raises(
        MediaProviderError,
        match="provider does not match",
    ):
        RecordingMediaProvider(
            "jellyfin",
            items={item.item_id: item},
        )


def test_seeded_item_id_must_match_mapping_key() -> None:
    item = _item(item_id="movie-123")

    with pytest.raises(
        MediaProviderError,
        match="ID does not match",
    ):
        RecordingMediaProvider(
            "jellyfin",
            items={"different-id": item},
        )


def test_preview_delete_item_records_safe_result() -> None:
    provider = RecordingMediaProvider(
        "jellyfin",
        clock=lambda: FIXED_TIME,
    )

    result = provider.preview_delete_item(
        "  movie-123  ",
    )

    assert result.provider == "jellyfin"
    assert result.operation is ProviderOperation.DELETE
    assert result.item_id == "movie-123"
    assert result.success is True
    assert result.executed_at == "2026-07-20T18:30:00Z"
    assert "no media was modified" in result.message
    assert provider.requests == (result,)


def test_delete_previews_preserve_execution_order() -> None:
    provider = RecordingMediaProvider(
        "jellyfin",
        clock=lambda: FIXED_TIME,
    )

    first = provider.preview_delete_item("movie-1")
    second = provider.preview_delete_item("movie-2")

    assert provider.requests == (
        first,
        second,
    )


def test_requests_returns_immutable_snapshot() -> None:
    provider = RecordingMediaProvider(
        "jellyfin",
        clock=lambda: FIXED_TIME,
    )

    provider.preview_delete_item("movie-123")
    requests = provider.requests

    assert isinstance(requests, tuple)

    with pytest.raises(AttributeError):
        requests.append("invalid")  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "name",
    [
        "",
        "   ",
        None,
    ],
)
def test_provider_name_is_required(
    name: object,
) -> None:
    with pytest.raises(
        MediaProviderError,
        match="provider name is required",
    ):
        RecordingMediaProvider(
            name,  # type: ignore[arg-type]
        )


def test_clock_must_return_datetime() -> None:
    provider = RecordingMediaProvider(
        "jellyfin",
        clock=lambda: "invalid",  # type: ignore[return-value]
    )

    with pytest.raises(
        MediaProviderError,
        match="clock must return a datetime",
    ):
        provider.preview_delete_item("movie-123")


def test_clock_must_return_timezone_aware_datetime() -> None:
    provider = RecordingMediaProvider(
        "jellyfin",
        clock=lambda: datetime(
            2026,
            7,
            20,
            18,
            30,
        ),
    )

    with pytest.raises(
        MediaProviderError,
        match="timezone-aware datetime",
    ):
        provider.preview_delete_item("movie-123")
