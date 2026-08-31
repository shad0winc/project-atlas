"""Authenticated playback response contracts."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict

from atlas.media import PlaybackAction, PlaybackSession


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


class PlaybackTrackResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    index: int
    kind: str
    label: str
    language: str | None = None
    codec: str | None = None
    default: bool = False
    forced: bool = False


class PlaybackSessionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    available: bool
    action: str
    label: str
    backend: str
    source_type: str
    provider: str
    requested_target_id: str
    playable_target_id: str
    title: str
    media_type: str
    duration_ticks: int | None
    can_seek: bool
    playback_bootstrap_url: str
    playback_capability: str
    audio_tracks: tuple[PlaybackTrackResponse, ...]
    subtitle_tracks: tuple[PlaybackTrackResponse, ...]
    previous_target_id: str | None = None
    next_target_id: str | None = None

    @classmethod
    def from_domain(
        cls,
        session: PlaybackSession,
        *,
        playback_bootstrap_url: str,
        playback_capability: str,
    ) -> "PlaybackSessionResponse":
        return cls(
            available=session.available,
            action=session.action.value,
            label=session.label,
            backend=session.backend,
            source_type=session.source_type.value,
            provider=session.provider,
            requested_target_id=session.requested_target_id,
            playable_target_id=session.playable_target_id,
            title=session.title,
            media_type=session.media_type,
            duration_ticks=session.duration_ticks,
            can_seek=session.can_seek,
            playback_bootstrap_url=playback_bootstrap_url,
            playback_capability=playback_capability,
            audio_tracks=tuple(
                PlaybackTrackResponse(
                    index=track.index,
                    kind=track.kind,
                    label=track.label,
                    language=track.language,
                    codec=track.codec,
                    default=track.default,
                    forced=track.forced,
                )
                for track in session.audio_tracks
            ),
            subtitle_tracks=tuple(
                PlaybackTrackResponse(
                    index=track.index,
                    kind=track.kind,
                    label=track.label,
                    language=track.language,
                    codec=track.codec,
                    default=track.default,
                    forced=track.forced,
                )
                for track in session.subtitle_tracks
            ),
            previous_target_id=session.previous_target_id,
            next_target_id=session.next_target_id,
        )
