#!/usr/bin/env python3

from typing import Any

def notification_route(notification: dict[str, Any]) -> str:
    event_name = notification.get("event", "unknown")

    if event_name.startswith("movie."):
        return "movies"

    if event_name.startswith("tv."):
        return "tv"

    if event_name.startswith("anime-movie."):
        return "anime_movies"

    if event_name.startswith("anime-tv."):
        return "anime_tv"

    if event_name.startswith("sports."):
        return "sports"

    return "system"

def notification_title(notification: dict[str, Any]) -> str:
    event_name = notification.get("event", "unknown")

    titles = {
        "atlas.health-changed": "Atlas Health Changed",
        "storage.low": "Atlas Storage Warning",
        "sports.game-started": "Sports Event Started",
        "sports.game-finished": "Sports Event Finished",
    }

    return titles.get(
        event_name,
        "Project Atlas Notification",
    )


def notification_description(notification: dict[str, Any]) -> str:
    event_name = notification.get("event", "unknown")
    payload = notification.get("payload", {})

    if event_name == "atlas.health-changed":
        previous = payload.get("previous", "Unknown")
        current = payload.get("current", "Unknown")

        return f"{previous} → {current}"

    if event_name == "storage.low":
        return "Available storage has reached a warning threshold."

    if event_name == "sports.game-started":
        return "A monitored sports event has started."

    if event_name == "sports.game-finished":
        return "A monitored sports event has finished."

    return f"Atlas event: {event_name}"


def notification_fields(
    notification: dict[str, Any],
) -> list[dict[str, Any]]:
    event_name = notification.get("event", "unknown")
    payload = notification.get("payload", {})

    if event_name == "atlas.health-changed":
        return [
            {
                "name": "Previous",
                "value": str(payload.get("previous", "Unknown")),
                "inline": True,
            },
            {
                "name": "Current",
                "value": str(payload.get("current", "Unknown")),
                "inline": True,
            },
            {
                "name": "Health Score",
                "value": f"{payload.get('score', 'Unknown')} / 100",
                "inline": True,
            },
        ]

    if event_name == "storage.low":
        return [
            {
                "name": "Available Storage",
                "value": str(payload.get("available", "Unknown")),
                "inline": True,
            },
        ]

    if event_name == "sports.game-started":
        return [
            {
                "name": "Game",
                "value": str(payload.get("game", "Unknown")),
                "inline": False,
            },
        ]

    if event_name == "sports.game-finished":
        return [
            {
                "name": "Game",
                "value": str(payload.get("game", "Unknown")),
                "inline": False,
            },
            {
                "name": "Status",
                "value": str(payload.get("status", "Complete")),
                "inline": True,
            },
        ]

    return [
        {
            "name": "Event",
            "value": event_name,
            "inline": False,
        },
    ]


def format_notification(notification: dict[str, Any]) -> str:
    title = notification_title(notification)
    description = notification_description(notification)

    return f"**{title}**\n{description}"
