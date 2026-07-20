"""Shared JSON state helpers for Project Atlas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from atlas.atomic import write_json_atomic


def load_json(
    path: Path,
    *,
    default: Any = None,
) -> Any:
    """Load JSON state, returning the default when unavailable."""
    if not path.exists():
        return default

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8",
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return default


def load_json_object(
    path: Path,
) -> dict[str, Any]:
    """Load a JSON object or return an empty dictionary."""
    value = load_json(
        path,
        default={},
    )

    if not isinstance(value, dict):
        return {}

    return value


def save_json(
    path: Path,
    value: Any,
) -> None:
    """Persist JSON state atomically."""
    write_json_atomic(
        path,
        value,
    )
