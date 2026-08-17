"""Idempotent Scheduler callback for Q.6 sustained-use sampling."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Callable, Sequence

from .collector import collect_sample
from .lifecycle import (
    SustainedUseLifecycleError,
    sample_session,
)
from .models import (
    SustainedUseContract,
    SustainedUseSample,
)
from .repository import (
    DEFAULT_SUSTAINED_USE_DIRECTORY,
    FileSustainedUseRepository,
    SustainedUseRepository,
    SustainedUseRepositoryError,
    SustainedUseSampleNotFoundError,
)


SampleCollector = Callable[[], SustainedUseSample]


@dataclass(frozen=True)
class ScheduledSampleOutcome:
    """Result of one Scheduler callback decision."""

    action: str
    sample_count: int
    expected_sample_count: int | None
    passed: bool | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "action": self.action,
            "sample_count": self.sample_count,
            "expected_sample_count": self.expected_sample_count,
            "passed": self.passed,
        }


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def _contract_from_session(session) -> SustainedUseContract:
    return SustainedUseContract(
        git_commit=session.git_commit,
        duration_seconds=session.duration_seconds,
        interval_seconds=session.interval_seconds,
        expected_running_containers=(
            session.expected_running_containers
        ),
    )


def run_scheduled_sample(
    *,
    repository: SustainedUseRepository,
    collector: SampleCollector = collect_sample,
    now: datetime | None = None,
) -> ScheduledSampleOutcome:
    """Capture one sample only when an active Q.6 interval is due."""

    try:
        session = repository.session()
    except SustainedUseSampleNotFoundError:
        return ScheduledSampleOutcome(
            action="no_session",
            sample_count=0,
            expected_sample_count=None,
        )

    history = repository.history(
        limit=session.expected_sample_count + 1,
    )

    sample_count = len(history)

    if session.status != "active":
        return ScheduledSampleOutcome(
            action="inactive",
            sample_count=sample_count,
            expected_sample_count=(
                session.expected_sample_count
            ),
        )

    if sample_count >= session.expected_sample_count:
        return ScheduledSampleOutcome(
            action="complete",
            sample_count=sample_count,
            expected_sample_count=(
                session.expected_sample_count
            ),
        )

    current = (
        datetime.now(timezone.utc)
        if now is None
        else now
    )

    if current.tzinfo is None:
        raise SustainedUseLifecycleError(
            "scheduled sample timestamp must include a timezone"
        )

    if history:
        latest = history[0]

        due_at = _timestamp(
            latest.generated_at
        ).astimezone(timezone.utc)

        from datetime import timedelta

        due_at = due_at + timedelta(
            seconds=session.interval_seconds,
        )

        if current.astimezone(timezone.utc) < due_at:
            return ScheduledSampleOutcome(
                action="not_due",
                sample_count=sample_count,
                expected_sample_count=(
                    session.expected_sample_count
                ),
            )

    contract = _contract_from_session(
        session,
    )

    result = sample_session(
        contract=contract,
        repository=repository,
        collector=collector,
    )

    return ScheduledSampleOutcome(
        action="sampled",
        sample_count=sample_count + 1,
        expected_sample_count=(
            session.expected_sample_count
        ),
        passed=result.passed,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="atlas sustained-use scheduled-sample",
        description=(
            "Capture one due Q.6 sample while an active "
            "certification session exists."
        ),
    )

    parser.add_argument(
        "--root",
        type=Path,
        default=DEFAULT_SUSTAINED_USE_DIRECTORY,
        help=argparse.SUPPRESS,
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Render deterministic JSON output",
    )

    return parser


def main(
    argv: Sequence[str] | None = None,
) -> int:
    args = build_parser().parse_args(argv)

    repository = FileSustainedUseRepository(
        args.root,
    )

    try:
        outcome = run_scheduled_sample(
            repository=repository,
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

    payload = outcome.to_dict()

    if args.json:
        print(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
    else:
        for key, value in payload.items():
            if value is None:
                rendered = "none"
            elif isinstance(value, bool):
                rendered = str(value).lower()
            else:
                rendered = str(value)

            print(f"{key}={rendered}")

    if outcome.action == "sampled" and outcome.passed is False:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
