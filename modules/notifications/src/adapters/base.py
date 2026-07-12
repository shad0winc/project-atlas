#!/usr/bin/env python3

from abc import ABC, abstractmethod
from typing import Any


class NotificationAdapter(ABC):
    """Base contract for Atlas notification delivery adapters."""

    name = "unknown"

    @abstractmethod
    def enabled(self) -> bool:
        """Return True when the adapter is configured and enabled."""

    @abstractmethod
    def deliver(self, notification: dict[str, Any]) -> bool:
        """Deliver a notification and return True on success."""
