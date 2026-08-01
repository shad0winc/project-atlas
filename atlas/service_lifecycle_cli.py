"""Command-line interface for Atlas Service Lifecycle."""

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
    ServiceHealth,
    ServiceLifecycleError,
    ServiceLifecycleService,
    ServiceRuntime,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas service",
        description="Inspect Atlas-managed infrastructure services.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

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

    show_parser = subparsers.add_parser(
        "show",
        help="Show identity, runtime, image, and health for one service.",
    )
    show_parser.add_argument(
        "identifier",
        help="Stable managed-service identifier.",
    )
    show_parser.add_argument(
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
        [
            service.to_dict()
            for service in services
        ],
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


def _render_show_json(
    identity: ManagedService,
    runtime: ServiceRuntime,
    health: ServiceHealth,
    *,
    output: TextIO,
) -> None:
    json.dump(
        {
            "service": identity.to_dict(),
            "runtime": runtime.to_dict(),
            "health": health.to_dict(),
        },
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_show_human(
    identity: ManagedService,
    runtime: ServiceRuntime,
    health: ServiceHealth,
    *,
    output: TextIO,
) -> None:
    dependencies = (
        ", ".join(identity.dependencies)
        if identity.dependencies
        else "None"
    )
    warnings = (
        "; ".join(health.warnings)
        if health.warnings
        else "None"
    )
    errors = (
        "; ".join(health.errors)
        if health.errors
        else "None"
    )

    output.write("Atlas Managed Service\n")
    output.write("=====================\n\n")

    output.write("Identity\n")
    output.write("--------\n")
    output.write(f"Name: {identity.name}\n")
    output.write(f"Identifier: {identity.identifier}\n")
    output.write(f"Provider: {identity.provider}\n")
    output.write(
        f"Compose Project: {identity.compose_project or 'None'}\n"
    )
    output.write(
        f"Container: {identity.container_name or 'None'}\n"
    )
    output.write(
        f"Enabled: {'Yes' if identity.enabled else 'No'}\n"
    )
    output.write(f"Dependencies: {dependencies}\n")

    output.write("\nRuntime\n")
    output.write("-------\n")
    output.write(f"State: {runtime.state}\n")
    output.write(f"Docker Health: {runtime.health}\n")
    output.write(f"Running: {'Yes' if runtime.running else 'No'}\n")
    output.write(f"Restart Count: {runtime.restart_count}\n")
    output.write(f"Started: {runtime.started_at or 'None'}\n")
    output.write(f"Finished: {runtime.finished_at or 'None'}\n")
    output.write(
        "Exit Code: "
        f"{runtime.exit_code if runtime.exit_code is not None else 'None'}\n"
    )
    output.write(
        f"Status Message: {runtime.status_message or 'None'}\n"
    )

    output.write("\nImage\n")
    output.write("-----\n")
    output.write(f"Reference: {runtime.image.reference}\n")
    output.write(
        f"Repository: {runtime.image.repository or 'None'}\n"
    )
    output.write(f"Tag: {runtime.image.tag or 'None'}\n")
    output.write(f"Digest: {runtime.image.digest or 'None'}\n")
    output.write(f"Image ID: {runtime.image.image_id or 'None'}\n")

    output.write("\nHealth\n")
    output.write("------\n")
    output.write(f"Status: {health.status.value}\n")
    output.write(f"Score: {health.score}/100\n")
    output.write(
        "Action Required: "
        f"{'Yes' if health.action_required else 'No'}\n"
    )
    output.write(f"Warnings: {warnings}\n")
    output.write(f"Errors: {errors}\n")
    output.write(f"Evaluated: {health.evaluated_at}\n")


def _command_show(
    identifier: str,
    *,
    service: ServiceLifecycleService,
    as_json: bool,
    output: TextIO,
) -> int:
    identity = service.inspect_service(identifier)
    runtime = service.inspect_runtime(identifier)
    health = service.inspect_health(identifier)

    if as_json:
        _render_show_json(
            identity,
            runtime,
            health,
            output=output,
        )
    else:
        _render_show_human(
            identity,
            runtime,
            health,
            output=output,
        )

    return 0


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
        if arguments.command == "list":
            services = resolved_service.list_services()

            if arguments.as_json:
                _render_json(
                    services,
                    output=resolved_output,
                )
            else:
                _render_human(
                    services,
                    output=resolved_output,
                )

            return 0

        if arguments.command == "show":
            return _command_show(
                arguments.identifier,
                service=resolved_service,
                as_json=arguments.as_json,
                output=resolved_output,
            )
    except ServiceLifecycleError as exc:
        resolved_error.write(
            f"Service Lifecycle error: {exc}\n"
        )
        return 1

    resolved_error.write(
        f"Unknown Service Lifecycle command: {arguments.command}\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
