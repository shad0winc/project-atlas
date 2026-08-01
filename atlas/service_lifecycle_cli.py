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
from atlas.service_lifecycle.service import InfrastructureHealthReport


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

    runtime_parser = subparsers.add_parser(
        "runtime",
        help="Show normalized runtime state for one service.",
    )
    runtime_parser.add_argument(
        "identifier",
        help="Stable managed-service identifier.",
    )
    runtime_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Render machine-readable JSON.",
    )

    health_parser = subparsers.add_parser(
        "health",
        help="Show aggregate infrastructure health or health for one service.",
    )
    health_parser.add_argument(
        "identifier",
        nargs="?",
        help=(
            "Optional stable managed-service identifier. "
            "Omit it for aggregate infrastructure health."
        ),
    )
    health_parser.add_argument(
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



def _render_runtime_json(
    runtime: ServiceRuntime,
    *,
    output: TextIO,
) -> None:
    json.dump(
        runtime.to_dict(),
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_runtime_human(
    runtime: ServiceRuntime,
    *,
    output: TextIO,
) -> None:
    output.write("Atlas Service Runtime\n")
    output.write("=====================\n\n")
    output.write(f"State: {runtime.state}\n")
    output.write(f"Docker Health: {runtime.health}\n")
    output.write(f"Running: {'Yes' if runtime.running else 'No'}\n")
    output.write(f"Healthy: {'Yes' if runtime.healthy else 'No'}\n")
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
    output.write(f"Image: {runtime.image.reference}\n")


def _command_runtime(
    identifier: str,
    *,
    service: ServiceLifecycleService,
    as_json: bool,
    output: TextIO,
) -> int:
    runtime = service.inspect_runtime(identifier)

    if as_json:
        _render_runtime_json(runtime, output=output)
    else:
        _render_runtime_human(runtime, output=output)

    return 0


def _render_health_json(
    health: ServiceHealth,
    *,
    output: TextIO,
) -> None:
    json.dump(
        health.to_dict(),
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_health_human(
    health: ServiceHealth,
    *,
    output: TextIO,
) -> None:
    warnings = "; ".join(health.warnings) if health.warnings else "None"
    errors = "; ".join(health.errors) if health.errors else "None"

    output.write("Atlas Service Health\n")
    output.write("====================\n\n")
    output.write(f"Status: {health.status.value}\n")
    output.write(f"Score: {health.score}/100\n")
    output.write(f"Healthy: {'Yes' if health.healthy else 'No'}\n")
    output.write(
        "Action Required: "
        f"{'Yes' if health.action_required else 'No'}\n"
    )
    output.write(f"Warnings: {warnings}\n")
    output.write(f"Errors: {errors}\n")
    output.write(f"Evaluated: {health.evaluated_at}\n")


def _render_health_report_json(
    report: InfrastructureHealthReport,
    *,
    output: TextIO,
) -> None:
    json.dump(
        report.to_dict(),
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_health_report_human(
    report: InfrastructureHealthReport,
    *,
    output: TextIO,
) -> None:
    counts = report.counts

    output.write("Atlas Infrastructure Health\n")
    output.write("===========================\n\n")
    output.write(f"Overall Score: {report.score}/100\n")
    output.write(f"Status: {report.status.title()}\n")

    output.write("\nServices\n")
    output.write("--------\n")
    output.write(f"Total:       {len(report.entries)}\n")
    output.write(f"Healthy:     {counts['healthy']}\n")
    output.write(f"Degraded:    {counts['degraded']}\n")
    output.write(f"Unhealthy:   {counts['unhealthy']}\n")
    output.write(f"Unknown:     {counts['unknown']}\n")

    output.write("\nAttention Required\n")
    output.write("------------------\n")
    if not report.attention:
        output.write("None\n")
    else:
        for entry in report.attention:
            output.write(f"- {entry.service.identifier}\n")
            messages = (
                tuple(entry.health.errors)
                + tuple(entry.health.warnings)
            )
            if not messages:
                messages = (
                    f"Health status is {entry.health.status.value}",
                )
            for message in messages:
                output.write(f"    - {message}\n")

    output.write("\nWarnings\n")
    output.write("--------\n")
    if report.warnings:
        for warning in report.warnings:
            output.write(f"- {warning}\n")
    else:
        output.write("None\n")

    output.write("\nErrors\n")
    output.write("------\n")
    if report.errors:
        for error in report.errors:
            output.write(f"- {error}\n")
    else:
        output.write("None\n")

    output.write(f"\nEvaluated: {report.evaluated_at}\n")


def _command_health(
    identifier: str | None,
    *,
    service: ServiceLifecycleService,
    as_json: bool,
    output: TextIO,
) -> int:
    if identifier is None:
        report = service.inspect_health_report()
        if as_json:
            _render_health_report_json(report, output=output)
        else:
            _render_health_report_human(report, output=output)
        return 0

    health = service.inspect_health(identifier)

    if as_json:
        _render_health_json(health, output=output)
    else:
        _render_health_human(health, output=output)

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

        if arguments.command == "runtime":
            return _command_runtime(
                arguments.identifier,
                service=resolved_service,
                as_json=arguments.as_json,
                output=resolved_output,
            )

        if arguments.command == "health":
            return _command_health(
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
