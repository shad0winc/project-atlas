"""Validated domain models for Atlas analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from math import isfinite
from typing import Any, Iterable, Mapping


def _normalize_required_text(
    value: object,
    *,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise ValueError(f"{field_name} must not be empty.")

    return normalized


def _normalize_nonnegative_integer(
    value: object,
    *,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer.")

    if value < 0:
        raise ValueError(f"{field_name} must not be negative.")

    return value


def _normalize_finite_number(
    value: object,
    *,
    field_name: str,
) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a number.")

    normalized = float(value)

    if not isfinite(normalized):
        raise ValueError(f"{field_name} must be finite.")

    return normalized


def _normalize_timestamp(
    value: object,
    *,
    field_name: str,
) -> str:
    if isinstance(value, datetime):
        timestamp = value
    elif isinstance(value, str):
        normalized = value.strip()

        if not normalized:
            raise ValueError(f"{field_name} must not be empty.")

        try:
            timestamp = datetime.fromisoformat(
                normalized.replace("Z", "+00:00")
            )
        except ValueError as error:
            raise ValueError(
                f"{field_name} must be a valid ISO 8601 timestamp."
            ) from error
    else:
        raise TypeError(
            f"{field_name} must be a datetime or ISO 8601 string."
        )

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return (
        timestamp.astimezone(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


class ForecastHealth(str, Enum):
    """Health classification for projected storage capacity."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StorageSummary:
    """Current storage utilization represented in bytes."""

    total_bytes: int
    used_bytes: int
    free_bytes: int
    utilization_percent: float

    def __post_init__(self) -> None:
        total_bytes = _normalize_nonnegative_integer(
            self.total_bytes,
            field_name="total_bytes",
        )
        used_bytes = _normalize_nonnegative_integer(
            self.used_bytes,
            field_name="used_bytes",
        )
        free_bytes = _normalize_nonnegative_integer(
            self.free_bytes,
            field_name="free_bytes",
        )
        utilization_percent = _normalize_finite_number(
            self.utilization_percent,
            field_name="utilization_percent",
        )

        if total_bytes == 0:
            if used_bytes != 0 or free_bytes != 0:
                raise ValueError(
                    "Zero total storage requires zero used and free bytes."
                )

            if utilization_percent != 0:
                raise ValueError(
                    "Zero total storage requires zero utilization."
                )
        else:
            if used_bytes > total_bytes:
                raise ValueError(
                    "used_bytes must not exceed total_bytes."
                )

            if free_bytes > total_bytes:
                raise ValueError(
                    "free_bytes must not exceed total_bytes."
                )

            if used_bytes + free_bytes != total_bytes:
                raise ValueError(
                    "used_bytes and free_bytes must equal total_bytes."
                )

            expected_utilization = used_bytes / total_bytes * 100

            if abs(utilization_percent - expected_utilization) > 0.01:
                raise ValueError(
                    "utilization_percent must match storage byte values."
                )

        if not 0 <= utilization_percent <= 100:
            raise ValueError(
                "utilization_percent must be between 0 and 100."
            )

        object.__setattr__(self, "total_bytes", total_bytes)
        object.__setattr__(self, "used_bytes", used_bytes)
        object.__setattr__(self, "free_bytes", free_bytes)
        object.__setattr__(
            self,
            "utilization_percent",
            round(utilization_percent, 2),
        )

    @classmethod
    def from_bytes(
        cls,
        *,
        total_bytes: int,
        used_bytes: int,
        free_bytes: int,
    ) -> StorageSummary:
        """Build a storage summary and calculate utilization."""

        normalized_total = _normalize_nonnegative_integer(
            total_bytes,
            field_name="total_bytes",
        )
        normalized_used = _normalize_nonnegative_integer(
            used_bytes,
            field_name="used_bytes",
        )
        normalized_free = _normalize_nonnegative_integer(
            free_bytes,
            field_name="free_bytes",
        )

        utilization = (
            normalized_used / normalized_total * 100
            if normalized_total
            else 0.0
        )

        return cls(
            total_bytes=normalized_total,
            used_bytes=normalized_used,
            free_bytes=normalized_free,
            utilization_percent=utilization,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the storage summary."""

        return {
            "total_bytes": self.total_bytes,
            "used_bytes": self.used_bytes,
            "free_bytes": self.free_bytes,
            "utilization_percent": self.utilization_percent,
        }


@dataclass(frozen=True, slots=True)
class LibraryGrowth:
    """Growth comparison for one normalized media library."""

    library: str
    current_count: int
    previous_count: int
    delta: int = field(init=False)
    percent_change: float | None = field(init=False)

    def __post_init__(self) -> None:
        library = _normalize_required_text(
            self.library,
            field_name="library",
        ).lower()
        current_count = _normalize_nonnegative_integer(
            self.current_count,
            field_name="current_count",
        )
        previous_count = _normalize_nonnegative_integer(
            self.previous_count,
            field_name="previous_count",
        )

        delta = current_count - previous_count
        percent_change = (
            delta / previous_count * 100
            if previous_count
            else None
        )

        object.__setattr__(self, "library", library)
        object.__setattr__(self, "current_count", current_count)
        object.__setattr__(self, "previous_count", previous_count)
        object.__setattr__(self, "delta", delta)
        object.__setattr__(
            self,
            "percent_change",
            None if percent_change is None else round(percent_change, 2),
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the library growth comparison."""

        return {
            "library": self.library,
            "current_count": self.current_count,
            "previous_count": self.previous_count,
            "delta": self.delta,
            "percent_change": self.percent_change,
        }


@dataclass(frozen=True, slots=True)
class ForecastSummary:
    """Projected storage capacity based on average daily growth."""

    daily_growth_bytes: float
    remaining_bytes: int
    estimated_days_remaining: int | None
    health: ForecastHealth

    def __post_init__(self) -> None:
        daily_growth_bytes = _normalize_finite_number(
            self.daily_growth_bytes,
            field_name="daily_growth_bytes",
        )
        remaining_bytes = _normalize_nonnegative_integer(
            self.remaining_bytes,
            field_name="remaining_bytes",
        )

        if (
            self.estimated_days_remaining is not None
            and (
                isinstance(self.estimated_days_remaining, bool)
                or not isinstance(self.estimated_days_remaining, int)
            )
        ):
            raise TypeError(
                "estimated_days_remaining must be an integer or None."
            )

        if (
            self.estimated_days_remaining is not None
            and self.estimated_days_remaining < 0
        ):
            raise ValueError(
                "estimated_days_remaining must not be negative."
            )

        try:
            health = (
                self.health
                if isinstance(self.health, ForecastHealth)
                else ForecastHealth(
                    _normalize_required_text(
                        self.health,
                        field_name="health",
                    ).lower()
                )
            )
        except ValueError as error:
            raise ValueError(
                "health must be a supported ForecastHealth value."
            ) from error

        if daily_growth_bytes <= 0:
            if self.estimated_days_remaining is not None:
                raise ValueError(
                    "Nonpositive growth requires no estimated capacity date."
                )

            if health is not ForecastHealth.UNKNOWN:
                raise ValueError(
                    "Nonpositive growth requires unknown forecast health."
                )
        elif self.estimated_days_remaining is None:
            raise ValueError(
                "Positive growth requires estimated_days_remaining."
            )

        object.__setattr__(
            self,
            "daily_growth_bytes",
            round(daily_growth_bytes, 2),
        )
        object.__setattr__(self, "remaining_bytes", remaining_bytes)
        object.__setattr__(self, "health", health)

    def to_dict(self) -> dict[str, object]:
        """Serialize the forecast summary."""

        return {
            "daily_growth_bytes": self.daily_growth_bytes,
            "remaining_bytes": self.remaining_bytes,
            "estimated_days_remaining": self.estimated_days_remaining,
            "health": self.health.value,
        }


@dataclass(frozen=True, slots=True)
class AnalyticsSnapshot:
    """Complete normalized analytics result for one ARI evaluation."""

    generated_at: str
    storage: StorageSummary
    libraries: tuple[LibraryGrowth, ...] = ()
    forecast: ForecastSummary | None = None

    def __post_init__(self) -> None:
        generated_at = _normalize_timestamp(
            self.generated_at,
            field_name="generated_at",
        )

        if not isinstance(self.storage, StorageSummary):
            raise TypeError(
                "storage must be a StorageSummary."
            )

        libraries = self._normalize_libraries(
            self.libraries
        )

        if (
            self.forecast is not None
            and not isinstance(
                self.forecast,
                ForecastSummary,
            )
        ):
            raise TypeError(
                "forecast must be a ForecastSummary or None."
            )

        library_names = [
            growth.library
            for growth in libraries
        ]

        if len(set(library_names)) != len(library_names):
            raise ValueError(
                "Analytics library names must be unique."
            )

        object.__setattr__(
            self,
            "generated_at",
            generated_at,
        )
        object.__setattr__(
            self,
            "libraries",
            libraries,
        )

    @staticmethod
    def _normalize_libraries(
        value: object,
    ) -> tuple[LibraryGrowth, ...]:
        if isinstance(value, (str, bytes, Mapping)):
            raise TypeError(
                "libraries must be an iterable of LibraryGrowth values."
            )

        if not isinstance(value, Iterable):
            raise TypeError(
                "libraries must be an iterable of LibraryGrowth values."
            )

        libraries = tuple(value)

        if not all(
            isinstance(item, LibraryGrowth)
            for item in libraries
        ):
            raise TypeError(
                "libraries must contain only LibraryGrowth values."
            )

        return libraries

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete analytics snapshot."""

        return {
            "generated_at": self.generated_at,
            "storage": self.storage.to_dict(),
            "libraries": [
                growth.to_dict()
                for growth in self.libraries
            ],
            "forecast": (
                None
                if self.forecast is None
                else self.forecast.to_dict()
            ),
        }


__all__ = [
    "AnalyticsSnapshot",
    "ForecastHealth",
    "ForecastSummary",
    "LibraryGrowth",
    "StorageSummary",
]
