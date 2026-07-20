"""Provider-neutral media models and interfaces for Project Atlas."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol

class MediaProviderError(RuntimeError):
    """Raised when a media provider cannot resolve an item."""

@dataclass(frozen=True)
class MediaItem:
    provider: str
    item_id: str
    media_type: str
    title: str
    metadata: Mapping[str, Any] = field(default_factory=dict)

class MediaProvider(Protocol):
    @property
    def name(self) -> str: ...
    def get_item(self, item_id: str) -> MediaItem: ...
