"""Tests for the complete public Project Atlas API foundation."""

from __future__ import annotations

from atlas import api


def test_api_package_exports_are_explicit() -> None:
    assert api.__all__ == [
        "API_MEDIA_TYPE",
        "API_SCHEMA_VERSION",
        "API_VERSION",
        "ApiContractError",
        "ApiError",
        "ApiFailureResponse",
        "ApiSerializationError",
        "ApiSuccessResponse",
        "to_api_json",
        "to_api_value",
    ]


def test_api_package_exports_are_unique() -> None:
    assert len(api.__all__) == len(
        set(api.__all__)
    )


def test_every_public_api_export_exists() -> None:
    for name in api.__all__:
        assert hasattr(api, name)
