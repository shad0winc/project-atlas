"""Command-line interface for Atlas Retention Intelligence analytics."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from atlas.ari.analytics import (
    ARIAnalytics,
    ARIAnalyticsError,
    ARIHistory,
    CapacityForecast,
    StorageChange,
    StorageInterval,
)
from atlas.ari.models import ARIReport
from atlas.ari.service import (
    ARIService,
    ARIServiceError,
    DEFAULT_ARI_DIRECTORY,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the ARI analytics command parser."""

    parser = argparse.ArgumentParser(
        prog="atlas ari",
        description="Inspect Atlas Retention Intelligence analytics.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    for command, help_text in (
        (
            "latest",
            "Display the latest validated ARI snapshot.",
        ),
        (
            "history",
            "Summarize validated ARI snapshot history.",
        ),
        (
            "growth",
            "Display historical storage growth analytics.",
        ),
        (
            "forecast",
            "Forecast when current storage capacity will be full.",
        ),
    ):
        command_parser = subparsers.add_parser(
            command,
            help=help_text,
        )
        command_parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Output machine-readable JSON.",
        )

    return parser


def default_service() -> ARIService:
    """Create an ARI service using Atlas runtime configuration."""

    snapshot_directory = os.environ.get(
        "ATLAS_ARI_DIR",
        str(DEFAULT_ARI_DIRECTORY),
    )

    return ARIService(
        snapshot_directory=Path(snapshot_directory),
    )


def _print_json(value: object) -> None:
    """Print consistently formatted JSON."""

    print(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
    )


def _format_bytes(value: float | int) -> str:
    """Return a human-readable binary byte quantity."""

    magnitude = float(value)
    units = (
        "bytes",
        "KiB",
        "MiB",
        "GiB",
        "TiB",
        "PiB",
    )

    unit = units[0]

    for candidate in units:
        unit = candidate

        if abs(magnitude) < 1024 or candidate == units[-1]:
            break

        magnitude /= 1024

    if unit == "bytes":
        return f"{int(round(magnitude)):,} {unit}"

    return f"{magnitude:,.2f} {unit}"


def _history_to_dict(
    history: ARIHistory,
) -> dict[str, Any]:
    """Serialize ARI history and skipped diagnostics."""

    return {
        "loaded_count": history.loaded_count,
        "skipped_count": history.skipped_count,
        "oldest_timestamp": (
            history.reports[0].timestamp
            if history.reports
            else None
        ),
        "newest_timestamp": (
            history.reports[-1].timestamp
            if history.reports
            else None
        ),
        "reports": [
            report.to_dict()
            for report in history.reports
        ],
        "skipped": [
            {
                "path": str(failure.path),
                "error": failure.error,
            }
            for failure in history.skipped
        ],
    }


def _storage_change_to_dict(
    change: StorageChange,
) -> dict[str, Any]:
    """Serialize a storage change."""

    return {
        "start_timestamp": change.start_timestamp,
        "end_timestamp": change.end_timestamp,
        "start_used_bytes": change.start_used_bytes,
        "end_used_bytes": change.end_used_bytes,
        "change_bytes": change.change_bytes,
        "elapsed_seconds": change.elapsed_seconds,
        "elapsed_days": change.elapsed_days,
        "average_bytes_per_day": (
            change.average_bytes_per_day
        ),
    }


def _storage_interval_to_dict(
    interval: StorageInterval,
) -> dict[str, Any]:
    """Serialize a storage interval."""

    return {
        "start_timestamp": interval.start_timestamp,
        "end_timestamp": interval.end_timestamp,
        "start_used_bytes": interval.start_used_bytes,
        "end_used_bytes": interval.end_used_bytes,
        "change_bytes": interval.change_bytes,
        "elapsed_seconds": interval.elapsed_seconds,
        "elapsed_days": interval.elapsed_days,
        "bytes_per_day": interval.bytes_per_day,
        "is_growth": interval.is_growth,
    }


def _forecast_to_dict(
    forecast: CapacityForecast,
) -> dict[str, Any]:
    """Serialize a capacity forecast."""

    return {
        "as_of_timestamp": forecast.as_of_timestamp,
        "capacity_bytes": forecast.capacity_bytes,
        "used_bytes": forecast.used_bytes,
        "available_bytes": forecast.available_bytes,
        "positive_interval_count": (
            forecast.positive_interval_count
        ),
        "average_growth_bytes_per_day": (
            forecast.average_growth_bytes_per_day
        ),
        "days_until_full": forecast.days_until_full,
        "estimated_full_timestamp": (
            forecast.estimated_full_timestamp
        ),
    }


def render_latest_human(
    report: ARIReport,
) -> str:
    """Render the latest ARI report for terminal users."""

    return "\n".join(
        [
            "Atlas ARI Latest",
            "----------------",
            f"Timestamp: {report.timestamp}",
            f"Atlas version: {report.atlas.version}",
            f"Hostname: {report.atlas.hostname}",
            (
                "Schema version: "
                f"{report.atlas.schema_version}"
            ),
            f"Media root: {report.storage.media_root}",
            (
                "Capacity: "
                f"{report.storage.capacity} "
                f"({report.storage.capacity_bytes:,} bytes)"
            ),
            (
                "Used: "
                f"{report.storage.used} "
                f"({report.storage.used_bytes:,} bytes)"
            ),
            (
                "Available: "
                f"{report.storage.available} "
                f"({report.storage.available_bytes:,} bytes)"
            ),
            (
                "Utilization: "
                f"{report.storage.utilization_percent}%"
            ),
            (
                "Jellyfin server: "
                f"{report.jellyfin.server_name}"
            ),
            (
                "Jellyfin version: "
                f"{report.jellyfin.version}"
            ),
            (
                "Jellyfin items: "
                f"{report.jellyfin.counts.total_items}"
            ),
        ]
    )


def render_history_human(
    history: ARIHistory,
) -> str:
    """Render ARI history diagnostics for terminal users."""

    lines = [
        "Atlas ARI History",
        "-----------------",
        f"Valid reports: {history.loaded_count}",
        f"Skipped snapshots: {history.skipped_count}",
        (
            "Oldest report: "
            f"{history.reports[0].timestamp}"
            if history.reports
            else "Oldest report: None"
        ),
        (
            "Newest report: "
            f"{history.reports[-1].timestamp}"
            if history.reports
            else "Newest report: None"
        ),
    ]

    if history.skipped:
        lines.append("Skipped diagnostics:")

        for failure in history.skipped:
            lines.append(
                f"  - {failure.path}: {failure.error}"
            )

    return "\n".join(lines)


def render_growth_human(
    history: ARIHistory,
    change: StorageChange,
    intervals: tuple[StorageInterval, ...],
) -> str:
    """Render storage growth analytics for terminal users."""

    growth_intervals = sum(
        1
        for interval in intervals
        if interval.is_growth
    )
    decline_intervals = sum(
        1
        for interval in intervals
        if interval.change_bytes < 0
    )
    unchanged_intervals = (
        len(intervals)
        - growth_intervals
        - decline_intervals
    )

    return "\n".join(
        [
            "Atlas ARI Growth",
            "----------------",
            f"Valid reports: {history.loaded_count}",
            f"Skipped snapshots: {history.skipped_count}",
            f"Intervals: {len(intervals)}",
            f"Growth intervals: {growth_intervals}",
            f"Decline intervals: {decline_intervals}",
            f"Unchanged intervals: {unchanged_intervals}",
            f"Start: {change.start_timestamp}",
            f"End: {change.end_timestamp}",
            (
                "Starting usage: "
                f"{_format_bytes(change.start_used_bytes)}"
            ),
            (
                "Ending usage: "
                f"{_format_bytes(change.end_used_bytes)}"
            ),
            (
                "Net change: "
                f"{_format_bytes(change.change_bytes)}"
            ),
            (
                "Elapsed: "
                f"{change.elapsed_days:,.2f} days"
            ),
            (
                "Average change: "
                f"{_format_bytes(change.average_bytes_per_day)}/day"
            ),
        ]
    )


def render_forecast_human(
    history: ARIHistory,
    forecast: CapacityForecast,
) -> str:
    """Render a capacity forecast for terminal users."""

    years_until_full = (
        forecast.days_until_full
        / 365.25
    )

    return "\n".join(
        [
            "Atlas ARI Forecast",
            "------------------",
            f"Valid reports: {history.loaded_count}",
            f"Skipped snapshots: {history.skipped_count}",
            f"As of: {forecast.as_of_timestamp}",
            (
                "Capacity: "
                f"{_format_bytes(forecast.capacity_bytes)}"
            ),
            (
                "Used: "
                f"{_format_bytes(forecast.used_bytes)}"
            ),
            (
                "Available: "
                f"{_format_bytes(forecast.available_bytes)}"
            ),
            (
                "Positive growth intervals: "
                f"{forecast.positive_interval_count}"
            ),
            (
                "Average growth: "
                f"{_format_bytes(
                    forecast.average_growth_bytes_per_day
                )}/day"
            ),
            (
                "Runway: "
                f"{forecast.days_until_full:,.2f} days "
                f"({years_until_full:,.2f} years)"
            ),
            (
                "Estimated full: "
                f"{forecast.estimated_full_timestamp}"
            ),
        ]
    )


def main(
    argv: Sequence[str] | None = None,
    *,
    service: ARIService | None = None,
    analytics: ARIAnalytics | None = None,
) -> int:
    """Run the ARI analytics CLI."""

    args = build_parser().parse_args(argv)

    ari_service = (
        service
        if service is not None
        else default_service()
    )
    ari_analytics = (
        analytics
        if analytics is not None
        else ARIAnalytics(ari_service)
    )

    try:
        if args.command == "latest":
            report = ari_service.latest()

            if args.json_output:
                _print_json(report.to_dict())
            else:
                print(render_latest_human(report))

            return 0

        history = ari_analytics.load_history()

        if args.command == "history":
            if args.json_output:
                _print_json(
                    _history_to_dict(history)
                )
            else:
                print(
                    render_history_human(history)
                )

            return 0

        if args.command == "growth":
            change = ari_analytics.storage_change()
            intervals = (
                ari_analytics.storage_intervals()
            )

            if args.json_output:
                _print_json(
                    {
                        "history": {
                            "loaded_count": (
                                history.loaded_count
                            ),
                            "skipped_count": (
                                history.skipped_count
                            ),
                            "skipped": [
                                {
                                    "path": str(
                                        failure.path
                                    ),
                                    "error": failure.error,
                                }
                                for failure in history.skipped
                            ],
                        },
                        "change": (
                            _storage_change_to_dict(
                                change
                            )
                        ),
                        "intervals": [
                            _storage_interval_to_dict(
                                interval
                            )
                            for interval in intervals
                        ],
                    }
                )
            else:
                print(
                    render_growth_human(
                        history,
                        change,
                        intervals,
                    )
                )

            return 0

        if args.command == "forecast":
            forecast = (
                ari_analytics.capacity_forecast()
            )

            if args.json_output:
                _print_json(
                    {
                        "history": {
                            "loaded_count": (
                                history.loaded_count
                            ),
                            "skipped_count": (
                                history.skipped_count
                            ),
                            "skipped": [
                                {
                                    "path": str(
                                        failure.path
                                    ),
                                    "error": failure.error,
                                }
                                for failure in history.skipped
                            ],
                        },
                        "forecast": (
                            _forecast_to_dict(
                                forecast
                            )
                        ),
                    }
                )
            else:
                print(
                    render_forecast_human(
                        history,
                        forecast,
                    )
                )

            return 0

    except (
        ARIServiceError,
        ARIAnalyticsError,
        ValueError,
        RuntimeError,
    ) as exc:
        print(
            f"ARI {args.command} failed: {exc}",
            file=sys.stderr,
        )
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
