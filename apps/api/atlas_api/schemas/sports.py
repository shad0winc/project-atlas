"""Schemas for the Atlas v1 Sports request journey."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


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
