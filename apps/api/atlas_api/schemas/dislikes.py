"""HTTP contracts for the authenticated Atlas Dislikes API."""

from __future__ import annotations

from typing import Any, Mapping, Self

from pydantic import BaseModel, ConfigDict, Field


class DislikeCreateRequest(BaseModel):
    """Create one dislike for the authenticated Atlas user."""

    model_config = ConfigDict(extra="forbid")

    provider: str = Field(
        min_length=1,
        max_length=32,
    )
    item_id: str = Field(
        min_length=1,
        max_length=256,
    )


class DislikeResponse(BaseModel):
    """Stable serialized Dislike record returned by the API."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    dislike_id: str
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
        """Validate one existing Core Dislike serialization."""

        return cls.model_validate(
            dict(record)
        )


class DislikeListResponse(BaseModel):
    """Dislikes owned by the authenticated Atlas user."""

    model_config = ConfigDict(extra="forbid")

    dislikes: tuple[DislikeResponse, ...]
