"""Normalized cleanup planning models for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from atlas.retention.models import RetentionDecision


class CleanupError(ValueError):
    """Raised when a cleanup model contains invalid data."""


class CleanupAction(str, Enum):
    """Actions Atlas may recommend."""

    KEEP = "keep"
    DELETE = "delete"
    REVIEW = "review"


@dataclass(frozen=True)
class CleanupDecision:
    """Normalized cleanup decision."""

    provider: str
    item_id: str
    action: CleanupAction
    retention: RetentionDecision
    evaluated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        provider = _required_text(
            self.provider,
            "provider",
        ).lower()

        item_id = _required_text(
            self.item_id,
            "item_id",
        )

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "item_id", item_id)

        if not isinstance(self.retention, RetentionDecision):
            raise CleanupError(
                "retention must be a RetentionDecision",
            )

        if self.retention.provider != provider:
            raise CleanupError(
                "retention provider does not match cleanup provider",
            )

        if self.retention.item_id != item_id:
            raise CleanupError(
                "retention item_id does not match cleanup item_id",
            )

        try:
            action = (
                self.action
                if isinstance(self.action, CleanupAction)
                else CleanupAction(self.action)
            )
        except (TypeError, ValueError) as exc:
            raise CleanupError(
                f"invalid cleanup action: {self.action}"
            ) from exc

        object.__setattr__(self, "action", action)

        object.__setattr__(
            self,
            "evaluated_at",
            _required_timestamp(
                self.evaluated_at,
                "evaluated_at",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "item_id": self.item_id,
            "action": self.action.value,
            "retention": self.retention.to_dict(),
            "evaluated_at": self.evaluated_at,
        }


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CleanupError(f"{field_name} is required")
    return value.strip()


def _required_timestamp(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CleanupError(f"{field_name} is required")

    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00")
        )
    except ValueError as exc:
        raise CleanupError(
            f"{field_name} must be an ISO-8601 timestamp"
        ) from exc

    if parsed.tzinfo is None:
        raise CleanupError(
            f"{field_name} must include a timezone"
        )

    return (
        parsed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _now_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
