"""Cleanup execution identity helpers for Project Atlas."""

from __future__ import annotations

import re
from uuid import uuid4


_EXECUTION_ID_PATTERN = re.compile(
    r"^cln_[0-9a-f]{32}$"
)


def new_execution_id() -> str:
    """Generate a new opaque cleanup execution identifier."""

    return f"cln_{uuid4().hex}"


def normalize_execution_id(value: object) -> str:
    """Normalize and validate a cleanup execution identifier.

    Raises:
        ValueError: When the value is not a supported execution ID.
    """

    if not isinstance(value, str):
        raise ValueError("execution_id must be a string")

    normalized = value.strip().lower()

    if not normalized:
        raise ValueError("execution_id must not be empty")

    if _EXECUTION_ID_PATTERN.fullmatch(normalized) is None:
        raise ValueError(
            "execution_id must match cln_<32 lowercase hex characters>"
        )

    return normalized
