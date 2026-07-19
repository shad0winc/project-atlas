"""Declarative scheduler integration for Atlas modules."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from atlas.scheduler import TaskScheduler


_ENABLED_PATTERN = re.compile(
    r"^ATLAS_MODULE_([A-Z0-9_]+)_ENABLED=(true|false)$",
    re.IGNORECASE,
)


def _registry_modules(registry_file: Path) -> dict[str, bool]:
    """Return module names and enabled states from modules.conf."""
    modules: dict[str, bool] = {}

    if not registry_file.exists():
        return modules

    for raw_line in registry_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        match = _ENABLED_PATTERN.match(line)
        if not match:
            continue

        name = match.group(1).lower().replace("_", "-")
        modules[name] = match.group(2).lower() == "true"

    return modules


def _load_manifest(manifest_file: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"invalid scheduler manifest: {manifest_file}"
        ) from exc

    if not isinstance(manifest, dict):
        raise ValueError(f"invalid scheduler manifest: {manifest_file}")

    if manifest.get("schema_version") != 1:
        raise ValueError(
            f"unsupported scheduler manifest schema: {manifest_file}"
        )

    jobs = manifest.get("jobs")
    if not isinstance(jobs, list):
        raise ValueError(
            f"scheduler manifest jobs must be a list: {manifest_file}"
        )

    return manifest


def _normalize_job(
    project_directory: Path,
    module_name: str,
    module_directory: Path,
    raw_job: object,
) -> dict[str, Any]:
    if not isinstance(raw_job, dict):
        raise ValueError(f"invalid scheduler job for module: {module_name}")

    name = raw_job.get("name")
    callback = raw_job.get("callback")
    interval = raw_job.get("interval_seconds")

    if not isinstance(name, str) or not name.strip():
        raise ValueError(f"scheduler job name is required: {module_name}")

    if not isinstance(callback, str) or not callback.strip():
        raise ValueError(
            f"scheduler job callback is required: {module_name}.{name}"
        )

    if not isinstance(interval, int) or isinstance(interval, bool) or interval < 0:
        raise ValueError(
            f"invalid scheduler interval: {module_name}.{name}"
        )

    callback_path = (module_directory / callback).resolve()
    module_root = module_directory.resolve()

    try:
        callback_path.relative_to(module_root)
    except ValueError as exc:
        raise ValueError(
            f"scheduler callback escapes module directory: "
            f"{module_name}.{name}"
        ) from exc

    if not callback_path.is_file():
        raise ValueError(
            f"scheduler callback does not exist: {module_name}.{name}"
        )

    callback_relative = callback_path.relative_to(
        project_directory.resolve()
    ).as_posix()

    return {
        "name": f"{module_name}.{name.strip()}",
        "callback": callback_relative,
        "interval_seconds": interval,
        "description": str(raw_job.get("description", "")).strip(),
        "enabled": bool(raw_job.get("enabled", True)),
        "module": module_name,
    }


def _remove_module_tasks(
    scheduler: TaskScheduler,
    module_name: str,
    retained_names: set[str] | None = None,
) -> list[str]:
    retained = retained_names or set()
    removed: list[str] = []

    for task in scheduler.list_tasks():
        if task.get("module") != module_name:
            continue

        task_name = str(task.get("name", ""))
        if not task_name or task_name in retained:
            continue

        if scheduler.remove(task_name):
            removed.append(task_name)

    return sorted(removed)


def sync_module_jobs(
    scheduler: TaskScheduler,
    project_directory: Path,
    registry_file: Path,
    module_name: str | None = None,
) -> dict[str, list[str]]:
    """Synchronize module scheduler manifests into the Atlas task registry."""
    project_directory = project_directory.resolve()
    modules_directory = project_directory / "modules"
    registry = _registry_modules(registry_file)

    if module_name is not None:
        requested = module_name.strip().lower()
        if requested not in registry:
            raise ValueError(f"module not found: {requested}")
        selected_modules = [requested]
    else:
        selected_modules = sorted(registry)

    registered: list[str] = []
    removed: list[str] = []
    skipped: list[str] = []

    for current_module in selected_modules:
        enabled = registry[current_module]
        module_directory = modules_directory / current_module
        manifest_file = module_directory / "scheduler.json"

        if not enabled:
            removed.extend(
                _remove_module_tasks(scheduler, current_module)
            )
            skipped.append(current_module)
            continue

        if not module_directory.is_dir() or not manifest_file.is_file():
            removed.extend(
                _remove_module_tasks(scheduler, current_module)
            )
            skipped.append(current_module)
            continue

        manifest = _load_manifest(manifest_file)
        retained_names: set[str] = set()

        for raw_job in manifest["jobs"]:
            job = _normalize_job(
                project_directory,
                current_module,
                module_directory,
                raw_job,
            )

            scheduler.register(
                job["name"],
                job["interval_seconds"],
                job["callback"],
                description=job["description"],
                enabled=job["enabled"],
                module=job["module"],
            )

            retained_names.add(job["name"])
            registered.append(job["name"])

        removed.extend(
            _remove_module_tasks(
                scheduler,
                current_module,
                retained_names,
            )
        )

    return {
        "registered": sorted(registered),
        "removed": sorted(set(removed)),
        "skipped": sorted(set(skipped)),
    }
