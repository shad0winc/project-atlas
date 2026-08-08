"""Canonical version contracts for the Project Atlas API."""

from __future__ import annotations

from typing import Final


API_SCHEMA_VERSION: Final[int] = 1
API_VERSION: Final[str] = "v1"
API_MEDIA_TYPE: Final[str] = (
    "application/vnd.project-atlas.v1+json"
)


__all__ = [
    "API_MEDIA_TYPE",
    "API_SCHEMA_VERSION",
    "API_VERSION",
]
