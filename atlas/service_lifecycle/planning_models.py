"""Guarded Service Lifecycle update-planning contracts."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import re
from typing import Any

from .models import ServiceLifecycleError
from .update_models import ImageReference


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


class ServiceUpdateOutcome(str, Enum):
    """Normalized outcome for a guarded lifecycle update."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled-back"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class ServiceUpdatePlan:
    """Immutable dry-run plan for one allow-listed managed service."""

    plan_id: str
    service_identifier: str
    service_name: str
    current_image: ImageReference
    target_image: ImageReference
    requested_by: str
    dependencies: tuple[str, ...] = ()
    dry_run: bool = True
    created_at: str = field(default_factory=lambda: _now_timestamp())
    correlation_id: str | None = None
    warnings: tuple[str, ...] = ()
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "plan_id",
            _required_identifier(self.plan_id, "plan_id"),
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
            "service_name",
            _required_text(self.service_name, "service_name"),
        )
        object.__setattr__(
            self,
            "requested_by",
            _required_text(self.requested_by, "requested_by"),
        )

        if not isinstance(self.current_image, ImageReference):
            raise ServiceLifecycleError(
                "current_image must be an ImageReference",
            )

        if not isinstance(self.target_image, ImageReference):
            raise ServiceLifecycleError(
                "target_image must be an ImageReference",
            )

        if self.current_image.canonical_reference == (
            self.target_image.canonical_reference
        ):
            raise ServiceLifecycleError(
                "target_image must differ from current_image",
            )

        if self.dry_run is not True:
            raise ServiceLifecycleError(
                "ServiceUpdatePlan must be dry-run",
            )

        object.__setattr__(
            self,
            "dependencies",
            _normalize_identifiers(
                self.dependencies,
                "dependencies",
            ),
        )
        object.__setattr__(
            self,
            "created_at",
            _required_timestamp(self.created_at, "created_at"),
        )
        object.__setattr__(
            self,
            "correlation_id",
            _optional_identifier(
                self.correlation_id,
                "correlation_id",
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

        if not isinstance(self.details, Mapping):
            raise ServiceLifecycleError(
                "details must be an object",
            )

        object.__setattr__(
            self,
            "details",
            dict(self.details),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized update-plan contract."""

        return {
            "plan_id": self.plan_id,
            "service_identifier": self.service_identifier,
            "service_name": self.service_name,
            "current_image": self.current_image.to_dict(),
            "target_image": self.target_image.to_dict(),
            "requested_by": self.requested_by,
            "dependencies": list(self.dependencies),
            "dry_run": self.dry_run,
            "created_at": self.created_at,
            "correlation_id": self.correlation_id,
            "warnings": list(self.warnings),
            "details": dict(self.details),
        }


@dataclass(frozen=True)
class ServiceUpdateResult:
    """Normalized result for one guarded lifecycle update operation."""

    operation_id: str
    plan_id: str
    service_identifier: str
    service_name: str
    outcome: ServiceUpdateOutcome
    previous_image: ImageReference
    resulting_image: ImageReference | None
    started_at: str
    completed_at: str
    rollback_performed: bool = False
    rollback_operation_id: str | None = None
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    correlation_id: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "operation_id",
            _required_identifier(
                self.operation_id,
                "operation_id",
            ),
        )
        object.__setattr__(
            self,
            "plan_id",
            _required_identifier(self.plan_id, "plan_id"),
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
            "service_name",
            _required_text(self.service_name, "service_name"),
        )
        object.__setattr__(
            self,
            "outcome",
            _normalize_enum(
                self.outcome,
                ServiceUpdateOutcome,
                "outcome",
            ),
        )

        if not isinstance(self.previous_image, ImageReference):
            raise ServiceLifecycleError(
                "previous_image must be an ImageReference",
            )

        if (
            self.resulting_image is not None
            and not isinstance(self.resulting_image, ImageReference)
        ):
            raise ServiceLifecycleError(
                "resulting_image must be an ImageReference or null",
            )

        object.__setattr__(
            self,
            "started_at",
            _required_timestamp(self.started_at, "started_at"),
        )
        object.__setattr__(
            self,
            "completed_at",
            _required_timestamp(
                self.completed_at,
                "completed_at",
            ),
        )

        if _parse_timestamp(self.completed_at) < (
            _parse_timestamp(self.started_at)
        ):
            raise ServiceLifecycleError(
                "completed_at must not precede started_at",
            )

        if not isinstance(self.rollback_performed, bool):
            raise ServiceLifecycleError(
                "rollback_performed must be a boolean",
            )

        object.__setattr__(
            self,
            "rollback_operation_id",
            _optional_identifier(
                self.rollback_operation_id,
                "rollback_operation_id",
            ),
        )

        if (
            self.rollback_operation_id is not None
            and not self.rollback_performed
        ):
            raise ServiceLifecycleError(
                "rollback_operation_id requires rollback_performed",
            )

        if (
            self.outcome is ServiceUpdateOutcome.ROLLED_BACK
            and not self.rollback_performed
        ):
            raise ServiceLifecycleError(
                "rolled-back outcome requires rollback_performed",
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
        object.__setattr__(
            self,
            "correlation_id",
            _optional_identifier(
                self.correlation_id,
                "correlation_id",
            ),
        )

        if not isinstance(self.details, Mapping):
            raise ServiceLifecycleError(
                "details must be an object",
            )

        object.__setattr__(
            self,
            "details",
            dict(self.details),
        )

    @property
    def succeeded(self) -> bool:
        return self.outcome is ServiceUpdateOutcome.SUCCEEDED

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized update-result contract."""

        return {
            "operation_id": self.operation_id,
            "plan_id": self.plan_id,
            "service_identifier": self.service_identifier,
            "service_name": self.service_name,
            "outcome": self.outcome.value,
            "succeeded": self.succeeded,
            "previous_image": self.previous_image.to_dict(),
            "resulting_image": (
                self.resulting_image.to_dict()
                if self.resulting_image is not None
                else None
            ),
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "rollback_performed": self.rollback_performed,
            "rollback_operation_id": self.rollback_operation_id,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "correlation_id": self.correlation_id,
            "details": dict(self.details),
        }


def _normalize_identifiers(
    values: Iterable[str],
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ServiceLifecycleError(
            f"{field_name} must be a collection",
        )

    try:
        items = tuple(values)
    except TypeError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be a collection",
        ) from exc

    normalized = tuple(
        _required_identifier(value, field_name)
        for value in items
    )

    if len(normalized) != len(set(normalized)):
        raise ServiceLifecycleError(
            f"{field_name} must not contain duplicates",
        )

    return normalized


def _normalize_text_collection(
    values: Iterable[str],
    field_name: str,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ServiceLifecycleError(
            f"{field_name} must be a collection",
        )

    try:
        items = tuple(values)
    except TypeError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be a collection",
        ) from exc

    return tuple(
        _required_text(value, field_name)
        for value in items
    )


def _normalize_enum(
    value: object,
    enum_type: type[Enum],
    field_name: str,
) -> Enum:
    if isinstance(value, enum_type):
        return value

    normalized = _required_text(
        value,
        field_name,
    ).casefold()

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
    normalized = _required_text(
        value,
        field_name,
    ).casefold()

    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ServiceLifecycleError(
            f"invalid {field_name}: {normalized}",
        )

    return normalized


def _optional_identifier(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_identifier(value, field_name)


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be non-empty text",
        )

    return value.strip()


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(value, field_name)

    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00"),
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
