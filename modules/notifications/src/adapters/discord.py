#!/usr/bin/env python3

import json
import os
import urllib.error
import urllib.request
from typing import Any

from adapters.base import NotificationAdapter
from formatter import (
    notification_description,
    notification_fields,
    notification_route,
    notification_title,
)


SEVERITY_COLORS = {
    "info": 3447003,
    "success": 5763719,
    "warning": 16776960,
    "critical": 15548997,
}


class DiscordAdapter(NotificationAdapter):
    name = "discord"

    def __init__(self) -> None:
        self.timeout = int(
            os.getenv(
                "ATLAS_NOTIFICATIONS_DISCORD_TIMEOUT",
                "10",
            )
        )

        self.webhooks = {
            "system": os.getenv(
                "ATLAS_NOTIFICATIONS_DISCORD_SYSTEM_WEBHOOK",
                "",
            ).strip(),
            "movies": os.getenv(
                "ATLAS_NOTIFICATIONS_DISCORD_MOVIES_WEBHOOK",
                "",
            ).strip(),
            "tv": os.getenv(
                "ATLAS_NOTIFICATIONS_DISCORD_TV_WEBHOOK",
                "",
            ).strip(),
            "anime_movies": os.getenv(
                "ATLAS_NOTIFICATIONS_DISCORD_ANIME_MOVIES_WEBHOOK",
                "",
            ).strip(),
            "anime_tv": os.getenv(
                "ATLAS_NOTIFICATIONS_DISCORD_ANIME_TV_WEBHOOK",
                "",
            ).strip(),
            "sports": os.getenv(
                "ATLAS_NOTIFICATIONS_DISCORD_SPORTS_WEBHOOK",
                "",
            ).strip(),
        }

    def enabled(self) -> bool:
        return any(self.webhooks.values())

    def deliver(self, notification: dict[str, Any]) -> bool:
        if not self.enabled():
            return True

        route = notification_route(notification)
        webhook_url = self.webhooks.get(route, "")

        if not webhook_url:
            return True

        severity = notification.get("severity", "info")
        color = SEVERITY_COLORS.get(
            severity,
            SEVERITY_COLORS["info"],
        )

        embed = {
            "title": notification_title(notification),
            "description": notification_description(notification),
            "color": color,
            "fields": notification_fields(notification),
            "timestamp": notification.get("timestamp"),
            "footer": {
                "text": (
                    f"Project Atlas • "
                    f"{notification.get('source', 'unknown')} • "
                    f"{route}"
                )
            },
        }

        payload = {
            "username": "Project Atlas",
            "embeds": [embed],
        }

        body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            webhook_url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Project-Atlas-Notifications/0.1",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout,
            ) as response:
                return 200 <= response.status < 300

        except (
            urllib.error.HTTPError,
            urllib.error.URLError,
            TimeoutError,
        ):
            return False
