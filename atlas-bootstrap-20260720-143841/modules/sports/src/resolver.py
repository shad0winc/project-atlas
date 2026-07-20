#!/usr/bin/env python3

from __future__ import annotations

from copy import deepcopy
from typing import Any

from subscriptions import game_matches_subscription


def resolve_subscribed_games(
    games: list[dict[str, Any]],
    subscriptions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resolved_games: list[dict[str, Any]] = []

    for game in games:
        matching_subscriptions = [
            subscription
            for subscription in subscriptions
            if game_matches_subscription(
                game,
                subscription,
            )
        ]

        if not matching_subscriptions:
            continue

        resolved_game = deepcopy(game)

        subscription_ids = sorted(
            {
                str(
                    subscription.get(
                        "subscription_id",
                        "",
                    )
                )
                for subscription in matching_subscriptions
                if subscription.get(
                    "subscription_id"
                )
            }
        )

        subscription_types = sorted(
            {
                str(
                    subscription.get(
                        "type",
                        "",
                    )
                )
                for subscription in matching_subscriptions
                if subscription.get("type")
            }
        )

        subscribed_users = sorted(
            {
                str(
                    subscription.get(
                        "user",
                        "system",
                    )
                )
                for subscription in matching_subscriptions
            }
        )

        resolved_game[
            "subscription_count"
        ] = len(matching_subscriptions)

        resolved_game[
            "subscription_ids"
        ] = subscription_ids

        resolved_game[
            "subscription_types"
        ] = subscription_types

        resolved_game[
            "subscribed_users"
        ] = subscribed_users

        resolved_games.append(
            resolved_game
        )

    return resolved_games
