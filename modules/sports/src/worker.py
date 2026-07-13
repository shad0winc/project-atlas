#!/usr/bin/env python3

from __future__ import annotations

import os
import sys
import time
from typing import Any

from controller import load_state, process_games
from providers.registry import enabled_providers


CONTROLLER_INTERVAL_SECONDS = int(
    os.getenv(
        "SPORTS_CONTROLLER_INTERVAL_SECONDS",
        "30",
    )
)


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


def run_cycle() -> int:
    providers = enabled_providers()

    if not providers:
        print(
            "No Sports providers enabled.",
            file=sys.stderr,
        )
        return 1

    previous_games = load_state()
    provider_games: list[dict[str, Any]] = []

    for provider in providers:
        event_ids = tracked_event_ids(
            previous_games,
            provider.name,
        )

        games = provider.fetch_games(
            tracked_event_ids=event_ids,
        )

        provider_games.extend(games)

        print(
            f"Provider {provider.name}: "
            f"{len(games)} game(s), "
            f"{len(event_ids)} tracked"
        )

    next_games = process_games(
        provider_games
    )

    print(
        f"Sports controller cycle complete: "
        f"{len(next_games)} game(s)"
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
            result = 1

        if once:
            return result

        time.sleep(
            CONTROLLER_INTERVAL_SECONDS
        )


if __name__ == "__main__":
    sys.exit(main())
