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
    except DiscoveryError as exc:
        error.write(f"Discovery error: {exc}\n")
        return 1

    error.write(
        f"Unsupported Discovery command: {arguments.command}\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
