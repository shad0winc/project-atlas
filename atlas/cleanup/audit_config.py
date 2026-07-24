"""Cleanup audit configuration for Project Atlas."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path


DEFAULT_ATLAS_STATE_DIR = Path(
    "/mnt/storage/configs/atlas"
)
DEFAULT_CLEANUP_AUDIT_RELATIVE_PATH = Path(
    "cleanup/audit.jsonl"
)


def default_cleanup_audit_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    """Resolve the configured cleanup audit-log path.

    Resolution order:

    1. ATLAS_CLEANUP_AUDIT_PATH
    2. ATLAS_STATE_DIR/cleanup/audit.jsonl
    3. /mnt/storage/configs/atlas/cleanup/audit.jsonl
    """

    environ = (
        environment
        if environment is not None
        else os.environ
    )

    explicit_path = environ.get(
        "ATLAS_CLEANUP_AUDIT_PATH",
        "",
    ).strip()

    if explicit_path:
        return Path(explicit_path)

    state_directory = environ.get(
        "ATLAS_STATE_DIR",
        "",
    ).strip()

    state_root = (
        Path(state_directory)
        if state_directory
        else DEFAULT_ATLAS_STATE_DIR
    )

    return (
        state_root
        / DEFAULT_CLEANUP_AUDIT_RELATIVE_PATH
    )
