"""Schemas for the Atlas v1 Sports request journey."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


def _required_text(value: Any, field_name: str) -> str:
    normalized = str(value).strip()

    if not normalized:
        raise ValueError(f"{field_name} cannot be empty.")

    return normalized


class _StrictSportsModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SportsEventResponse(_StrictSportsModel):
    provider: str
    provider_event_id: str
    name: str
    sport: str
    league: str
    start_at: datetime
    status: str
    requested: bool
    provider_league_id: str | None = None
    home_team_id: str | None = None
    away_team_id: str | None = None
    metadata_observed_at: datetime | None = None
    metadata_expires_at: datetime | None = None

    @model_validator(mode="after")
    def validate_metadata_age(self):
        observed, expires = self.metadata_observed_at, self.metadata_expires_at
        if observed is None and expires is None:
            return self
        if (observed is None or expires is None or observed.tzinfo is None
            or expires.tzinfo is None or observed.utcoffset() is None
            or expires.utcoffset() is None):
            raise ValueError("Metadata observation and expiry must be paired aware timestamps")
        if not 0 < (expires - observed).total_seconds() <= 3600:
            raise ValueError("Invalid metadata lifetime")
        return self

    @field_validator(
        "provider",
        "provider_event_id",
        "name",
        "sport",
        "league",
        "status",
        mode="before",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: Any,
        info,
    ) -> str:
        return _required_text(value, info.field_name)


class SportsEventListResponse(_StrictSportsModel):
    events: list[SportsEventResponse]


class SportsSubscriptionCreateRequest(_StrictSportsModel):
    provider: str
    provider_event_id: str

    @field_validator(
        "provider",
        "provider_event_id",
        mode="before",
    )
    @classmethod
    def normalize_identity(
        cls,
        value: Any,
        info,
    ) -> str:
        return _required_text(value, info.field_name)


class SportsSubscriptionResponse(_StrictSportsModel):
    subscription_id: str
    type: str
    provider: str
    provider_event_id: str
    name: str
    user_id: str
    enabled: bool
    created_at: datetime

    @field_validator(
        "subscription_id",
        "type",
        "provider",
        "provider_event_id",
        "name",
        "user_id",
        mode="before",
    )
    @classmethod
    def normalize_required_text(
        cls,
        value: Any,
        info,
    ) -> str:
        return _required_text(value, info.field_name)

class SportsSearchResultResponse(_StrictSportsModel):
    id: str
    name: str
    sport: str = ""
    league: str = ""


class SportsSearchResponse(_StrictSportsModel):
    results: list[SportsSearchResultResponse]


class SportsFollowCreateRequest(_StrictSportsModel):
    type: str
    provider: str = "thesportsdb"
    provider_id: str


class SportsRecordingIntentRequest(_StrictSportsModel):
    record: bool


class SportsFollowResponse(_StrictSportsModel):
    subscription_id: str
    type: str
    provider: str
    provider_id: str
    name: str
    user_id: str
    enabled: bool
    record: bool = False
    created_at: datetime | None = None


class SportsFollowListResponse(_StrictSportsModel):
    subscriptions: list[SportsFollowResponse]


class SportsLiveChannelResponse(_StrictSportsModel):
    atlas_channel_id: str
    name: str
    playback_configured: bool


class SportsLiveChannelListResponse(_StrictSportsModel):
    channels: list[SportsLiveChannelResponse]


class SportsDiscoveryProviderResponse(_StrictSportsModel):
    provider: str
    enabled: bool


class SportsDiscoveryProvidersResponse(_StrictSportsModel):
    version: int
    providers: list[SportsDiscoveryProviderResponse]
