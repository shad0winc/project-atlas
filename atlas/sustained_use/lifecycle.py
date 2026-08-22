"""Lifecycle orchestration for Q.6 sustained-use certification."""

from __future__ import annotations

from dataclasses import dataclass, replace
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from .collector import collect_runtime_bus, collect_sample
from .evaluator import (
    SustainedUseEvaluation,
    evaluate_fixed_cadence,
    evaluate_history,
    evaluate_sample,
)
from .models import (
    RuntimeBusObservation,
    SustainedUseContract,
    SustainedUseSample,
    SustainedUseSession,
)
from .repository import SustainedUseRepository
from .terminal import (
    RuntimeBusTerminalEvaluation,
    RuntimeBusTerminalProbe,
    TERMINAL_CONVERGENCE_TIMEOUT_SECONDS,
    evaluate_runtime_bus_terminal_convergence,
)


SampleCollector = Callable[[], SustainedUseSample]
RuntimeBusCollector = Callable[[], RuntimeBusObservation]
TerminalSleeper = Callable[[float], None]
TerminalMonotonicClock = Callable[[], float]


class SustainedUseLifecycleError(RuntimeError):
    """Raised when a Q.6 lifecycle action cannot safely proceed."""


@dataclass(frozen=True)
class SustainedUseStartResult:
    """Result of establishing a strict T0."""

    session: SustainedUseSession
    sample: SustainedUseSample
    evaluation: SustainedUseEvaluation
    snapshot_path: Path

    @property
    def passed(self) -> bool:
        return self.evaluation.passed


@dataclass(frozen=True)
class SustainedUseStatus:
    """Read-only progress state for the current Q.6 run."""

    session: SustainedUseSession
    sample_count: int
    latest_sample: SustainedUseSample | None

    @property
    def remaining_samples(self) -> int:
        return max(
            0,
            self.session.expected_sample_count
            - self.sample_count,
        )


@dataclass(frozen=True)
class SustainedUseAbortResult:
    """Result of explicitly retiring an incomplete Q.6 run."""

    session: SustainedUseSession
    archive_path: Path


@dataclass(frozen=True)
class SustainedUseFinalizeResult:
    """Final hard + temporal + terminal certification result."""

    session: SustainedUseSession
    temporal_evaluation: SustainedUseEvaluation
    terminal_evaluation: RuntimeBusTerminalEvaluation
    hard_failure_count: int

    @property
    def passed(self) -> bool:
        return (
            self.session.status == "completed"
            and self.temporal_evaluation.passed
            and self.terminal_evaluation.passed
            and self.hard_failure_count == 0
        )


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def _utc_timestamp(value: datetime) -> str:
    if value.tzinfo is None:
        raise SustainedUseLifecycleError(
            "timestamp must include a timezone",
        )

    return (
        value.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _run_id(started_at: str) -> str:
    parsed = _parse_timestamp(started_at)

    return (
        "q6-"
        + parsed.astimezone(timezone.utc)
        .strftime("%Y%m%dT%H%M%SZ")
    )


def start_session(
    *,
    contract: SustainedUseContract,
    repository: SustainedUseRepository,
    collector: SampleCollector = collect_sample,
) -> SustainedUseStartResult:
    """Strictly validate T0 before establishing the durable run."""

    sample = collector()

    if not isinstance(sample, SustainedUseSample):
        raise SustainedUseLifecycleError(
            "collector did not return a SustainedUseSample",
        )

    evaluation = evaluate_sample(
        sample,
        contract,
    )

    if not evaluation.passed:
        raise SustainedUseLifecycleError(
            "T0 failed strict Q.6 evaluation: "
            + ", ".join(evaluation.failed_codes)
        )

    started = _parse_timestamp(
        sample.generated_at,
    )

    scheduled_end = started + timedelta(
        seconds=contract.duration_seconds,
    )

    session = SustainedUseSession.from_contract(
        run_id=_run_id(sample.generated_at),
        started_at=sample.generated_at,
        scheduled_end_at=_utc_timestamp(scheduled_end),
        contract=contract,
    )

    repository.create_session(
        session,
    )

    snapshot_path = repository.save(
        sample,
    )

    return SustainedUseStartResult(
        session=session,
        sample=sample,
        evaluation=evaluation,
        snapshot_path=snapshot_path,
    )


def sample_session(
    *,
    contract: SustainedUseContract,
    repository: SustainedUseRepository,
    collector: SampleCollector = collect_sample,
):
    """Capture one sample for an existing active session."""

    from .service import SustainedUseRunResult

    session = repository.session()

    if session.status != "active":
        raise SustainedUseLifecycleError(
            "sustained-use session is not active",
        )

    if session.git_commit != contract.git_commit:
        raise SustainedUseLifecycleError(
            "session Git commit differs from requested contract",
        )

    sample = collector()

    if not isinstance(sample, SustainedUseSample):
        raise SustainedUseLifecycleError(
            "collector did not return a SustainedUseSample",
        )

    evaluation = evaluate_sample(
        sample,
        contract,
    )

    snapshot_path = repository.save(
        sample,
    )

    return SustainedUseRunResult(
        sample=sample,
        evaluation=evaluation,
        snapshot_path=snapshot_path,
    )


def status_session(
    *,
    repository: SustainedUseRepository,
) -> SustainedUseStatus:
    """Read the durable session and current sample progress."""

    session = repository.session()

    history = repository.history(
        limit=session.expected_sample_count + 1,
    )

    latest = (
        history[0]
        if history
        else None
    )

    return SustainedUseStatus(
        session=session,
        sample_count=len(history),
        latest_sample=latest,
    )


def abort_session(
    *,
    repository: SustainedUseRepository,
    now: datetime | None = None,
) -> SustainedUseAbortResult:
    """Abort and archive one incomplete active Q.6 session.

    If the session was already transitioned to ``aborted`` but
    archival was interrupted before session.json moved, retry the
    archive operation without changing the completion timestamp.
    """

    session = repository.session()

    if session.status not in {
        "active",
        "aborted",
    }:
        raise SustainedUseLifecycleError(
            "only an active or partially archived aborted "
            "sustained-use session can be aborted",
        )

    if session.status == "active":
        current = (
            datetime.now(timezone.utc)
            if now is None
            else now
        )

        if current.tzinfo is None:
            raise SustainedUseLifecycleError(
                "abort timestamp must include a timezone",
            )

        closed = replace(
            session,
            status="aborted",
            completed_at=_utc_timestamp(current),
        )

        repository.update_session(
            closed,
        )
    else:
        closed = session

    archive_path = repository.archive_session(
        closed,
    )

    return SustainedUseAbortResult(
        session=closed,
        archive_path=archive_path,
    )



def _observe_runtime_bus_terminal_convergence(
    initial: RuntimeBusObservation,
    *,
    collector: RuntimeBusCollector = collect_runtime_bus,
    sleeper: TerminalSleeper = time.sleep,
    monotonic: TerminalMonotonicClock = time.monotonic,
    timeout_seconds: int = TERMINAL_CONVERGENCE_TIMEOUT_SECONDS,
    poll_seconds: int = 1,
) -> RuntimeBusTerminalEvaluation:
    """Prove Notifications consumes through the frozen terminal journal tail."""

    if not isinstance(initial, RuntimeBusObservation):
        raise TypeError("initial must be a RuntimeBusObservation")
    if isinstance(poll_seconds, bool) or not isinstance(poll_seconds, int):
        raise TypeError("poll_seconds must be an integer")
    if poll_seconds <= 0:
        raise ValueError("poll_seconds must be greater than zero")

    target = initial.journal_lines
    probes = (RuntimeBusTerminalProbe(elapsed_seconds=0, runtime_bus=initial),)
    evaluation = evaluate_runtime_bus_terminal_convergence(
        probes, target_journal_lines=target, timeout_seconds=timeout_seconds
    )
    if not evaluation.pending:
        return evaluation

    started = monotonic()
    while evaluation.pending:
        previous_elapsed = probes[-1].elapsed_seconds
        remaining = timeout_seconds - previous_elapsed
        if remaining <= 0:
            return evaluation
        sleeper(float(min(poll_seconds, remaining)))
        observed = collector()
        if not isinstance(observed, RuntimeBusObservation):
            raise TypeError("terminal collector must return RuntimeBusObservation")
        raw_elapsed = monotonic() - started
        if raw_elapsed < 0:
            raise SustainedUseLifecycleError("terminal monotonic clock moved backward")
        elapsed = min(timeout_seconds, max(previous_elapsed, int(raw_elapsed)))
        if elapsed == previous_elapsed:
            elapsed = min(timeout_seconds, previous_elapsed + 1)
        probes = (*probes, RuntimeBusTerminalProbe(elapsed_seconds=elapsed, runtime_bus=observed))
        evaluation = evaluate_runtime_bus_terminal_convergence(
            probes, target_journal_lines=target, timeout_seconds=timeout_seconds
        )
    return evaluation

def finalize_session(
    *,
    contract: SustainedUseContract,
    repository: SustainedUseRepository,
    now: datetime | None = None,
    runtime_bus_collector: RuntimeBusCollector = collect_runtime_bus,
    terminal_sleeper: TerminalSleeper = time.sleep,
    terminal_monotonic: TerminalMonotonicClock = time.monotonic,
    terminal_timeout_seconds: int = TERMINAL_CONVERGENCE_TIMEOUT_SECONDS,
    terminal_poll_seconds: int = 1,
) -> SustainedUseFinalizeResult:
    """Evaluate the completed history and close the Q.6 run."""

    session = repository.session()

    if session.status != "active":
        raise SustainedUseLifecycleError(
            "sustained-use session is not active",
        )

    if session.git_commit != contract.git_commit:
        raise SustainedUseLifecycleError(
            "session Git commit differs from requested contract",
        )

    current = (
        datetime.now(timezone.utc)
        if now is None
        else now
    )

    if current.tzinfo is None:
        raise SustainedUseLifecycleError(
            "finalize timestamp must include a timezone",
        )

    scheduled_end = _parse_timestamp(
        session.scheduled_end_at,
    )

    if current.astimezone(timezone.utc) < scheduled_end:
        raise SustainedUseLifecycleError(
            "Q.6 scheduled end has not been reached",
        )

    newest_first = repository.history(
        limit=session.expected_sample_count + 1,
    )

    if len(newest_first) != session.expected_sample_count:
        raise SustainedUseLifecycleError(
            "Q.6 sample count is incomplete: "
            f"{len(newest_first)}/"
            f"{session.expected_sample_count}"
        )

    samples = tuple(
        reversed(newest_first)
    )

    hard_evaluations = tuple(
        evaluate_sample(
            sample,
            contract,
        )
        for sample in samples
    )

    hard_failure_count = sum(
        not evaluation.passed
        for evaluation in hard_evaluations
    )

    temporal_history = evaluate_history(
        samples,
        contract,
    )

    cadence = evaluate_fixed_cadence(
        samples,
        contract,
        started_at=session.started_at,
    )

    temporal = SustainedUseEvaluation(
        findings=(
            temporal_history.findings
            + cadence.findings
        ),
    )

    try:
        terminal = _observe_runtime_bus_terminal_convergence(
            samples[-1].runtime_bus,
            collector=runtime_bus_collector,
            sleeper=terminal_sleeper,
            monotonic=terminal_monotonic,
            timeout_seconds=terminal_timeout_seconds,
            poll_seconds=terminal_poll_seconds,
        )
    except Exception as error:
        if isinstance(error, SustainedUseLifecycleError):
            raise
        raise SustainedUseLifecycleError(
            "Runtime Bus terminal convergence observation failed"
        ) from error

    final_status = (
        "completed"
        if (
            hard_failure_count == 0
            and temporal.passed
            and terminal.passed
        )
        else "failed"
    )

    closed = replace(
        session,
        status=final_status,
        completed_at=_utc_timestamp(current),
    )

    repository.update_session(
        closed,
    )

    return SustainedUseFinalizeResult(
        session=closed,
        temporal_evaluation=temporal,
        terminal_evaluation=terminal,
        hard_failure_count=hard_failure_count,
    )
