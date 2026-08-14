"""Normalized maintenance-history contracts for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import re
from typing import Any

from .models import ServiceLifecycleError


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


class MaintenanceAction(str, Enum):
    """Normalized maintenance or observation action."""

    NONE = "none"
    INSPECTION = "inspection"
    HEALTH_CHECK = "health-check"
    UPDATE_CHECK = "update-check"
    BACKUP = "backup"
    PULL = "pull"
    RESTART = "restart"
    STOP = "stop"
    START = "start"
    ROLLBACK = "rollback"
    OTHER = "other"


class MaintenanceResult(str, Enum):
    """Normalized maintenance outcome."""

    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"
    SKIPPED = "skipped"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class MaintenanceRecord:
    """One immutable maintenance-history record."""

    service_identifier: str
    service_name: str
    action: MaintenanceAction
    result: MaintenanceResult
    started_at: str
    completed_at: str | None = None
    provider: str = "unknown"
    summary: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        service_identifier = _required_identifier(
            self.service_identifier,
            "service_identifier",
        )
        service_name = _required_text(
            self.service_name,
            "service_name",
        )
        action = _normalize_enum(
            self.action,
            MaintenanceAction,
            "action",
        )
        result = _normalize_enum(
            self.result,
            MaintenanceResult,
            "result",
        )
        provider = _required_identifier(
            self.provider,
            "provider",
        )
        started_at = _required_timestamp(
            self.started_at,
            "started_at",
        )
        completed_at = _optional_timestamp(
            self.completed_at,
            "completed_at",
        )
        summary = _optional_text(self.summary, "summary")

        if not isinstance(self.details, Mapping):
            raise ServiceLifecycleError("details must be an object")

        if completed_at is not None:
            started = _parse_timestamp(started_at)
            completed = _parse_timestamp(completed_at)
            if completed < started:
                raise ServiceLifecycleError(
                    "completed_at must not be before started_at",
                )

        object.__setattr__(
            self,
            "service_identifier",
            service_identifier,
        )
        object.__setattr__(self, "service_name", service_name)
        object.__setattr__(self, "action", action)
        object.__setattr__(self, "result", result)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "started_at", started_at)
        object.__setattr__(self, "completed_at", completed_at)
        object.__setattr__(self, "summary", summary)
        object.__setattr__(self, "details", dict(self.details))

    @property
    def duration_seconds(self) -> float | None:
        """Return elapsed seconds when the record is complete."""

        if self.completed_at is None:
            return None

        return (
            _parse_timestamp(self.completed_at)
            - _parse_timestamp(self.started_at)
        ).total_seconds()

    @property
    def succeeded(self) -> bool:
        """Return whether the record completed successfully."""

        return self.result is MaintenanceResult.SUCCESS

    @property
    def failed(self) -> bool:
        """Return whether the record represents a failed outcome."""

        return self.result is MaintenanceResult.FAILED

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized maintenance record."""

        return {
            "service_identifier": self.service_identifier,
            "service_name": self.service_name,
            "provider": self.provider,
            "action": self.action.value,
            "result": self.result.value,
            "succeeded": self.succeeded,
            "failed": self.failed,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "duration_seconds": self.duration_seconds,
            "summary": self.summary,
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class MaintenanceReport:
    """Deterministic aggregate maintenance-history report."""

    records: tuple[MaintenanceRecord, ...] = ()
    provider: str = "unknown"
    generated_at: str = field(
        default_factory=lambda: _now_timestamp(),
    )

    def __post_init__(self) -> None:
        records = _normalize_records(self.records)
        provider = _required_identifier(
            self.provider,
            "provider",
        )
        generated_at = _required_timestamp(
            self.generated_at,
            "generated_at",
        )

        object.__setattr__(self, "records", records)
        object.__setattr__(self, "provider", provider)
        object.__setattr__(self, "generated_at", generated_at)

    @property
    def counts(self) -> dict[str, int]:
        """Return deterministic counts by maintenance result."""

        counts = {
            result.value: 0
            for result in MaintenanceResult
        }
        for record in self.records:
            counts[record.result.value] += 1
        return counts

    @property
    def latest_record(self) -> MaintenanceRecord | None:
        """Return the most recent maintenance record."""

        return self.records[0] if self.records else None

    @property
    def latest_success(self) -> MaintenanceRecord | None:
        """Return the most recent successful record."""

        return next(
            (
                record
                for record in self.records
                if record.result is MaintenanceResult.SUCCESS
            ),
            None,
        )

    @property
    def latest_failure(self) -> MaintenanceRecord | None:
        """Return the most recent failed record."""

        return next(
            (
                record
                for record in self.records
                if record.result is MaintenanceResult.FAILED
            ),
            None,
        )

    @property
    def requires_attention(self) -> bool:
        """Return whether any failed or partial records exist."""

        return any(
            record.result in {
                MaintenanceResult.FAILED,
                MaintenanceResult.PARTIAL,
            }
            for record in self.records
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the maintenance-history report."""

        return {
            "provider": self.provider,
            "generated_at": self.generated_at,
            "total_records": len(self.records),
            "counts": self.counts,
            "requires_attention": self.requires_attention,
            "latest_record": (
                self.latest_record.to_dict()
                if self.latest_record is not None
                else None
            ),
            "latest_success": (
                self.latest_success.to_dict()
                if self.latest_success is not None
                else None
            ),
            "latest_failure": (
                self.latest_failure.to_dict()
                if self.latest_failure is not None
                else None
            ),
            "records": [
                record.to_dict()
                for record in self.records
            ],
        }


def _normalize_records(
    value: object,
) -> tuple[MaintenanceRecord, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(
        value,
        Iterable,
    ):
        raise ServiceLifecycleError(
            "records must be a collection of MaintenanceRecord objects",
        )

    records = tuple(value)
    if any(
        not isinstance(record, MaintenanceRecord)
        for record in records
    ):
        raise ServiceLifecycleError(
            "records must contain MaintenanceRecord objects",
        )

    return tuple(
        sorted(
            records,
            key=lambda record: (
                _parse_timestamp(record.started_at),
                record.service_identifier,
                record.action.value,
            ),
            reverse=True,
        )
    )


def _normalize_enum(
    value: object,
    enum_type: type[Enum],
    field_name: str,
) -> Enum:
    if isinstance(value, enum_type):
        return value

    normalized = _required_text(value, field_name).casefold()
    try:
        return enum_type(normalized)
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"invalid {field_name}: {normalized}",
        ) from exc


def _required_identifier(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(value, field_name).casefold()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ServiceLifecycleError(
            f"invalid {field_name}: {normalized}",
        )
    return normalized


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be non-empty text",
        )
    return value.strip()


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _required_text(value, field_name)


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    return _normalize_timestamp(
        _required_text(value, field_name),
        field_name,
    )


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None
    return _required_timestamp(value, field_name)


def _normalize_timestamp(
    value: str,
    field_name: str,
) -> str:
    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00"),
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise ServiceLifecycleError(
            f"{field_name} must include a timezone",
        )

    return (
        parsed.astimezone(UTC)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00"),
    )


def _now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class MaintenanceEvent:
    """Auditable lifecycle mutation event defined by ADR 0010."""

    event_id: str
    service_identifier: str
    operation_type: str
    requested_by: str
    started_at: str
    completed_at: str | None
    previous_state: Mapping[str, Any]
    resulting_state: Mapping[str, Any] | None
    outcome: MaintenanceResult
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    rollback_information: Mapping[str, Any] = field(
        default_factory=dict,
    )
    correlation_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "event_id",
            _required_identifier(self.event_id, "event_id"),
        )
        object.__setattr__(
            self,
            "service_identifier",
            _required_identifier(
                self.service_identifier,
                "service_identifier",
            ),
        )
        object.__setattr__(
            self,
            "operation_type",
            _required_identifier(
                self.operation_type,
                "operation_type",
            ),
        )
        object.__setattr__(
            self,
            "requested_by",
            _required_text(self.requested_by, "requested_by"),
        )
        object.__setattr__(
            self,
            "started_at",
            _required_timestamp(self.started_at, "started_at"),
        )
        object.__setattr__(
            self,
            "completed_at",
            _optional_timestamp(
                self.completed_at,
                "completed_at",
            ),
        )

        if (
            self.completed_at is not None
            and _parse_timestamp(self.completed_at)
            < _parse_timestamp(self.started_at)
        ):
            raise ServiceLifecycleError(
                "completed_at must not precede started_at",
            )

        if not isinstance(self.previous_state, Mapping):
            raise ServiceLifecycleError(
                "previous_state must be an object",
            )

        if (
            self.resulting_state is not None
            and not isinstance(self.resulting_state, Mapping)
        ):
            raise ServiceLifecycleError(
                "resulting_state must be an object or null",
            )

        object.__setattr__(
            self,
            "previous_state",
            dict(self.previous_state),
        )
        object.__setattr__(
            self,
            "resulting_state",
            (
                dict(self.resulting_state)
                if self.resulting_state is not None
                else None
            ),
        )
        object.__setattr__(
            self,
            "outcome",
            _normalize_enum(
                self.outcome,
                MaintenanceResult,
                "outcome",
            ),
        )
        object.__setattr__(
            self,
            "warnings",
            _normalize_text_collection(
                self.warnings,
                "warnings",
            ),
        )
        object.__setattr__(
            self,
            "errors",
            _normalize_text_collection(
                self.errors,
                "errors",
            ),
        )

        if not isinstance(self.rollback_information, Mapping):
            raise ServiceLifecycleError(
                "rollback_information must be an object",
            )

        object.__setattr__(
            self,
            "rollback_information",
            dict(self.rollback_information),
        )
        object.__setattr__(
            self,
            "correlation_id",
            (
                None
                if self.correlation_id is None
                else _required_identifier(
                    self.correlation_id,
                    "correlation_id",
                )
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized maintenance-event contract."""

        return {
            "event_id": self.event_id,
            "service_identifier": self.service_identifier,
            "operation_type": self.operation_type,
            "requested_by": self.requested_by,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "previous_state": dict(self.previous_state),
            "resulting_state": (
                dict(self.resulting_state)
                if self.resulting_state is not None
                else None
            ),
            "outcome": self.outcome.value,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "rollback_information": dict(
                self.rollback_information,
            ),
            "correlation_id": self.correlation_id,
        }


def _normalize_text_collection(
    values: Iterable[str],
    field_name: str,
) -> tuple[str, ...]:
    """Normalize one immutable collection of non-empty text values."""

    if isinstance(values, (str, bytes)) or not isinstance(
        values,
        Iterable,
    ):
        raise ServiceLifecycleError(
            f"{field_name} must be a collection",
        )

    return tuple(
        _required_text(value, field_name)
        for value in values
    )
