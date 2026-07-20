"""Command-line interface for Atlas retention decisions."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from atlas.policies import PolicyError
from atlas.retention import RetentionError, RetentionService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas retention",
        description="Evaluate Atlas media-retention decisions.",
    )

    subparsers = parser.add_subparsers(
        dest="action",
        required=True,
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Evaluate whether a media item is eligible for cleanup.",
    )
    evaluate_parser.add_argument(
        "provider",
        help="Media provider, such as jellyfin.",
    )
    evaluate_parser.add_argument(
        "item_id",
        help="Provider-specific media item ID.",
    )
    evaluate_parser.add_argument(
        "--json",
        action="store_true",
        help="Return the complete machine-readable decision.",
    )

    return parser


def _print_json(value: object) -> None:
    print(
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
        )
    )


def _print_decision(decision: object) -> None:
    data = decision.to_dict()
    policy = data["policy"]
    reasons = policy["reasons"]

    print("Atlas Retention Decision")
    print("------------------------")
    print(f"Provider: {data['provider']}")
    print(f"Item ID: {data['item_id']}")
    print(
        "Eligible for cleanup: "
        f"{'Yes' if data['eligible'] else 'No'}"
    )
    print(
        "Retained by Atlas: "
        f"{'Yes' if data['retained'] else 'No'}"
    )
    print(f"Policy action: {policy['action']}")

    if reasons:
        print("Reasons:")
        for reason in reasons:
            print(
                f"  - {reason['detail']} "
                f"[{reason['code']}]"
            )
    else:
        print("Reasons: None")

    print(f"Evaluated at: {data['evaluated_at']}")


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)

    try:
        if args.action == "evaluate":
            decision = RetentionService().evaluate(
                args.provider,
                args.item_id,
            )

            if args.json:
                _print_json(decision.to_dict())
            else:
                _print_decision(decision)

            return 0

    except (PolicyError, RetentionError) as exc:
        print(
            f"unable to evaluate retention: {exc}",
            file=sys.stderr,
        )
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
