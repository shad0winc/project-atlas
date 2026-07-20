"""Normalized media-retention decisions for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from atlas.policies.models import PolicyDecision


class RetentionError(ValueError):
    """Raised when a retention model contains invalid data."""


@dataclass(frozen=True)
class RetentionDecision:
    """Final retention eligibility decision for one provider media item."""

    provider: str
    item_id: str
    eligible: bool
    policy: PolicyDecision
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

        if not isinstance(self.eligible, bool):
            raise RetentionError("eligible must be a boolean")

        if not isinstance(self.policy, PolicyDecision):
            raise RetentionError(
                "policy must be a PolicyDecision",
            )

        if self.policy.provider != provider:
            raise RetentionError(
                "policy provider does not match retention provider",
            )

        if self.policy.item_id != item_id:
            raise RetentionError(
                "policy item_id does not match retention item_id",
            )

        object.__setattr__(
            self,
            "evaluated_at",
            _required_timestamp(
                self.evaluated_at,
                "evaluated_at",
            ),
        )

    @property
    def retained(self) -> bool:
        """Return whether Atlas must retain the media item."""

        return not self.eligible

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized retention decision."""

        return {
            "provider": self.provider,
            "item_id": self.item_id,
            "eligible": self.eligible,
            "retained": self.retained,
            "policy": self.policy.to_dict(),
            "evaluated_at": self.evaluated_at,
        }


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetentionError(
            f"{field_name} is required",
        )

    return value.strip()


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise RetentionError(
            f"{field_name} is required",
        )

    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00"),
        )
    except ValueError as exc:
        raise RetentionError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise RetentionError(
            f"{field_name} must include a timezone",
        )

    return (
        parsed
        .astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _now_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )
