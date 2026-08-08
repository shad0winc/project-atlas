"""Tests for the canonical Project Atlas API error contract."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas import api
from atlas.api import (
    ApiContractError,
    ApiError,
)
from atlas.api.errors import __all__ as error_exports


def test_api_error_normalizes_inputs() -> None:
    error = ApiError(
        code=" Validation Failed ",
        message="  Request payload is invalid.  ",
        details={
            "zeta": 2,
            "alpha": 1,
        },
    )

    assert error.code == "validation_failed"
    assert error.message == "Request payload is invalid."
    assert error.details == {
        "alpha": 1,
        "zeta": 2,
    }


def test_api_error_is_immutable() -> None:
    error = ApiError(
        code="not_found",
        message="Resource not found",
    )

    with pytest.raises(FrozenInstanceError):
        error.code = "changed"  # type: ignore[misc]


def test_api_error_serialization_is_stable() -> None:
    error = ApiError(
        code="not_found",
        message="Resource not found",
        details={
            "resource": "operations_report",
        },
    )

    assert error.to_dict() == {
        "code": "not_found",
        "message": "Resource not found",
        "details": {
            "resource": "operations_report",
        },
    }


def test_api_error_round_trip() -> None:
    original = ApiError(
        code="conflict",
        message="Resource already exists",
        details={
            "identifier": "example",
        },
    )

    restored = ApiError.from_dict(
        original.to_dict(),
    )

    assert restored == original
    assert restored is not original


def test_api_error_from_dict_requires_mapping() -> None:
    with pytest.raises(
        ApiContractError,
        match="error payload must be an object",
    ):
        ApiError.from_dict(
            [],  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    (
        (
            "code",
            "",
            "code is required",
        ),
        (
            "code",
            1,
            "code must be text",
        ),
        (
            "message",
            "   ",
            "message is required",
        ),
        (
            "message",
            None,
            "message must be text",
        ),
    ),
)
def test_api_error_rejects_invalid_required_fields(
    field_name: str,
    value: object,
    message: str,
) -> None:
    values = {
        "code": "invalid_request",
        "message": "Invalid request",
    }
    values[field_name] = value

    with pytest.raises(
        ApiContractError,
        match=message,
    ):
        ApiError(**values)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "code",
    (
        "bad/code",
        "bad:code",
        ".invalid",
        "invalid.",
        "bad@code",
    ),
)
def test_api_error_rejects_invalid_codes(
    code: str,
) -> None:
    with pytest.raises(
        ApiContractError,
        match="code contains unsupported characters",
    ):
        ApiError(
            code=code,
            message="Invalid request",
        )


def test_api_error_rejects_non_mapping_details() -> None:
    with pytest.raises(
        ApiContractError,
        match="details must be an object",
    ):
        ApiError(
            code="invalid_request",
            message="Invalid request",
            details=[],  # type: ignore[arg-type]
        )


def test_api_error_rejects_empty_detail_key() -> None:
    with pytest.raises(
        ApiContractError,
        match="details key is required",
    ):
        ApiError(
            code="invalid_request",
            message="Invalid request",
            details={
                "   ": "value",
            },
        )


def test_api_error_copies_detail_mapping() -> None:
    details = {
        "resource": "operations",
    }

    error = ApiError(
        code="not_found",
        message="Resource not found",
        details=details,
    )

    details["resource"] = "changed"

    assert error.details == {
        "resource": "operations",
    }


def test_api_package_exports_error_contract() -> None:
    assert api.ApiContractError is ApiContractError
    assert api.ApiError is ApiError


def test_api_error_module_exports_are_explicit() -> None:
    assert error_exports == [
        "ApiContractError",
        "ApiError",
    ]


def test_api_package_exports_error_contract() -> None:
    assert {
        "ApiContractError",
        "ApiError",
    }.issubset(api.__all__)
