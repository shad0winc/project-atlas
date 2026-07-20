"""Policy rule registry."""

from __future__ import annotations

from atlas.policies.engine import PolicyRule
from atlas.policies.favorites import FavoriteRule


def builtin_rules() -> list[PolicyRule]:
    """Return all built-in policy rules in evaluation order."""

    return [
        FavoriteRule(),
    ]
