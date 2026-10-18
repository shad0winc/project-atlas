"""Check complete-snapshot availability without extending its observation age."""
from datetime import datetime, timezone
import math
from typing import Any


def provider_snapshot_usable(row: Any, now: datetime | None = None) -> bool:
    if not isinstance(row, dict) or row.get("status") != "healthy":
        return False
    # Existing providers without the complete-snapshot contract keep their behavior.
    if "refresh_snapshot" not in row:
        return "refresh_state" not in row
    snapshot = row["refresh_snapshot"]
    if not isinstance(snapshot, dict):
        return False
    if type(snapshot.get("version")) is not int or snapshot["version"] != 1:
        return False
    if snapshot.get("maximum_age_seconds") != 900:
        return False
    count = snapshot.get("completed_request_count")
    if type(count) is not int or not 1 <= count <= 128:
        return False
    oldest = snapshot.get("oldest_response_age_seconds")
    if isinstance(oldest, bool) or not isinstance(oldest, (int, float)):
        return False
    if not math.isfinite(oldest) or not 0 <= oldest <= 900:
        return False
    try:
        completed = datetime.fromisoformat(row["last_success_at"].replace("Z", "+00:00"))
        if completed.tzinfo is None:
            return False
        current = datetime.now(timezone.utc) if now is None else now
        if current.tzinfo is None:
            return False
        elapsed = (current - completed).total_seconds()
    except (KeyError, AttributeError, TypeError, ValueError, OverflowError):
        return False
    return math.isfinite(elapsed) and 0 <= elapsed and oldest + elapsed <= 900
