"""Canonical error contracts for the Project Atlas API."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import re
from typing import Any


_ERROR_CODE_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


class ApiContractError(ValueError):
    """Raised when an Atlas API contract contains invalid data."""


@dataclass(frozen=True, slots=True)
class ApiError:
    """One normalized transport-neutral API error."""

    code: str
    message: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        code = _required_error_code(
            self.code,
            "code",
        )
        message = _required_text(
            self.message,
            "message",
        )
        details = _normalize_details(
            self.details,
            "details",
        )

        object.__setattr__(
            self,
            "code",
            code,
        )
        object.__setattr__(
            self,
            "message",
            message,
        )
        object.__setattr__(
            self,
            "details",
            details,
        )

    @classmethod
    def from_dict(
        cls,
        payload: Mapping[str, Any],
    ) -> "ApiError":
        """Build a normalized API error from serialized data."""

        if not isinstance(payload, Mapping):
            raise ApiContractError(
                "error payload must be an object",
            )

        return cls(
            code=payload.get("code"),
            message=payload.get("message"),
            details=payload.get("details", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the stable API error contract."""

        return {
            "code": self.code,
            "message": self.message,
            "details": dict(self.details),
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


def _required_error_code(
    value: object,
    field_name: str,
) -> str:
    normalized = (
        _required_text(
            value,
            field_name,
        )
        .lower()
        .replace(" ", "_")
        .replace("-", "_")
    )

    if not _ERROR_CODE_PATTERN.fullmatch(normalized):
        raise ApiContractError(
            f"{field_name} contains unsupported characters",
        )

    return normalized


def _normalize_details(
    value: object,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ApiContractError(
            f"{field_name} must be an object",
        )

    normalized: dict[str, Any] = {}

    for key, detail_value in value.items():
        normalized_key = _required_text(
            key,
            f"{field_name} key",
        )

        if normalized_key in normalized:
            raise ApiContractError(
                f"{field_name} contains duplicate key: "
                f"{normalized_key}",
            )

        normalized[normalized_key] = detail_value

    return {
        key: normalized[key]
        for key in sorted(normalized)
    }


__all__ = [
    "ApiContractError",
    "ApiError",
]
