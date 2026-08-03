"""Command-line interface for Project Atlas Operations."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
import sys
from typing import TextIO

from atlas.operations import (
    OperationsReport,
    OperationsService,
)
from atlas.operations.collectors import (
    DockerCollector,
    SystemCollector,
)


OperationsServiceFactory = Callable[[], OperationsService]


def build_parser() -> argparse.ArgumentParser:
    """Build the Atlas Operations command parser."""

    parser = argparse.ArgumentParser(
        prog="atlas operations",
        description=(
            "Collect and render Project Atlas operational health."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    report_parser = subparsers.add_parser(
        "report",
        help="Collect the current Operations report",
    )
    report_parser.add_argument(
        "--json",
        action="store_true",
        help="Render deterministic JSON output",
    )
    report_parser.add_argument(
        "--report-id",
        default="operations-report",
        help=(
            "Report identity "
            "(default: operations-report)"
        ),
    )

    return parser


def default_service_factory() -> OperationsService:
    """Construct the default live Operations service."""

    return OperationsService(
        collectors=(
            SystemCollector(),
            DockerCollector(),
        ),
    )


def _status_marker(status: str) -> str:
    """Return a stable plain-text marker for one status."""

    markers = {
        "healthy": "[OK]",
        "warning": "[!]",
        "critical": "[X]",
        "unknown": "[?]",
    }

    return markers.get(status, "[?]")


def _status_label(status: str) -> str:
    """Return a display label for one normalized status."""

    labels = {
        "healthy": "Healthy",
        "warning": "Warning",
        "critical": "Critical",
        "unknown": "Unknown",
    }

    return labels.get(
        status,
        status.replace("-", " ").title(),
    )


def render_report_human(report: OperationsReport) -> str:
    """Render the complete human-readable Operations report."""

    lines = [
        "Atlas Operations Report",
        "=======================",
        "",
        f"Report:      {report.report_id}",
        f"Generated:   {report.generated_at}",
        f"Host:        {report.hostname}",
        f"Version:     {report.atlas_version}",
        f"Commit:      {report.git_commit}",
        "",
        "Overall",
        "-------",
        (
            f"{_status_marker(report.status.value)} "
            f"Status: {_status_label(report.status.value)}"
        ),
        f"Score:       {report.score}/100",
        f"Sections:    {report.summary.section_count}",
        f"Findings:    {report.summary.finding_count}",
        f"Attention:   {report.summary.attention_count}",
        "",
        "Sections",
        "--------",
    ]

    if not report.sections:
        lines.append("No Operations sections were collected.")
    else:
        for section_index, section in enumerate(
            report.sections
        ):
            if section_index:
                lines.append("")

            lines.extend(
                [
                    (
                        f"{_status_marker(section.status.value)} "
                        f"{section.name}"
                    ),
                    (
                        f"  Status: "
                        f"{_status_label(section.status.value)}"
                    ),
                    f"  Score:  {section.score}/100",
                    (
                        f"  Findings: "
                        f"{len(section.findings)}"
                    ),
                ]
            )

            if section.description:
                lines.append(
                    f"  Description: {section.description}"
                )

            if not section.findings:
                lines.append("  No findings.")
                continue

            lines.append("")

            for finding in section.findings:
                lines.append(
                    "  "
                    f"{_status_marker(finding.status.value)} "
                    f"{finding.name}"
                )
                lines.append(
                    f"       {finding.message}"
                )

                if finding.recommendation:
                    lines.append(
                        "       Recommendation: "
                        f"{finding.recommendation}"
                    )

    lines.extend(
        [
            "",
            "Attention Required",
            "------------------",
        ]
    )

    if not report.attention_findings:
        lines.append("None.")
    else:
        for finding in report.attention_findings:
            lines.append(
                f"{_status_marker(finding.status.value)} "
                f"{finding.name}: {finding.message}"
            )

            if finding.recommendation:
                lines.append(
                    "     Recommendation: "
                    f"{finding.recommendation}"
                )

    return "\n".join(lines)


def _run_report(
    args: argparse.Namespace,
    *,
    service_factory: OperationsServiceFactory,
    stdout: TextIO,
    stderr: TextIO,
) -> int:
    try:
        service = service_factory()
        report = service.collect(
            report_id=args.report_id,
        )
    except Exception as exc:
        detail = (
            str(exc).strip()
            or exc.__class__.__name__
        )
        print(
            f"Operations report failed: {detail}",
            file=stderr,
        )
        return 1

    if args.json:
        print(
            report.to_json(),
            file=stdout,
        )
    else:
        print(
            render_report_human(report),
            file=stdout,
        )

    return 0


def main(
    argv: Sequence[str] | None = None,
    *,
    service_factory: OperationsServiceFactory = (
        default_service_factory
    ),
    stdout: TextIO | None = None,
    stderr: TextIO | None = None,
) -> int:
    """Run the Atlas Operations CLI and return an exit code."""

    output = stdout or sys.stdout
    errors = stderr or sys.stderr
    parser = build_parser()

    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)

    if args.command == "report":
        return _run_report(
            args,
            service_factory=service_factory,
            stdout=output,
            stderr=errors,
        )

    print(
        f"Unknown Operations command: {args.command}",
        file=errors,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
