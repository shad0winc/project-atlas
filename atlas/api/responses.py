"""Canonical response envelopes for the Project Atlas API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .errors import (
    ApiContractError,
    ApiError,
)
from .version import (
    API_SCHEMA_VERSION,
    API_VERSION,
)


@dataclass(frozen=True, slots=True)
class ApiSuccessResponse:
    """One normalized successful API response envelope."""

    data: Mapping[str, Any] = field(default_factory=dict)
    generated_at: str = field(
        default_factory=lambda: _now_timestamp(),
    )

    def __post_init__(self) -> None:
        data = _normalize_mapping(
            self.data,
            "data",
        )
        generated_at = _required_timestamp(
            self.generated_at,
            "generated_at",
        )

        object.__setattr__(
            self,
            "data",
            data,
        )
        object.__setattr__(
            self,
            "generated_at",
            generated_at,
        )

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "ApiSuccessResponse":
        """Build a successful response from serialized data."""

        _validate_envelope_header(
            payload,
            expected_success=True,
        )

        return cls(
            data=payload.get("data", {}),
            generated_at=payload.get("generated_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the stable success response contract."""

        return {
            "schema_version": API_SCHEMA_VERSION,
            "api_version": API_VERSION,
            "success": True,
            "generated_at": self.generated_at,
            "data": dict(self.data),
        }


@dataclass(frozen=True, slots=True)
class ApiFailureResponse:
    """One normalized failed API response envelope."""

    error: ApiError
    generated_at: str = field(
        default_factory=lambda: _now_timestamp(),
    )

    def __post_init__(self) -> None:
        if not isinstance(self.error, ApiError):
            raise ApiContractError(
                "error must be an ApiError",
            )

        generated_at = _required_timestamp(
            self.generated_at,
            "generated_at",
        )

        object.__setattr__(
            self,
            "generated_at",
            generated_at,
        )

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "ApiFailureResponse":
        """Build a failed response from serialized data."""

        _validate_envelope_header(
            payload,
            expected_success=False,
        )

        raw_error = payload.get("error")

        if not isinstance(raw_error, Mapping):
            raise ApiContractError(
                "error must be an object",
            )

        return cls(
            error=ApiError.from_dict(raw_error),
            generated_at=payload.get("generated_at"),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the stable failure response contract."""

        return {
            "schema_version": API_SCHEMA_VERSION,
            "api_version": API_VERSION,
            "success": False,
            "generated_at": self.generated_at,
            "error": self.error.to_dict(),
        }


def _validate_envelope_header(
    payload: object,
    *,
    expected_success: bool,
) -> None:
    if not isinstance(payload, Mapping):
        raise ApiContractError(
            "response payload must be an object",
        )

    schema_version = payload.get("schema_version")

    if schema_version != API_SCHEMA_VERSION:
        raise ApiContractError(
            "schema_version is not supported: "
            f"{schema_version!r}",
        )

    api_version = payload.get("api_version")

    if api_version != API_VERSION:
        raise ApiContractError(
            "api_version is not supported: "
            f"{api_version!r}",
        )

    success = payload.get("success")

    if not isinstance(success, bool):
        raise ApiContractError(
            "success must be boolean",
        )

    if success is not expected_success:
        expected = str(expected_success).lower()

        raise ApiContractError(
            f"success must be {expected}",
        )


def _normalize_mapping(
    value: object,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ApiContractError(
            f"{field_name} must be an object",
        )

    normalized: dict[str, Any] = {}

    for key, item in value.items():
        normalized_key = _required_text(
            key,
            f"{field_name} key",
        )

        if normalized_key in normalized:
            raise ApiContractError(
                f"{field_name} contains duplicate key: "
                f"{normalized_key}",
            )

        normalized[normalized_key] = item

    return {
        key: normalized[key]
        for key in sorted(normalized)
    }


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise ApiContractError(
            f"{field_name} must be text",
        )

    normalized = value.strip()

    if not normalized:
        raise ApiContractError(
            f"{field_name} is required",
        )

    return normalized


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(
        value,
        field_name,
    )

    candidate = (
        normalized[:-1] + "+00:00"
        if normalized.endswith("Z")
        else normalized
    )

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise ApiContractError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise ApiContractError(
            f"{field_name} must include timezone information",
        )

    utc_value = parsed.astimezone(timezone.utc)

    return (
        utc_value.isoformat()
        .replace("+00:00", "Z")
    )


def _now_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


__all__ = [
    "ApiFailureResponse",
    "ApiSuccessResponse",
]
