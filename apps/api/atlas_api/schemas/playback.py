"""Authenticated playback response contracts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict

from atlas.media import PlaybackAction


class PlaybackActionResponse(BaseModel):
    """Safe playback capability exposed to authenticated Portal clients."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool
    action: str
    label: str
    backend: str
    source_type: str
    provider: str
    target_id: str
    href: str | None

    @classmethod
    def from_domain(cls, action: PlaybackAction) -> Self:
        if not isinstance(action, PlaybackAction):
            raise TypeError("action must be a PlaybackAction")
        return cls(
            available=action.available,
            action=action.action.value,
            label=action.label,
            backend=action.backend,
            source_type=action.source_type.value,
            provider=action.provider,
            target_id=action.target_id,
            href=action.href,
        )
