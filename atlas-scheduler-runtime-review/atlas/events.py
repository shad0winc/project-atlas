"""Event publishing helpers for Project Atlas modules."""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Mapping
from typing import Any

DEFAULT_ATLAS_BINARY = "/bin/atlas"


def publish_event(
    module: str,
    event_name: str,
    payload: Mapping[str, Any] | None = None,
    *,
    atlas_binary: str | None = None,
) -> None:
    """Publish a declared module event through the Atlas CLI.

    The Atlas CLI remains the authority for module validation, event
    declaration checks, durable storage, and subscriber delivery.
    """
    normalized_module = module.strip()
    normalized_event = event_name.strip()

    if not normalized_module:
        raise ValueError("module cannot be empty")

    if not normalized_event:
        raise ValueError("event_name cannot be empty")

    serialized_payload = json.dumps(
        dict(payload or {}),
        separators=(",", ":"),
    )

    command = [
        atlas_binary
        or os.getenv("ATLAS_BINARY", DEFAULT_ATLAS_BINARY),
        "module",
        "publish",
        normalized_module,
        normalized_event,
        serialized_payload,
    ]

    subprocess.run(
        command,
        check=True,
    )
