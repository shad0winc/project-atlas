"""Policy provider registry."""

from __future__ import annotations

from dataclasses import dataclass

from atlas.favorites import FavoriteStore


@dataclass(frozen=True)
class PolicyProviders:
    """Shared data providers used during policy evaluation."""

    favorites: FavoriteStore
