"""Cleanup execution contracts for Project Atlas."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from atlas.cleanup.execution_identity import (
    normalize_execution_id,
)
from atlas.cleanup.execution_models import CleanupExecutionMode
from atlas.cleanup.execution_models import CleanupExecutionReport


class CleanupExecutionError(RuntimeError):
    """Raised when cleanup execution cannot be completed."""


class CleanupRunStatus(str, Enum):
    """Overall execution result."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class CleanupExecutionSummary:
    """Summary produced by a cleanup executor."""

    execution_id: str
    provider: str
    mode: CleanupExecutionMode
    status: CleanupRunStatus

    started_at: str
    completed_at: str

    total: int
    planned: int
    skipped: int
    modified: int

    errors: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        try:
            execution_id = normalize_execution_id(
                self.execution_id
            )
        except ValueError as exc:
            raise CleanupExecutionError(str(exc)) from exc

        provider = _required_text(
            self.provider,
            "provider",
        ).lower()

        object.__setattr__(
            self,
            "execution_id",
            execution_id,
        )
        object.__setattr__(self, "provider", provider)

        if not isinstance(
            self.mode,
            CleanupExecutionMode,
        ):
            raise CleanupExecutionError(
                "mode must be a CleanupExecutionMode"
            )

        if not isinstance(
            self.status,
            CleanupRunStatus,
        ):
            raise CleanupExecutionError(
                "status must be a CleanupRunStatus"
            )

        object.__setattr__(
            self,
            "started_at",
            _required_timestamp(
                self.started_at,
                "started_at",
            ),
        )

        object.__setattr__(
            self,
            "completed_at",
            _required_timestamp(
                self.completed_at,
                "completed_at",
            ),
        )

        for field_name in (
            "total",
            "planned",
            "skipped",
            "modified",
        ):
            value = getattr(self, field_name)

            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                raise CleanupExecutionError(
                    f"{field_name} must be a non-negative integer"
                )

        if self.planned + self.skipped != self.total:
            raise CleanupExecutionError(
                "planned + skipped must equal total"
            )

        if self.modified > self.planned:
            raise CleanupExecutionError(
                "modified cannot exceed planned"
            )

        normalized_errors: list[str] = []

        for error in self.errors:
            normalized_errors.append(
                _required_text(
                    error,
                    "error",
                )
            )

        normalized_errors_tuple = tuple(normalized_errors)

        if (
            self.status is CleanupRunStatus.SUCCESS
            and normalized_errors_tuple
        ):
            raise CleanupExecutionError(
                "successful execution cannot contain errors"
            )

        if (
            self.status
            in {
                CleanupRunStatus.PARTIAL,
                CleanupRunStatus.FAILED,
            }
            and not normalized_errors_tuple
        ):
            raise CleanupExecutionError(
                f"{self.status.value} execution must contain "
                "at least one error"
            )

        object.__setattr__(
            self,
            "errors",
            normalized_errors_tuple,
        )

    @property
    def successful(self) -> bool:
        """Return True when execution succeeded."""

        return self.status is CleanupRunStatus.SUCCESS

    @property
    def failed(self) -> bool:
        """Return True when execution failed."""

        return self.status is CleanupRunStatus.FAILED

    def to_dict(self) -> dict[str, Any]:
        """Serialize the summary."""

        return {
            "execution_id": self.execution_id,
            "provider": self.provider,
            "mode": self.mode.value,
            "status": self.status.value,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total": self.total,
            "planned": self.planned,
            "skipped": self.skipped,
            "modified": self.modified,
            "errors": list(self.errors),
        }


class CleanupExecutor(ABC):
    """Abstract cleanup execution engine."""

    @abstractmethod
    def execute(
        self,
        report: CleanupExecutionReport,
    ) -> CleanupExecutionSummary:
        """Execute a cleanup plan."""
        raise NotImplementedError


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CleanupExecutionError(
            f"{field_name} is required"
        )

    return value.strip()


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CleanupExecutionError(
            f"{field_name} is required"
        )

    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as exc:
        raise CleanupExecutionError(
            f"{field_name} must be an ISO-8601 timestamp"
        ) from exc

    if parsed.tzinfo is None:
        raise CleanupExecutionError(
            f"{field_name} must include a timezone"
        )

    return (
        parsed.astimezone(
            timezone.utc,
        )
        .isoformat()
        .replace("+00:00", "Z")
    )
