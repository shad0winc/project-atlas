#!/usr/bin/env python3

import json
import os
import urllib.error
import urllib.request
from typing import Any

from adapters.base import NotificationAdapter
from formatter import format_notification


class DiscordAdapter(NotificationAdapter):
    name = "discord"

    def __init__(self) -> None:
        self.webhook_url = os.getenv(
            "ATLAS_NOTIFICATIONS_DISCORD_WEBHOOK",
            "",
        ).strip()

        self.timeout = int(
            os.getenv(
                "ATLAS_NOTIFICATIONS_DISCORD_TIMEOUT",
                "10",
            )
        )

    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def deliver(self, notification: dict[str, Any]) -> bool:
        if not self.enabled():
            return True

        payload = {
            "content": format_notification(notification),
            "username": "Project Atlas",
        }

        body = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            self.webhook_url,
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
