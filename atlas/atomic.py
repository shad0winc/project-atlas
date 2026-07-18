"""Atomic file-writing helpers for Project Atlas."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def write_text_atomic(
    path: Path,
    content: str,
    *,
    encoding: str = "utf-8",
) -> None:
    """Write text atomically by replacing a temporary file."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = path.with_name(
        f".{path.name}.tmp"
    )

    try:
        temporary_path.write_text(
            content,
            encoding=encoding,
        )

        temporary_path.replace(path)
    finally:
        if temporary_path.exists():
            temporary_path.unlink()


def write_json_atomic(
    path: Path,
    value: Any,
) -> None:
    """Serialize JSON and write it atomically."""
    content = (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )

    write_text_atomic(
        path,
        content,
    )
