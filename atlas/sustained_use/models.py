"""Sustained-use release-certification domain contracts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final, Mapping


SCHEMA_VERSION: Final = 1

DEFAULT_DURATION_SECONDS: Final = 48 * 60 * 60
DEFAULT_INTERVAL_SECONDS: Final = 15 * 60
DEFAULT_EXPECTED_RUNNING_CONTAINERS: Final = 22


class SustainedUseModelError(ValueError):
    """Raised when a sustained-use model violates its contract."""


def _positive_integer(
    value: object,
    *,
    field: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SustainedUseModelError(
            f"{field} must be an integer",
        )

    if value <= 0:
        raise SustainedUseModelError(
            f"{field} must be greater than zero",
        )

    return value


def _git_commit(value: object) -> str:
    if not isinstance(value, str):
        raise SustainedUseModelError(
            "git_commit must be a string",
        )

    normalized = value.strip().lower()

    if len(normalized) != 40:
        raise SustainedUseModelError(
            "git_commit must be a 40-character hexadecimal SHA",
        )

    if any(
        character not in "0123456789abcdef"
        for character in normalized
    ):
        raise SustainedUseModelError(
            "git_commit must be a 40-character hexadecimal SHA",
        )

    return normalized


@dataclass(frozen=True)
class SustainedUseContract:
    """Frozen execution policy for one Q.6 sustained-use run."""

    git_commit: str
    duration_seconds: int = DEFAULT_DURATION_SECONDS
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS
    expected_running_containers: int = (
        DEFAULT_EXPECTED_RUNNING_CONTAINERS
    )
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        commit = _git_commit(self.git_commit)

        duration = _positive_integer(
            self.duration_seconds,
            field="duration_seconds",
        )

        interval = _positive_integer(
            self.interval_seconds,
            field="interval_seconds",
        )

        expected = _positive_integer(
            self.expected_running_containers,
            field="expected_running_containers",
        )

        if duration % interval != 0:
            raise SustainedUseModelError(
                "duration_seconds must be evenly divisible "
                "by interval_seconds",
            )

        if self.schema_version != SCHEMA_VERSION:
            raise SustainedUseModelError(
                f"schema_version must equal {SCHEMA_VERSION}",
            )

        object.__setattr__(self, "git_commit", commit)
        object.__setattr__(self, "duration_seconds", duration)
        object.__setattr__(self, "interval_seconds", interval)
        object.__setattr__(
            self,
            "expected_running_containers",
            expected,
        )

    @property
    def expected_sample_count(self) -> int:
        """Return T0 + cadence observations through final endpoint."""

        return (
            self.duration_seconds // self.interval_seconds
        ) + 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize the deterministic public contract."""

        return {
            "schema_version": self.schema_version,
            "git_commit": self.git_commit,
            "duration_seconds": self.duration_seconds,
            "interval_seconds": self.interval_seconds,
            "expected_running_containers": (
                self.expected_running_containers
            ),
            "expected_sample_count": self.expected_sample_count,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "SustainedUseContract":
        """Normalize and validate a serialized contract."""

        if not isinstance(value, Mapping):
            raise SustainedUseModelError(
                "SustainedUseContract payload must be an object",
            )

        return cls(
            git_commit=value.get("git_commit"),
            duration_seconds=value.get(
                "duration_seconds",
                DEFAULT_DURATION_SECONDS,
            ),
            interval_seconds=value.get(
                "interval_seconds",
                DEFAULT_INTERVAL_SECONDS,
            ),
            expected_running_containers=value.get(
                "expected_running_containers",
                DEFAULT_EXPECTED_RUNNING_CONTAINERS,
            ),
            schema_version=value.get(
                "schema_version",
                SCHEMA_VERSION,
            ),
        )


_CONTAINER_HEALTH_VALUES: Final = frozenset(
    {
        "healthy",
        "unhealthy",
        "starting",
        "none",
        "unknown",
    }
)


def _non_negative_integer(
    value: object,
    *,
    field: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SustainedUseModelError(
            f"{field} must be an integer",
        )

    if value < 0:
        raise SustainedUseModelError(
            f"{field} cannot be negative",
        )

    return value


def _timestamp(
    value: object,
    *,
    field: str,
) -> str:
    from datetime import datetime, timezone

    if not isinstance(value, str):
        raise SustainedUseModelError(
            f"{field} must be a string",
        )

    normalized = value.strip()

    if not normalized:
        raise SustainedUseModelError(
            f"{field} cannot be empty",
        )

    candidate = normalized

    if candidate.endswith("Z"):
        candidate = candidate[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as error:
        raise SustainedUseModelError(
            f"{field} must be an ISO-8601 timestamp",
        ) from error

    if parsed.tzinfo is None:
        raise SustainedUseModelError(
            f"{field} must include a timezone",
        )

    return (
        parsed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


@dataclass(frozen=True)
class ContainerObservation:
    """One live Docker container observation."""

    name: str
    container_id: str
    status: str
    health: str
    restart_count: int
    oom_killed: bool
    started_at: str

    def __post_init__(self) -> None:
        for field in ("name", "container_id", "status", "health"):
            value = getattr(self, field)

            if not isinstance(value, str) or not value.strip():
                raise SustainedUseModelError(
                    f"{field} must be a non-empty string",
                )

        health = self.health.strip().lower()

        if health not in _CONTAINER_HEALTH_VALUES:
            raise SustainedUseModelError(
                "health must be one of: "
                + ", ".join(sorted(_CONTAINER_HEALTH_VALUES)),
            )

        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(
            self,
            "container_id",
            self.container_id.strip(),
        )
        object.__setattr__(
            self,
            "status",
            self.status.strip().lower(),
        )
        object.__setattr__(self, "health", health)
        object.__setattr__(
            self,
            "restart_count",
            _non_negative_integer(
                self.restart_count,
                field="restart_count",
            ),
        )

        if not isinstance(self.oom_killed, bool):
            raise SustainedUseModelError(
                "oom_killed must be a boolean",
            )

        object.__setattr__(
            self,
            "started_at",
            _timestamp(
                self.started_at,
                field="started_at",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "container_id": self.container_id,
            "status": self.status,
            "health": self.health,
            "restart_count": self.restart_count,
            "oom_killed": self.oom_killed,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "ContainerObservation":
        if not isinstance(value, Mapping):
            raise SustainedUseModelError(
                "ContainerObservation payload must be an object",
            )

        return cls(
            name=value.get("name"),
            container_id=value.get("container_id"),
            status=value.get("status"),
            health=value.get("health"),
            restart_count=value.get("restart_count"),
            oom_killed=value.get("oom_killed"),
            started_at=value.get("started_at"),
        )


@dataclass(frozen=True)
class RuntimeBusObservation:
    """Runtime Bus and Notifications subscriber observation."""

    journal_lines: int
    cursor_value: int
    journal_uid: int
    journal_gid: int
    journal_mode: int
    journal_readable: bool
    journal_writable: bool
    heartbeat_age_seconds: int

    def __post_init__(self) -> None:
        for field in (
            "journal_lines",
            "cursor_value",
            "journal_uid",
            "journal_gid",
            "journal_mode",
            "heartbeat_age_seconds",
        ):
            object.__setattr__(
                self,
                field,
                _non_negative_integer(
                    getattr(self, field),
                    field=field,
                ),
            )

        if self.cursor_value > self.journal_lines:
            raise SustainedUseModelError(
                "cursor_value cannot exceed journal_lines",
            )

        if not isinstance(self.journal_readable, bool):
            raise SustainedUseModelError(
                "journal_readable must be a boolean",
            )

        if not isinstance(self.journal_writable, bool):
            raise SustainedUseModelError(
                "journal_writable must be a boolean",
            )

    @property
    def backlog(self) -> int:
        """Return unconsumed Runtime Bus event count."""

        return self.journal_lines - self.cursor_value

    def to_dict(self) -> dict[str, Any]:
        return {
            "journal_lines": self.journal_lines,
            "cursor_value": self.cursor_value,
            "backlog": self.backlog,
            "journal_uid": self.journal_uid,
            "journal_gid": self.journal_gid,
            "journal_mode": self.journal_mode,
            "journal_readable": self.journal_readable,
            "journal_writable": self.journal_writable,
            "heartbeat_age_seconds": self.heartbeat_age_seconds,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "RuntimeBusObservation":
        if not isinstance(value, Mapping):
            raise SustainedUseModelError(
                "RuntimeBusObservation payload must be an object",
            )

        return cls(
            journal_lines=value.get("journal_lines"),
            cursor_value=value.get("cursor_value"),
            journal_uid=value.get("journal_uid"),
            journal_gid=value.get("journal_gid"),
            journal_mode=value.get("journal_mode"),
            journal_readable=value.get("journal_readable"),
            journal_writable=value.get("journal_writable"),
            heartbeat_age_seconds=value.get(
                "heartbeat_age_seconds",
            ),
        )


def _optional_timestamp(
    value: object,
    *,
    field: str,
) -> str | None:
    if value is None:
        return None

    return _timestamp(
        value,
        field=field,
    )


@dataclass(frozen=True)
class SchedulerObservation:
    """One Atlas scheduler task observation."""

    name: str
    enabled: bool
    status: str
    due: bool
    run_count: int
    failure_count: int
    last_success: str | None = None
    next_run: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise SustainedUseModelError(
                "name must be a non-empty string",
            )

        if not isinstance(self.enabled, bool):
            raise SustainedUseModelError(
                "enabled must be a boolean",
            )

        if not isinstance(self.status, str) or not self.status.strip():
            raise SustainedUseModelError(
                "status must be a non-empty string",
            )

        if not isinstance(self.due, bool):
            raise SustainedUseModelError(
                "due must be a boolean",
            )

        object.__setattr__(
            self,
            "name",
            self.name.strip(),
        )

        object.__setattr__(
            self,
            "status",
            self.status.strip().lower(),
        )

        object.__setattr__(
            self,
            "run_count",
            _non_negative_integer(
                self.run_count,
                field="run_count",
            ),
        )

        object.__setattr__(
            self,
            "failure_count",
            _non_negative_integer(
                self.failure_count,
                field="failure_count",
            ),
        )

        object.__setattr__(
            self,
            "last_success",
            _optional_timestamp(
                self.last_success,
                field="last_success",
            ),
        )

        object.__setattr__(
            self,
            "next_run",
            _optional_timestamp(
                self.next_run,
                field="next_run",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": self.enabled,
            "status": self.status,
            "due": self.due,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "last_success": self.last_success,
            "next_run": self.next_run,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "SchedulerObservation":
        if not isinstance(value, Mapping):
            raise SustainedUseModelError(
                "SchedulerObservation payload must be an object",
            )

        return cls(
            name=value.get("name"),
            enabled=value.get("enabled"),
            status=value.get("status"),
            due=value.get("due"),
            run_count=value.get("run_count"),
            failure_count=value.get("failure_count"),
            last_success=value.get("last_success"),
            next_run=value.get("next_run"),
        )


def _percentage(
    value: object,
    *,
    field: str,
) -> int:
    normalized = _non_negative_integer(
        value,
        field=field,
    )

    if normalized > 100:
        raise SustainedUseModelError(
            f"{field} cannot exceed 100",
        )

    return normalized


@dataclass(frozen=True)
class AriObservation:
    """Minimal ARI state required by Q.6 certification."""

    status: str
    score: int
    warnings: tuple[str, ...]
    tv_filesystem_count: int | None = None
    tv_jellyfin_count: int | None = None

    def __post_init__(self) -> None:
        if (
            not isinstance(self.status, str)
            or not self.status.strip()
        ):
            raise SustainedUseModelError(
                "status must be a non-empty string",
            )

        object.__setattr__(
            self,
            "status",
            self.status.strip().lower(),
        )

        object.__setattr__(
            self,
            "score",
            _percentage(
                self.score,
                field="score",
            ),
        )

        if not isinstance(self.warnings, tuple):
            raise SustainedUseModelError(
                "warnings must be a tuple",
            )

        normalized_warnings: list[str] = []

        for warning in self.warnings:
            if (
                not isinstance(warning, str)
                or not warning.strip()
            ):
                raise SustainedUseModelError(
                    "warnings must contain non-empty strings",
                )

            normalized_warnings.append(
                warning.strip(),
            )

        object.__setattr__(
            self,
            "warnings",
            tuple(normalized_warnings),
        )

        for field in (
            "tv_filesystem_count",
            "tv_jellyfin_count",
        ):
            value = getattr(self, field)

            if value is None:
                continue

            object.__setattr__(
                self,
                field,
                _non_negative_integer(
                    value,
                    field=field,
                ),
            )

    @property
    def tv_synchronized(self) -> bool | None:
        """Return TV sync state when both counts are available."""

        if (
            self.tv_filesystem_count is None
            or self.tv_jellyfin_count is None
        ):
            return None

        return (
            self.tv_filesystem_count
            == self.tv_jellyfin_count
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "score": self.score,
            "warnings": list(self.warnings),
            "tv_filesystem_count": self.tv_filesystem_count,
            "tv_jellyfin_count": self.tv_jellyfin_count,
            "tv_synchronized": self.tv_synchronized,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "AriObservation":
        if not isinstance(value, Mapping):
            raise SustainedUseModelError(
                "AriObservation payload must be an object",
            )

        warnings = value.get("warnings")

        if not isinstance(warnings, list):
            raise SustainedUseModelError(
                "warnings must be an array",
            )

        return cls(
            status=value.get("status"),
            score=value.get("score"),
            warnings=tuple(warnings),
            tv_filesystem_count=value.get(
                "tv_filesystem_count",
            ),
            tv_jellyfin_count=value.get(
                "tv_jellyfin_count",
            ),
        )


@dataclass(frozen=True)
class SustainedUseSample:
    """One immutable Q.6 sustained-use observation."""

    generated_at: str
    git_commit: str
    atlas_health_status: str
    atlas_health_score: int
    running_containers: int
    unhealthy_containers: int
    root_usage_percent: int
    storage_usage_percent: int
    containers: tuple[ContainerObservation, ...]
    schedulers: tuple[SchedulerObservation, ...]
    runtime_bus: RuntimeBusObservation
    ari: AriObservation
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "generated_at",
            _timestamp(
                self.generated_at,
                field="generated_at",
            ),
        )

        object.__setattr__(
            self,
            "git_commit",
            _git_commit(self.git_commit),
        )

        if (
            not isinstance(self.atlas_health_status, str)
            or not self.atlas_health_status.strip()
        ):
            raise SustainedUseModelError(
                "atlas_health_status must be a non-empty string",
            )

        object.__setattr__(
            self,
            "atlas_health_status",
            self.atlas_health_status.strip().lower(),
        )

        object.__setattr__(
            self,
            "atlas_health_score",
            _percentage(
                self.atlas_health_score,
                field="atlas_health_score",
            ),
        )

        object.__setattr__(
            self,
            "running_containers",
            _non_negative_integer(
                self.running_containers,
                field="running_containers",
            ),
        )

        object.__setattr__(
            self,
            "unhealthy_containers",
            _non_negative_integer(
                self.unhealthy_containers,
                field="unhealthy_containers",
            ),
        )

        object.__setattr__(
            self,
            "root_usage_percent",
            _percentage(
                self.root_usage_percent,
                field="root_usage_percent",
            ),
        )

        object.__setattr__(
            self,
            "storage_usage_percent",
            _percentage(
                self.storage_usage_percent,
                field="storage_usage_percent",
            ),
        )

        if not isinstance(self.containers, tuple):
            raise SustainedUseModelError(
                "containers must be a tuple",
            )

        if not all(
            isinstance(item, ContainerObservation)
            for item in self.containers
        ):
            raise SustainedUseModelError(
                "containers must contain ContainerObservation values",
            )

        if not isinstance(self.schedulers, tuple):
            raise SustainedUseModelError(
                "schedulers must be a tuple",
            )

        if not all(
            isinstance(item, SchedulerObservation)
            for item in self.schedulers
        ):
            raise SustainedUseModelError(
                "schedulers must contain SchedulerObservation values",
            )

        if not isinstance(
            self.runtime_bus,
            RuntimeBusObservation,
        ):
            raise SustainedUseModelError(
                "runtime_bus must be a RuntimeBusObservation",
            )

        if not isinstance(self.ari, AriObservation):
            raise SustainedUseModelError(
                "ari must be an AriObservation",
            )

        if self.schema_version != SCHEMA_VERSION:
            raise SustainedUseModelError(
                f"schema_version must equal {SCHEMA_VERSION}",
            )

        container_names = tuple(
            item.name
            for item in self.containers
        )

        if len(container_names) != len(set(container_names)):
            raise SustainedUseModelError(
                "container names must be unique",
            )

        scheduler_names = tuple(
            item.name
            for item in self.schedulers
        )

        if len(scheduler_names) != len(set(scheduler_names)):
            raise SustainedUseModelError(
                "scheduler names must be unique",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generated_at": self.generated_at,
            "git_commit": self.git_commit,
            "atlas_health_status": self.atlas_health_status,
            "atlas_health_score": self.atlas_health_score,
            "running_containers": self.running_containers,
            "unhealthy_containers": self.unhealthy_containers,
            "root_usage_percent": self.root_usage_percent,
            "storage_usage_percent": self.storage_usage_percent,
            "containers": [
                item.to_dict()
                for item in self.containers
            ],
            "schedulers": [
                item.to_dict()
                for item in self.schedulers
            ],
            "runtime_bus": self.runtime_bus.to_dict(),
            "ari": self.ari.to_dict(),
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "SustainedUseSample":
        if not isinstance(value, Mapping):
            raise SustainedUseModelError(
                "SustainedUseSample payload must be an object",
            )

        containers = value.get("containers")
        schedulers = value.get("schedulers")
        runtime_bus = value.get("runtime_bus")
        ari = value.get("ari")

        if not isinstance(containers, list):
            raise SustainedUseModelError(
                "containers must be an array",
            )

        if not isinstance(schedulers, list):
            raise SustainedUseModelError(
                "schedulers must be an array",
            )

        if not isinstance(runtime_bus, Mapping):
            raise SustainedUseModelError(
                "runtime_bus must be an object",
            )

        if not isinstance(ari, Mapping):
            raise SustainedUseModelError(
                "ari must be an object",
            )

        return cls(
            generated_at=value.get("generated_at"),
            git_commit=value.get("git_commit"),
            atlas_health_status=value.get(
                "atlas_health_status",
            ),
            atlas_health_score=value.get(
                "atlas_health_score",
            ),
            running_containers=value.get(
                "running_containers",
            ),
            unhealthy_containers=value.get(
                "unhealthy_containers",
            ),
            root_usage_percent=value.get(
                "root_usage_percent",
            ),
            storage_usage_percent=value.get(
                "storage_usage_percent",
            ),
            containers=tuple(
                ContainerObservation.from_dict(item)
                for item in containers
            ),
            schedulers=tuple(
                SchedulerObservation.from_dict(item)
                for item in schedulers
            ),
            runtime_bus=RuntimeBusObservation.from_dict(
                runtime_bus,
            ),
            ari=AriObservation.from_dict(ari),
            schema_version=value.get(
                "schema_version",
                SCHEMA_VERSION,
            ),
        )


_SESSION_STATUSES: Final = frozenset(
    {
        "active",
        "completed",
        "failed",
        "aborted",
    }
)


@dataclass(frozen=True)
class SustainedUseSession:
    """Durable boundary for one Q.6 sustained-use certification run."""

    run_id: str
    git_commit: str
    started_at: str
    scheduled_end_at: str
    duration_seconds: int
    interval_seconds: int
    expected_sample_count: int
    expected_running_containers: int
    status: str = "active"
    completed_at: str | None = None
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not isinstance(self.run_id, str) or not self.run_id.strip():
            raise SustainedUseModelError(
                "run_id must be a non-empty string",
            )

        object.__setattr__(
            self,
            "run_id",
            self.run_id.strip(),
        )

        object.__setattr__(
            self,
            "git_commit",
            _git_commit(self.git_commit),
        )

        started_at = _timestamp(
            self.started_at,
            field="started_at",
        )

        scheduled_end_at = _timestamp(
            self.scheduled_end_at,
            field="scheduled_end_at",
        )

        object.__setattr__(
            self,
            "started_at",
            started_at,
        )

        object.__setattr__(
            self,
            "scheduled_end_at",
            scheduled_end_at,
        )

        duration = _positive_integer(
            self.duration_seconds,
            field="duration_seconds",
        )

        interval = _positive_integer(
            self.interval_seconds,
            field="interval_seconds",
        )

        expected_samples = _positive_integer(
            self.expected_sample_count,
            field="expected_sample_count",
        )

        expected_containers = _positive_integer(
            self.expected_running_containers,
            field="expected_running_containers",
        )

        if duration % interval != 0:
            raise SustainedUseModelError(
                "duration_seconds must be evenly divisible "
                "by interval_seconds",
            )

        calculated_samples = (
            duration // interval
        ) + 1

        if expected_samples != calculated_samples:
            raise SustainedUseModelError(
                "expected_sample_count does not match "
                "duration/interval contract",
            )

        from datetime import datetime

        start_dt = datetime.fromisoformat(
            started_at.replace("Z", "+00:00")
        )

        end_dt = datetime.fromisoformat(
            scheduled_end_at.replace("Z", "+00:00")
        )

        actual_duration = int(
            (end_dt - start_dt).total_seconds()
        )

        if actual_duration != duration:
            raise SustainedUseModelError(
                "scheduled_end_at does not match duration_seconds",
            )

        status = (
            self.status.strip().lower()
            if isinstance(self.status, str)
            else ""
        )

        if status not in _SESSION_STATUSES:
            raise SustainedUseModelError(
                "status must be one of: "
                + ", ".join(sorted(_SESSION_STATUSES)),
            )

        object.__setattr__(
            self,
            "status",
            status,
        )

        completed_at = self.completed_at

        if completed_at is not None:
            completed_at = _timestamp(
                completed_at,
                field="completed_at",
            )

        if status == "active" and completed_at is not None:
            raise SustainedUseModelError(
                "active session cannot have completed_at",
            )

        if status != "active" and completed_at is None:
            raise SustainedUseModelError(
                "non-active session requires completed_at",
            )

        object.__setattr__(
            self,
            "completed_at",
            completed_at,
        )

        if self.schema_version != SCHEMA_VERSION:
            raise SustainedUseModelError(
                f"schema_version must equal {SCHEMA_VERSION}",
            )

        object.__setattr__(
            self,
            "duration_seconds",
            duration,
        )
        object.__setattr__(
            self,
            "interval_seconds",
            interval,
        )
        object.__setattr__(
            self,
            "expected_sample_count",
            expected_samples,
        )
        object.__setattr__(
            self,
            "expected_running_containers",
            expected_containers,
        )

    @classmethod
    def from_contract(
        cls,
        *,
        run_id: str,
        started_at: str,
        scheduled_end_at: str,
        contract: SustainedUseContract,
    ) -> "SustainedUseSession":
        if not isinstance(contract, SustainedUseContract):
            raise SustainedUseModelError(
                "contract must be a SustainedUseContract",
            )

        return cls(
            run_id=run_id,
            git_commit=contract.git_commit,
            started_at=started_at,
            scheduled_end_at=scheduled_end_at,
            duration_seconds=contract.duration_seconds,
            interval_seconds=contract.interval_seconds,
            expected_sample_count=contract.expected_sample_count,
            expected_running_containers=(
                contract.expected_running_containers
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "git_commit": self.git_commit,
            "started_at": self.started_at,
            "scheduled_end_at": self.scheduled_end_at,
            "duration_seconds": self.duration_seconds,
            "interval_seconds": self.interval_seconds,
            "expected_sample_count": self.expected_sample_count,
            "expected_running_containers": (
                self.expected_running_containers
            ),
            "status": self.status,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(
        cls,
        value: Mapping[str, Any],
    ) -> "SustainedUseSession":
        if not isinstance(value, Mapping):
            raise SustainedUseModelError(
                "SustainedUseSession payload must be an object",
            )

        return cls(
            run_id=value.get("run_id"),
            git_commit=value.get("git_commit"),
            started_at=value.get("started_at"),
            scheduled_end_at=value.get(
                "scheduled_end_at",
            ),
            duration_seconds=value.get(
                "duration_seconds",
            ),
            interval_seconds=value.get(
                "interval_seconds",
            ),
            expected_sample_count=value.get(
                "expected_sample_count",
            ),
            expected_running_containers=value.get(
                "expected_running_containers",
            ),
            status=value.get(
                "status",
                "active",
            ),
            completed_at=value.get(
                "completed_at",
            ),
            schema_version=value.get(
                "schema_version",
                SCHEMA_VERSION,
            ),
        )
