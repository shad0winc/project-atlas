#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from atlas.scheduler import TaskScheduler


def check(
    condition: bool,
    message: str,
) -> None:
    if not condition:
        raise AssertionError(message)

    print(f"PASS: {message}")


def main() -> int:
    with tempfile.TemporaryDirectory() as directory:
        state_file = (
            Path(directory)
            / "scheduler.json"
        )

        scheduler = TaskScheduler(
            state_file
        )

        now = datetime(
            2026,
            7,
            18,
            12,
            0,
            tzinfo=timezone.utc,
        )

        check(
            scheduler.due(
                "maintenance",
                3600,
                now=now,
            ),
            "New task is immediately due",
        )

        scheduler.started(
            "maintenance",
            now=now,
        )

        running = scheduler.task_state(
            "maintenance"
        )

        check(
            running["status"] == "running",
            "Task start is persisted",
        )

        scheduler.succeeded(
            "maintenance",
            now=now,
            details={
                "removed": 2,
            },
        )

        check(
            not scheduler.due(
                "maintenance",
                3600,
                now=now + timedelta(
                    minutes=30
                ),
            ),
            "Successful task is not due early",
        )

        check(
            scheduler.due(
                "maintenance",
                3600,
                now=now + timedelta(
                    hours=1
                ),
            ),
            "Successful task becomes due at interval",
        )

        scheduler.failed(
            "maintenance",
            "simulated failure",
            now=now + timedelta(
                hours=1
            ),
        )

        failed = scheduler.task_state(
            "maintenance"
        )

        check(
            failed["status"] == "degraded",
            "Failure status is persisted",
        )

        check(
            failed["consecutive_failures"] == 1,
            "Failure count is persisted",
        )

        parsed_state = json.loads(
            state_file.read_text(
                encoding="utf-8",
            )
        )

        check(
            "tasks" in parsed_state,
            "Scheduler state is valid JSON",
        )

    print()
    print("Atlas Core Scheduler Tests: PASS")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
