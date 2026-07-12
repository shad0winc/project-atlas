#!/usr/bin/env python3

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

LOG_FILE = Path(
    "/mnt/storage/configs/atlas/notifications/logs/notifications.log"
)


def build_notification(event: dict) -> dict:
    event_name = event.get("event", "unknown")
    source = event.get("source", "unknown")
    payload = event.get("payload", {})

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_id": event.get("id"),
        "event": event_name,
        "source": source,
        "payload": payload,
    }


def main() -> int:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

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

        print(
            f"Processed notification event: "
            f"{notification['event']}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
