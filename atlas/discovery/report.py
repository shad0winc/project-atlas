"""
Discovery reporting models.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class DiscoveryReport:
    """Summary of discovery operations."""

    indexer_count: int = 0
    warning_count: int = 0
    error_count: int = 0

    metadata: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "indexer_count": self.indexer_count,
            "warning_count": self.warning_count,
            "error_count": self.error_count,
            "metadata": dict(self.metadata),
        }
