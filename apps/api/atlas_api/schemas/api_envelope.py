"""FastAPI adapters for transport-neutral Atlas API envelopes."""

from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict

from atlas.api import (
    API_SCHEMA_VERSION,
    API_VERSION,
    ApiFailureResponse,
    ApiSuccessResponse,
    to_api_value,
)


class ApiErrorSchema(BaseModel):
    """Stable OpenAPI representation of one Atlas API error."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    code: str
    message: str
    details: dict[str, Any]


class ApiSuccessEnvelopeSchema(BaseModel):
    """OpenAPI-compatible successful Atlas API envelope."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal[1]
    api_version: Literal["v1"]
    success: Literal[True]
    generated_at: str
    data: dict[str, Any]

    @classmethod
    def from_contract(
        cls,
        response: ApiSuccessResponse,
    ) -> Self:
        """Adapt a validated transport-neutral success contract."""

        if not isinstance(response, ApiSuccessResponse):
            raise TypeError(
                "response must be an ApiSuccessResponse",
            )

        payload = to_api_value(response)

        if not isinstance(payload, dict):
            raise TypeError(
                "serialized success response must be an object",
            )

        return cls.model_validate(payload)


class ApiFailureEnvelopeSchema(BaseModel):
    """OpenAPI-compatible failed Atlas API envelope."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
    )

    schema_version: Literal[1]
    api_version: Literal["v1"]
    success: Literal[False]
    generated_at: str
    error: ApiErrorSchema

    @classmethod
    def from_contract(
        cls,
        response: ApiFailureResponse,
    ) -> Self:
        """Adapt a validated transport-neutral failure contract."""

        if not isinstance(response, ApiFailureResponse):
            raise TypeError(
                "response must be an ApiFailureResponse",
            )

        payload = to_api_value(response)

        if not isinstance(payload, dict):
            raise TypeError(
                "serialized failure response must be an object",
            )

        return cls.model_validate(payload)


assert API_SCHEMA_VERSION == 1
assert API_VERSION == "v1"


__all__ = [
    "ApiErrorSchema",
    "ApiFailureEnvelopeSchema",
    "ApiSuccessEnvelopeSchema",
]
