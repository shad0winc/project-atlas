"""Tests for Atlas FastAPI envelope-construction helpers."""

from __future__ import annotations

from datetime import datetime

import pytest

from atlas.api import (
    ApiContractError,
    ApiError,
    ApiFailureResponse,
)
from atlas_api import adapters
from atlas_api.adapters.api_envelope import (
    failure_envelope,
    success_envelope,
)
from atlas_api.schemas.api_envelope import (
    ApiFailureEnvelopeSchema,
    ApiSuccessEnvelopeSchema,
)


GENERATED_AT = "2026-08-04T00:00:00Z"


def test_success_envelope_builds_schema() -> None:
    response = success_envelope(
        {
            "status": "healthy",
            "count": 2,
        },
        generated_at=GENERATED_AT,
    )

    assert isinstance(
        response,
        ApiSuccessEnvelopeSchema,
    )
    assert response.model_dump() == {
        "schema_version": 1,
        "api_version": "v1",
        "success": True,
        "generated_at": GENERATED_AT,
        "data": {
            "count": 2,
            "status": "healthy",
        },
    }


def test_success_envelope_defaults_to_empty_data() -> None:
    response = success_envelope(
        generated_at=GENERATED_AT,
    )

    assert response.data == {}


def test_success_envelope_serializes_nested_contract() -> None:
    nested_contract = ApiFailureResponse(
        error=ApiError(
            code="example_error",
            message="Example failure",
        ),
        generated_at=GENERATED_AT,
    )

    response = success_envelope(
        {
            "nested": nested_contract,
        },
        generated_at=GENERATED_AT,
    )

    nested = response.data["nested"]

    assert nested["success"] is False
    assert nested["error"]["code"] == "example_error"


def test_failure_envelope_builds_schema() -> None:
    response = failure_envelope(
        " Operations Report Not Found ",
        " Operations report was not found. ",
        details={
            "report_id": "missing-report",
        },
        generated_at=GENERATED_AT,
    )

    assert isinstance(
        response,
        ApiFailureEnvelopeSchema,
    )
    assert response.model_dump() == {
        "schema_version": 1,
        "api_version": "v1",
        "success": False,
        "generated_at": GENERATED_AT,
        "error": {
            "code": "operations_report_not_found",
            "message": "Operations report was not found.",
            "details": {
                "report_id": "missing-report",
            },
        },
    }


def test_failure_envelope_defaults_to_empty_details() -> None:
    response = failure_envelope(
        "internal_error",
        "Unexpected failure",
        generated_at=GENERATED_AT,
    )

    assert response.error.details == {}


def test_helpers_generate_utc_timestamp_by_default() -> None:
    success = success_envelope()
    failure = failure_envelope(
        "internal_error",
        "Unexpected failure",
    )

    for generated_at in (
        success.generated_at,
        failure.generated_at,
    ):
        parsed = datetime.fromisoformat(
            generated_at.replace(
                "Z",
                "+00:00",
            )
        )

        assert parsed.utcoffset() is not None
        assert parsed.utcoffset().total_seconds() == 0


def test_success_envelope_rejects_invalid_data() -> None:
    with pytest.raises(
        ApiContractError,
        match="data must be an object",
    ):
        success_envelope(
            [],  # type: ignore[arg-type]
            generated_at=GENERATED_AT,
        )


def test_failure_envelope_rejects_invalid_error() -> None:
    with pytest.raises(
        ApiContractError,
        match="code is required",
    ):
        failure_envelope(
            " ",
            "Unexpected failure",
            generated_at=GENERATED_AT,
        )


def test_adapter_package_exports_helpers() -> None:
    assert adapters.success_envelope is success_envelope
    assert adapters.failure_envelope is failure_envelope


def test_adapter_exports_are_explicit() -> None:
    assert adapters.__all__ == [
        "failure_envelope",
        "success_envelope",
    ]

    from atlas_api.adapters.api_envelope import __all__

    assert __all__ == [
        "failure_envelope",
        "success_envelope",
    ]
