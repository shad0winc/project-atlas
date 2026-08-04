"""Tests for the canonical Project Atlas API version contract."""

from __future__ import annotations

import re

from atlas import api
from atlas.api import (
    API_MEDIA_TYPE,
    API_SCHEMA_VERSION,
    API_VERSION,
)
from atlas.api.version import __all__ as version_exports


def test_api_schema_version_is_stable() -> None:
    assert API_SCHEMA_VERSION == 1
    assert isinstance(API_SCHEMA_VERSION, int)
    assert not isinstance(API_SCHEMA_VERSION, bool)


def test_api_version_is_stable() -> None:
    assert API_VERSION == "v1"
    assert re.fullmatch(
        r"v[1-9][0-9]*",
        API_VERSION,
    )


def test_api_media_type_is_stable() -> None:
    assert API_MEDIA_TYPE == (
        "application/vnd.project-atlas.v1+json"
    )


def test_api_media_type_matches_api_version() -> None:
    numeric_version = API_VERSION.removeprefix("v")

    assert API_MEDIA_TYPE == (
        "application/vnd.project-atlas."
        f"v{numeric_version}+json"
    )


def test_api_media_type_is_normalized() -> None:
    assert API_MEDIA_TYPE == API_MEDIA_TYPE.strip()
    assert API_MEDIA_TYPE == API_MEDIA_TYPE.lower()
    assert " " not in API_MEDIA_TYPE


def test_api_package_exports_version_contract() -> None:
    assert api.API_SCHEMA_VERSION is API_SCHEMA_VERSION
    assert api.API_VERSION is API_VERSION
    assert api.API_MEDIA_TYPE is API_MEDIA_TYPE


def test_api_version_module_exports_are_explicit() -> None:
    assert version_exports == [
        "API_MEDIA_TYPE",
        "API_SCHEMA_VERSION",
        "API_VERSION",
    ]


def test_api_package_exports_version_contract() -> None:
    assert api.__all__[:3] == [
        "API_MEDIA_TYPE",
        "API_SCHEMA_VERSION",
        "API_VERSION",
    ]

    assert {
        "API_MEDIA_TYPE",
        "API_SCHEMA_VERSION",
        "API_VERSION",
    }.issubset(api.__all__)
