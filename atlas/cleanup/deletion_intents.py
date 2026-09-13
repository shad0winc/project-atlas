"""Durable destructive cleanup intent contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from atlas.cleanup.execution_identity import (
    normalize_execution_id,
)
from atlas.cleanup.models import CleanupError


def _required_text(
    value: object,
    field_name: str,
    *,
    lowercase: bool = False,
) -> str:
    if not isinstance(value, str):
        raise CleanupError(
            f"{field_name} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise CleanupError(
            f"{field_name} must not be empty"
        )

    if lowercase:
        normalized = normalized.lower()

    return normalized


def _normalize_timestamp(
    value: object,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise CleanupError(
            f"{field_name} must be a datetime"
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise CleanupError(
            f"{field_name} must be timezone-aware"
        )

    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CleanupDeletionIntent:
    """Durable replay barrier for one pending provider deletion."""

    execution_id: str
    provider: str
    item_id: str
    created_at: datetime

    def __post_init__(self) -> None:
        try:
            execution_id = normalize_execution_id(
                self.execution_id
            )
        except ValueError as exc:
            raise CleanupError(str(exc)) from exc

        provider = _required_text(
            self.provider,
            "provider",
            lowercase=True,
        )
        item_id = _required_text(
            self.item_id,
            "item_id",
        )
        created_at = _normalize_timestamp(
            self.created_at,
            "created_at",
        )

        object.__setattr__(
            self,
            "execution_id",
            execution_id,
        )
        object.__setattr__(
            self,
            "provider",
            provider,
        )
        object.__setattr__(
            self,
            "item_id",
            item_id,
        )
        object.__setattr__(
            self,
            "created_at",
            created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized deletion intent."""

        return {
            "execution_id": self.execution_id,
            "provider": self.provider,
            "item_id": self.item_id,
            "created_at": (
                self.created_at
                .isoformat()
                .replace("+00:00", "Z")
            ),
        }
