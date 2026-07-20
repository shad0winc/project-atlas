"""Tests for provider-neutral media mutation contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from enum import Enum

import pytest

from atlas.media import (
    ProviderMutationError,
    ProviderMutationResult,
    ProviderOperation,
)


def _result(
    **overrides: object,
) -> ProviderMutationResult:
    values: dict[str, object] = {
        "provider": "jellyfin",
        "operation": ProviderOperation.DELETE,
        "item_id": "movie-123",
        "success": True,
        "message": "Deletion recorded",
        "executed_at": "2026-07-20T18:30:00Z",
    }
    values.update(overrides)

    return ProviderMutationResult(**values)  # type: ignore[arg-type]


def test_provider_operation_is_string_enum() -> None:
    assert issubclass(ProviderOperation, str)
    assert issubclass(ProviderOperation, Enum)
    assert ProviderOperation.DELETE.value == "delete"


def test_mutation_result_normalizes_values() -> None:
    result = _result(
        provider="  Jellyfin  ",
        operation="delete",
        item_id="  movie-123  ",
        message="  Deletion recorded  ",
        executed_at="2026-07-20T14:30:00-04:00",
    )

    assert result.provider == "jellyfin"
    assert result.operation is ProviderOperation.DELETE
    assert result.item_id == "movie-123"
    assert result.message == "Deletion recorded"
    assert result.executed_at == "2026-07-20T18:30:00Z"


def test_mutation_result_serializes_to_dict() -> None:
    result = _result()

    assert result.to_dict() == {
        "provider": "jellyfin",
        "operation": "delete",
        "item_id": "movie-123",
        "success": True,
        "message": "Deletion recorded",
        "executed_at": "2026-07-20T18:30:00Z",
    }


def test_mutation_result_is_immutable() -> None:
    result = _result()

    with pytest.raises(FrozenInstanceError):
        result.provider = "plex"  # type: ignore[misc]


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("provider", ""),
        ("provider", "   "),
        ("provider", None),
        ("item_id", ""),
        ("item_id", "   "),
        ("item_id", None),
        ("message", ""),
        ("message", "   "),
        ("message", None),
    ],
)
def test_required_text_fields_reject_invalid_values(
    field_name: str,
    value: object,
) -> None:
    with pytest.raises(
        ProviderMutationError,
        match=rf"{field_name} is required",
    ):
        _result(**{field_name: value})


@pytest.mark.parametrize(
    "operation",
    [
        "",
        "archive",
        None,
        42,
    ],
)
def test_invalid_operation_is_rejected(
    operation: object,
) -> None:
    with pytest.raises(
        ProviderMutationError,
        match="invalid provider operation",
    ):
        _result(operation=operation)


@pytest.mark.parametrize(
    "success",
    [
        1,
        0,
        "true",
        None,
    ],
)
def test_success_requires_boolean(
    success: object,
) -> None:
    with pytest.raises(
        ProviderMutationError,
        match="success must be a boolean",
    ):
        _result(success=success)


@pytest.mark.parametrize(
    "executed_at",
    [
        "",
        "not-a-timestamp",
        "2026-07-20T18:30:00",
        None,
    ],
)
def test_invalid_timestamp_is_rejected(
    executed_at: object,
) -> None:
    with pytest.raises(
        ProviderMutationError,
        match="executed_at",
    ):
        _result(executed_at=executed_at)


def test_media_provider_exposes_safe_delete_preview() -> None:
    from atlas.media import MediaProvider

    assert hasattr(
        MediaProvider,
        "preview_delete_item",
    )
    assert not hasattr(
        MediaProvider,
        "delete_item",
    )
