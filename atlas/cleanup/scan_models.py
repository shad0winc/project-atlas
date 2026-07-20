"""Normalized models for Atlas cleanup library scans."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
)


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


def _normalize_identity(value: object, field_name: str) -> str:
    """Normalize and validate a provider identity value."""

    if not isinstance(value, str):
        raise CleanupError(f"{field_name} must be a string")

    normalized = value.strip().lower()

    if not normalized:
        raise CleanupError(f"{field_name} must not be empty")

    return normalized


def _normalize_timestamp(value: object) -> datetime:
    """Validate a timezone-aware scan timestamp."""

    if not isinstance(value, datetime):
        raise CleanupError("scanned_at must be a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise CleanupError("scanned_at must be timezone-aware")

    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class CleanupScanReport:
    """Normalized cleanup decisions for one provider scan."""

    provider: str
    decisions: tuple[CleanupDecision, ...] = field(
        default_factory=tuple
    )
    scanned_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Normalize and validate the scan report."""

        provider = _normalize_identity(
            self.provider,
            "provider",
        )
        scanned_at = _normalize_timestamp(self.scanned_at)

        if not isinstance(self.decisions, tuple):
            raise CleanupError("decisions must be a tuple")

        item_ids: set[str] = set()

        for decision in self.decisions:
            if not isinstance(decision, CleanupDecision):
                raise CleanupError(
                    "decisions must contain CleanupDecision values"
                )

            if decision.provider != provider:
                raise CleanupError(
                    "cleanup decision provider does not match scan provider"
                )

            if decision.item_id in item_ids:
                raise CleanupError(
                    "cleanup scan contains duplicate item IDs"
                )

            item_ids.add(decision.item_id)

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "scanned_at", scanned_at)

    @property
    def scanned(self) -> int:
        """Return the total number of scanned items."""

        return len(self.decisions)

    @property
    def delete_count(self) -> int:
        """Return the number of delete recommendations."""

        return self._count_action(CleanupAction.DELETE)

    @property
    def keep_count(self) -> int:
        """Return the number of keep recommendations."""

        return self._count_action(CleanupAction.KEEP)

    @property
    def review_count(self) -> int:
        """Return the number of review recommendations."""

        return self._count_action(CleanupAction.REVIEW)

    def decisions_for(
        self,
        action: CleanupAction | str,
    ) -> tuple[CleanupDecision, ...]:
        """Return decisions matching one cleanup action."""

        try:
            normalized_action = CleanupAction(action)
        except (TypeError, ValueError) as exc:
            raise CleanupError(
                f"invalid cleanup action: {action}"
            ) from exc

        return tuple(
            decision
            for decision in self.decisions
            if decision.action is normalized_action
        )

    def _count_action(self, action: CleanupAction) -> int:
        """Count decisions matching one cleanup action."""

        return sum(
            decision.action is action
            for decision in self.decisions
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the scan report."""

        return {
            "provider": self.provider,
            "scanned_at": (
                self.scanned_at
                .isoformat()
                .replace("+00:00", "Z")
            ),
            "summary": {
                "scanned": self.scanned,
                "delete": self.delete_count,
                "keep": self.keep_count,
                "review": self.review_count,
            },
            "decisions": [
                decision.to_dict()
                for decision in self.decisions
            ],
        }
