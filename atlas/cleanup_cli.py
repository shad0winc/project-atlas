"""Command-line interface for Atlas cleanup planning."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from atlas.cleanup.models import CleanupDecision, CleanupError
from atlas.cleanup.service import CleanupService


def build_parser() -> argparse.ArgumentParser:
    """Build the Cleanup CLI argument parser."""

    parser = argparse.ArgumentParser(
        prog="atlas cleanup",
        description="Evaluate media cleanup recommendations.",
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


def main(
    argv: Sequence[str] | None = None,
    *,
    service: CleanupService | None = None,
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

    except (CleanupError, ValueError, RuntimeError) as exc:
        print(
            f"cleanup evaluation failed: {exc}",
            file=sys.stderr,
        )
        return 1

    parser.error(f"unsupported cleanup command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
