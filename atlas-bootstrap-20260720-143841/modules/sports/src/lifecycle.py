#!/usr/bin/env python3

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


ACTIVE_STATES = {
    "scheduled",
    "live",
    "final",
    "grace",
    "finished",
}


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        timestamp = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return timestamp.astimezone(timezone.utc)


def lifecycle_state(
    game: dict[str, Any],
    now: datetime,
    grace_minutes: int,
) -> str:
    provider_status = str(
        game.get("status", "scheduled")
    ).lower()

    previous_state = str(
        game.get("lifecycle_state", "scheduled")
    ).lower()

    if provider_status in {"live", "in_progress"}:
        return "live"

    if provider_status in {"final", "finished", "ended"}:
        final_at = parse_timestamp(game.get("final_at"))

        if final_at is None:
            return "final"

        grace_ends_at = final_at + timedelta(
            minutes=grace_minutes
        )

        if now < grace_ends_at:
            return "grace"

        return "finished"

    if previous_state == "live":
        return "live"

    return "scheduled"


def should_publish_started(
    previous_state: str,
    current_state: str,
) -> bool:
    return (
        previous_state != "live"
        and current_state == "live"
    )


def should_publish_finished(
    previous_state: str,
    current_state: str,
) -> bool:
    return (
        previous_state != "finished"
        and current_state == "finished"
    )


def should_include_in_feed(state: str) -> bool:
    return state in {
        "scheduled",
        "live",
        "final",
        "grace",
    }

def should_surface_game(
    game: dict[str, Any],
    now: datetime,
    pregame_minutes: int,
) -> bool:
    state = str(
        game.get(
            "lifecycle_state",
            "scheduled",
        )
    ).lower()

    if state in {
        "live",
        "final",
        "grace",
    }:
        return True

    if state == "finished":
        return False

    start_at = parse_timestamp(
        game.get("start_at")
    )

    if start_at is None:
        return False

    visible_at = start_at - timedelta(
        minutes=pregame_minutes
    )

    return now >= visible_at
