#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import subprocess
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from feed import generate_feed

from lifecycle import (
    lifecycle_state,
    should_publish_finished,
    should_publish_started,
)

STATE_DIR = Path(
    os.getenv(
        "SPORTS_STATE_DIR",
        "/mnt/storage/configs/sportyfin/state",
    )
)

STATE_FILE = STATE_DIR / "games.json"

POSTGAME_GRACE_MINUTES = int(
    os.getenv(
        "SPORTS_POSTGAME_GRACE_MINUTES",
        "15",
    )
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    return value.isoformat()


def load_state() -> dict[str, dict[str, Any]]:
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


def save_state(
    games: dict[str, dict[str, Any]],
) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    temporary_file = STATE_FILE.with_suffix(".json.tmp")

    temporary_file.write_text(
        json.dumps(
            games,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_file.replace(STATE_FILE)


def publish_event(
    event_name: str,
    payload: dict[str, Any],
) -> None:
    command = [
        "/bin/atlas",
        "module",
        "publish",
        "sports",
        event_name,
        json.dumps(
            payload,
            separators=(",", ":"),
        ),
    ]

    subprocess.run(
        command,
        check=True,
    )


def normalize_game(
    game: dict[str, Any],
) -> dict[str, Any]:
    normalized = deepcopy(game)

    game_id = str(
        normalized.get("id", "")
    ).strip()

    if not game_id:
        raise ValueError("Game ID is required")

    normalized["id"] = game_id

    normalized["status"] = str(
        normalized.get("status", "scheduled")
    ).lower()

    return normalized


def process_games(
    provider_games: list[dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, dict[str, Any]]:
    if now is None:
        now = utc_now()

    previous_games = load_state()
    next_games: dict[str, dict[str, Any]] = {}

    for raw_game in provider_games:
        game = normalize_game(raw_game)
        game_id = game["id"]

        previous = previous_games.get(
            game_id,
            {},
        )

        previous_state = str(
            previous.get(
                "lifecycle_state",
                "scheduled",
            )
        )

        if (
            game["status"]
            in {"final", "finished", "ended"}
            and not game.get("final_at")
        ):
            game["final_at"] = (
                previous.get("final_at")
                or format_timestamp(now)
            )

        current_state = lifecycle_state(
            game,
            now,
            POSTGAME_GRACE_MINUTES,
        )

        game["lifecycle_state"] = current_state
        game["updated_at"] = format_timestamp(now)

        if should_publish_started(
            previous_state,
            current_state,
        ):
            publish_event(
                "sports.game-started",
                {
                    "game_id": game_id,
                    "game": game.get(
                        "name",
                        game_id,
                    ),
                    "status": "started",
                },
            )

        if should_publish_finished(
            previous_state,
            current_state,
        ):
            publish_event(
                "sports.game-finished",
                {
                    "game_id": game_id,
                    "game": game.get(
                        "name",
                        game_id,
                    ),
                    "status": "finished",
                },
            )

        next_games[game_id] = game

    for game_id, previous in previous_games.items():
        if game_id in next_games:
            continue

        previous_state = str(
            previous.get(
                "lifecycle_state",
                "scheduled",
            )
        )

        if previous_state == "finished":
            continue

        preserved = deepcopy(previous)
        preserved["updated_at"] = format_timestamp(now)

        next_games[game_id] = preserved

    save_state(next_games)

    feed_result = generate_feed()

    if feed_result != 0:
        raise RuntimeError(
            "Sports feed generation failed"
        )

    return next_games


def read_provider_games() -> list[dict[str, Any]]:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid provider JSON: {exc}"
        ) from exc

    if not isinstance(data, list):
        raise ValueError(
            "Provider input must be a JSON array"
        )

    return data


def main() -> int:
    try:
        provider_games = read_provider_games()
        process_games(provider_games)
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as exc:
        print(
            f"Sports controller failed: {exc}",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
