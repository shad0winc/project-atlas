"""Tests for canonical Project Atlas API response envelopes."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime

import pytest

from atlas import api
from atlas.api import (
    API_SCHEMA_VERSION,
    API_VERSION,
    ApiContractError,
    ApiError,
    ApiFailureResponse,
    ApiSuccessResponse,
)
from atlas.api.responses import __all__ as response_exports


GENERATED_AT = "2026-08-04T00:00:00Z"


def test_success_response_normalizes_data() -> None:
    response = ApiSuccessResponse(
        data={
            "zeta": 2,
            "alpha": 1,
        },
        generated_at=(
            "2026-08-03T20:00:00-04:00"
        ),
    )

    assert response.data == {
        "alpha": 1,
        "zeta": 2,
    }
    assert response.generated_at == GENERATED_AT


def test_success_response_serialization_is_stable() -> None:
    response = ApiSuccessResponse(
        data={
            "report_id": "latest",
        },
        generated_at=GENERATED_AT,
    )

    assert response.to_dict() == {
        "schema_version": 1,
        "api_version": "v1",
        "success": True,
        "generated_at": GENERATED_AT,
        "data": {
            "report_id": "latest",
        },
    }


def test_success_response_round_trip() -> None:
    original = ApiSuccessResponse(
        data={
            "count": 2,
        },
        generated_at=GENERATED_AT,
    )

    restored = ApiSuccessResponse.from_dict(
        original.to_dict(),
    )

    assert restored == original
    assert restored is not original


def test_success_response_copies_data_mapping() -> None:
    data = {
        "count": 1,
    }

    response = ApiSuccessResponse(
        data=data,
        generated_at=GENERATED_AT,
    )

    data["count"] = 2

    assert response.data == {
        "count": 1,
    }


def test_success_response_is_immutable() -> None:
    response = ApiSuccessResponse(
        generated_at=GENERATED_AT,
    )

    with pytest.raises(FrozenInstanceError):
        response.generated_at = GENERATED_AT  # type: ignore[misc]


def test_failure_response_serialization_is_stable() -> None:
    response = ApiFailureResponse(
        error=ApiError(
            code="not_found",
            message="Resource not found",
            details={
                "resource": "operations_report",
            },
        ),
        generated_at=GENERATED_AT,
    )

    assert response.to_dict() == {
        "schema_version": 1,
        "api_version": "v1",
        "success": False,
        "generated_at": GENERATED_AT,
        "error": {
            "code": "not_found",
            "message": "Resource not found",
            "details": {
                "resource": "operations_report",
            },
        },
    }


def test_failure_response_round_trip() -> None:
    original = ApiFailureResponse(
        error=ApiError(
            code="internal_error",
            message="Unexpected failure",
        ),
        generated_at=GENERATED_AT,
    )

    restored = ApiFailureResponse.from_dict(
        original.to_dict(),
    )

    assert restored == original
    assert restored is not original
    assert restored.error is not original.error


def test_failure_response_requires_api_error() -> None:
    with pytest.raises(
        ApiContractError,
        match="error must be an ApiError",
    ):
        ApiFailureResponse(
            error={},  # type: ignore[arg-type]
            generated_at=GENERATED_AT,
        )


@pytest.mark.parametrize(
    "factory",
    (
        ApiSuccessResponse.from_dict,
        ApiFailureResponse.from_dict,
    ),
)
def test_response_from_dict_requires_mapping(
    factory,
) -> None:
    with pytest.raises(
        ApiContractError,
        match="response payload must be an object",
    ):
        factory([])


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    (
        (
            "schema_version",
            2,
            "schema_version is not supported",
        ),
        (
            "api_version",
            "v2",
            "api_version is not supported",
        ),
        (
            "success",
            "true",
            "success must be boolean",
        ),
    ),
)
def test_success_response_rejects_invalid_header(
    field_name: str,
    value: object,
    message: str,
) -> None:
    payload = ApiSuccessResponse(
        generated_at=GENERATED_AT,
    ).to_dict()
    payload[field_name] = value

    with pytest.raises(
        ApiContractError,
        match=message,
    ):
        ApiSuccessResponse.from_dict(payload)


def test_success_response_rejects_false_success_flag() -> None:
    payload = ApiSuccessResponse(
        generated_at=GENERATED_AT,
    ).to_dict()
    payload["success"] = False

    with pytest.raises(
        ApiContractError,
        match="success must be true",
    ):
        ApiSuccessResponse.from_dict(payload)


def test_failure_response_rejects_true_success_flag() -> None:
    payload = ApiFailureResponse(
        error=ApiError(
            code="internal_error",
            message="Unexpected failure",
        ),
        generated_at=GENERATED_AT,
    ).to_dict()
    payload["success"] = True

    with pytest.raises(
        ApiContractError,
        match="success must be false",
    ):
        ApiFailureResponse.from_dict(payload)


def test_success_response_rejects_non_mapping_data() -> None:
    with pytest.raises(
        ApiContractError,
        match="data must be an object",
    ):
        ApiSuccessResponse(
            data=[],  # type: ignore[arg-type]
            generated_at=GENERATED_AT,
        )


def test_failure_from_dict_requires_error_object() -> None:
    payload = {
        "schema_version": API_SCHEMA_VERSION,
        "api_version": API_VERSION,
        "success": False,
        "generated_at": GENERATED_AT,
        "error": [],
    }

    with pytest.raises(
        ApiContractError,
        match="error must be an object",
    ):
        ApiFailureResponse.from_dict(payload)


@pytest.mark.parametrize(
    "timestamp",
    (
        "",
        "not-a-timestamp",
        "2026-08-04T00:00:00",
    ),
)
def test_response_rejects_invalid_timestamp(
    timestamp: str,
) -> None:
    with pytest.raises(ApiContractError):
        ApiSuccessResponse(
            generated_at=timestamp,
        )


def test_default_timestamp_is_utc() -> None:
    response = ApiSuccessResponse()

    parsed = datetime.fromisoformat(
        response.generated_at.replace(
            "Z",
            "+00:00",
        )
    )

    assert parsed.utcoffset() is not None
    assert parsed.utcoffset().total_seconds() == 0


def test_api_package_exports_response_contracts() -> None:
    assert api.ApiSuccessResponse is ApiSuccessResponse
    assert api.ApiFailureResponse is ApiFailureResponse


def test_response_module_exports_are_explicit() -> None:
    assert response_exports == [
        "ApiFailureResponse",
        "ApiSuccessResponse",
    ]
