"""Deterministic serialization helpers for Project Atlas API contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from typing import Any

from .errors import ApiContractError


class ApiSerializationError(ApiContractError):
    """Raised when a value cannot be serialized safely for the API."""


def to_api_value(
    value: object,
) -> Any:
    """Convert one value into a deterministic JSON-compatible value."""

    if value is None or isinstance(
        value,
        (
            bool,
            int,
            float,
            str,
        ),
    ):
        return value

    if isinstance(value, datetime):
        return _serialize_datetime(value)

    if isinstance(value, Enum):
        return to_api_value(value.value)

    to_dict = getattr(
        value,
        "to_dict",
        None,
    )

    if callable(to_dict):
        try:
            serialized = to_dict()
        except Exception as exc:
            raise ApiSerializationError(
                "to_dict() serialization failed",
            ) from exc

        return to_api_value(serialized)

    if isinstance(value, Mapping):
        return _serialize_mapping(value)

    if isinstance(value, (list, tuple)):
        return [
            to_api_value(item)
            for item in value
        ]

    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: to_api_value(
                getattr(value, field.name),
            )
            for field in fields(value)
        }

    raise ApiSerializationError(
        "value is not API serializable: "
        f"{value.__class__.__name__}",
    )


def to_api_json(
    value: object,
    *,
    indent: int | None = 2,
) -> str:
    """Render one value as deterministic API JSON."""

    if (
        indent is not None
        and (
            isinstance(indent, bool)
            or not isinstance(indent, int)
            or indent < 0
        )
    ):
        raise ApiSerializationError(
            "indent must be a non-negative integer or null",
        )

    return json.dumps(
        to_api_value(value),
        indent=indent,
        sort_keys=True,
        ensure_ascii=False,
        separators=(
            (",", ":")
            if indent is None
            else None
        ),
    )


def _serialize_mapping(
    value: Mapping[object, object],
) -> dict[str, Any]:
    normalized: dict[str, Any] = {}

    for key, item in value.items():
        if not isinstance(key, str):
            raise ApiSerializationError(
                "mapping keys must be text",
            )

        if key in normalized:
            raise ApiSerializationError(
                f"mapping contains duplicate key: {key}",
            )

        normalized[key] = to_api_value(item)

    return {
        key: normalized[key]
        for key in sorted(normalized)
    }


def _serialize_datetime(
    value: datetime,
) -> str:
    if value.tzinfo is None:
        raise ApiSerializationError(
            "datetime values must include timezone information",
        )

    return (
        value.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


__all__ = [
    "ApiSerializationError",
    "to_api_json",
    "to_api_value",
]
