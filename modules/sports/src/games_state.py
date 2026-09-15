#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


STATE_FILE = Path(
    os.getenv(
        "SPORTS_STATE_FILE",
        "/mnt/storage/configs/sportyfin/state/games.json",
    )
)


def load_games() -> dict[str, dict[str, Any]]:
    if not STATE_FILE.exists():
        return {}

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
    except (json.JSONDecodeError, OSError):
        return {}

    if not isinstance(data, dict):
        return {}

    return data
