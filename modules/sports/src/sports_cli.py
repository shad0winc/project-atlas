#!/usr/bin/env python3

from __future__ import annotations

import sys

from subscriptions import (
    active_subscriptions,
    create_subscription,
    load_subscriptions,
    remove_subscription,
)


def print_usage() -> None:
    print(
        "Atlas Sports\n"
        "\n"
        "Usage:\n"
        "  atlas module sports subscriptions [user]\n"
        "  atlas module sports subscribe <type> <provider> <id> <name> <user>\n"
        "  atlas module sports unsubscribe <subscription-id>"
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
        subscription = create_subscription(
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

    print("Sports Subscription Added")
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
