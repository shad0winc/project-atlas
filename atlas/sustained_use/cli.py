"""Executable CLI adapter for Q.6 sustained-use certification."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence

from .lifecycle import (
    SustainedUseFinalizeResult,
    SustainedUseLifecycleError,
    SustainedUseStartResult,
    SustainedUseStatus,
    finalize_session,
    sample_session,
    start_session,
    status_session,
)
from .models import (
    SustainedUseContract,
    SustainedUseSession,
)
from .repository import (
    DEFAULT_SUSTAINED_USE_DIRECTORY,
    FileSustainedUseRepository,
    SustainedUseRepositoryError,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the executable `atlas sustained-use` parser."""

    parser = argparse.ArgumentParser(
        prog="atlas sustained-use",
        description=(
            "Manage the Project Atlas Q.6 sustained-use "
            "release-certification lifecycle."
        ),
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_SUSTAINED_USE_DIRECTORY,
        help=argparse.SUPPRESS,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    for name, help_text in (
        (
            "start",
            "Validate and persist the strict T0 sample",
        ),
        (
            "sample",
            "Capture one sample for the active Q.6 session",
        ),
        (
            "status",
            "Show the current Q.6 session and progress",
        ),
        (
            "finalize",
            "Evaluate and close the completed Q.6 session",
        ),
    ):
        subparser = subparsers.add_parser(
            name,
            help=help_text,
        )

        subparser.add_argument(
            "--json",
            action="store_true",
            help="Render deterministic JSON output",
        )

    return parser


def _current_git_commit() -> str:
    try:
        result = subprocess.run(
            (
                "git",
                "rev-parse",
                "HEAD",
            ),
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        raise SustainedUseLifecycleError(
            "unable to resolve the current Git commit",
        ) from error

    commit = result.stdout.strip()

    if len(commit) != 40:
        raise SustainedUseLifecycleError(
            "current Git commit is not a full SHA",
        )

    return commit


def _contract_from_session(
    session: SustainedUseSession,
) -> SustainedUseContract:
    return SustainedUseContract(
        git_commit=session.git_commit,
        duration_seconds=session.duration_seconds,
        interval_seconds=session.interval_seconds,
        expected_running_containers=(
            session.expected_running_containers
        ),
    )


def _start_payload(
    result: SustainedUseStartResult,
) -> dict[str, object]:
    return {
        "command": "start",
        "passed": result.passed,
        "run_id": result.session.run_id,
        "status": result.session.status,
        "started_at": result.session.started_at,
        "scheduled_end_at": result.session.scheduled_end_at,
        "expected_sample_count": (
            result.session.expected_sample_count
        ),
        "sample_generated_at": result.sample.generated_at,
        "snapshot_path": str(result.snapshot_path),
        "failed_codes": list(
            result.evaluation.failed_codes
        ),
    }


def _sample_payload(result) -> dict[str, object]:
    return {
        "command": "sample",
        "passed": result.passed,
        "sample_generated_at": result.sample.generated_at,
        "snapshot_path": str(result.snapshot_path),
        "failed_codes": list(
            result.evaluation.failed_codes
        ),
    }


def _status_payload(
    result: SustainedUseStatus,
) -> dict[str, object]:
    return {
        "command": "status",
        "run_id": result.session.run_id,
        "status": result.session.status,
        "started_at": result.session.started_at,
        "scheduled_end_at": result.session.scheduled_end_at,
        "sample_count": result.sample_count,
        "expected_sample_count": (
            result.session.expected_sample_count
        ),
        "remaining_samples": result.remaining_samples,
        "latest_sample_generated_at": (
            result.latest_sample.generated_at
            if result.latest_sample is not None
            else None
        ),
    }


def _finalize_payload(
    result: SustainedUseFinalizeResult,
) -> dict[str, object]:
    return {
        "command": "finalize",
        "passed": result.passed,
        "run_id": result.session.run_id,
        "status": result.session.status,
        "completed_at": result.session.completed_at,
        "hard_failure_count": result.hard_failure_count,
        "temporal_failed_codes": list(
            result.temporal_evaluation.failed_codes
        ),
    }


def _render(
    payload: dict[str, object],
    *,
    as_json: bool,
) -> None:
    if as_json:
        print(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return

    for key, value in payload.items():
        if isinstance(value, list):
            rendered = (
                ",".join(str(item) for item in value)
                if value
                else "none"
            )
        elif value is None:
            rendered = "none"
        elif isinstance(value, bool):
            rendered = str(value).lower()
        else:
            rendered = str(value)

        print(f"{key}={rendered}")


def main(
    argv: Sequence[str] | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    repository = FileSustainedUseRepository(
        args.root,
    )

    try:
        if args.command == "start":
            contract = SustainedUseContract(
                git_commit=_current_git_commit(),
            )

            result = start_session(
                contract=contract,
                repository=repository,
            )

            _render(
                _start_payload(result),
                as_json=args.json,
            )

            return 0

        session = repository.session()
        contract = _contract_from_session(
            session,
        )

        if args.command == "sample":
            result = sample_session(
                contract=contract,
                repository=repository,
            )

            _render(
                _sample_payload(result),
                as_json=args.json,
            )

            return 0 if result.passed else 1

        if args.command == "status":
            result = status_session(
                repository=repository,
            )

            _render(
                _status_payload(result),
                as_json=args.json,
            )

            return 0

        if args.command == "finalize":
            result = finalize_session(
                contract=contract,
                repository=repository,
            )

            _render(
                _finalize_payload(result),
                as_json=args.json,
            )

            return 0 if result.passed else 1

        parser.error(
            f"unknown sustained-use command: {args.command}"
        )

    except (
        SustainedUseLifecycleError,
        SustainedUseRepositoryError,
    ) as error:
        print(
            f"ERROR: {error}",
            file=sys.stderr,
        )
        return 1

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
