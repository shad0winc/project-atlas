"""Command-line management for the Atlas scheduler registry."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Sequence

from atlas.scheduler import TaskScheduler


def scheduler_state_file() -> Path:
    configured = os.environ.get("ATLAS_SCHEDULER_STATE_FILE")
    if configured:
        return Path(configured)

    runtime_root = os.environ.get(
        "ATLAS_RUNTIME_CONFIG_DIR",
        "/mnt/storage/configs/atlas",
    )
    return Path(runtime_root) / "scheduler" / "tasks.json"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas scheduler")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List registered tasks")

    inspect_parser = subparsers.add_parser(
        "inspect", help="Show one registered task"
    )
    inspect_parser.add_argument("task_name")

    register_parser = subparsers.add_parser(
        "register", help="Register or update a task"
    )
    register_parser.add_argument("task_name")
    register_parser.add_argument("interval_seconds", type=int)
    register_parser.add_argument("callback")
    register_parser.add_argument("--description", default="")
    register_parser.add_argument("--module")
    register_parser.add_argument(
        "--disabled", action="store_true", help="Register disabled"
    )

    remove_parser = subparsers.add_parser(
        "remove", help="Remove a registered task"
    )
    remove_parser.add_argument("task_name")

    return parser


def _print_task(task: dict[str, object]) -> None:
    print(json.dumps(task, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    scheduler = TaskScheduler(scheduler_state_file())

    try:
        if args.command == "list":
            tasks = scheduler.list_tasks()
            if not tasks:
                print("No scheduler tasks registered.")
                return 0

            print("NAME\tENABLED\tINTERVAL\tSTATUS\tDUE\tNEXT RUN")
            for task in tasks:
                print(
                    f"{task['name']}\t"
                    f"{str(task.get('enabled', True)).lower()}\t"
                    f"{task.get('interval_seconds', '-')}\t"
                    f"{task.get('status', 'unknown')}\t"
                    f"{str(task.get('due', False)).lower()}\t"
                    f"{task.get('next_run') or '-'}"
                )
            return 0

        if args.command == "inspect":
            task = scheduler.task_state(args.task_name)
            if not task:
                print(f"Scheduler task not found: {args.task_name}")
                return 1
            _print_task(task)
            return 0

        if args.command == "register":
            task = scheduler.register(
                args.task_name,
                args.interval_seconds,
                args.callback,
                description=args.description,
                enabled=not args.disabled,
                module=args.module,
            )
            _print_task(task)
            return 0

        if args.command == "remove":
            if not scheduler.remove(args.task_name):
                print(f"Scheduler task not found: {args.task_name}")
                return 1
            print(f"Removed scheduler task: {args.task_name}")
            return 0
    except ValueError as error:
        print(f"Scheduler error: {error}")
        return 2

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
