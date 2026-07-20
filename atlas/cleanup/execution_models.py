"""Normalized models for controlled Atlas cleanup execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
)


class CleanupExecutionMode(str, Enum):
    """Supported cleanup execution modes."""

    DRY_RUN = "dry_run"


class CleanupExecutionStatus(str, Enum):
    """Status of one cleanup execution item."""

    PLANNED = "planned"
    SKIPPED = "skipped"


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


def _normalize_identity(
    value: object,
    field_name: str,
    *,
    lowercase: bool = False,
) -> str:
    """Normalize and validate an execution identity value."""

    if not isinstance(value, str):
        raise CleanupError(f"{field_name} must be a string")

    normalized = value.strip()

    if not normalized:
        raise CleanupError(f"{field_name} must not be empty")

    if lowercase:
        normalized = normalized.lower()

    return normalized


def _normalize_timestamp(
    value: object,
    field_name: str,
) -> datetime:
    """Validate and normalize a timezone-aware timestamp."""

    if not isinstance(value, datetime):
        raise CleanupError(f"{field_name} must be a datetime")

    if value.tzinfo is None or value.utcoffset() is None:
        raise CleanupError(
            f"{field_name} must be timezone-aware"
        )

    return value.astimezone(timezone.utc)


def _normalize_mode(
    value: CleanupExecutionMode | str,
) -> CleanupExecutionMode:
    """Normalize a cleanup execution mode."""

    try:
        return (
            value
            if isinstance(value, CleanupExecutionMode)
            else CleanupExecutionMode(value)
        )
    except (TypeError, ValueError) as exc:
        raise CleanupError(
            f"invalid cleanup execution mode: {value}"
        ) from exc


def _normalize_status(
    value: CleanupExecutionStatus | str,
) -> CleanupExecutionStatus:
    """Normalize a cleanup execution status."""

    try:
        return (
            value
            if isinstance(value, CleanupExecutionStatus)
            else CleanupExecutionStatus(value)
        )
    except (TypeError, ValueError) as exc:
        raise CleanupError(
            f"invalid cleanup execution status: {value}"
        ) from exc


@dataclass(frozen=True, slots=True)
class CleanupExecutionItem:
    """Normalized execution plan for one cleanup decision."""

    provider: str
    item_id: str
    decision: CleanupDecision
    mode: CleanupExecutionMode = CleanupExecutionMode.DRY_RUN
    status: CleanupExecutionStatus = (
        CleanupExecutionStatus.PLANNED
    )
    modified: bool = False
    planned_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Normalize and validate the execution item."""

        provider = _normalize_identity(
            self.provider,
            "provider",
            lowercase=True,
        )
        item_id = _normalize_identity(
            self.item_id,
            "item_id",
        )
        mode = _normalize_mode(self.mode)
        status = _normalize_status(self.status)
        planned_at = _normalize_timestamp(
            self.planned_at,
            "planned_at",
        )

        if not isinstance(self.decision, CleanupDecision):
            raise CleanupError(
                "decision must be a CleanupDecision"
            )

        if self.decision.provider != provider:
            raise CleanupError(
                "cleanup decision provider does not match "
                "execution provider"
            )

        if self.decision.item_id != item_id:
            raise CleanupError(
                "cleanup decision item_id does not match "
                "execution item_id"
            )

        if not isinstance(self.modified, bool):
            raise CleanupError("modified must be a boolean")

        if mode is CleanupExecutionMode.DRY_RUN and self.modified:
            raise CleanupError(
                "dry-run execution items cannot modify media"
            )

        expected_status = (
            CleanupExecutionStatus.PLANNED
            if self.decision.action is CleanupAction.DELETE
            else CleanupExecutionStatus.SKIPPED
        )

        if status is not expected_status:
            raise CleanupError(
                "execution status does not match cleanup decision"
            )

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "planned_at", planned_at)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the execution item."""

        return {
            "provider": self.provider,
            "item_id": self.item_id,
            "mode": self.mode.value,
            "status": self.status.value,
            "modified": self.modified,
            "planned_at": (
                self.planned_at
                .isoformat()
                .replace("+00:00", "Z")
            ),
            "decision": self.decision.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class CleanupExecutionReport:
    """Normalized execution plan for one provider scan."""

    provider: str
    items: tuple[CleanupExecutionItem, ...] = field(
        default_factory=tuple
    )
    mode: CleanupExecutionMode = CleanupExecutionMode.DRY_RUN
    created_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Normalize and validate the execution report."""

        provider = _normalize_identity(
            self.provider,
            "provider",
            lowercase=True,
        )
        mode = _normalize_mode(self.mode)
        created_at = _normalize_timestamp(
            self.created_at,
            "created_at",
        )

        if not isinstance(self.items, tuple):
            raise CleanupError("items must be a tuple")

        item_ids: set[str] = set()

        for item in self.items:
            if not isinstance(item, CleanupExecutionItem):
                raise CleanupError(
                    "items must contain CleanupExecutionItem values"
                )

            if item.provider != provider:
                raise CleanupError(
                    "execution item provider does not match "
                    "report provider"
                )

            if item.mode is not mode:
                raise CleanupError(
                    "execution item mode does not match report mode"
                )

            if item.item_id in item_ids:
                raise CleanupError(
                    "cleanup execution report contains duplicate "
                    "item IDs"
                )

            item_ids.add(item.item_id)

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "created_at", created_at)

    @property
    def total(self) -> int:
        """Return the total number of execution items."""

        return len(self.items)

    @property
    def planned_count(self) -> int:
        """Return the number of planned execution items."""

        return self._count_status(
            CleanupExecutionStatus.PLANNED
        )

    @property
    def skipped_count(self) -> int:
        """Return the number of skipped execution items."""

        return self._count_status(
            CleanupExecutionStatus.SKIPPED
        )

    @property
    def modified_count(self) -> int:
        """Return the number of modified media items."""

        return sum(item.modified for item in self.items)

    def items_for(
        self,
        status: CleanupExecutionStatus | str,
    ) -> tuple[CleanupExecutionItem, ...]:
        """Return execution items matching one status."""

        normalized_status = _normalize_status(status)

        return tuple(
            item
            for item in self.items
            if item.status is normalized_status
        )

    def _count_status(
        self,
        status: CleanupExecutionStatus,
    ) -> int:
        """Count execution items matching one status."""

        return sum(
            item.status is status
            for item in self.items
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the execution report."""

        return {
            "provider": self.provider,
            "mode": self.mode.value,
            "created_at": (
                self.created_at
                .isoformat()
                .replace("+00:00", "Z")
            ),
            "summary": {
                "total": self.total,
                "planned": self.planned_count,
                "skipped": self.skipped_count,
                "modified": self.modified_count,
            },
            "items": [
                item.to_dict()
                for item in self.items
            ],
        }
