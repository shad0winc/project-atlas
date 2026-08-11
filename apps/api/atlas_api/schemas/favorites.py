"""HTTP contracts for the authenticated Atlas Favorites API."""

from __future__ import annotations

from typing import Any, Mapping, Self

from pydantic import BaseModel, ConfigDict, Field


class FavoriteCreateRequest(BaseModel):
    """Create one favorite for the authenticated Atlas user."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(
        min_length=1,
        max_length=32,
    )
    item_id: str = Field(
        min_length=1,
        max_length=256,
    )


class FavoriteResponse(BaseModel):
    """Stable serialized Favorite record returned by the API."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    favorite_id: str
    user_id: str
    provider: str
    item_id: str
    media_type: str
    title: str | None
    metadata: dict[str, Any]
    created_at: str
    updated_at: str

    @classmethod
    def from_record(
        cls,
        record: Mapping[str, Any],
    ) -> Self:
        """Validate one existing Core Favorite serialization."""

        return cls.model_validate(
            dict(record)
        )


class FavoriteListResponse(BaseModel):
    """Favorites owned by the authenticated Atlas user."""

    model_config = ConfigDict(extra="forbid")

    favorites: tuple[FavoriteResponse, ...]
