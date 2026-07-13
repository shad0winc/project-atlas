#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sys
import time
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from controller import load_state, process_games
from providers.registry import enabled_providers


CONTROLLER_INTERVAL_SECONDS = int(
    os.getenv(
        "SPORTS_CONTROLLER_INTERVAL_SECONDS",
        "30",
    )
)

HEARTBEAT_FILE = Path(
    os.getenv(
        "SPORTS_CONTROLLER_HEARTBEAT_FILE",
        "/mnt/storage/configs/sportyfin/state/controller-heartbeat",
    )
)

PROVIDER_HEALTH_FILE = Path(
    os.getenv(
        "SPORTS_PROVIDER_HEALTH_FILE",
        "/mnt/storage/configs/sportyfin/state/provider-health.json",
    )
)


def utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def tracked_event_ids(
    games: dict[str, dict[str, Any]],
    provider_name: str,
) -> list[str]:
    event_ids: list[str] = []

    for game in games.values():
        if game.get("provider") != provider_name:
            continue

        lifecycle_state = str(
            game.get(
                "lifecycle_state",
                "scheduled",
            )
        )

        if lifecycle_state == "finished":
            continue

        provider_event_id = str(
            game.get(
                "provider_event_id",
                "",
            )
        ).strip()

        if provider_event_id:
            event_ids.append(provider_event_id)

    return event_ids


def write_heartbeat() -> None:
    HEARTBEAT_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    HEARTBEAT_FILE.touch()


def load_provider_health() -> dict[str, dict[str, Any]]:
    if not PROVIDER_HEALTH_FILE.exists():
        return {}

    try:
        with PROVIDER_HEALTH_FILE.open(
            "r",
            encoding="utf-8",
        ) as handle:
            data = json.load(handle)
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def write_provider_health(
    health: dict[str, dict[str, Any]],
) -> None:
    PROVIDER_HEALTH_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = PROVIDER_HEALTH_FILE.with_suffix(
        ".tmp"
    )

    with temporary_file.open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            health,
            handle,
            indent=2,
            sort_keys=True,
        )

        handle.write("\n")

    temporary_file.replace(
        PROVIDER_HEALTH_FILE
    )

def publish_event(
    event_name: str,
    payload: dict[str, Any],
) -> None:
    subprocess.run(
        [
            "/bin/atlas",
            "module",
            "publish",
            "sports",
            event_name,
            json.dumps(
                payload,
                separators=(",", ":"),
            ),
        ],
        check=True,
    )

def mark_provider_healthy(
    health: dict[str, dict[str, Any]],
    provider_name: str,
    game_count: int,
) -> None:
    previous = health.get(
        provider_name,
        {},
    )

    previous_status = str(
        previous.get(
            "status",
            "unknown",
        )
    )

    health[provider_name] = {
        "status": "healthy",
        "last_success_at": utc_now(),
        "last_failure_at": previous.get(
            "last_failure_at"
        ),
        "last_error": None,
        "consecutive_failures": 0,
        "game_count": game_count,
    }

    if previous_status == "degraded":
        publish_event(
            "sports.provider-recovered",
            {
                "provider": provider_name,
                "status": "healthy",
                "previous_status": previous_status,
                "game_count": game_count,
            },
        )


def mark_provider_degraded(
    health: dict[str, dict[str, Any]],
    provider_name: str,
    error: Exception,
) -> None:
    previous = health.get(
        provider_name,
        {},
    )

    previous_status = str(
        previous.get(
            "status",
            "unknown",
        )
    )

    consecutive_failures = int(
        previous.get(
            "consecutive_failures",
            0,
        )
    ) + 1

    health[provider_name] = {
        "status": "degraded",
        "last_success_at": previous.get(
            "last_success_at"
        ),
        "last_failure_at": utc_now(),
        "last_error": str(error),
        "consecutive_failures": consecutive_failures,
        "game_count": previous.get(
            "game_count",
            0,
        ),
    }

    if previous_status != "degraded":
        publish_event(
            "sports.provider-degraded",
            {
                "provider": provider_name,
                "status": "degraded",
                "previous_status": previous_status,
                "error": str(error),
                "consecutive_failures": consecutive_failures,
            },
        )


def run_cycle() -> int:
    providers = enabled_providers()

    if not providers:
        print(
            "No Sports providers enabled.",
            file=sys.stderr,
        )

        write_heartbeat()

        return 1

    previous_games = load_state()
    provider_games: list[dict[str, Any]] = []
    provider_health = load_provider_health()

    degraded_count = 0

    for provider in providers:
        event_ids = tracked_event_ids(
            previous_games,
            provider.name,
        )

        try:
            games = provider.fetch_games(
                tracked_event_ids=event_ids,
            )

        except Exception as exc:
            degraded_count += 1

            mark_provider_degraded(
                provider_health,
                provider.name,
                exc,
            )

            print(
                f"Provider {provider.name}: "
                f"DEGRADED - {exc}",
                file=sys.stderr,
            )

            continue

        provider_games.extend(games)

        mark_provider_healthy(
            provider_health,
            provider.name,
            len(games),
        )

        print(
            f"Provider {provider.name}: "
            f"{len(games)} game(s), "
            f"{len(event_ids)} tracked"
        )

    next_games = process_games(
        provider_games
    )

    write_provider_health(
        provider_health
    )

    write_heartbeat()

    print(
        f"Sports controller cycle complete: "
        f"{len(next_games)} game(s), "
        f"{degraded_count} degraded provider(s)"
    )

    return 0


def main() -> int:
    once = "--once" in sys.argv[1:]

    while True:
        try:
            result = run_cycle()

        except Exception as exc:
            print(
                f"Sports worker cycle failed: {exc}",
                file=sys.stderr,
            )

            write_heartbeat()

            result = 1

        if once:
            return result

        time.sleep(
            CONTROLLER_INTERVAL_SECONDS
        )


if __name__ == "__main__":
    sys.exit(main())
