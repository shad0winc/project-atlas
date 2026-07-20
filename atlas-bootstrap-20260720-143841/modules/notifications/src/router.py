#!/usr/bin/env python3

from typing import Any

from adapters.base import NotificationAdapter
from adapters.discord import DiscordAdapter
from adapters.webhook import WebhookAdapter


class NotificationRouter:
    """Routes Atlas notifications to configured delivery adapters."""

    def __init__(self) -> None:
        self.adapters: list[NotificationAdapter] = [
            DiscordAdapter(),
            WebhookAdapter(),
        ]

    def enabled_adapters(self) -> list[NotificationAdapter]:
        return [
            adapter
            for adapter in self.adapters
            if adapter.enabled()
        ]

    def deliver(self, notification: dict[str, Any]) -> bool:
        failed = False

        for adapter in self.enabled_adapters():
            try:
                delivered = adapter.deliver(notification)
            except Exception as exc:
                print(
                    f"Adapter failure [{adapter.name}]: {exc}"
                )
                failed = True
                continue

            if not delivered:
                print(
                    f"Adapter delivery failed [{adapter.name}]"
                )
                failed = True

        return not failed
