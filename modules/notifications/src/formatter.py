#!/usr/bin/env python3

from typing import Any

def notification_route(notification: dict[str, Any]) -> str:
    event_name = notification.get("event", "unknown")
    payload = notification.get("payload", {})

    if event_name.startswith("request."):
        routes = {
            "movie": "movies",
            "tv": "tv",
            "anime_movie": "anime_movies",
            "anime_tv": "anime_tv",
        }

        return routes.get(
            str(payload.get("media_type", "")),
            "system",
        )

    if event_name.startswith("movie."):
        return "movies"

    if event_name.startswith("tv."):
        return "tv"

    if event_name.startswith("anime-movie."):
        return "anime_movies"

    if event_name.startswith("anime-tv."):
        return "anime_tv"

    if event_name in {
        "sports.provider-degraded",
        "sports.provider-recovered",
    }:
        return "system"

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
        "request.created": "Media Request Created",
        "request.submitted": "Media Request Submitted",
        "request.pending": "Media Request Pending",
        "request.approved": "Media Request Approved",
        "request.searching": "Media Search Started",
        "request.downloading": "Media Download Started",
        "request.importing": "Media Import Started",
        "request.available": "Ready to Watch",
        "request.rejected": "Media Request Rejected",
        "request.failed": "Media Request Failed",
        "request.cancelled": "Media Request Cancelled",
    }

    return titles.get(
        event_name,
        "Project Atlas Notification",
    )


def notification_description(notification: dict[str, Any]) -> str:
    event_name = notification.get("event", "unknown")
    payload = notification.get("payload", {})

    if event_name.startswith("request."):
        title = str(
            payload.get(
                "title",
                "Requested media",
            )
        )
        year = payload.get("year")

        display_title = (
            f"{title} ({year})"
            if year is not None
            else title
        )

        descriptions = {
            "request.created": (
                f"{display_title} was added to Atlas requests."
            ),
            "request.submitted": (
                f"{display_title} was submitted to the media provider."
            ),
            "request.pending": (
                f"{display_title} is waiting for approval."
            ),
            "request.approved": (
                f"{display_title} was approved."
            ),
            "request.searching": (
                f"Atlas is searching for {display_title}."
            ),
            "request.downloading": (
                f"{display_title} is downloading."
            ),
            "request.importing": (
                f"{display_title} is being imported."
            ),
            "request.available": (
                f"{display_title} is ready to watch."
            ),
            "request.rejected": (
                f"{display_title} was rejected."
            ),
            "request.failed": (
                f"The request for {display_title} failed."
            ),
            "request.cancelled": (
                f"The request for {display_title} was cancelled."
            ),
        }

        return descriptions.get(
            event_name,
            f"Request update for {display_title}.",
        )

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

    if event_name.startswith("request."):
        fields = [
            {
                "name": "Media",
                "value": str(
                    payload.get(
                        "title",
                        "Unknown",
                    )
                ),
                "inline": False,
            },
            {
                "name": "Type",
                "value": str(
                    payload.get(
                        "media_type",
                        "Unknown",
                    )
                ).replace("_", " ").title(),
                "inline": True,
            },
            {
                "name": "Status",
                "value": str(
                    payload.get(
                        "status",
                        "Unknown",
                    )
                ).title(),
                "inline": True,
            },
            {
                "name": "Provider",
                "value": str(
                    payload.get(
                        "provider",
                        "Unknown",
                    )
                ).title(),
                "inline": True,
            },
            {
                "name": "Request ID",
                "value": str(
                    payload.get(
                        "request_id",
                        "Unknown",
                    )
                ),
                "inline": False,
            },
        ]

        if payload.get("year") is not None:
            fields.insert(
                1,
                {
                    "name": "Year",
                    "value": str(payload["year"]),
                    "inline": True,
                },
            )

        if payload.get("season_number") is not None:
            fields.append(
                {
                    "name": "Season",
                    "value": str(
                        payload["season_number"]
                    ),
                    "inline": True,
                },
            )

        if (
            event_name == "request.available"
            and payload.get("available_at")
        ):
            fields.append(
                {
                    "name": "Available At",
                    "value": str(
                        payload["available_at"]
                    ),
                    "inline": False,
                },
            )

        return fields

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
        subscribed_users = payload.get(
            "subscribed_users",
            [],
        )

        subscription_types = payload.get(
            "subscription_types",
            [],
        )

        followers = (
            ", ".join(subscribed_users)
            if subscribed_users
            else "None"
        )

        matched_by = (
            ", ".join(subscription_types)
            if subscription_types
            else "Unknown"
        )

        return [
            {
                "name": "Game",
                "value": str(
                    payload.get(
                        "game",
                        "Unknown",
                    )
                ),
                "inline": False,
            },
            {
                "name": "Followers",
                "value": followers,
                "inline": True,
            },
            {
                "name": "Subscription Matches",
                "value": str(
                    payload.get(
                        "subscription_count",
                        0,
                    )
                ),
                "inline": True,
            },
            {
                "name": "Matched By",
                "value": matched_by,
                "inline": False,
            },
        ]

    if event_name == "sports.game-finished":
        subscribed_users = payload.get(
            "subscribed_users",
            [],
        )

        subscription_types = payload.get(
            "subscription_types",
            [],
        )

        followers = (
            ", ".join(subscribed_users)
            if subscribed_users
            else "None"
        )

        matched_by = (
            ", ".join(subscription_types)
            if subscription_types
            else "Unknown"
        )

        return [
            {
                "name": "Game",
                "value": str(
                    payload.get(
                        "game",
                        "Unknown",
                    )
                ),
                "inline": False,
            },
            {
                "name": "Status",
                "value": str(
                    payload.get(
                        "status",
                        "Complete",
                    )
                ),
                "inline": True,
            },
            {
                "name": "Followers",
                "value": followers,
                "inline": True,
            },
            {
                "name": "Subscription Matches",
                "value": str(
                    payload.get(
                        "subscription_count",
                        0,
                    )
                ),
                "inline": True,
            },
            {
                "name": "Matched By",
                "value": matched_by,
                "inline": False,
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
