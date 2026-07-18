"""Persistent interval scheduling for Project Atlas workers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from atlas.state import load_json_object, save_json
from atlas.time import (
    age_seconds,
    format_timestamp,
    parse_timestamp,
    utc_now,
)


class TaskScheduler:
    """Track persistent interval-based worker tasks."""

    def __init__(
        self,
        state_file: Path,
    ) -> None:
        self.state_file = state_file

    def _load(self) -> dict[str, Any]:
        state = load_json_object(
            self.state_file
        )

        tasks = state.get("tasks")

        if not isinstance(tasks, dict):
            state["tasks"] = {}

        return state

    def _save(
        self,
        state: dict[str, Any],
    ) -> None:
        state["updated_at"] = format_timestamp(
            utc_now()
        )

        save_json(
            self.state_file,
            state,
        )

    def task_state(
        self,
        task_name: str,
    ) -> dict[str, Any]:
        """Return the persisted state for a task."""
        state = self._load()
        tasks = state["tasks"]
        task = tasks.get(task_name, {})

        if not isinstance(task, dict):
            return {}

        return dict(task)

    def due(
        self,
        task_name: str,
        interval_seconds: int,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Return whether a task is due based on last success."""
        if interval_seconds < 0:
            raise ValueError(
                "interval_seconds cannot be negative"
            )

        current_time = now or utc_now()
        task = self.task_state(task_name)

        last_success = parse_timestamp(
            task.get("last_success")
        )

        if last_success is None:
            return True

        return (
            age_seconds(
                last_success,
                now=current_time,
            )
            >= interval_seconds
        )

    def started(
        self,
        task_name: str,
        *,
        now: datetime | None = None,
    ) -> None:
        """Record that a task execution started."""
        self._record(
            task_name,
            {
                "last_started": format_timestamp(
                    now or utc_now()
                ),
                "status": "running",
            },
        )

    def succeeded(
        self,
        task_name: str,
        *,
        now: datetime | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record a successful task execution."""
        updates: dict[str, Any] = {
            "last_success": format_timestamp(
                now or utc_now()
            ),
            "status": "healthy",
            "consecutive_failures": 0,
            "last_error": None,
        }

        if details is not None:
            updates["details"] = details

        self._record(
            task_name,
            updates,
        )

    def failed(
        self,
        task_name: str,
        error: str,
        *,
        now: datetime | None = None,
    ) -> None:
        """Record a failed task execution."""
        state = self._load()
        tasks = state["tasks"]

        task = tasks.get(task_name, {})

        if not isinstance(task, dict):
            task = {}

        failures = int(
            task.get(
                "consecutive_failures",
                0,
            )
        )

        task.update(
            {
                "last_failure": format_timestamp(
                    now or utc_now()
                ),
                "status": "degraded",
                "last_error": error,
                "consecutive_failures": failures + 1,
            }
        )

        tasks[task_name] = task
        self._save(state)

    def _record(
        self,
        task_name: str,
        updates: dict[str, Any],
    ) -> None:
        if not task_name.strip():
            raise ValueError(
                "task_name cannot be empty"
            )

        state = self._load()
        tasks = state["tasks"]

        task = tasks.get(task_name, {})

        if not isinstance(task, dict):
            task = {}

        task.update(updates)
        tasks[task_name] = task

        self._save(state)
