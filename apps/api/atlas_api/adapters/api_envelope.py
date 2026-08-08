"""Construction helpers for Atlas FastAPI response envelopes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from atlas.api import (
    ApiError,
    ApiFailureResponse,
    ApiSuccessResponse,
)

from atlas_api.schemas.api_envelope import (
    ApiFailureEnvelopeSchema,
    ApiSuccessEnvelopeSchema,
)


def success_envelope(
    data: Mapping[str, Any] | None = None,
    *,
    generated_at: str | None = None,
) -> ApiSuccessEnvelopeSchema:
    """Create an OpenAPI-compatible successful Atlas response."""

    normalized_data: Mapping[str, Any] = (
        {}
        if data is None
        else data
    )

    if generated_at is None:
        contract = ApiSuccessResponse(
            data=normalized_data,
        )
    else:
        contract = ApiSuccessResponse(
            data=normalized_data,
            generated_at=generated_at,
        )

    return ApiSuccessEnvelopeSchema.from_contract(
        contract,
    )


def failure_envelope(
    code: str,
    message: str,
    *,
    details: Mapping[str, Any] | None = None,
    generated_at: str | None = None,
) -> ApiFailureEnvelopeSchema:
    """Create an OpenAPI-compatible failed Atlas response."""

    error = ApiError(
        code=code,
        message=message,
        details=(
            {}
            if details is None
            else details
        ),
    )

    if generated_at is None:
        contract = ApiFailureResponse(
            error=error,
        )
    else:
        contract = ApiFailureResponse(
            error=error,
            generated_at=generated_at,
        )

    return ApiFailureEnvelopeSchema.from_contract(
        contract,
    )


__all__ = [
    "failure_envelope",
    "success_envelope",
]
