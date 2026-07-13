#!/usr/bin/env python3

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SportsProvider(ABC):
    """Base contract for Atlas sports data providers."""

    name = "unknown"

    @abstractmethod
    def enabled(self) -> bool:
        """Return True when the provider is configured."""

    @abstractmethod
    def fetch_games(self) -> list[dict[str, Any]]:
        """Fetch and return normalized Atlas game records."""
