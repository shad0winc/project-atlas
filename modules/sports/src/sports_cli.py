#!/usr/bin/env python3

from __future__ import annotations

import sys

from subscriptions import (
    active_subscriptions,
    create_subscription,
    load_subscriptions,
    remove_subscription,
)

from providers.registry import enabled_providers

import os
from pathlib import Path

def print_usage() -> None:
    print(
        "Atlas Sports\n"
        "\n"
        "Usage:\n"
        "  atlas module sports subscriptions [user]\n"
        "  atlas module sports search team <query>\n"
        "  atlas module sports search league <query>\n"
        "  atlas module sports upcoming <team-id>\n"
        "  atlas module sports follow-team <team-id> <user>\n"
        "  atlas module sports follow-league <league-id> <user>\n"
        "  atlas module sports follow-event <event-id> <user>\n"
        "  atlas module sports subscribe <type> <provider> <id> <name> <user>\n"
        "  atlas module sports unsubscribe <subscription-id>"
    )

def load_module_env() -> None:
    env_file = Path(
        "/opt/project-atlas/modules/sports/.env"
    )

    if not env_file.exists():
        return

    for raw_line in env_file.read_text(
        encoding="utf-8",
    ).splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if line.startswith("#"):
            continue

        if "=" not in line:
            continue

        key, value = line.split(
            "=",
            1,
        )

        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key:
            os.environ.setdefault(
                key,
                value,
            )

def get_provider(
    provider_name: str = "thesportsdb",
):
    load_module_env()

    for provider in enabled_providers():
        if provider.name == provider_name:
            return provider

    raise RuntimeError(
        f"Sports provider unavailable: {provider_name}"
    )

def list_subscriptions(
    arguments: list[str],
) -> int:
    subscriptions = load_subscriptions()

    user_filter = (
        arguments[0]
        if arguments
        else None
    )

    if user_filter is not None:
        subscriptions = [
            subscription
            for subscription in subscriptions
            if str(
                subscription.get(
                    "user",
                    "system",
                )
            )
            == user_filter
        ]

    print("Sports Subscriptions")
    print("--------------------")

    if not subscriptions:
        print("No Sports subscriptions configured.")
        return 0

    for subscription in subscriptions:
        status = (
            "enabled"
            if subscription.get("enabled", True)
            else "disabled"
        )

        print()
        print(
            f"ID:       "
            f"{subscription.get('subscription_id', 'unknown')}"
        )
        print(
            f"Type:     "
            f"{subscription.get('type', 'unknown')}"
        )
        print(
            f"Provider: "
            f"{subscription.get('provider', 'unknown')}"
        )
        print(
            f"Target:   "
            f"{subscription.get('id', 'unknown')}"
        )
        print(
            f"Name:     "
            f"{subscription.get('name', 'unknown')}"
        )
        print(
            f"User:     "
            f"{subscription.get('user', 'system')}"
        )
        print(f"Status:   {status}")

    print()
    print(
        f"Total: {len(subscriptions)}"
    )

    return 0


def subscribe(arguments: list[str]) -> int:
    if len(arguments) < 5:
        print_usage()
        return 1

    subscription_type = arguments[0]
    provider = arguments[1]
    target_id = arguments[2]
    name = arguments[3]
    user = arguments[4]

    try:
        subscription, created = create_subscription(
            subscription_type,
            provider,
            target_id,
            name,
            user,
        )
    except ValueError as exc:
        print(
            f"Sports subscription failed: {exc}",
            file=sys.stderr,
        )
        return 1

    print(
        "Sports Subscription Added"
        if created
        else "Sports Subscription Already Exists"
    )
    print("-------------------------")
    print(
        f"ID:       "
        f"{subscription['subscription_id']}"
    )
    print(
        f"Type:     {subscription['type']}"
    )
    print(
        f"Provider: {subscription['provider']}"
    )
    print(
        f"Target:   {subscription['id']}"
    )
    print(
        f"Name:     {subscription['name']}"
    )
    print(
        f"User:     {subscription['user']}"
    )

    return 0


def unsubscribe(arguments: list[str]) -> int:
    if not arguments:
        print_usage()
        return 1

    atlas_subscription_id = arguments[0]

    removed = remove_subscription(
        atlas_subscription_id
    )

    if not removed:
        print(
            "Sports subscription not found: "
            f"{atlas_subscription_id}",
            file=sys.stderr,
        )
        return 1

    print(
        "Sports subscription removed: "
        f"{atlas_subscription_id}"
    )

    return 0

def search(arguments: list[str]) -> int:
    if len(arguments) < 2:
        print_usage()
        return 1

    search_type = arguments[0]

    query = " ".join(
        arguments[1:]
    ).strip()

    provider = get_provider()

    if search_type == "team":
        results = provider.search_teams(
            query
        )

    elif search_type == "league":
        results = provider.search_leagues(
            query
        )

    else:
        print(
            f"Unsupported search type: {search_type}",
            file=sys.stderr,
        )
        return 1

    if not results:
        print("No Sports results found.")
        return 0

    for result in results:
        print()
        print(
            f"ID:       {result['id']}"
        )
        print(
            f"Name:     {result['name']}"
        )

        if result.get("sport"):
            print(
                f"Sport:    {result['sport']}"
            )

        if result.get("league"):
            print(
                f"League:   {result['league']}"
            )

        if result.get("country"):
            print(
                f"Country:  {result['country']}"
            )

    return 0

def upcoming(arguments: list[str]) -> int:
    if not arguments:
        print_usage()
        return 1

    team_id = arguments[0]

    provider = get_provider()

    games = provider.upcoming_team_games(
        team_id
    )

    if not games:
        print("No upcoming games found.")
        return 0

    for game in games:
        print()
        print(
            f"ID:      {game['provider_event_id']}"
        )
        print(
            f"Game:    {game['name']}"
        )
        print(
            f"League:  {game.get('league', 'Unknown')}"
        )
        print(
            f"Start:   {game.get('start_at', 'Unknown')}"
        )
        print(
            f"Status:  {game.get('status', 'Unknown')}"
        )

    return 0

def follow_team(arguments: list[str]) -> int:
    if len(arguments) < 2:
        print_usage()
        return 1

    team_id = arguments[0]
    user = arguments[1]

    provider = get_provider()

    team = provider.fetch_team(
        team_id
    )

    if team is None:
        print(
            f"Sports team not found: {team_id}",
            file=sys.stderr,
        )
        return 1

    name = str(
        team.get(
            "strTeam",
            team_id,
        )
    )

    subscription, created = create_subscription(
        "team",
        provider.name,
        team_id,
        name,
        user,
    )

    print(
        "Sports Team Followed"
        if created
        else "Sports Team Already Followed"
    )
    print("--------------------")
    print(
        f"ID:       "
        f"{subscription['subscription_id']}"
    )
    print(f"Team:     {name}")
    print(f"Provider: {provider.name}")
    print(f"Target:   {team_id}")
    print(f"User:     {user}")

    return 0


def follow_league(arguments: list[str]) -> int:
    if len(arguments) < 2:
        print_usage()
        return 1

    league_id = arguments[0]
    user = arguments[1]

    provider = get_provider()

    league = provider.fetch_league(
        league_id
    )

    if league is None:
        print(
            f"Sports league not found: {league_id}",
            file=sys.stderr,
        )
        return 1

    name = str(
        league.get(
            "strLeague",
            league_id,
        )
    )

    subscription, created = create_subscription(
        "league",
        provider.name,
        league_id,
        name,
        user,
    )

    print(
        "Sports League Followed"
        if created
        else "Sports League Already Followed"
    )
    print("----------------------")
    print(
        f"ID:       "
        f"{subscription['subscription_id']}"
    )
    print(f"League:   {name}")
    print(f"Provider: {provider.name}")
    print(f"Target:   {league_id}")
    print(f"User:     {user}")

    return 0


def follow_event(arguments: list[str]) -> int:
    if len(arguments) < 2:
        print_usage()
        return 1

    event_id = arguments[0]
    user = arguments[1]

    provider = get_provider()

    event = provider.fetch_event(
        event_id
    )

    if event is None:
        print(
            f"Sports event not found: {event_id}",
            file=sys.stderr,
        )
        return 1

    game = provider.normalize_event(
        event
    )

    subscription, created = create_subscription(
        "event",
        provider.name,
        event_id,
        game["name"],
        user,
    )

    print(
        "Sports Event Followed"
        if created
        else "Sports Event Already Followed"
    )
    print("---------------------")
    print(
        f"ID:       "
        f"{subscription['subscription_id']}"
    )
    print(f"Event:    {game['name']}")
    print(f"Provider: {provider.name}")
    print(f"Target:   {event_id}")
    print(f"User:     {user}")

    return 0

def main() -> int:
    arguments = sys.argv[1:]

    command = (
        arguments[0]
        if arguments
        else "subscriptions"
    )

    command_arguments = arguments[1:]

    if command in {
        "subscriptions",
        "list",
    }:
        return list_subscriptions(
            command_arguments
        )

    if command == "subscribe":
        return subscribe(
            command_arguments
        )

    if command == "unsubscribe":
        return unsubscribe(
            command_arguments
        )

    if command == "search":
        return search(
            command_arguments
        )

    if command == "upcoming":
        return upcoming(
            command_arguments
        )

    if command == "follow-team":
        return follow_team(
            command_arguments
        )

    if command == "follow-league":
        return follow_league(
            command_arguments
        )

    if command == "follow-event":
        return follow_event(
            command_arguments
        )

    if command in {
        "help",
        "-h",
        "--help",
    }:
        print_usage()
        return 0

    print(
        f"Unknown Sports command: {command}",
        file=sys.stderr,
    )

    print_usage()

    return 1


if __name__ == "__main__":
    sys.exit(main())
