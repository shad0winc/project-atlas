#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from router import NotificationRouter


LOG_FILE = Path(
    "/mnt/storage/configs/atlas/notifications/logs/notifications.log"
)

def classify_severity(event_name: str, payload: dict) -> str:
    if event_name == "atlas.health-changed":
        current = payload.get("current", "Unknown")

        if current == "Degraded":
            return "critical"

        if current == "Warning":
            return "warning"

        if current == "Healthy":
            return "success"

        return "warning"

    if event_name == "atlas.health-report":
        status = payload.get("status", "Unknown")

        if status == "Degraded":
            return "critical"

        if status == "Warning":
            return "warning"

        if status == "Healthy":
            return "success"

        return "info"

    if event_name == "storage.threshold-crossed":
        threshold = int(payload.get("threshold", 0))

        if threshold >= 90:
            return "critical"

        if threshold >= 75:
            return "warning"

        return "info"

    if event_name == "storage.threshold-recovered":
        return "success"

    if event_name == "sports.provider-degraded":
        return "critical"

    if event_name == "sports.provider-recovered":
        return "success"

    if event_name in {
        "sports.game-started",
        "sports.game-finished",
    }:
        return "info"

    return "info"

def build_notification(event: dict) -> dict:
    event_name = event.get("event", "unknown")
    source = event.get("source", "unknown")
    payload = event.get("payload", {})
    severity = classify_severity(event_name, payload)

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": event.get("id"),
        "event": event_name,
        "source": source,
        "severity": severity,
        "payload": payload,
    }


def main() -> int:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    router = NotificationRouter()

    for raw_line in sys.stdin:
        raw_line = raw_line.strip()

        if not raw_line:
            continue

        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue

        notification = build_notification(event)

        with LOG_FILE.open("a", encoding="utf-8") as log_file:
            log_file.write(
                json.dumps(notification, separators=(",", ":")) + "\n"
            )

        if not router.deliver(notification):
            print(
                f"Notification delivery failed: "
                f"{notification['event']}",
                file=sys.stderr,
            )
            return 1

        print(
            f"Processed notification event: "
            f"{notification['event']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
