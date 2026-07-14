#!/usr/bin/env python3

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from datetime import datetime, timezone
from uuid import uuid4

SUBSCRIPTIONS_FILE = Path(
    os.getenv(
        "SPORTS_SUBSCRIPTIONS_FILE",
        "/mnt/storage/configs/sportyfin/state/subscriptions.json",
    )
)

VALID_SUBSCRIPTION_TYPES = {
    "event",
    "team",
    "league",
}


def load_subscriptions() -> list[dict[str, Any]]:
    if not SUBSCRIPTIONS_FILE.exists():
        return []

    try:
        data = json.loads(
            SUBSCRIPTIONS_FILE.read_text(
                encoding="utf-8",
            )
        )
    except (
        OSError,
        json.JSONDecodeError,
    ):
        return []

    if not isinstance(data, dict):
        return []

    subscriptions = data.get(
        "subscriptions",
        [],
    )

    if not isinstance(subscriptions, list):
        return []

    return [
        subscription
        for subscription in subscriptions
        if isinstance(subscription, dict)
    ]

def write_subscriptions(
    subscriptions: list[dict[str, Any]],
) -> None:
    SUBSCRIPTIONS_FILE.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_file = SUBSCRIPTIONS_FILE.with_suffix(
        ".tmp"
    )

    payload = {
        "subscriptions": subscriptions,
    }

    temporary_file.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    temporary_file.replace(
        SUBSCRIPTIONS_FILE
    )


def create_subscription(
    subscription_type: str,
    provider: str,
    subscription_id: str,
    name: str,
    user: str,
) -> dict[str, Any]:
    subscription = normalize_subscription(
        {
            "type": subscription_type,
            "provider": provider,
            "id": subscription_id,
            "name": name,
            "user": user,
            "enabled": True,
        }
    )

    subscription["subscription_id"] = (
        f"sub-{uuid4()}"
    )

    subscription["created_at"] = datetime.now(
        timezone.utc
    ).isoformat()

    subscriptions = load_subscriptions()

    subscriptions.append(subscription)

    write_subscriptions(
        subscriptions
    )

    return subscription


def remove_subscription(
    atlas_subscription_id: str,
) -> bool:
    subscriptions = load_subscriptions()

    remaining = [
        subscription
        for subscription in subscriptions
        if str(
            subscription.get(
                "subscription_id",
                "",
            )
        )
        != atlas_subscription_id
    ]

    if len(remaining) == len(subscriptions):
        return False

    write_subscriptions(
        remaining
    )

    return True

def normalize_subscription(
    subscription: dict[str, Any],
) -> dict[str, Any]:
    subscription_type = str(
        subscription.get(
            "type",
            "",
        )
    ).strip().lower()

    if subscription_type not in VALID_SUBSCRIPTION_TYPES:
        raise ValueError(
            f"Invalid subscription type: {subscription_type}"
        )

    provider = str(
        subscription.get(
            "provider",
            "",
        )
    ).strip()

    subscription_id = str(
        subscription.get(
            "id",
            "",
        )
    ).strip()

    if not provider:
        raise ValueError(
            "Subscription provider is required"
        )

    if not subscription_id:
        raise ValueError(
            "Subscription ID is required"
        )

    return {
        "subscription_id": str(
            subscription.get(
                "subscription_id",
                "",
            )
        ),
        "type": subscription_type,
        "provider": provider,
        "id": subscription_id,
        "name": str(
            subscription.get(
                "name",
                subscription_id,
            )
        ),
        "user": str(
            subscription.get(
                "user",
                "system",
            )
        ),
        "enabled": bool(
            subscription.get(
                "enabled",
                True,
            )
        ),
        "created_at": subscription.get(
            "created_at"
        ),
    }


def active_subscriptions() -> list[dict[str, Any]]:
    subscriptions: list[dict[str, Any]] = []

    for raw_subscription in load_subscriptions():
        try:
            subscription = normalize_subscription(
                raw_subscription
            )
        except ValueError:
            continue

        if subscription["enabled"]:
            subscriptions.append(
                subscription
            )

    return subscriptions


def game_matches_subscription(
    game: dict[str, Any],
    subscription: dict[str, Any],
) -> bool:
    if game.get("provider") != subscription["provider"]:
        return False

    subscription_type = subscription["type"]
    subscription_id = subscription["id"]

    if subscription_type == "event":
        return str(
            game.get(
                "provider_event_id",
                "",
            )
        ) == subscription_id

    if subscription_type == "league":
        return str(
            game.get(
                "provider_league_id",
                "",
            )
        ) == subscription_id

    if subscription_type == "team":
        team_ids = {
            str(
                game.get(
                    "home_team_id",
                    "",
                )
            ),
            str(
                game.get(
                    "away_team_id",
                    "",
                )
            ),
        }

        return subscription_id in team_ids

    return False


def filter_subscribed_games(
    games: list[dict[str, Any]],
    subscriptions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    matched_games: list[dict[str, Any]] = []

    for game in games:
        if any(
            game_matches_subscription(
                game,
                subscription,
            )
            for subscription in subscriptions
        ):
            matched_games.append(game)

    return matched_games

def provider_discovery_targets(
    subscriptions: list[dict[str, Any]],
    provider_name: str,
) -> dict[str, list[str]]:
    targets = {
        "events": [],
        "teams": [],
        "leagues": [],
    }

    for subscription in subscriptions:
        if subscription["provider"] != provider_name:
            continue

        subscription_type = subscription["type"]
        subscription_id = subscription["id"]

        if subscription_type == "event":
            targets["events"].append(
                subscription_id
            )

        elif subscription_type == "team":
            targets["teams"].append(
                subscription_id
            )

        elif subscription_type == "league":
            targets["leagues"].append(
                subscription_id
            )

    for target_type in targets:
        targets[target_type] = sorted(
            set(targets[target_type])
        )

    return targets
