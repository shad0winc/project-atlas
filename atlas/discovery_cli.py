"""Command-line interface for the Atlas Discovery domain."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from typing import TextIO

from atlas.discovery import (
    DiscoveryError,
    DiscoveryHealth,
    DiscoveryIndexer,
    DiscoveryService,
)
from atlas.discovery.providers import (
    DiscoveryProviderError,
    ProwlarrDiscoveryProvider,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the Discovery command-line parser."""

    parser = argparse.ArgumentParser(
        prog="atlas discovery",
        description="Inspect Atlas discovery infrastructure.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    indexers_parser = subparsers.add_parser(
        "indexers",
        help="List configured discovery indexers.",
    )
    indexers_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Render machine-readable JSON.",
    )

    categories_parser = subparsers.add_parser(
        "categories",
        help="List discovery categories.",
    )
    categories_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Render machine-readable JSON.",
    )

    applications_parser = subparsers.add_parser(
        "applications",
        help="List connected discovery applications.",
    )
    applications_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Render machine-readable JSON.",
    )

    health_parser = subparsers.add_parser(
        "health",
        help="Evaluate discovery health.",
    )
    health_parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Render machine-readable JSON.",
    )

    return parser


def _provider_from_environment() -> ProwlarrDiscoveryProvider:
    """Build the Prowlarr provider from runtime-only configuration."""

    base_url = os.environ.get(
        "ATLAS_PROWLARR_URL",
        "",
    ).strip()

    api_key = os.environ.get(
        "ATLAS_PROWLARR_API_KEY",
        "",
    ).strip()

    timeout_value = os.environ.get(
        "ATLAS_PROWLARR_TIMEOUT",
        "10",
    ).strip()

    if not base_url:
        raise DiscoveryProviderError(
            "ATLAS_PROWLARR_URL is required",
        )

    if not api_key:
        raise DiscoveryProviderError(
            "ATLAS_PROWLARR_API_KEY is required",
        )

    try:
        timeout = float(timeout_value)
    except ValueError as exc:
        raise DiscoveryProviderError(
            "ATLAS_PROWLARR_TIMEOUT must be a positive number",
        ) from exc

    return ProwlarrDiscoveryProvider(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
    )


def _indexer_rows(
    indexers: Sequence[DiscoveryIndexer],
) -> list[dict[str, object]]:
    """Serialize indexers for JSON output."""

    return [
        indexer.to_dict()
        for indexer in indexers
    ]


def _render_indexers_json(
    indexers: Sequence[DiscoveryIndexer],
    *,
    output: TextIO,
) -> None:
    """Render machine-readable indexer output."""

    json.dump(
        _indexer_rows(indexers),
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_indexers_human(
    indexers: Sequence[DiscoveryIndexer],
    *,
    output: TextIO,
) -> None:
    """Render a human-readable indexer table."""

    output.write("Atlas Discovery Indexers\n")
    output.write("========================\n\n")

    if not indexers:
        output.write("No discovery indexers were returned.\n")
        return

    columns = (
        ("NAME", 22),
        ("ENABLED", 8),
        ("PROTOCOL", 10),
        ("PRIORITY", 8),
        ("CAPABILITIES", 32),
        ("TAGS", 20),
    )

    header = "  ".join(
        title.ljust(width)
        for title, width in columns
    )

    output.write(header.rstrip() + "\n")
    output.write("-" * len(header.rstrip()) + "\n")

    for indexer in indexers:
        capabilities = ",".join(
            capability.value
            for capability in indexer.capabilities
        )

        tags = ",".join(indexer.tags)

        values = (
            indexer.name,
            "yes" if indexer.enabled else "no",
            indexer.protocol,
            (
                str(indexer.priority)
                if indexer.priority is not None
                else "-"
            ),
            capabilities or "-",
            tags or "-",
        )

        row = "  ".join(
            value[:width].ljust(width)
            for value, (_, width) in zip(
                values,
                columns,
                strict=True,
            )
        )

        output.write(row.rstrip() + "\n")

    output.write(f"\nTotal: {len(indexers)}\n")


def _command_indexers(
    *,
    as_json: bool,
    output: TextIO,
) -> int:
    """Execute the indexer-list command."""

    provider = _provider_from_environment()
    service = DiscoveryService(provider)
    indexers = service.list_indexers()

    if as_json:
        _render_indexers_json(
            indexers,
            output=output,
        )
    else:
        _render_indexers_human(
            indexers,
            output=output,
        )

    return 0


def _render_categories_json(
    categories: Sequence[str],
    *,
    output: TextIO,
) -> None:
    """Render machine-readable category output."""

    json.dump(
        list(categories),
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_categories_human(
    categories: Sequence[str],
    *,
    output: TextIO,
) -> None:
    """Render human-readable category output."""

    output.write("Atlas Discovery Categories\n")
    output.write("==========================\n\n")

    if not categories:
        output.write("No discovery categories were returned.\n")
        return

    for category in categories:
        output.write(f"- {category}\n")

    output.write(f"\nTotal: {len(categories)}\n")


def _command_categories(
    *,
    as_json: bool,
    output: TextIO,
) -> int:
    """Execute the category-list command."""

    provider = _provider_from_environment()
    service = DiscoveryService(provider)
    categories = service.list_categories()

    if as_json:
        _render_categories_json(
            categories,
            output=output,
        )
    else:
        _render_categories_human(
            categories,
            output=output,
        )

    return 0


def _render_applications_json(
    applications: Sequence[str],
    *,
    output: TextIO,
) -> None:
    """Render machine-readable application output."""

    json.dump(
        list(applications),
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_applications_human(
    applications: Sequence[str],
    *,
    output: TextIO,
) -> None:
    """Render human-readable application output."""

    output.write("Atlas Discovery Applications\n")
    output.write("============================\n\n")

    if not applications:
        output.write(
            "No discovery applications were returned.\n"
        )
        return

    for application in applications:
        output.write(f"- {application}\n")

    output.write(f"\nTotal: {len(applications)}\n")


def _command_applications(
    *,
    as_json: bool,
    output: TextIO,
) -> int:
    """Execute the application-list command."""

    provider = _provider_from_environment()
    service = DiscoveryService(provider)
    applications = service.list_applications()

    if as_json:
        _render_applications_json(
            applications,
            output=output,
        )
    else:
        _render_applications_human(
            applications,
            output=output,
        )

    return 0


def _render_health_json(
    health: DiscoveryHealth,
    *,
    output: TextIO,
) -> None:
    """Render machine-readable health output."""

    json.dump(
        health.to_dict(),
        output,
        indent=2,
        sort_keys=True,
    )
    output.write("\n")


def _render_health_human(
    health: DiscoveryHealth,
    *,
    output: TextIO,
) -> None:
    """Render human-readable health output."""

    output.write("Atlas Discovery Health\n")
    output.write("======================\n\n")

    output.write(
        f"Status: {'Healthy' if health.healthy else 'Unhealthy'}\n"
    )
    output.write(f"Score: {health.score}/100\n")
    output.write(f"Evaluated: {health.evaluated_at}\n")

    if health.details:
        output.write("\nDetails\n")
        output.write("-------\n")

        for key in sorted(
            health.details,
            key=lambda value: (
                str(value).casefold(),
                str(value),
            ),
        ):
            label = str(key).replace("_", " ").title()
            output.write(f"{label}: {health.details[key]}\n")

    output.write("\nWarnings\n")
    output.write("--------\n")

    if health.warnings:
        for warning in health.warnings:
            output.write(f"- {warning}\n")
    else:
        output.write("None\n")

    output.write("\nErrors\n")
    output.write("------\n")

    if health.errors:
        for error_message in health.errors:
            output.write(f"- {error_message}\n")
    else:
        output.write("None\n")


def _command_health(
    *,
    as_json: bool,
    output: TextIO,
) -> int:
    """Execute the Discovery health command."""

    provider = _provider_from_environment()
    service = DiscoveryService(provider)
    health = service.health()

    if as_json:
        _render_health_json(
            health,
            output=output,
        )
    else:
        _render_health_human(
            health,
            output=output,
        )

    return 0 if health.healthy else 1


def main(
    argv: Sequence[str] | None = None,
    *,
    output: TextIO = sys.stdout,
    error: TextIO = sys.stderr,
) -> int:
    """Run the Discovery command-line interface."""

    parser = build_parser()
    arguments = parser.parse_args(argv)

    try:
        if arguments.command == "indexers":
            return _command_indexers(
                as_json=arguments.as_json,
                output=output,
            )

        if arguments.command == "categories":
            return _command_categories(
                as_json=arguments.as_json,
                output=output,
            )

        if arguments.command == "applications":
            return _command_applications(
                as_json=arguments.as_json,
                output=output,
            )

        if arguments.command == "health":
            return _command_health(
                as_json=arguments.as_json,
                output=output,
            )
    except DiscoveryError as exc:
        error.write(f"Discovery error: {exc}\n")
        return 1

    error.write(
        f"Unsupported Discovery command: {arguments.command}\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
