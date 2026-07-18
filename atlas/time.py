"""Shared UTC time utilities for Project Atlas."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def format_timestamp(value: datetime) -> str:
    """Return a datetime as an ISO-8601 UTC timestamp."""
    if value.tzinfo is None:
        raise ValueError("Timestamp must be timezone-aware")

    return value.astimezone(timezone.utc).isoformat()


def parse_timestamp(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp into a UTC datetime."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return None

    return parsed.astimezone(timezone.utc)


def age_seconds(
    timestamp: datetime,
    *,
    now: datetime | None = None,
) -> float:
    """Return the non-negative age of a timestamp in seconds."""
    current_time = now or utc_now()

    if timestamp.tzinfo is None or current_time.tzinfo is None:
        raise ValueError("Timestamps must be timezone-aware")

    return max(
        0.0,
        (
            current_time.astimezone(timezone.utc)
            - timestamp.astimezone(timezone.utc)
        ).total_seconds(),
    )
