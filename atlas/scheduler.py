"""Persistent interval scheduling and execution for Project Atlas workers."""

from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Mapping

from atlas.state import load_json_object, save_json
from atlas.time import age_seconds, format_timestamp, parse_timestamp, utc_now

EventPublisher = Callable[[str, Mapping[str, Any]], None]


@dataclass(frozen=True)
class ExecutionResult:
    """Normalized result returned by scheduler executions."""

    task: str
    result: str
    started_at: str
    ended_at: str
    duration_ms: int
    return_code: int | None = None
    error: str | None = None
    event_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SchedulerLockedError(RuntimeError):
    """Raised when another scheduler runtime owns the execution lock."""


class TaskScheduler:
    """Track and execute persistent interval-based worker tasks."""

    SCHEMA_VERSION = 2
    HISTORY_LIMIT = 100

    def __init__(
        self,
        state_file: Path,
        *,
        lock_file: Path | None = None,
        event_publisher: EventPublisher | None = None,
        working_directory: Path | None = None,
    ) -> None:
        self.state_file = state_file
        self.lock_file = lock_file or state_file.with_suffix(".lock")
        self.event_publisher = event_publisher
        self.working_directory = working_directory

    def _load(self) -> dict[str, Any]:
        state = load_json_object(self.state_file)
        if not isinstance(state.get("tasks"), dict):
            state["tasks"] = {}
        if not isinstance(state.get("history"), list):
            state["history"] = []
        state.setdefault("schema_version", self.SCHEMA_VERSION)
        return state

    def _save(self, state: dict[str, Any]) -> None:
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
        if name not in state["tasks"]:
            return False
        del state["tasks"][name]
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

    def task_state(self, task_name: str) -> dict[str, Any]:
        """Return the persisted state for a task."""
        name = self._validate_task_name(task_name)
        task = self._load()["tasks"].get(name)
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
                raise ValueError("interval_seconds is required for unregistered tasks")
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
        last_success = parse_timestamp(task.get("last_success"))
        if last_success is None:
            return True
        return age_seconds(last_success, now=now or utc_now()) >= interval

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

    def started(self, task_name: str, *, now: datetime | None = None) -> None:
        self._record(task_name, {"last_started": format_timestamp(now or utc_now()), "status": "running"})

    def succeeded(
        self,
        task_name: str,
        *,
        now: datetime | None = None,
        details: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> None:
        task = self.task_state(task_name)
        updates: dict[str, Any] = {
            "last_success": format_timestamp(now or utc_now()),
            "status": "healthy",
            "consecutive_failures": 0,
            "last_error": None,
            "run_count": int(task.get("run_count", 0)) + 1,
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
        task = self.task_state(task_name)
        updates: dict[str, Any] = {
            "last_failure": format_timestamp(now or utc_now()),
            "status": "degraded",
            "last_error": error,
            "consecutive_failures": int(task.get("consecutive_failures", 0)) + 1,
            "failure_count": int(task.get("failure_count", 0)) + 1,
            "run_count": int(task.get("run_count", 0)) + 1,
        }
        if duration_ms is not None:
            if duration_ms < 0:
                raise ValueError("duration_ms cannot be negative")
            updates["last_duration_ms"] = duration_ms
        self._record(task_name, updates)

    def dry_run(self) -> list[dict[str, Any]]:
        """Return enabled tasks that are currently due without executing them."""
        return [task for task in self.list_tasks() if task.get("due") is True]

    def history(self, limit: int = 25) -> list[dict[str, Any]]:
        """Return newest execution history entries first."""
        if limit < 0:
            raise ValueError("limit cannot be negative")
        entries = self._load()["history"]
        return [dict(entry) for entry in reversed(entries[-limit:]) if isinstance(entry, dict)]

    def run_task(self, task_name: str, *, force: bool = True) -> ExecutionResult:
        """Execute one registered task under the scheduler runtime lock."""
        with self._runtime_lock():
            task = self.task_state(task_name)
            if not task:
                raise KeyError(task_name)
            if task.get("enabled", True) is False:
                raise ValueError(f"scheduler task is disabled: {task_name}")
            if not force and not task.get("due", False):
                raise ValueError(f"scheduler task is not due: {task_name}")
            return self._execute(task)

    def run_due_tasks(self) -> list[ExecutionResult]:
        """Execute every enabled task that is currently due."""
        with self._runtime_lock():
            tasks = self.dry_run()
            return [self._execute(task) for task in tasks]

    def _execute(self, task: dict[str, Any]) -> ExecutionResult:
        name = str(task["name"])
        callback = task.get("callback")
        if not isinstance(callback, str) or not callback.strip():
            raise ValueError(f"scheduler task has no callback: {name}")

        command = shlex.split(callback)
        if not command:
            raise ValueError(f"scheduler task has no callback: {name}")

        started_at = utc_now()
        started_text = format_timestamp(started_at)
        self.started(name, now=started_at)
        event_error = self._publish("scheduler.task.started", task, {"started_at": started_text})
        clock_start = time.monotonic()

        return_code: int | None = None
        error: str | None = None
        try:
            completed = subprocess.run(
                command,
                cwd=self.working_directory,
                check=False,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return_code = completed.returncode
            if return_code != 0:
                error = completed.stderr.strip() or completed.stdout.strip() or f"callback exited with status {return_code}"
        except OSError as exc:
            error = str(exc)

        duration_ms = max(0, round((time.monotonic() - clock_start) * 1000))
        ended_at = utc_now()
        ended_text = format_timestamp(ended_at)
        result_name = "success" if error is None else "failed"

        if error is None:
            self.succeeded(name, now=ended_at, duration_ms=duration_ms)
            completion_event_error = self._publish(
                "scheduler.task.completed",
                task,
                {"ended_at": ended_text, "duration_ms": duration_ms, "return_code": return_code},
            )
        else:
            self.failed(name, error, now=ended_at, duration_ms=duration_ms)
            completion_event_error = self._publish(
                "scheduler.task.failed",
                task,
                {"ended_at": ended_text, "duration_ms": duration_ms, "return_code": return_code, "error": error},
            )
        event_error = completion_event_error or event_error

        execution = ExecutionResult(
            task=name,
            result=result_name,
            started_at=started_text,
            ended_at=ended_text,
            duration_ms=duration_ms,
            return_code=return_code,
            error=error,
            event_error=event_error,
        )
        self._append_history(execution.to_dict())
        return execution

    def _publish(
        self,
        event_name: str,
        task: dict[str, Any],
        payload: dict[str, Any],
    ) -> str | None:
        if self.event_publisher is None:
            return None
        event_payload = {"task": task.get("name"), "module": task.get("module"), **payload}
        try:
            self.event_publisher(event_name, event_payload)
        except Exception as exc:  # Event delivery must not alter task outcome.
            return str(exc)
        return None

    def _append_history(self, entry: dict[str, Any]) -> None:
        state = self._load()
        state["history"].append(entry)
        state["history"] = state["history"][-self.HISTORY_LIMIT :]
        self._save(state)

    def _record(self, task_name: str, updates: dict[str, Any]) -> None:
        name = self._validate_task_name(task_name)
        state = self._load()
        task = state["tasks"].get(name, {})
        if not isinstance(task, dict):
            task = {}
        task.update(updates)
        state["tasks"][name] = task
        self._save(state)

    class _Lock:
        def __init__(self, path: Path) -> None:
            self.path = path
            self.fd: int | None = None

        def __enter__(self) -> None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as exc:
                if self._remove_stale_lock():
                    self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                else:
                    raise SchedulerLockedError(f"scheduler runtime is already locked: {self.path}") from exc
            os.write(self.fd, f"{os.getpid()}\n".encode())

        def _remove_stale_lock(self) -> bool:
            try:
                owner = int(self.path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                self.path.unlink(missing_ok=True)
                return True
            try:
                os.kill(owner, 0)
            except ProcessLookupError:
                self.path.unlink(missing_ok=True)
                return True
            except PermissionError:
                return False
            return False

        def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
            if self.fd is not None:
                os.close(self.fd)
            self.path.unlink(missing_ok=True)

    def _runtime_lock(self) -> TaskScheduler._Lock:
        return self._Lock(self.lock_file)
