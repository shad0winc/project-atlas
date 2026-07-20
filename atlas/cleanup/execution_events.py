"""Normalized item-level cleanup execution events."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from atlas.cleanup.execution_models import CleanupExecutionMode
from atlas.cleanup.models import (
    CleanupAction,
    CleanupError,
)


class CleanupExecutionEventStatus(str, Enum):
    """Observed outcome for one cleanup execution item."""

    SKIPPED = "skipped"
    PREVIEW_SUCCEEDED = "preview_succeeded"
    PREVIEW_FAILED = "preview_failed"


def _utc_now() -> datetime:
    """Return the current UTC time."""

    return datetime.now(timezone.utc)


def _normalize_identity(
    value: object,
    field_name: str,
    *,
    lowercase: bool = False,
) -> str:
    """Normalize and validate an event identity."""

    if not isinstance(value, str):
        raise CleanupError(f"{field_name} must be a string")

    normalized = value.strip()

    if not normalized:
        raise CleanupError(f"{field_name} must not be empty")

    if lowercase:
        normalized = normalized.lower()

    return normalized


def _normalize_action(
    value: CleanupAction | str,
) -> CleanupAction:
    """Normalize a cleanup action."""

    try:
        return (
            value
            if isinstance(value, CleanupAction)
            else CleanupAction(value)
        )
    except (TypeError, ValueError) as exc:
        raise CleanupError(
            f"invalid cleanup action: {value}"
        ) from exc


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
    value: CleanupExecutionEventStatus | str,
) -> CleanupExecutionEventStatus:
    """Normalize an execution-event status."""

    try:
        return (
            value
            if isinstance(
                value,
                CleanupExecutionEventStatus,
            )
            else CleanupExecutionEventStatus(value)
        )
    except (TypeError, ValueError) as exc:
        raise CleanupError(
            f"invalid cleanup execution event status: {value}"
        ) from exc


def _normalize_message(value: object) -> str:
    """Normalize and validate an event message."""

    if not isinstance(value, str):
        raise CleanupError("message must be a string")

    normalized = value.strip()

    if not normalized:
        raise CleanupError("message must not be empty")

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


@dataclass(frozen=True, slots=True)
class CleanupExecutionEvent:
    """Observed execution outcome for one cleanup item."""

    provider: str
    item_id: str
    action: CleanupAction
    status: CleanupExecutionEventStatus
    message: str
    mode: CleanupExecutionMode = CleanupExecutionMode.DRY_RUN
    modified: bool = False
    occurred_at: datetime = field(default_factory=_utc_now)

    def __post_init__(self) -> None:
        """Normalize and validate the execution event."""

        provider = _normalize_identity(
            self.provider,
            "provider",
            lowercase=True,
        )
        item_id = _normalize_identity(
            self.item_id,
            "item_id",
        )
        action = _normalize_action(self.action)
        status = _normalize_status(self.status)
        message = _normalize_message(self.message)
        mode = _normalize_mode(self.mode)
        occurred_at = _normalize_timestamp(
            self.occurred_at,
            "occurred_at",
        )

        if not isinstance(self.modified, bool):
            raise CleanupError("modified must be a boolean")

        if mode is CleanupExecutionMode.DRY_RUN and self.modified:
            raise CleanupError(
                "dry-run execution events cannot modify media"
            )

        if (
            status
            in {
                CleanupExecutionEventStatus.PREVIEW_SUCCEEDED,
                CleanupExecutionEventStatus.PREVIEW_FAILED,
            }
            and action is not CleanupAction.DELETE
        ):
            raise CleanupError(
                "preview execution events require delete action"
            )

        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "item_id", item_id)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "occurred_at", occurred_at)

    @property
    def successful(self) -> bool:
        """Return whether the event represents a successful outcome."""

        return self.status in {
            CleanupExecutionEventStatus.SKIPPED,
            CleanupExecutionEventStatus.PREVIEW_SUCCEEDED,
        }

    @property
    def failed(self) -> bool:
        """Return whether the event represents a failed outcome."""

        return (
            self.status
            is CleanupExecutionEventStatus.PREVIEW_FAILED
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the execution event."""

        return {
            "provider": self.provider,
            "item_id": self.item_id,
            "action": self.action.value,
            "mode": self.mode.value,
            "status": self.status.value,
            "message": self.message,
            "modified": self.modified,
            "occurred_at": (
                self.occurred_at
                .isoformat()
                .replace("+00:00", "Z")
            ),
        }
