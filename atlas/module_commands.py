"""Allowlisted command execution for Atlas modules."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

_ENABLED_PATTERN = re.compile(
    r"^ATLAS_MODULE_([A-Z0-9_]+)_ENABLED=(true|false)$",
    re.IGNORECASE,
)
_COMMAND_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@dataclass(frozen=True)
class ModuleCommand:
    module: str
    name: str
    callback: Path
    arguments: tuple[str, ...]
    description: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "name": self.name,
            "callback": self.callback.as_posix(),
            "arguments": list(self.arguments),
            "description": self.description,
        }


def registry_modules(registry_file: Path) -> dict[str, bool]:
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

        module_name = match.group(1).lower().replace("_", "-")
        modules[module_name] = match.group(2).lower() == "true"

    return modules


def load_manifest(manifest_file: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid command manifest: {manifest_file}") from exc

    if not isinstance(manifest, dict):
        raise ValueError(f"invalid command manifest: {manifest_file}")

    if manifest.get("schema_version") != 1:
        raise ValueError(f"unsupported command manifest schema: {manifest_file}")

    commands = manifest.get("commands")
    if not isinstance(commands, dict):
        raise ValueError(f"command manifest commands must be an object: {manifest_file}")

    return manifest


def normalize_command(
    project_directory: Path,
    module_name: str,
    command_name: str,
    raw_command: object,
) -> ModuleCommand:
    if not _COMMAND_PATTERN.fullmatch(command_name):
        raise ValueError(f"invalid module command name: {module_name}.{command_name}")

    if not isinstance(raw_command, dict):
        raise ValueError(f"invalid module command: {module_name}.{command_name}")

    callback = raw_command.get("callback")
    if not isinstance(callback, str) or not callback.strip():
        raise ValueError(f"module command callback is required: {module_name}.{command_name}")

    raw_arguments = raw_command.get("arguments", [])
    if not isinstance(raw_arguments, list) or not all(
        isinstance(argument, str) for argument in raw_arguments
    ):
        raise ValueError(f"module command arguments must be strings: {module_name}.{command_name}")

    module_directory = (project_directory / "modules" / module_name).resolve()
    callback_path = (module_directory / callback).resolve()

    try:
        callback_path.relative_to(module_directory)
    except ValueError as exc:
        raise ValueError(
            f"module command callback escapes module directory: {module_name}.{command_name}"
        ) from exc

    if not callback_path.is_file():
        raise ValueError(f"module command callback does not exist: {module_name}.{command_name}")

    if callback_path.suffix not in {".py", ".sh"} and not callback_path.stat().st_mode & 0o111:
        raise ValueError(f"unsupported module command callback: {module_name}.{command_name}")

    return ModuleCommand(
        module=module_name,
        name=command_name,
        callback=callback_path,
        arguments=tuple(raw_arguments),
        description=str(raw_command.get("description", "")).strip(),
    )


def module_commands(
    project_directory: Path,
    registry_file: Path,
    module_name: str,
    *,
    require_enabled: bool = True,
) -> list[ModuleCommand]:
    module_name = module_name.strip().lower()
    registry = registry_modules(registry_file)

    if module_name not in registry:
        raise ValueError(f"module not found: {module_name}")

    if require_enabled and not registry[module_name]:
        raise ValueError(f"module is disabled: {module_name}")

    manifest_file = project_directory / "modules" / module_name / "commands.json"
    if not manifest_file.is_file():
        raise ValueError(f"module command manifest not found: {module_name}")

    manifest = load_manifest(manifest_file)
    commands = [
        normalize_command(project_directory, module_name, name, definition)
        for name, definition in manifest["commands"].items()
    ]
    return sorted(commands, key=lambda command: command.name)


def execute_module_command(
    project_directory: Path,
    registry_file: Path,
    module_name: str,
    command_name: str,
    arguments: Sequence[str] = (),
) -> int:
    commands = {
        command.name: command
        for command in module_commands(project_directory, registry_file, module_name)
    }

    if command_name not in commands:
        raise ValueError(f"unknown module command: {module_name}.{command_name}")

    command = commands[command_name]
    if command.callback.suffix == ".py":
        invocation = [sys.executable, str(command.callback)]
    elif command.callback.suffix == ".sh":
        invocation = ["bash", str(command.callback)]
    else:
        invocation = [str(command.callback)]

    invocation.extend(command.arguments)
    invocation.extend(arguments)

    completed = subprocess.run(
        invocation,
        cwd=project_directory,
        check=False,
    )
    return completed.returncode


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="atlas module")
    parser.add_argument(
        "--project-directory",
        default="/opt/project-atlas",
    )
    parser.add_argument(
        "--registry-file",
        default=None,
    )

    subparsers = parser.add_subparsers(dest="action", required=True)

    commands_parser = subparsers.add_parser("commands")
    commands_parser.add_argument("module")
    commands_parser.add_argument("--json", action="store_true")

    exec_parser = subparsers.add_parser("exec")
    exec_parser.add_argument("module")
    exec_parser.add_argument("command")
    exec_parser.add_argument("arguments", nargs=argparse.REMAINDER)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    project_directory = Path(args.project_directory).resolve()
    registry_file = (
        Path(args.registry_file).resolve()
        if args.registry_file
        else project_directory / "config" / "modules" / "modules.conf"
    )

    try:
        if args.action == "commands":
            commands = module_commands(project_directory, registry_file, args.module)
            if args.json:
                print(json.dumps([command.to_dict() for command in commands], indent=2))
            else:
                print("COMMAND\tDESCRIPTION")
                for command in commands:
                    print(f"{command.name}\t{command.description}")
            return 0

        if args.action == "exec":
            return execute_module_command(
                project_directory,
                registry_file,
                args.module,
                args.command,
                args.arguments,
            )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
