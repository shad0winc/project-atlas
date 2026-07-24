"""Command-line interface for Atlas cleanup operations."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from atlas.cleanup.execution_models import CleanupExecutionReport
from atlas.cleanup.execution_service import CleanupExecutionService
from atlas.cleanup.executor import (
    CleanupExecutionError,
    CleanupExecutionSummary,
)
from atlas.cleanup.models import CleanupDecision, CleanupError
from atlas.cleanup.scan_models import CleanupScanReport
from atlas.cleanup.scanner import CleanupScanner
from atlas.cleanup.service import CleanupService
from atlas.cleanup.workflow import CleanupWorkflowService
from atlas.media.jellyfin import (
    JellyfinProvider,
    default_jellyfin_provider,
)
from atlas.media.provider import MediaProviderError


def build_parser() -> argparse.ArgumentParser:
    """Build the Cleanup CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="atlas cleanup",
        description=(
            "Evaluate, scan, plan, and safely preview media cleanup."
        ),
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Evaluate one media item for cleanup.",
    )
    evaluate_parser.add_argument(
        "provider",
        help="Media provider name, such as jellyfin.",
    )
    evaluate_parser.add_argument(
        "item_id",
        help="Provider-specific media item identifier.",
    )
    evaluate_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output the cleanup decision as JSON.",
    )

    scan_parser = subparsers.add_parser(
        "scan",
        help="Scan a provider library for cleanup recommendations.",
    )
    scan_parser.add_argument(
        "provider",
        help="Media provider name, such as jellyfin.",
    )
    scan_parser.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="Number of provider items requested per page.",
    )
    scan_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output the cleanup scan report as JSON.",
    )

    execute_parser = subparsers.add_parser(
        "execute",
        help="Build a non-destructive cleanup execution plan.",
    )
    execute_parser.add_argument(
        "provider",
        help="Media provider name, such as jellyfin.",
    )
    execute_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help="Plan cleanup actions without modifying media.",
    )
    execute_parser.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="Number of provider items requested per page.",
    )
    execute_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output the cleanup execution report as JSON.",
    )

    run_parser = subparsers.add_parser(
        "run",
        help=(
            "Run the complete cleanup workflow using safe "
            "provider previews."
        ),
    )
    run_parser.add_argument(
        "provider",
        help="Media provider name, such as jellyfin.",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        default=True,
        help=(
            "Preview planned cleanup actions without modifying media."
        ),
    )
    run_parser.add_argument(
        "--page-size",
        type=int,
        default=200,
        help="Number of provider items requested per page.",
    )
    run_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output the cleanup workflow summary as JSON.",
    )

    return parser


def render_human(decision: CleanupDecision) -> str:
    """Render a cleanup decision for terminal users."""

    retention = decision.retention
    policy = retention.policy

    reasons = (
        "\n".join(
            f"  - [{reason.source}] {reason.code}: {reason.detail}"
            for reason in policy.reasons
        )
        if policy.reasons
        else "  - None"
    )

    return "\n".join(
        [
            "Atlas Cleanup Decision",
            "----------------------",
            f"Provider: {decision.provider}",
            f"Item ID: {decision.item_id}",
            f"Action: {decision.action.value}",
            f"Eligible for cleanup: {retention.eligible}",
            f"Retained by Atlas: {retention.retained}",
            f"Policy action: {policy.action.value}",
            "Reasons:",
            reasons,
            f"Evaluated at: {decision.evaluated_at}",
        ]
    )


def render_scan_human(report: CleanupScanReport) -> str:
    """Render a cleanup scan report for terminal users."""

    decisions = (
        "\n".join(
            f"  - {decision.action.value.upper()}: "
            f"{decision.item_id}"
            for decision in report.decisions
        )
        if report.decisions
        else "  - None"
    )

    return "\n".join(
        [
            "Atlas Cleanup Scan",
            "------------------",
            f"Provider: {report.provider}",
            f"Scanned: {report.scanned}",
            f"Delete: {report.delete_count}",
            f"Keep: {report.keep_count}",
            f"Review: {report.review_count}",
            "Decisions:",
            decisions,
            f"Scanned at: {report.scanned_at}",
        ]
    )


def render_execution_human(
    report: CleanupExecutionReport,
) -> str:
    """Render a cleanup execution plan for terminal users."""

    planned_items = tuple(
        item
        for item in report.items
        if item.status.value == "planned"
    )

    planned = (
        "\n".join(
            f"  - {item.item_id}"
            for item in planned_items
        )
        if planned_items
        else "  - None"
    )

    return "\n".join(
        [
            "Atlas Cleanup Execution Plan",
            "----------------------------",
            f"Provider: {report.provider}",
            f"Mode: {report.mode.value}",
            f"Total: {report.total}",
            f"Planned: {report.planned_count}",
            f"Skipped: {report.skipped_count}",
            f"Modified: {report.modified_count}",
            "Planned items:",
            planned,
            f"Created at: {report.created_at}",
        ]
    )


def render_workflow_human(
    summary: CleanupExecutionSummary,
) -> str:
    """Render a complete cleanup workflow summary."""

    errors = (
        "\n".join(
            f"  - {error}"
            for error in summary.errors
        )
        if summary.errors
        else "  - None"
    )

    return "\n".join(
        [
            "Atlas Cleanup Workflow",
            "----------------------",
            f"Provider: {summary.provider}",
            f"Mode: {summary.mode.value}",
            f"Status: {summary.status.value}",
            f"Total: {summary.total}",
            f"Planned: {summary.planned}",
            f"Skipped: {summary.skipped}",
            f"Modified: {summary.modified}",
            "Errors:",
            errors,
            f"Started at: {summary.started_at}",
            f"Completed at: {summary.completed_at}",
        ]
    )


def _provider_name(
    value: str,
    *,
    operation: str,
) -> str:
    """Validate and normalize a supported provider name."""

    provider_name = value.strip().lower()

    if provider_name != "jellyfin":
        raise CleanupError(
            f"unsupported cleanup {operation} provider: "
            f"{provider_name or value}"
        )

    return provider_name


def main(
    argv: Sequence[str] | None = None,
    *,
    service: CleanupService | None = None,
    scanner: CleanupScanner | None = None,
    execution_service: CleanupExecutionService | None = None,
    workflow_service: CleanupWorkflowService | None = None,
    jellyfin_provider: JellyfinProvider | None = None,
) -> int:
    """Run the Cleanup CLI."""

    parser = build_parser()
    args = parser.parse_args(argv)

    cleanup_service = (
        service
        if service is not None
        else CleanupService()
    )

    try:
        if args.command == "evaluate":
            decision = cleanup_service.evaluate(
                args.provider,
                args.item_id,
            )

            if args.json_output:
                print(
                    json.dumps(
                        decision.to_dict(),
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print(render_human(decision))

            return 0

        if args.command in {"scan", "execute", "run"}:
            provider_operation = {
                "scan": "scan",
                "execute": "execution",
                "run": "workflow",
            }[args.command]

            provider_name = _provider_name(
                args.provider,
                operation=provider_operation,
            )

            provider = (
                jellyfin_provider
                if jellyfin_provider is not None
                else default_jellyfin_provider()
            )

            cleanup_scanner = (
                scanner
                if scanner is not None
                else CleanupScanner(cleanup_service)
            )

            planner = (
                execution_service
                if execution_service is not None
                else CleanupExecutionService()
            )

            if args.command == "run":
                workflow = (
                    workflow_service
                    if workflow_service is not None
                    else CleanupWorkflowService(
                        scanner=cleanup_scanner,
                        planner=planner,
                    )
                )

                summary = workflow.execute(
                    provider,
                    page_size=args.page_size,
                    mode="dry_run",
                )

                if args.json_output:
                    print(
                        json.dumps(
                            summary.to_dict(),
                            indent=2,
                            sort_keys=True,
                        )
                    )
                else:
                    print(render_workflow_human(summary))

                return 0

            item_ids = provider.list_media_item_ids(
                page_size=args.page_size
            )

            scan_report = cleanup_scanner.scan(
                provider_name,
                item_ids,
            )

            if args.command == "scan":
                if args.json_output:
                    print(
                        json.dumps(
                            scan_report.to_dict(),
                            indent=2,
                            sort_keys=True,
                        )
                    )
                else:
                    print(render_scan_human(scan_report))

                return 0

            execution_report = planner.plan(
                scan_report,
                mode="dry_run",
            )

            if args.json_output:
                print(
                    json.dumps(
                        execution_report.to_dict(),
                        indent=2,
                        sort_keys=True,
                    )
                )
            else:
                print(
                    render_execution_human(
                        execution_report
                    )
                )

            return 0

    except (
        CleanupError,
        CleanupExecutionError,
        MediaProviderError,
        ValueError,
        RuntimeError,
    ) as exc:
        operation = {
            "evaluate": "evaluation",
            "scan": "scan",
            "execute": "execution",
            "run": "workflow",
        }.get(
            args.command,
            args.command,
        )

        print(
            f"cleanup {operation} failed: {exc}",
            file=sys.stderr,
        )
        return 1

    parser.error(
        f"unsupported cleanup command: {args.command}"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
