"""Schemas for the Atlas v1 Sports request journey."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, field_validator, model_validator


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


CuratedStatus = Literal['disabled', 'preparing', 'ready', 'partial', 'stale', 'unavailable', 'unsupported']
CURATED_COMPETITION_ROUTES = {'nfl': 'football/nfl', 'college-football': None,
    'nba': 'basketball/nba', 'college-basketball': None, 'mlb': 'baseball/mlb',
    'nhl': 'hockey/nhl', 'premier-league': 'soccer/eng.1', 'ufc': 'mma/ufc'}


class SportsCuratedCompetition(_StrictSportsModel):
    id: str = Field(min_length=1, max_length=64)
    sport: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    provider: Literal['espn']
    provider_league_id: str | None = Field(default=None, max_length=64)
    team_directory_supported: StrictBool
    status: Literal['configured', 'disabled', 'unsupported']

    @model_validator(mode='after')
    def scoped_competition(self):
        if self.id not in CURATED_COMPETITION_ROUTES or self.provider_league_id != CURATED_COMPETITION_ROUTES[self.id]:
            raise ValueError('Competition route mismatch')
        if (self.status == 'unsupported') != (self.provider_league_id is None):
            raise ValueError('Unsupported competition mismatch')
        return self


class _CuratedResponse(_StrictSportsModel):
    version: Literal[1]
    evaluated_at: datetime

    @field_validator('evaluated_at')
    @classmethod
    def aware_evaluation(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError('Aware cache evaluation required')
        return value


class SportsCuratedCatalogResponse(_CuratedResponse):
    enabled: StrictBool
    competitions: list[SportsCuratedCompetition] = Field(max_length=16)

    @model_validator(mode='after')
    def unique_catalog(self):
        if len(self.competitions) != len(CURATED_COMPETITION_ROUTES) or {row.id for row in self.competitions} != set(CURATED_COMPETITION_ROUTES):
            raise ValueError('Competition catalog coverage mismatch')
        if not self.enabled and any(row.status == 'configured' for row in self.competitions):
            raise ValueError('Disabled catalog cannot admit configuration')
        return self


class SportsCuratedTeam(_StrictSportsModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=512)


class SportsCuratedTeamsResponse(_CuratedResponse):
    competition_id: str = Field(min_length=1, max_length=64)
    provider: Literal['espn']
    provider_league_id: str | None = Field(default=None, max_length=64)
    status: CuratedStatus
    observed_at: datetime | None
    expires_at: datetime | None
    retry_after_seconds: StrictInt = Field(ge=0, le=3600)
    teams: list[SportsCuratedTeam] = Field(max_length=500)

    @model_validator(mode='after')
    def scoped_teams(self):
        if self.competition_id not in CURATED_COMPETITION_ROUTES or self.provider_league_id != CURATED_COMPETITION_ROUTES[self.competition_id]:
            raise ValueError('Team competition route mismatch')
        prefix = (self.provider_league_id or '').replace('/', '-') + '-'
        if len({row.id for row in self.teams}) != len(self.teams) or any(not row.id.startswith(prefix) or not row.id[len(prefix):].isascii() or not row.id[len(prefix):].isdecimal() for row in self.teams):
            raise ValueError('Team source identity mismatch')
        return self


class SportsCuratedScheduleResponse(_CuratedResponse):
    competition_id: str = Field(min_length=1, max_length=64)
    provider: Literal['espn']
    provider_league_id: str = Field(min_length=1, max_length=64)
    start_at: datetime
    end_at: datetime
    status: CuratedStatus
    coverage_complete: StrictBool
    provider_completeness_proven: Literal[False]
    required_buckets: StrictInt = Field(ge=1, le=9)
    fresh_buckets: StrictInt = Field(ge=0, le=9)
    retry_after_seconds: StrictInt = Field(ge=0, le=3600)
    observed_at: datetime | None
    expires_at: datetime | None
    events: list[SportsEventResponse] = Field(max_length=500)

    @model_validator(mode='after')
    def coherent_coverage(self):
        if self.competition_id not in CURATED_COMPETITION_ROUTES or self.provider_league_id != CURATED_COMPETITION_ROUTES[self.competition_id]:
            raise ValueError('Schedule competition route mismatch')
        if self.start_at.tzinfo is None or self.end_at.tzinfo is None or not 0 < (self.end_at-self.start_at).total_seconds() <= 7*86400:
            raise ValueError('Invalid aware schedule window')
        if self.fresh_buckets > self.required_buckets:
            raise ValueError('Invalid bucket counts')
        if self.coverage_complete != (self.status == 'ready') or (self.coverage_complete and self.fresh_buckets != self.required_buckets):
            raise ValueError('Invalid cache coverage assertion')
        prefix = self.provider_league_id.replace('/', '-') + '-'
        if len({row.provider_event_id for row in self.events}) != len(self.events):
            raise ValueError('Duplicate schedule event')
        for event in self.events:
            if (event.provider != 'espn' or event.provider_league_id != self.provider_league_id
                or not event.provider_event_id.startswith(prefix)
                or not event.provider_event_id[len(prefix):].isascii() or not event.provider_event_id[len(prefix):].isdecimal()
                or event.start_at.tzinfo is None or not self.start_at <= event.start_at < self.end_at):
                raise ValueError('Event source or window mismatch')
        return self
