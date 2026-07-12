#!/usr/bin/env python3

import os
from typing import Any

from adapters.base import NotificationAdapter


class DiscordAdapter(NotificationAdapter):
    name = "discord"

    def __init__(self) -> None:
        self.webhook_url = os.getenv(
            "ATLAS_NOTIFICATIONS_DISCORD_WEBHOOK",
            "",
        ).strip()

    def enabled(self) -> bool:
        return bool(self.webhook_url)

    def deliver(self, notification: dict[str, Any]) -> bool:
        if not self.enabled():
            return True

        # Delivery implementation will be added after
        # the adapter framework is validated.
        return True
