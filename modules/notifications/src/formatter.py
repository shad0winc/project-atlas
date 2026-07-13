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
        "atlas.health-report": "Atlas Daily Health Report",
        "sports.game-started": "Sports Event Started",
        "sports.game-finished": "Sports Event Finished",
        "storage.threshold-crossed": "Atlas Storage Threshold Reached",
        "storage.threshold-recovered": "Atlas Storage Threshold Recovered",
        "sports.provider-degraded": "Sports Provider Degraded",
        "sports.provider-recovered": "Sports Provider Recovered",
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

    if event_name == "atlas.health-report":
        status = payload.get("status", "Unknown")

        return f"Daily platform health summary: {status}"

    if event_name == "storage.threshold-crossed":
        threshold = payload.get("threshold", "Unknown")

        return (
            f"Storage usage has crossed the {threshold}% threshold."
        )

    if event_name == "storage.threshold-recovered":
        threshold = payload.get("threshold", "Unknown")

        return (
            f"Storage usage has recovered below the {threshold}% threshold."
        )

    if event_name == "sports.provider-degraded":
        provider = payload.get(
            "provider",
            "Unknown",
        )

        return (
            f"The {provider} sports provider "
            "is currently degraded."
        )

    if event_name == "sports.provider-recovered":
        provider = payload.get(
            "provider",
            "Unknown",
        )

        return (
            f"The {provider} sports provider "
            "has recovered."
        )

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

    if event_name == "atlas.health-report":
        storage = payload.get("storage", {})
        forecast = payload.get("forecast", {})

        days_remaining = forecast.get("days_remaining", 0)

        if days_remaining:
            forecast_value = f"{days_remaining} days remaining"
        else:
            forecast_value = str(
                forecast.get("status", "Unknown")
            )

        return [
            {
                "name": "Status",
                "value": str(payload.get("status", "Unknown")),
                "inline": True,
            },
            {
                "name": "Health Score",
                "value": f"{payload.get('score', 'Unknown')} / 100",
                "inline": True,
            },
            {
                "name": "Storage Usage",
                "value": f"{storage.get('usage_percent', 'Unknown')}%",
                "inline": True,
            },
            {
                "name": "Used",
                "value": str(storage.get("used", "Unknown")),
                "inline": True,
            },
            {
                "name": "Available",
                "value": str(storage.get("available", "Unknown")),
                "inline": True,
            },
            {
                "name": "Capacity",
                "value": str(storage.get("capacity", "Unknown")),
                "inline": True,
            },
            {
                "name": "Forecast",
                "value": forecast_value,
                "inline": True,
            },
            {
                "name": "Forecast Confidence",
                "value": str(
                    forecast.get("confidence", "Unknown")
                ),
                "inline": True,
            },
        ]

    if event_name in {
        "storage.threshold-crossed",
        "storage.threshold-recovered",
    }:
        return [
            {
                "name": "Usage",
                "value": f"{payload.get('usage_percent', 'Unknown')}%",
                "inline": True,
            },
            {
                "name": "Used",
                "value": str(payload.get("used", "Unknown")),
                "inline": True,
            },
            {
                "name": "Available",
                "value": str(payload.get("available", "Unknown")),
                "inline": True,
            },
            {
                "name": "Capacity",
                "value": str(payload.get("capacity", "Unknown")),
                "inline": True,
            },
            {
                "name": "Threshold",
                "value": f"{payload.get('threshold', 'Unknown')}%",
                "inline": True,
            },
        ]

    if event_name == "sports.provider-degraded":
        return [
            {
                "name": "Provider",
                "value": str(
                    payload.get(
                        "provider",
                        "Unknown",
                    )
                ),
                "inline": True,
            },
            {
                "name": "Status",
                "value": "Degraded",
                "inline": True,
            },
            {
                "name": "Failures",
                "value": str(
                    payload.get(
                        "consecutive_failures",
                        "Unknown",
                    )
                ),
                "inline": True,
            },
            {
                "name": "Error",
                "value": str(
                    payload.get(
                        "error",
                        "Unknown",
                    )
                ),
                "inline": False,
            },
        ]

    if event_name == "sports.provider-recovered":
        return [
            {
                "name": "Provider",
                "value": str(
                    payload.get(
                        "provider",
                        "Unknown",
                    )
                ),
                "inline": True,
            },
            {
                "name": "Status",
                "value": "Healthy",
                "inline": True,
            },
            {
                "name": "Games",
                "value": str(
                    payload.get(
                        "game_count",
                        0,
                    )
                ),
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
