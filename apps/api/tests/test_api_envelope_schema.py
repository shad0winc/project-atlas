"""Tests for FastAPI adapters over shared Atlas API envelopes."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from atlas.api import (
    ApiError,
    ApiFailureResponse,
    ApiSuccessResponse,
)
from atlas_api import schemas
from atlas_api.schemas.api_envelope import (
    ApiErrorSchema,
    ApiFailureEnvelopeSchema,
    ApiSuccessEnvelopeSchema,
)


GENERATED_AT = "2026-08-04T00:00:00Z"


def test_success_envelope_adapts_shared_contract() -> None:
    contract = ApiSuccessResponse(
        data={
            "status": "healthy",
            "count": 2,
        },
        generated_at=GENERATED_AT,
    )

    response = ApiSuccessEnvelopeSchema.from_contract(
        contract,
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


def test_success_envelope_serializes_domain_contract() -> None:
    error = ApiError(
        code="example",
        message="Example error",
    )

    contract = ApiSuccessResponse(
        data={
            "nested": error,
        },
        generated_at=GENERATED_AT,
    )

    response = ApiSuccessEnvelopeSchema.from_contract(
        contract,
    )

    assert response.data["nested"] == {
        "code": "example",
        "message": "Example error",
        "details": {},
    }


def test_failure_envelope_adapts_shared_contract() -> None:
    contract = ApiFailureResponse(
        error=ApiError(
            code="operations_report_not_found",
            message="Operations report was not found",
            details={
                "report_id": "missing-report",
            },
        ),
        generated_at=GENERATED_AT,
    )

    response = ApiFailureEnvelopeSchema.from_contract(
        contract,
    )

    assert response.model_dump() == {
        "schema_version": 1,
        "api_version": "v1",
        "success": False,
        "generated_at": GENERATED_AT,
        "error": {
            "code": "operations_report_not_found",
            "message": "Operations report was not found",
            "details": {
                "report_id": "missing-report",
            },
        },
    }


def test_success_adapter_requires_success_contract() -> None:
    with pytest.raises(
        TypeError,
        match="response must be an ApiSuccessResponse",
    ):
        ApiSuccessEnvelopeSchema.from_contract(
            object(),  # type: ignore[arg-type]
        )


def test_failure_adapter_requires_failure_contract() -> None:
    with pytest.raises(
        TypeError,
        match="response must be an ApiFailureResponse",
    ):
        ApiFailureEnvelopeSchema.from_contract(
            object(),  # type: ignore[arg-type]
        )


def test_success_schema_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ApiSuccessEnvelopeSchema.model_validate(
            {
                "schema_version": 1,
                "api_version": "v1",
                "success": True,
                "generated_at": GENERATED_AT,
                "data": {},
                "unexpected": True,
            }
        )


def test_failure_schema_requires_false_success() -> None:
    with pytest.raises(ValidationError):
        ApiFailureEnvelopeSchema.model_validate(
            {
                "schema_version": 1,
                "api_version": "v1",
                "success": True,
                "generated_at": GENERATED_AT,
                "error": {
                    "code": "internal_error",
                    "message": "Unexpected failure",
                    "details": {},
                },
            }
        )


def test_envelope_schemas_are_frozen() -> None:
    response = ApiSuccessEnvelopeSchema.from_contract(
        ApiSuccessResponse(
            generated_at=GENERATED_AT,
        )
    )

    with pytest.raises(ValidationError):
        response.success = False  # type: ignore[misc]


def test_schema_package_exports_envelopes() -> None:
    assert schemas.ApiErrorSchema is ApiErrorSchema
    assert (
        schemas.ApiFailureEnvelopeSchema
        is ApiFailureEnvelopeSchema
    )
    assert (
        schemas.ApiSuccessEnvelopeSchema
        is ApiSuccessEnvelopeSchema
    )


def test_envelope_module_exports_are_explicit() -> None:
    from atlas_api.schemas.api_envelope import __all__

    assert __all__ == [
        "ApiErrorSchema",
        "ApiFailureEnvelopeSchema",
        "ApiSuccessEnvelopeSchema",
    ]
