"""Validated historical ARI snapshot timelines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import median
from typing import Iterable

from .snapshot_reader import ARISnapshot


class AnalyticsTimelineError(ValueError):
    """Raised when snapshots cannot form a valid analytics timeline."""


def _parse_timestamp(
    value: str,
    *,
    field_name: str,
) -> datetime:
    """Parse one timezone-aware ISO-8601 timestamp."""

    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string.")

    normalized = value.strip()

    if not normalized:
        raise AnalyticsTimelineError(
            f"{field_name} must not be empty."
        )

    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise AnalyticsTimelineError(
            f"{field_name} must be a valid ISO-8601 timestamp."
        ) from error

    if parsed.tzinfo is None:
        raise AnalyticsTimelineError(
            f"{field_name} must include a timezone."
        )

    return parsed


@dataclass(frozen=True)
class TimelineGap:
    """A longer-than-expected interval between adjacent snapshots."""

    previous_timestamp: str
    current_timestamp: str
    interval_seconds: float
    expected_interval_seconds: float

    def __post_init__(self) -> None:
        previous = _parse_timestamp(
            self.previous_timestamp,
            field_name="previous_timestamp",
        )
        current = _parse_timestamp(
            self.current_timestamp,
            field_name="current_timestamp",
        )

        if current <= previous:
            raise AnalyticsTimelineError(
                "current_timestamp must follow previous_timestamp."
            )

        if (
            isinstance(self.interval_seconds, bool)
            or not isinstance(self.interval_seconds, (int, float))
        ):
            raise TypeError(
                "interval_seconds must be a number."
            )

        if (
            isinstance(self.expected_interval_seconds, bool)
            or not isinstance(
                self.expected_interval_seconds,
                (int, float),
            )
        ):
            raise TypeError(
                "expected_interval_seconds must be a number."
            )

        if self.interval_seconds <= 0:
            raise AnalyticsTimelineError(
                "interval_seconds must be greater than zero."
            )

        if self.expected_interval_seconds <= 0:
            raise AnalyticsTimelineError(
                "expected_interval_seconds must be greater than zero."
            )

        object.__setattr__(
            self,
            "interval_seconds",
            float(self.interval_seconds),
        )
        object.__setattr__(
            self,
            "expected_interval_seconds",
            float(self.expected_interval_seconds),
        )

    @property
    def excess_seconds(self) -> float:
        """Return the interval beyond the expected cadence."""

        return max(
            0.0,
            self.interval_seconds
            - self.expected_interval_seconds,
        )

    def to_dict(self) -> dict[str, object]:
        """Serialize the gap contract."""

        return {
            "previous_timestamp": self.previous_timestamp,
            "current_timestamp": self.current_timestamp,
            "interval_seconds": self.interval_seconds,
            "expected_interval_seconds": (
                self.expected_interval_seconds
            ),
            "excess_seconds": self.excess_seconds,
        }


@dataclass(frozen=True)
class AnalyticsTimeline:
    """Chronologically ordered, validated ARI history."""

    snapshots: tuple[ARISnapshot, ...]
    expected_interval_seconds: float | None
    gaps: tuple[TimelineGap, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.snapshots, tuple):
            raise TypeError("snapshots must be a tuple.")

        if len(self.snapshots) < 2:
            raise AnalyticsTimelineError(
                "An analytics timeline requires at least two snapshots."
            )

        parsed_timestamps: list[datetime] = []
        schema_versions: set[int] = set()

        for index, snapshot in enumerate(self.snapshots):
            if not isinstance(snapshot, ARISnapshot):
                raise TypeError(
                    f"snapshots[{index}] must be an ARISnapshot."
                )

            parsed_timestamps.append(
                _parse_timestamp(
                    snapshot.timestamp,
                    field_name=f"snapshots[{index}].timestamp",
                )
            )
            schema_versions.add(snapshot.schema_version)

        for previous, current in zip(
            parsed_timestamps,
            parsed_timestamps[1:],
        ):
            if current <= previous:
                raise AnalyticsTimelineError(
                    "snapshots must be strictly ordered by timestamp."
                )

        if len(schema_versions) != 1:
            raise AnalyticsTimelineError(
                "All timeline snapshots must use the same schema_version."
            )

        if self.expected_interval_seconds is not None:
            if (
                isinstance(self.expected_interval_seconds, bool)
                or not isinstance(
                    self.expected_interval_seconds,
                    (int, float),
                )
            ):
                raise TypeError(
                    "expected_interval_seconds must be a number or None."
                )

            if self.expected_interval_seconds <= 0:
                raise AnalyticsTimelineError(
                    "expected_interval_seconds must be greater than zero."
                )

            object.__setattr__(
                self,
                "expected_interval_seconds",
                float(self.expected_interval_seconds),
            )

        if not isinstance(self.gaps, tuple):
            raise TypeError("gaps must be a tuple.")

        for index, gap in enumerate(self.gaps):
            if not isinstance(gap, TimelineGap):
                raise TypeError(
                    f"gaps[{index}] must be a TimelineGap."
                )

    @property
    def first(self) -> ARISnapshot:
        """Return the oldest snapshot."""

        return self.snapshots[0]

    @property
    def latest(self) -> ARISnapshot:
        """Return the newest snapshot."""

        return self.snapshots[-1]

    @property
    def previous(self) -> ARISnapshot:
        """Return the snapshot immediately before the newest."""

        return self.snapshots[-2]

    @property
    def schema_version(self) -> int:
        """Return the common ARI schema version."""

        return self.snapshots[0].schema_version

    @property
    def snapshot_count(self) -> int:
        """Return the number of snapshots."""

        return len(self.snapshots)

    @property
    def duration_seconds(self) -> float:
        """Return the total timeline duration."""

        first = _parse_timestamp(
            self.first.timestamp,
            field_name="first.timestamp",
        )
        latest = _parse_timestamp(
            self.latest.timestamp,
            field_name="latest.timestamp",
        )

        return (latest - first).total_seconds()

    @property
    def interval_seconds(self) -> tuple[float, ...]:
        """Return intervals between adjacent snapshots."""

        parsed = tuple(
            _parse_timestamp(
                snapshot.timestamp,
                field_name="snapshot.timestamp",
            )
            for snapshot in self.snapshots
        )

        return tuple(
            (current - previous).total_seconds()
            for previous, current in zip(
                parsed,
                parsed[1:],
            )
        )

    @property
    def median_interval_seconds(self) -> float:
        """Return the median observed interval."""

        return float(median(self.interval_seconds))

    @property
    def has_gaps(self) -> bool:
        """Return whether cadence gaps were detected."""

        return bool(self.gaps)

    def to_dict(self) -> dict[str, object]:
        """Serialize the timeline contract."""

        return {
            "schema_version": self.schema_version,
            "snapshot_count": self.snapshot_count,
            "first_timestamp": self.first.timestamp,
            "latest_timestamp": self.latest.timestamp,
            "duration_seconds": self.duration_seconds,
            "expected_interval_seconds": (
                self.expected_interval_seconds
            ),
            "median_interval_seconds": (
                self.median_interval_seconds
            ),
            "has_gaps": self.has_gaps,
            "gaps": [
                gap.to_dict()
                for gap in self.gaps
            ],
            "snapshots": [
                snapshot.to_dict()
                for snapshot in self.snapshots
            ],
        }


class AnalyticsTimelineBuilder:
    """Build validated timelines from ARI snapshots."""

    DEFAULT_GAP_MULTIPLIER = 1.5

    def build(
        self,
        snapshots: Iterable[ARISnapshot],
        *,
        expected_interval_seconds: float | None = None,
        gap_multiplier: float = DEFAULT_GAP_MULTIPLIER,
    ) -> AnalyticsTimeline:
        """Normalize, order, and validate ARI history."""

        normalized = tuple(snapshots)

        if len(normalized) < 2:
            raise AnalyticsTimelineError(
                "At least two ARI snapshots are required."
            )

        for index, snapshot in enumerate(normalized):
            if not isinstance(snapshot, ARISnapshot):
                raise TypeError(
                    f"snapshots[{index}] must be an ARISnapshot."
                )

        self._validate_gap_multiplier(gap_multiplier)

        ordered = tuple(
            sorted(
                normalized,
                key=lambda snapshot: _parse_timestamp(
                    snapshot.timestamp,
                    field_name="snapshot.timestamp",
                ),
            )
        )

        self._validate_unique_timestamps(ordered)
        self._validate_schema_versions(ordered)

        observed_intervals = self._intervals(ordered)

        resolved_expected_interval = (
            self._resolve_expected_interval(
                observed_intervals,
                expected_interval_seconds=(
                    expected_interval_seconds
                ),
            )
        )

        gaps = self._detect_gaps(
            ordered,
            observed_intervals=observed_intervals,
            expected_interval_seconds=(
                resolved_expected_interval
            ),
            gap_multiplier=float(gap_multiplier),
        )

        return AnalyticsTimeline(
            snapshots=ordered,
            expected_interval_seconds=(
                resolved_expected_interval
            ),
            gaps=gaps,
        )

    @staticmethod
    def _validate_gap_multiplier(
        gap_multiplier: float,
    ) -> None:
        if (
            isinstance(gap_multiplier, bool)
            or not isinstance(gap_multiplier, (int, float))
        ):
            raise TypeError(
                "gap_multiplier must be a number."
            )

        if gap_multiplier <= 1:
            raise AnalyticsTimelineError(
                "gap_multiplier must be greater than 1."
            )

    @staticmethod
    def _validate_unique_timestamps(
        snapshots: tuple[ARISnapshot, ...],
    ) -> None:
        timestamps: set[datetime] = set()

        for snapshot in snapshots:
            parsed = _parse_timestamp(
                snapshot.timestamp,
                field_name="snapshot.timestamp",
            )

            if parsed in timestamps:
                raise AnalyticsTimelineError(
                    "Timeline snapshots must have unique timestamps."
                )

            timestamps.add(parsed)

    @staticmethod
    def _validate_schema_versions(
        snapshots: tuple[ARISnapshot, ...],
    ) -> None:
        versions = {
            snapshot.schema_version
            for snapshot in snapshots
        }

        if len(versions) != 1:
            raise AnalyticsTimelineError(
                "All timeline snapshots must use the same schema_version."
            )

    @staticmethod
    def _intervals(
        snapshots: tuple[ARISnapshot, ...],
    ) -> tuple[float, ...]:
        parsed = tuple(
            _parse_timestamp(
                snapshot.timestamp,
                field_name="snapshot.timestamp",
            )
            for snapshot in snapshots
        )

        return tuple(
            (current - previous).total_seconds()
            for previous, current in zip(
                parsed,
                parsed[1:],
            )
        )

    @staticmethod
    def _resolve_expected_interval(
        observed_intervals: tuple[float, ...],
        *,
        expected_interval_seconds: float | None,
    ) -> float:
        if expected_interval_seconds is not None:
            if (
                isinstance(expected_interval_seconds, bool)
                or not isinstance(
                    expected_interval_seconds,
                    (int, float),
                )
            ):
                raise TypeError(
                    "expected_interval_seconds must be a number or None."
                )

            if expected_interval_seconds <= 0:
                raise AnalyticsTimelineError(
                    "expected_interval_seconds must be greater than zero."
                )

            return float(expected_interval_seconds)

        return float(median(observed_intervals))

    @staticmethod
    def _detect_gaps(
        snapshots: tuple[ARISnapshot, ...],
        *,
        observed_intervals: tuple[float, ...],
        expected_interval_seconds: float,
        gap_multiplier: float,
    ) -> tuple[TimelineGap, ...]:
        threshold = (
            expected_interval_seconds
            * gap_multiplier
        )

        gaps: list[TimelineGap] = []

        for index, interval in enumerate(
            observed_intervals,
        ):
            if interval <= threshold:
                continue

            gaps.append(
                TimelineGap(
                    previous_timestamp=(
                        snapshots[index].timestamp
                    ),
                    current_timestamp=(
                        snapshots[index + 1].timestamp
                    ),
                    interval_seconds=interval,
                    expected_interval_seconds=(
                        expected_interval_seconds
                    ),
                )
            )

        return tuple(gaps)


__all__ = [
    "AnalyticsTimeline",
    "AnalyticsTimelineBuilder",
    "AnalyticsTimelineError",
    "TimelineGap",
]
