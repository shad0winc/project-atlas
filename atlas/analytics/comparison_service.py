"""Create analytics results by comparing validated ARI snapshots."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from .models import (
    AnalyticsSnapshot,
    ForecastHealth,
    ForecastSummary,
    LibraryGrowth,
)
from .snapshot_reader import ARISnapshot


class AnalyticsComparisonError(ValueError):
    """Raised when ARI snapshots cannot be compared safely."""


def _parse_timestamp(
    value: str,
    *,
    field_name: str,
) -> datetime:
    """Parse one timezone-aware ISO-8601 timestamp."""

    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise AnalyticsComparisonError(
            f"{field_name} must be a valid ISO-8601 timestamp."
        ) from error

    if parsed.tzinfo is None:
        raise AnalyticsComparisonError(
            f"{field_name} must include a timezone."
        )

    return parsed


def _library_count_map(
    snapshot: ARISnapshot,
) -> dict[str, int]:
    """Convert an ARI library tuple into a lookup mapping."""

    return dict(snapshot.library_counts)


class AnalyticsComparisonService:
    """Compare current and previous ARI source snapshots."""

    def compare(
        self,
        *,
        current: ARISnapshot,
        previous: ARISnapshot,
    ) -> AnalyticsSnapshot:
        """Create a normalized analytics snapshot."""

        self._validate_snapshot(
            current,
            field_name="current",
        )
        self._validate_snapshot(
            previous,
            field_name="previous",
        )
        self._validate_order(
            current=current,
            previous=previous,
        )

        current_counts = _library_count_map(current)
        previous_counts = _library_count_map(previous)

        library_names = sorted(
            set(current_counts) | set(previous_counts)
        )

        libraries = tuple(
            LibraryGrowth(
                library=name,
                current_count=current_counts.get(name, 0),
                previous_count=previous_counts.get(name, 0),
            )
            for name in library_names
        )

        forecast = self._unknown_forecast(
            remaining_bytes=current.storage.free_bytes,
        )

        return AnalyticsSnapshot(
            generated_at=current.timestamp,
            storage=current.storage,
            libraries=libraries,
            forecast=forecast,
        )

    def compare_many(
        self,
        snapshots: Iterable[ARISnapshot],
    ) -> AnalyticsSnapshot:
        """Compare the two newest snapshots from an iterable."""

        normalized = tuple(snapshots)

        if len(normalized) < 2:
            raise AnalyticsComparisonError(
                "At least two ARI snapshots are required."
            )

        for index, snapshot in enumerate(normalized):
            self._validate_snapshot(
                snapshot,
                field_name=f"snapshots[{index}]",
            )

        ordered = sorted(
            normalized,
            key=lambda snapshot: _parse_timestamp(
                snapshot.timestamp,
                field_name="snapshot.timestamp",
            ),
        )

        return self.compare(
            current=ordered[-1],
            previous=ordered[-2],
        )

    @staticmethod
    def _validate_snapshot(
        snapshot: ARISnapshot,
        *,
        field_name: str,
    ) -> None:
        if not isinstance(snapshot, ARISnapshot):
            raise TypeError(
                f"{field_name} must be an ARISnapshot."
            )

    @staticmethod
    def _validate_order(
        *,
        current: ARISnapshot,
        previous: ARISnapshot,
    ) -> None:
        current_timestamp = _parse_timestamp(
            current.timestamp,
            field_name="current.timestamp",
        )
        previous_timestamp = _parse_timestamp(
            previous.timestamp,
            field_name="previous.timestamp",
        )

        if previous_timestamp >= current_timestamp:
            raise AnalyticsComparisonError(
                "previous.timestamp must precede current.timestamp."
            )

    @staticmethod
    def _unknown_forecast(
        *,
        remaining_bytes: int,
    ) -> ForecastSummary:
        """Create the explicit pre-forecast-engine state."""

        return ForecastSummary(
            daily_growth_bytes=0,
            remaining_bytes=remaining_bytes,
            estimated_days_remaining=None,
            health=ForecastHealth.UNKNOWN,
        )


__all__ = [
    "AnalyticsComparisonError",
    "AnalyticsComparisonService",
]
