"""Immutable restart-recovery contracts for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from .models import (
    ManagedService,
    ServiceHealth,
    ServiceLifecycleError,
    ServiceRuntime,
)


class ServiceRecoveryStatus(str, Enum):
    """Normalized restart-recovery outcomes."""

    NOT_OBSERVED = "not-observed"
    RECOVERING = "recovering"
    RECOVERED = "recovered"
    DEGRADED = "degraded"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ServiceRecoveryObservation:
    """One normalized observation of a managed service."""

    service: ManagedService
    runtime: ServiceRuntime
    health: ServiceHealth
    observed_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        if not isinstance(self.service, ManagedService):
            raise ServiceLifecycleError(
                "service must be a ManagedService",
            )
        if not isinstance(self.runtime, ServiceRuntime):
            raise ServiceLifecycleError(
                "runtime must be a ServiceRuntime",
            )
        if not isinstance(self.health, ServiceHealth):
            raise ServiceLifecycleError(
                "health must be a ServiceHealth",
            )

        _validate_health_identity(
            service=self.service,
            health=self.health,
        )

        object.__setattr__(
            self,
            "observed_at",
            _required_timestamp(
                self.observed_at,
                "observed_at",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized recovery observation."""

        return {
            "service": self.service.to_dict(),
            "runtime": self.runtime.to_dict(),
            "health": self.health.to_dict(),
            "observed_at": self.observed_at,
        }


@dataclass(frozen=True, slots=True)
class ServiceRecoveryResult:
    """One deterministic comparison of recovery observations."""

    before: ServiceRecoveryObservation
    after: ServiceRecoveryObservation
    status: ServiceRecoveryStatus | str
    reason: str
    warnings: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    evaluated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        if not isinstance(self.before, ServiceRecoveryObservation):
            raise ServiceLifecycleError(
                "before must be a ServiceRecoveryObservation",
            )
        if not isinstance(self.after, ServiceRecoveryObservation):
            raise ServiceLifecycleError(
                "after must be a ServiceRecoveryObservation",
            )

        _validate_observation_identity(
            before=self.before,
            after=self.after,
        )

        if _parse_timestamp(self.after.observed_at) < _parse_timestamp(
            self.before.observed_at,
        ):
            raise ServiceLifecycleError(
                "after observation must not precede before observation",
            )

        status = _normalize_status(self.status, "status")
        reason = _required_text(self.reason, "reason")
        warnings = _normalize_text_collection(
            self.warnings,
            "warnings",
        )
        errors = _normalize_text_collection(
            self.errors,
            "errors",
        )
        evaluated_at = _required_timestamp(
            self.evaluated_at,
            "evaluated_at",
        )

        if _parse_timestamp(evaluated_at) < _parse_timestamp(
            self.after.observed_at,
        ):
            raise ServiceLifecycleError(
                "evaluated_at must not precede the after observation",
            )

        if status is ServiceRecoveryStatus.RECOVERED and errors:
            raise ServiceLifecycleError(
                "recovered results must not contain errors",
            )

        object.__setattr__(self, "status", status)
        object.__setattr__(self, "reason", reason)
        object.__setattr__(self, "warnings", warnings)
        object.__setattr__(self, "errors", errors)
        object.__setattr__(self, "evaluated_at", evaluated_at)

    @property
    def service_identifier(self) -> str:
        """Return the stable compared service identity."""

        return self.after.service.identifier

    @property
    def restart_count_delta(self) -> int:
        """Return the signed restart-count change."""

        return (
            self.after.runtime.restart_count
            - self.before.runtime.restart_count
        )

    @property
    def start_time_advanced(self) -> bool:
        """Return whether both timestamps show a later start."""

        before_started = self.before.runtime.started_at
        after_started = self.after.runtime.started_at

        if before_started is None or after_started is None:
            return False

        return _parse_timestamp(after_started) > _parse_timestamp(
            before_started,
        )

    @property
    def restart_observed(self) -> bool:
        """Return whether normalized evidence shows a restart."""

        return self.restart_count_delta > 0 or self.start_time_advanced

    @property
    def passed(self) -> bool:
        """Return whether recovery is explicitly successful."""

        return (
            self.status is ServiceRecoveryStatus.RECOVERED
            and not self.errors
        )

    @property
    def requires_attention(self) -> bool:
        """Return whether the result needs operator attention."""

        return self.status in {
            ServiceRecoveryStatus.RECOVERING,
            ServiceRecoveryStatus.DEGRADED,
            ServiceRecoveryStatus.FAILED,
            ServiceRecoveryStatus.UNKNOWN,
        } or bool(self.errors)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized recovery result."""

        return {
            "service_identifier": self.service_identifier,
            "status": self.status.value,
            "reason": self.reason,
            "restart_observed": self.restart_observed,
            "restart_count_delta": self.restart_count_delta,
            "start_time_advanced": self.start_time_advanced,
            "passed": self.passed,
            "requires_attention": self.requires_attention,
            "warnings": list(self.warnings),
            "errors": list(self.errors),
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "evaluated_at": self.evaluated_at,
        }


def _validate_health_identity(
    *,
    service: ManagedService,
    health: ServiceHealth,
) -> None:
    value = health.details.get("service_identifier")

    if value is None:
        return

    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            "health service_identifier must be non-empty text",
        )

    if value.strip().casefold() != service.identifier:
        raise ServiceLifecycleError(
            "health service_identifier must match service identity",
        )


def _validate_observation_identity(
    *,
    before: ServiceRecoveryObservation,
    after: ServiceRecoveryObservation,
) -> None:
    if before.service.identifier != after.service.identifier:
        raise ServiceLifecycleError(
            "recovery observations must share a service identifier",
        )

    if before.service.provider != after.service.provider:
        raise ServiceLifecycleError(
            "recovery observations must share a provider",
        )


def _normalize_status(
    value: object,
    field_name: str,
) -> ServiceRecoveryStatus:
    if isinstance(value, ServiceRecoveryStatus):
        return value

    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be a supported recovery status",
        )

    try:
        return ServiceRecoveryStatus(
            value.strip().casefold().replace("_", "-"),
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be a supported recovery status",
        ) from exc


def _normalize_text_collection(
    values: object,
    field_name: str,
) -> tuple[str, ...]:
    if values is None:
        return ()

    if (
        isinstance(values, (str, bytes))
        or not isinstance(values, Iterable)
    ):
        raise ServiceLifecycleError(
            f"{field_name} must be a collection",
        )

    return tuple(
        sorted(
            {
                _required_text(value, f"{field_name} value")
                for value in values
            }
        )
    )


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} is required",
        )
    return value.strip()


def _required_timestamp(value: object, field_name: str) -> str:
    normalized = _required_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(
            normalized.replace("Z", "+00:00"),
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be a valid timestamp",
        ) from exc
    if parsed.tzinfo is None:
        raise ServiceLifecycleError(
            f"{field_name} must include a timezone",
        )
    return parsed.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
