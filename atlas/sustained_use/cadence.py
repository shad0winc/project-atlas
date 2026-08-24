"""Fixed-slot temporal cadence contracts for Q.6 certification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Final

from .models import SustainedUseSession


DEFAULT_CADENCE_LATENESS_SECONDS: Final = 180


class SustainedUseCadenceError(ValueError):
    """Raised when a sustained-use cadence contract is invalid."""


class CadenceAction(str, Enum):
    """Action required for the next fixed Q.6 sampling slot."""

    NOT_DUE = "not_due"
    SAMPLE = "sample"
    MISSED = "missed"
    COMPLETE = "complete"


@dataclass(frozen=True)
class SustainedUseCadenceDecision:
    """Deterministic decision for one fixed Q.6 sampling slot."""

    action: CadenceAction
    sample_count: int
    next_sample_number: int | None
    expected_at: str | None
    lateness_seconds: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.action, CadenceAction):
            raise SustainedUseCadenceError(
                "action must be a CadenceAction"
            )

        if (
            isinstance(self.sample_count, bool)
            or not isinstance(self.sample_count, int)
            or self.sample_count < 0
        ):
            raise SustainedUseCadenceError(
                "sample_count must be a non-negative integer"
            )

        if self.next_sample_number is not None:
            if (
                isinstance(self.next_sample_number, bool)
                or not isinstance(self.next_sample_number, int)
                or self.next_sample_number < 1
            ):
                raise SustainedUseCadenceError(
                    "next_sample_number must be a positive integer or None"
                )

        if self.expected_at is not None:
            _parse_timestamp(self.expected_at)

        if self.lateness_seconds is not None:
            if isinstance(self.lateness_seconds, bool) or not isinstance(
                self.lateness_seconds,
                (int, float),
            ):
                raise SustainedUseCadenceError(
                    "lateness_seconds must be numeric or None"
                )

    def to_dict(self) -> dict[str, object]:
        """Serialize the decision for CLI/runtime diagnostics."""

        return {
            "action": self.action.value,
            "sample_count": self.sample_count,
            "next_sample_number": self.next_sample_number,
            "expected_at": self.expected_at,
            "lateness_seconds": self.lateness_seconds,
        }


def _parse_timestamp(value: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise SustainedUseCadenceError(
            "timestamp must be a non-empty string"
        )

    normalized = value.strip()

    try:
        parsed = datetime.fromisoformat(
            normalized.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as error:
        raise SustainedUseCadenceError(
            f"invalid timestamp: {value}"
        ) from error

    if parsed.tzinfo is None:
        raise SustainedUseCadenceError(
            "timestamp must include a timezone"
        )

    return parsed.astimezone(timezone.utc)


def _utc_timestamp(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .isoformat()
        .replace(
            "+00:00",
            "Z",
        )
    )


def fixed_sample_time(
    session: SustainedUseSession,
    sample_number: int,
) -> datetime:
    """Return the immutable T0-derived time for one sample ordinal."""

    if not isinstance(session, SustainedUseSession):
        raise TypeError(
            "session must be a SustainedUseSession"
        )

    if (
        isinstance(sample_number, bool)
        or not isinstance(sample_number, int)
    ):
        raise TypeError(
            "sample_number must be an integer"
        )

    if (
        sample_number < 1
        or sample_number > session.expected_sample_count
    ):
        raise SustainedUseCadenceError(
            "sample_number is outside the Q.6 contract"
        )

    started_at = _parse_timestamp(
        session.started_at
    )

    return started_at + timedelta(
        seconds=(
            (sample_number - 1)
            * session.interval_seconds
        )
    )


def cadence_decision(
    *,
    session: SustainedUseSession,
    sample_count: int,
    now: datetime,
    max_lateness_seconds: int = DEFAULT_CADENCE_LATENESS_SECONDS,
) -> SustainedUseCadenceDecision:
    """Classify the next required fixed Q.6 sampling slot.

    The certification clock is always anchored to session.started_at.
    Runtime execution/completion timestamps never move future slots.

    No backfill is permitted. If the next required slot is missed beyond
    the configured tolerance, the result is MISSED rather than SAMPLE.
    """

    if not isinstance(session, SustainedUseSession):
        raise TypeError(
            "session must be a SustainedUseSession"
        )

    if (
        isinstance(sample_count, bool)
        or not isinstance(sample_count, int)
    ):
        raise TypeError(
            "sample_count must be an integer"
        )

    if sample_count < 0:
        raise SustainedUseCadenceError(
            "sample_count must not be negative"
        )

    if sample_count > session.expected_sample_count:
        raise SustainedUseCadenceError(
            "sample_count exceeds the Q.6 contract"
        )

    if not isinstance(now, datetime):
        raise TypeError(
            "now must be a datetime"
        )

    if now.tzinfo is None:
        raise SustainedUseCadenceError(
            "now must include a timezone"
        )

    if (
        isinstance(max_lateness_seconds, bool)
        or not isinstance(max_lateness_seconds, int)
    ):
        raise TypeError(
            "max_lateness_seconds must be an integer"
        )

    if (
        max_lateness_seconds < 0
        or max_lateness_seconds >= session.interval_seconds
    ):
        raise SustainedUseCadenceError(
            "max_lateness_seconds must be non-negative "
            "and less than interval_seconds"
        )

    if sample_count == session.expected_sample_count:
        return SustainedUseCadenceDecision(
            action=CadenceAction.COMPLETE,
            sample_count=sample_count,
            next_sample_number=None,
            expected_at=None,
            lateness_seconds=None,
        )

    next_sample_number = sample_count + 1

    expected = fixed_sample_time(
        session,
        next_sample_number,
    )

    current = now.astimezone(
        timezone.utc
    )

    lateness = (
        current
        - expected
    ).total_seconds()

    expected_at = _utc_timestamp(
        expected
    )

    if lateness < 0:
        action = CadenceAction.NOT_DUE
    elif lateness <= max_lateness_seconds:
        action = CadenceAction.SAMPLE
    else:
        action = CadenceAction.MISSED

    return SustainedUseCadenceDecision(
        action=action,
        sample_count=sample_count,
        next_sample_number=next_sample_number,
        expected_at=expected_at,
        lateness_seconds=lateness,
    )
