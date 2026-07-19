"""Persistent interval scheduling for Project Atlas workers."""

from __future__ import annotations

from datetime import datetime, timedelta
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
    """Track persistent interval-based worker tasks and metadata."""

    SCHEMA_VERSION = 1

    def __init__(
        self,
        state_file: Path,
    ) -> None:
        self.state_file = state_file

    def _load(self) -> dict[str, Any]:
        state = load_json_object(self.state_file)

        tasks = state.get("tasks")
        if not isinstance(tasks, dict):
            state["tasks"] = {}

        state.setdefault("schema_version", self.SCHEMA_VERSION)
        return state

    def _save(
        self,
        state: dict[str, Any],
    ) -> None:
        state["schema_version"] = self.SCHEMA_VERSION
        state["updated_at"] = format_timestamp(utc_now())
        save_json(self.state_file, state)

    @staticmethod
    def _validate_task_name(task_name: str) -> str:
        normalized = task_name.strip()
        if not normalized:
            raise ValueError("task_name cannot be empty")
        return normalized

    @staticmethod
    def _validate_interval(interval_seconds: int) -> int:
        if interval_seconds < 0:
            raise ValueError("interval_seconds cannot be negative")
        return interval_seconds

    def register(
        self,
        task_name: str,
        interval_seconds: int,
        callback: str,
        *,
        description: str = "",
        enabled: bool = True,
        module: str | None = None,
    ) -> dict[str, Any]:
        """Register or update a persistent task definition."""
        name = self._validate_task_name(task_name)
        interval = self._validate_interval(interval_seconds)
        normalized_callback = callback.strip()

        if not normalized_callback:
            raise ValueError("callback cannot be empty")

        state = self._load()
        tasks = state["tasks"]
        task = tasks.get(name, {})
        if not isinstance(task, dict):
            task = {}

        now = format_timestamp(utc_now())
        task.setdefault("created_at", now)
        task.update(
            {
                "name": name,
                "enabled": enabled,
                "interval_seconds": interval,
                "callback": normalized_callback,
                "description": description.strip(),
                "module": module.strip() if module else None,
                "updated_at": now,
            }
        )
        task.setdefault("status", "never_run")
        task.setdefault("run_count", 0)
        task.setdefault("failure_count", 0)
        task.setdefault("consecutive_failures", 0)

        tasks[name] = task
        self._save(state)
        return dict(task)

    def remove(self, task_name: str) -> bool:
        """Remove a task definition and its persisted runtime state."""
        name = self._validate_task_name(task_name)
        state = self._load()
        tasks = state["tasks"]

        if name not in tasks:
            return False

        del tasks[name]
        self._save(state)
        return True

    def list_tasks(self) -> list[dict[str, Any]]:
        """Return all task records sorted by task name."""
        state = self._load()
        records: list[dict[str, Any]] = []

        for name, raw_task in state["tasks"].items():
            if not isinstance(raw_task, dict):
                continue

            task = dict(raw_task)
            task.setdefault("name", name)
            task["due"] = self._task_due(task)
            task["next_run"] = self._next_run(task)
            records.append(task)

        return sorted(records, key=lambda task: str(task["name"]))

    def task_state(
        self,
        task_name: str,
    ) -> dict[str, Any]:
        """Return the persisted state for a task."""
        name = self._validate_task_name(task_name)
        state = self._load()
        tasks = state["tasks"]

        if name not in tasks:
            return {}

        task = tasks[name]
        if not isinstance(task, dict):
            return {}

        result = dict(task)
        result.setdefault("name", name)
        result["due"] = self._task_due(result)
        result["next_run"] = self._next_run(result)
        return result

    def due(
        self,
        task_name: str,
        interval_seconds: int | None = None,
        *,
        now: datetime | None = None,
    ) -> bool:
        """Return whether a task is due based on last success."""
        name = self._validate_task_name(task_name)
        task = self.task_state(name)

        if interval_seconds is None:
            stored_interval = task.get("interval_seconds")
            if not isinstance(stored_interval, int):
                raise ValueError(
                    "interval_seconds is required for unregistered tasks"
                )
            interval = stored_interval
        else:
            interval = interval_seconds

        self._validate_interval(interval)
        return self._task_due(task, interval_seconds=interval, now=now)

    def _task_due(
        self,
        task: dict[str, Any],
        *,
        interval_seconds: int | None = None,
        now: datetime | None = None,
    ) -> bool:
        if task.get("enabled", True) is False:
            return False

        interval = interval_seconds
        if interval is None:
            stored = task.get("interval_seconds")
            if not isinstance(stored, int) or stored < 0:
                return False
            interval = stored

        current_time = now or utc_now()
        last_success = parse_timestamp(task.get("last_success"))
        if last_success is None:
            return True

        return age_seconds(last_success, now=current_time) >= interval

    def _next_run(self, task: dict[str, Any]) -> str | None:
        if task.get("enabled", True) is False:
            return None

        interval = task.get("interval_seconds")
        if not isinstance(interval, int) or interval < 0:
            return None

        last_success = parse_timestamp(task.get("last_success"))
        if last_success is None:
            return format_timestamp(utc_now())

        return format_timestamp(last_success + timedelta(seconds=interval))

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
                "last_started": format_timestamp(now or utc_now()),
                "status": "running",
            },
        )

    def succeeded(
        self,
        task_name: str,
        *,
        now: datetime | None = None,
        details: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Record a successful task execution."""
        task = self.task_state(task_name)
        run_count = int(task.get("run_count", 0))

        updates: dict[str, Any] = {
            "last_success": format_timestamp(now or utc_now()),
            "status": "healthy",
            "consecutive_failures": 0,
            "last_error": None,
            "run_count": run_count + 1,
        }

        if details is not None:
            updates["details"] = details
        if duration_ms is not None:
            if duration_ms < 0:
                raise ValueError("duration_ms cannot be negative")
            updates["last_duration_ms"] = duration_ms

        self._record(task_name, updates)

    def failed(
        self,
        task_name: str,
        error: str,
        *,
        now: datetime | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Record a failed task execution."""
        name = self._validate_task_name(task_name)
        state = self._load()
        tasks = state["tasks"]
        task = tasks.get(name, {})

        if not isinstance(task, dict):
            task = {}

        failures = int(task.get("consecutive_failures", 0))
        failure_count = int(task.get("failure_count", 0))
        run_count = int(task.get("run_count", 0))

        updates: dict[str, Any] = {
            "last_failure": format_timestamp(now or utc_now()),
            "status": "degraded",
            "last_error": error,
            "consecutive_failures": failures + 1,
            "failure_count": failure_count + 1,
            "run_count": run_count + 1,
        }
        if duration_ms is not None:
            if duration_ms < 0:
                raise ValueError("duration_ms cannot be negative")
            updates["last_duration_ms"] = duration_ms

        task.update(updates)
        tasks[name] = task
        self._save(state)

    def _record(
        self,
        task_name: str,
        updates: dict[str, Any],
    ) -> None:
        name = self._validate_task_name(task_name)
        state = self._load()
        tasks = state["tasks"]
        task = tasks.get(name, {})

        if not isinstance(task, dict):
            task = {}

        task.update(updates)
        tasks[name] = task
        self._save(state)
