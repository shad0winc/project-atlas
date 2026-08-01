from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import TextIO

from atlas.service_lifecycle import (
    DockerComposeProvider,
    ManagedService,
    ServiceLifecycleError,
    ServiceLifecycleService,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas service",
        description="Inspect Atlas-managed infrastructure services.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser(
        "list",
        help="List configured Atlas-managed services.",
    )
    list_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Render machine-readable JSON.",
    )
    return parser


def _service_from_environment() -> ServiceLifecycleService:
    project_root = Path(__file__).resolve().parents[1]
    compose_file = Path(
        os.environ.get(
            "ATLAS_COMPOSE_FILE",
            str(project_root / "docker-compose.yml"),
        )
    ).expanduser()
    project_directory = Path(
        os.environ.get(
            "ATLAS_PROJECT_DIR",
            str(compose_file.parent),
        )
    ).expanduser()

    return ServiceLifecycleService(
        DockerComposeProvider(
            compose_file=compose_file,
            project_directory=project_directory,
        )
    )


def _render_json(
    services: Sequence[ManagedService],
    *,
    output: TextIO,
) -> None:
    json.dump(
        [service.to_dict() for service in services],
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_human(
    services: Sequence[ManagedService],
    *,
    output: TextIO,
) -> None:
    output.write("Atlas Managed Services\n")
    output.write("======================\n\n")

    if not services:
        output.write("No managed services were returned.\n")
        return

    for service in services:
        dependencies = (
            ", ".join(service.dependencies)
            if service.dependencies
            else "None"
        )
        output.write(
            f"- {service.identifier}"
            f" | container={service.container_name or '-'}"
            f" | dependencies={dependencies}\n"
        )

    output.write(f"\nTotal: {len(services)}\n")


def main(
    argv: Sequence[str] | None = None,
    *,
    service: ServiceLifecycleService | None = None,
    output: TextIO | None = None,
    error: TextIO | None = None,
) -> int:
    arguments = build_parser().parse_args(argv)
    resolved_service = service or _service_from_environment()
    resolved_output = output or sys.stdout
    resolved_error = error or sys.stderr

    try:
        services = resolved_service.list_services()
    except ServiceLifecycleError as exc:
        resolved_error.write(f"Service Lifecycle error: {exc}\n")
        return 1

    if arguments.as_json:
        _render_json(services, output=resolved_output)
    else:
        _render_human(services, output=resolved_output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
