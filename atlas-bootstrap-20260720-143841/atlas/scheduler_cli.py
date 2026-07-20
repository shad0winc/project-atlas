"""Command-line management for the Atlas scheduler runtime."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from atlas.events import publish_event
from atlas.module_scheduler import sync_module_jobs
from atlas.scheduler import SchedulerLockedError, TaskScheduler


def scheduler_state_file() -> Path:
    configured = os.environ.get("ATLAS_SCHEDULER_STATE_FILE")
    if configured:
        return Path(configured)
    runtime_root = os.environ.get("ATLAS_RUNTIME_CONFIG_DIR", "/mnt/storage/configs/atlas")
    return Path(runtime_root) / "scheduler" / "tasks.json"


def scheduler_lock_file() -> Path | None:
    configured = os.environ.get("ATLAS_SCHEDULER_LOCK_FILE")
    return Path(configured) if configured else None


def _publish_scheduler_event(event_name: str, payload: dict[str, object]) -> None:
    module = payload.get("module")
    if isinstance(module, str) and module.strip():
        publish_event(module, event_name, payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas scheduler")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List registered tasks")

    inspect_parser = subparsers.add_parser("inspect", help="Show one registered task")
    inspect_parser.add_argument("task_name")

    register_parser = subparsers.add_parser("register", help="Register or update a task")
    register_parser.add_argument("task_name")
    register_parser.add_argument("interval_seconds", type=int)
    register_parser.add_argument("callback")
    register_parser.add_argument("--description", default="")
    register_parser.add_argument("--module")
    register_parser.add_argument("--disabled", action="store_true", help="Register disabled")

    remove_parser = subparsers.add_parser("remove", help="Remove a registered task")
    remove_parser.add_argument("task_name")

    run_parser = subparsers.add_parser("run", help="Execute due tasks or one named task")
    run_parser.add_argument("task_name", nargs="?")
    run_parser.add_argument("--due-only", action="store_true", help="Require a named task to be due")

    subparsers.add_parser("dry-run", help="Show tasks that are currently due")
    history_parser = subparsers.add_parser("history", help="Show recent task executions")
    history_parser.add_argument("--limit", type=int, default=25)

    sync_parser = subparsers.add_parser("sync", help="Synchronize module scheduler manifests")
    sync_parser.add_argument("module_name", nargs="?")
    return parser


def _print_json(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_directory = Path(os.environ.get("ATLAS_PROJECT_DIR", "/opt/project-atlas"))
    scheduler = TaskScheduler(
        scheduler_state_file(),
        lock_file=scheduler_lock_file(),
        event_publisher=_publish_scheduler_event,
        working_directory=project_directory if project_directory.is_dir() else None,
    )

    try:
        if args.command == "list":
            tasks = scheduler.list_tasks()
            if not tasks:
                print("No scheduler tasks registered.")
                return 0
            print("NAME\tENABLED\tINTERVAL\tSTATUS\tDUE\tNEXT RUN")
            for task in tasks:
                print(f"{task['name']}\t{str(task.get('enabled', True)).lower()}\t{task.get('interval_seconds', '-')}\t{task.get('status', 'unknown')}\t{str(task.get('due', False)).lower()}\t{task.get('next_run') or '-'}")
            return 0

        if args.command == "inspect":
            task = scheduler.task_state(args.task_name)
            if not task:
                print(f"Scheduler task not found: {args.task_name}")
                return 1
            _print_json(task)
            return 0

        if args.command == "register":
            _print_json(scheduler.register(args.task_name, args.interval_seconds, args.callback, description=args.description, enabled=not args.disabled, module=args.module))
            return 0

        if args.command == "remove":
            if not scheduler.remove(args.task_name):
                print(f"Scheduler task not found: {args.task_name}")
                return 1
            print(f"Removed scheduler task: {args.task_name}")
            return 0

        if args.command == "dry-run":
            tasks = scheduler.dry_run()
            _print_json(tasks)
            return 0

        if args.command == "history":
            _print_json(scheduler.history(args.limit))
            return 0

        if args.command == "sync":
            registry_file = Path(
                os.environ.get(
                    "ATLAS_MODULES_CONFIG_FILE",
                    str(project_directory / "config" / "modules" / "modules.conf"),
                )
            )
            _print_json(
                sync_module_jobs(
                    scheduler,
                    project_directory,
                    registry_file,
                    args.module_name,
                )
            )
            return 0

        if args.command == "run":
            if args.task_name:
                result = scheduler.run_task(args.task_name, force=not args.due_only)
                _print_json(result.to_dict())
                return 0 if result.result == "success" else 1
            results = scheduler.run_due_tasks()
            _print_json([result.to_dict() for result in results])
            return 0 if all(result.result == "success" for result in results) else 1

    except KeyError as error:
        print(f"Scheduler task not found: {error.args[0]}")
        return 1
    except SchedulerLockedError as error:
        print(f"Scheduler error: {error}")
        return 3
    except ValueError as error:
        print(f"Scheduler error: {error}")
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
