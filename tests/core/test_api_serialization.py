"""Tests for shared Project Atlas API serialization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
import json

import pytest

from atlas import api
from atlas.api import (
    ApiError,
    ApiSerializationError,
    ApiSuccessResponse,
    to_api_json,
    to_api_value,
)
from atlas.api.serialization import __all__ as serialization_exports


class ExampleState(str, Enum):
    READY = "ready"


@dataclass(frozen=True)
class ExampleDataclass:
    name: str
    count: int


class ExampleAtlasContract:
    def to_dict(self) -> dict[str, object]:
        return {
            "state": ExampleState.READY,
            "items": (
                2,
                1,
            ),
        }


def test_serializer_preserves_json_primitives() -> None:
    assert to_api_value(None) is None
    assert to_api_value(True) is True
    assert to_api_value(7) == 7
    assert to_api_value(1.5) == 1.5
    assert to_api_value("atlas") == "atlas"


def test_serializer_orders_nested_mappings() -> None:
    assert to_api_value(
        {
            "zeta": {
                "beta": 2,
                "alpha": 1,
            },
            "alpha": 0,
        }
    ) == {
        "alpha": 0,
        "zeta": {
            "alpha": 1,
            "beta": 2,
        },
    }


def test_serializer_converts_sequences_to_lists() -> None:
    assert to_api_value(
        (
            "one",
            [
                "two",
                "three",
            ],
        )
    ) == [
        "one",
        [
            "two",
            "three",
        ],
    ]


def test_serializer_converts_enums() -> None:
    assert to_api_value(ExampleState.READY) == "ready"


def test_serializer_normalizes_datetime_to_utc() -> None:
    value = datetime.fromisoformat(
        "2026-08-03T20:00:00-04:00"
    )

    assert to_api_value(value) == (
        "2026-08-04T00:00:00Z"
    )


def test_serializer_rejects_naive_datetime() -> None:
    with pytest.raises(
        ApiSerializationError,
        match="must include timezone information",
    ):
        to_api_value(
            datetime(2026, 8, 4),
        )


def test_serializer_prefers_to_dict_contract() -> None:
    assert to_api_value(
        ExampleAtlasContract(),
    ) == {
        "items": [
            2,
            1,
        ],
        "state": "ready",
    }


def test_serializer_supports_plain_dataclass() -> None:
    assert to_api_value(
        ExampleDataclass(
            name="atlas",
            count=2,
        )
    ) == {
        "name": "atlas",
        "count": 2,
    }


def test_serializer_handles_api_envelope() -> None:
    response = ApiSuccessResponse(
        data={
            "error": ApiError(
                code="example",
                message="Example",
            ).to_dict(),
        },
        generated_at="2026-08-04T00:00:00Z",
    )

    payload = to_api_value(response)

    assert payload["schema_version"] == 1
    assert payload["success"] is True
    assert payload["data"]["error"]["code"] == "example"


def test_serializer_rejects_non_text_mapping_key() -> None:
    with pytest.raises(
        ApiSerializationError,
        match="mapping keys must be text",
    ):
        to_api_value(
            {
                1: "invalid",
            }
        )


@pytest.mark.parametrize(
    "value",
    (
        {1, 2},
        b"atlas",
        object(),
    ),
)
def test_serializer_rejects_unsupported_values(
    value: object,
) -> None:
    with pytest.raises(
        ApiSerializationError,
        match="value is not API serializable",
    ):
        to_api_value(value)


def test_serializer_wraps_to_dict_failure() -> None:
    class BrokenContract:
        def to_dict(self) -> dict[str, object]:
            raise RuntimeError("failed")

    with pytest.raises(
        ApiSerializationError,
        match=r"to_dict\(\) serialization failed",
    ):
        to_api_value(
            BrokenContract(),
        )


def test_api_json_is_deterministic() -> None:
    rendered = to_api_json(
        {
            "zeta": 2,
            "alpha": 1,
        },
        indent=None,
    )

    assert rendered == (
        '{"alpha":1,"zeta":2}'
    )
    assert json.loads(rendered) == {
        "alpha": 1,
        "zeta": 2,
    }


def test_api_json_supports_unicode() -> None:
    rendered = to_api_json(
        {
            "message": "Café",
        },
        indent=None,
    )

    assert "Café" in rendered


@pytest.mark.parametrize(
    "indent",
    (
        True,
        -1,
        1.5,
        "2",
    ),
)
def test_api_json_rejects_invalid_indent(
    indent: object,
) -> None:
    with pytest.raises(
        ApiSerializationError,
        match="indent must be a non-negative integer or null",
    ):
        to_api_json(
            {},
            indent=indent,  # type: ignore[arg-type]
        )


def test_api_package_exports_serializer() -> None:
    assert api.ApiSerializationError is ApiSerializationError
    assert api.to_api_json is to_api_json
    assert api.to_api_value is to_api_value


def test_serialization_module_exports_are_explicit() -> None:
    assert serialization_exports == [
        "ApiSerializationError",
        "to_api_json",
        "to_api_value",
    ]


def test_utc_datetime_serialization_is_stable() -> None:
    value = datetime(
        2026,
        8,
        4,
        tzinfo=timezone.utc,
    )

    assert to_api_value(value) == (
        "2026-08-04T00:00:00Z"
    )
