"""Host-authoritative bounded runtime publication for the Portal dashboard."""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import shutil
from typing import Any, Mapping

from atlas.health import HealthCheck, HealthReport


SCHEMA_VERSION = 1
RUNTIME_DIRECTORY_MODE = 0o750
RUNTIME_FILE_MODE = 0o640
RUNTIME_OWNER_UID = 0
RUNTIME_GROUP_GID = 20000


class DashboardRuntimeError(RuntimeError):
    """Raised when a Dashboard runtime snapshot cannot be read or published."""


def health_report_from_payload(payload: Mapping[str, Any]) -> HealthReport:
    """Reconstruct a validated HealthReport from its bounded runtime payload."""
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise DashboardRuntimeError("unsupported Dashboard health snapshot schema")

    generated_at = payload.get("generated_at")
    checks_payload = payload.get("checks")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise DashboardRuntimeError("Dashboard health snapshot generated_at is invalid")
    if not isinstance(checks_payload, list):
        raise DashboardRuntimeError("Dashboard health snapshot checks are invalid")

    checks: list[HealthCheck] = []
    try:
        for raw in checks_payload:
            if not isinstance(raw, Mapping):
                raise DashboardRuntimeError("Dashboard health snapshot check is invalid")
            details = raw.get("details", {})
            if not isinstance(details, Mapping):
                raise DashboardRuntimeError("Dashboard health snapshot check details are invalid")
            checks.append(
                HealthCheck(
                    name=raw.get("name"),
                    category=raw.get("category"),
                    status=raw.get("status"),
                    message=raw.get("message", ""),
                    details=details,
                )
            )
    except (TypeError, ValueError) as exc:
        raise DashboardRuntimeError("Dashboard health snapshot check is invalid") from exc

    return HealthReport(checks=checks, generated_at=generated_at)


def scheduler_tasks_from_payload(payload: Mapping[str, Any]) -> tuple[dict[str, Any], ...]:
    """Validate one bounded Scheduler runtime payload."""
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise DashboardRuntimeError("unsupported Dashboard scheduler snapshot schema")
    generated_at = payload.get("generated_at")
    tasks = payload.get("tasks")
    if not isinstance(generated_at, str) or not generated_at.strip():
        raise DashboardRuntimeError("Dashboard scheduler snapshot generated_at is invalid")
    if not isinstance(tasks, list):
        raise DashboardRuntimeError("Dashboard scheduler snapshot tasks are invalid")
    result = []
    for raw in tasks:
        if not isinstance(raw, Mapping):
            raise DashboardRuntimeError("Dashboard scheduler snapshot task is invalid")
        task = dict(raw)
        if not isinstance(task.get("name"), str) or not task["name"].strip():
            raise DashboardRuntimeError("Dashboard scheduler snapshot task name is invalid")
        result.append(task)
    return tuple(sorted(result, key=lambda item: item["name"]))


def read_scheduler_snapshot(path: str | Path) -> tuple[dict[str, Any], ...]:
    """Read one API-safe Dashboard Scheduler snapshot."""
    snapshot = Path(path).expanduser()
    try:
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardRuntimeError("Dashboard scheduler snapshot is unavailable") from exc
    if not isinstance(payload, Mapping):
        raise DashboardRuntimeError("Dashboard scheduler snapshot payload must be an object")
    return scheduler_tasks_from_payload(payload)


def read_health_snapshot(path: str | Path) -> HealthReport:
    """Read one API-safe Dashboard health snapshot."""
    snapshot = Path(path).expanduser()
    try:
        payload = json.loads(snapshot.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DashboardRuntimeError("Dashboard health snapshot is unavailable") from exc
    if not isinstance(payload, Mapping):
        raise DashboardRuntimeError("Dashboard health snapshot payload must be an object")
    return health_report_from_payload(payload)


def publish_operations_projection(
    source_root: str | Path,
    destination_root: str | Path,
    *,
    history_limit: int = 2,
) -> Path:
    """Publish a bounded generation-swapped Operations projection."""
    if (
        isinstance(history_limit, bool)
        or not isinstance(history_limit, int)
        or history_limit <= 0
    ):
        raise DashboardRuntimeError(
            "Dashboard Operations history_limit must be a positive integer"
        )

    from atlas.operations.repository import FileOperationsRepository

    source = FileOperationsRepository(Path(source_root).expanduser())
    latest = source.latest()
    history = source.history(limit=history_limit)

    root = Path(destination_root).expanduser()
    generations = root / "generations"
    current = root / "current"

    for directory in (root, generations):
        try:
            directory.mkdir(parents=True, exist_ok=True)
            os.chown(directory, RUNTIME_OWNER_UID, RUNTIME_GROUP_GID)
            os.chmod(directory, RUNTIME_DIRECTORY_MODE)
        except OSError as exc:
            raise DashboardRuntimeError(
                "unable to secure Dashboard Operations runtime directory"
            ) from exc

    if current.exists() and not current.is_symlink():
        raise DashboardRuntimeError(
            "Dashboard Operations current path must be a symlink"
        )
    if current.is_symlink() and not current.exists():
        raise DashboardRuntimeError(
            "Dashboard Operations current pointer is dangling"
        )

    generation = Path(
        tempfile.mkdtemp(prefix=".generation-", dir=generations)
    )

    try:
        os.chown(generation, RUNTIME_OWNER_UID, RUNTIME_GROUP_GID)
        os.chmod(generation, RUNTIME_DIRECTORY_MODE)

        publish_snapshot(latest.to_dict(), generation / "latest.json")

        history_directory = generation / "history"
        history_directory.mkdir()
        os.chown(history_directory, RUNTIME_OWNER_UID, RUNTIME_GROUP_GID)
        os.chmod(history_directory, RUNTIME_DIRECTORY_MODE)

        for report in history:
            filename = report.generated_at.replace(":", "-") + ".json"
            publish_snapshot(
                report.to_dict(),
                history_directory / filename,
            )

        temporary_pointer = root / (
            ".current." + generation.name.removeprefix(".generation-")
        )
        relative_target = Path("generations") / generation.name

        try:
            temporary_pointer.unlink(missing_ok=True)
            os.symlink(relative_target.as_posix(), temporary_pointer)
            os.replace(temporary_pointer, current)
        except OSError as exc:
            raise DashboardRuntimeError(
                "unable to publish Dashboard Operations current pointer"
            ) from exc
        finally:
            temporary_pointer.unlink(missing_ok=True)

        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        descriptor = os.open(root, flags)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

        other_generations = []
        for candidate in generations.iterdir():
            if not candidate.is_dir() or candidate == generation:
                continue
            other_generations.append(candidate)

        other_generations.sort(
            key=lambda candidate: candidate.stat().st_mtime_ns,
            reverse=True,
        )

        for obsolete in other_generations[1:]:
            shutil.rmtree(obsolete)

        return current

    except Exception:
        selected = False
        try:
            selected = current.is_symlink() and current.resolve() == generation.resolve()
        except OSError:
            selected = False

        if not selected and generation.exists():
            shutil.rmtree(generation, ignore_errors=True)
        raise


def publish_snapshot(payload: Mapping[str, Any], destination: str | Path) -> Path:
    """Atomically publish one API-readable bounded Dashboard runtime snapshot."""
    if not isinstance(payload, Mapping):
        raise TypeError("Dashboard runtime snapshot payload must be a mapping")

    target = Path(destination).expanduser()
    directory = target.parent
    if not target.name:
        raise DashboardRuntimeError("Dashboard runtime snapshot must name a file")

    try:
        directory.mkdir(parents=True, exist_ok=True)
        os.chown(directory, RUNTIME_OWNER_UID, RUNTIME_GROUP_GID)
        os.chmod(directory, RUNTIME_DIRECTORY_MODE)
    except OSError as exc:
        raise DashboardRuntimeError("unable to secure Dashboard runtime directory") from exc

    temporary: Path | None = None
    try:
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=directory)
        temporary = Path(temporary_name)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
            os.fchown(stream.fileno(), RUNTIME_OWNER_UID, RUNTIME_GROUP_GID)
            os.fchmod(stream.fileno(), RUNTIME_FILE_MODE)
        os.replace(temporary, target)
        temporary = None
        flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
        directory_fd = os.open(directory, flags)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except (OSError, TypeError, ValueError) as exc:
        raise DashboardRuntimeError("unable to publish Dashboard runtime snapshot") from exc
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink(missing_ok=True)

    return target
