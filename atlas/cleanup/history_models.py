"""Cleanup execution-history models for Project Atlas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from atlas.cleanup.execution_events import (
    CleanupExecutionEvent,
    CleanupExecutionEventStatus,
)
from atlas.cleanup.execution_identity import (
    normalize_execution_id,
)
from atlas.cleanup.execution_models import (
    CleanupExecutionMode,
)


class CleanupHistoryError(RuntimeError):
    """Raised when cleanup history data is invalid."""


@dataclass(frozen=True, slots=True)
class CleanupHistoryEntry:
    """One persisted cleanup execution reconstructed from audit events."""

    execution_id: str
    provider: str
    mode: CleanupExecutionMode
    events: tuple[CleanupExecutionEvent, ...]

    def __post_init__(self) -> None:
        """Normalize and validate the history entry."""

        try:
            execution_id = normalize_execution_id(
                self.execution_id
            )
        except ValueError as exc:
            raise CleanupHistoryError(str(exc)) from exc

        provider = _required_text(
            self.provider,
            "provider",
        ).lower()

        if not isinstance(self.mode, CleanupExecutionMode):
            raise CleanupHistoryError(
                "mode must be a CleanupExecutionMode"
            )

        if not isinstance(self.events, tuple):
            raise CleanupHistoryError(
                "events must be a tuple"
            )

        if not self.events:
            raise CleanupHistoryError(
                "events must contain at least one event"
            )

        normalized_events: list[CleanupExecutionEvent] = []
        item_ids: set[str] = set()

        for event in self.events:
            if not isinstance(event, CleanupExecutionEvent):
                raise CleanupHistoryError(
                    "events must contain "
                    "CleanupExecutionEvent values"
                )

            if event.execution_id != execution_id:
                raise CleanupHistoryError(
                    "event execution_id does not match "
                    "history execution_id"
                )

            if event.provider != provider:
                raise CleanupHistoryError(
                    "event provider does not match "
                    "history provider"
                )

            if event.mode is not self.mode:
                raise CleanupHistoryError(
                    "event mode does not match history mode"
                )

            if event.item_id in item_ids:
                raise CleanupHistoryError(
                    "history events must not contain "
                    "duplicate item IDs"
                )

            item_ids.add(event.item_id)
            normalized_events.append(event)

        normalized_events.sort(
            key=lambda event: (
                event.occurred_at,
                event.item_id,
            )
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
            "events",
            tuple(normalized_events),
        )

    @property
    def started_at(self) -> datetime:
        """Return the earliest persisted event timestamp."""

        return self.events[0].occurred_at

    @property
    def completed_at(self) -> datetime:
        """Return the latest persisted event timestamp.

        This is the latest audit-event time, not necessarily the workflow
        summary completion time.
        """

        return self.events[-1].occurred_at

    @property
    def total(self) -> int:
        """Return the number of persisted item events."""

        return len(self.events)

    @property
    def skipped_count(self) -> int:
        """Return the number of skipped events."""

        return self._count_status(
            CleanupExecutionEventStatus.SKIPPED
        )

    @property
    def preview_succeeded_count(self) -> int:
        """Return the number of successful preview events."""

        return self._count_status(
            CleanupExecutionEventStatus.PREVIEW_SUCCEEDED
        )

    @property
    def preview_failed_count(self) -> int:
        """Return the number of failed preview events."""

        return self._count_status(
            CleanupExecutionEventStatus.PREVIEW_FAILED
        )

    @property
    def modified_count(self) -> int:
        """Return the number of events that modified media."""

        return sum(
            1
            for event in self.events
            if event.modified
        )

    @property
    def successful_count(self) -> int:
        """Return the number of successful item outcomes."""

        return sum(
            1
            for event in self.events
            if event.successful
        )

    @property
    def failed_count(self) -> int:
        """Return the number of failed item outcomes."""

        return sum(
            1
            for event in self.events
            if event.failed
        )

    @property
    def has_failures(self) -> bool:
        """Return whether any persisted item event failed."""

        return self.failed_count > 0

    def events_for(
        self,
        status: CleanupExecutionEventStatus | str,
    ) -> tuple[CleanupExecutionEvent, ...]:
        """Return events matching one normalized status."""

        normalized_status = _normalize_status(status)

        return tuple(
            event
            for event in self.events
            if event.status is normalized_status
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized history entry."""

        return {
            "execution_id": self.execution_id,
            "provider": self.provider,
            "mode": self.mode.value,
            "started_at": _timestamp(self.started_at),
            "completed_at": _timestamp(self.completed_at),
            "total": self.total,
            "skipped": self.skipped_count,
            "preview_succeeded": self.preview_succeeded_count,
            "preview_failed": self.preview_failed_count,
            "modified": self.modified_count,
            "successful": self.successful_count,
            "failed": self.failed_count,
            "has_failures": self.has_failures,
            "events": [
                event.to_dict()
                for event in self.events
            ],
        }

    def _count_status(
        self,
        status: CleanupExecutionEventStatus,
    ) -> int:
        """Count events with one status."""

        return sum(
            1
            for event in self.events
            if event.status is status
        )


def _required_text(
    value: object,
    field_name: str,
) -> str:
    """Normalize and validate required text."""

    if not isinstance(value, str):
        raise CleanupHistoryError(
            f"{field_name} must be a string"
        )

    normalized = value.strip()

    if not normalized:
        raise CleanupHistoryError(
            f"{field_name} must not be empty"
        )

    return normalized


def _normalize_status(
    value: CleanupExecutionEventStatus | str,
) -> CleanupExecutionEventStatus:
    """Normalize one execution-event status."""

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
        raise CleanupHistoryError(
            f"invalid cleanup execution event status: {value}"
        ) from exc


def _timestamp(value: datetime) -> str:
    """Serialize a normalized datetime as UTC ISO-8601."""

    return (
        value.isoformat()
        .replace("+00:00", "Z")
    )
