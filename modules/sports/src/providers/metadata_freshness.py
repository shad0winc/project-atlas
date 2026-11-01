"""Shorten active scoreboard cache lifetimes without renewing observations.

Provider calendar buckets may contain games after UTC midnight. A bucket is
active when it is today's UTC bucket or contains a live/near-start event.
The shared broker's request budget and cooldown remain authoritative.
"""
from datetime import datetime, timezone


def active_scoreboard(day, events, now):
    if day == datetime.fromtimestamp(now, timezone.utc).date().isoformat():
        return True
    for event in events:
        if event.status == 'live':
            return True
        if event.status != 'scheduled' or event.start_at is None:
            continue
        start = datetime.fromisoformat(event.start_at.replace('Z', '+00:00'))
        # Retain fast status updates through delayed starts. Never infer live
        # from a scheduled time: only a provider observation can establish it.
        if -6 * 3600 <= start.timestamp() - now <= 3600:
            return True
    return False


def scoreboard_expiry(day, events, observed, expires, now, current_ttl):
    return min(expires, observed + current_ttl) if active_scoreboard(day, events, now) else expires
