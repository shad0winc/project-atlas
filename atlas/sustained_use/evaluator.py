"""Evaluation contracts for Atlas sustained-use certification."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Final

from .models import (
    SustainedUseContract,
    SustainedUseSample,
)


MAX_ROOT_USAGE_PERCENT: Final = 85
MAX_STORAGE_USAGE_PERCENT: Final = 90
MAX_HEARTBEAT_AGE_SECONDS: Final = 30

EXPECTED_JOURNAL_UID: Final = 0
EXPECTED_JOURNAL_GID: Final = 20000
EXPECTED_JOURNAL_MODE: Final = 660

MIN_ARI_SCORE: Final = 80
BASELINE_ARI_WARNINGS: Final = frozenset(
    {
        "Library synchronization failed",
    }
)


@dataclass(frozen=True)
class SustainedUseFinding:
    """One deterministic sustained-use evaluation finding."""

    code: str
    passed: bool
    message: str

    def __post_init__(self) -> None:
        for field in ("code", "message"):
            value = getattr(self, field)

            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{field} must be a non-empty string",
                )

        if not isinstance(self.passed, bool):
            raise ValueError(
                "passed must be a boolean",
            )

        object.__setattr__(
            self,
            "code",
            self.code.strip(),
        )

        object.__setattr__(
            self,
            "message",
            self.message.strip(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass(frozen=True)
class SustainedUseEvaluation:
    """Evaluation result for one sustained-use sample."""

    findings: tuple[SustainedUseFinding, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.findings, tuple):
            raise ValueError(
                "findings must be a tuple",
            )

        if not all(
            isinstance(item, SustainedUseFinding)
            for item in self.findings
        ):
            raise ValueError(
                "findings must contain SustainedUseFinding values",
            )

        codes = tuple(
            item.code
            for item in self.findings
        )

        if len(codes) != len(set(codes)):
            raise ValueError(
                "finding codes must be unique",
            )

    @property
    def passed(self) -> bool:
        return all(
            item.passed
            for item in self.findings
        )

    @property
    def failed_codes(self) -> tuple[str, ...]:
        return tuple(
            item.code
            for item in self.findings
            if not item.passed
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "failed_codes": list(self.failed_codes),
            "findings": [
                item.to_dict()
                for item in self.findings
            ],
        }


def _finding(
    code: str,
    passed: bool,
    success: str,
    failure: str,
) -> SustainedUseFinding:
    return SustainedUseFinding(
        code=code,
        passed=passed,
        message=(
            success
            if passed
            else failure
        ),
    )


def evaluate_sample(
    sample: SustainedUseSample,
    contract: SustainedUseContract,
) -> SustainedUseEvaluation:
    """Evaluate hard invariants that must hold for every Q.6 sample."""

    if not isinstance(sample, SustainedUseSample):
        raise TypeError(
            "sample must be a SustainedUseSample",
        )

    if not isinstance(contract, SustainedUseContract):
        raise TypeError(
            "contract must be a SustainedUseContract",
        )

    findings: list[SustainedUseFinding] = []

    findings.append(
        _finding(
            "git.commit",
            sample.git_commit == contract.git_commit,
            "Git commit matches the certified Q.6 candidate.",
            (
                "Git commit differs from the certified Q.6 "
                f"candidate: {sample.git_commit}"
            ),
        )
    )

    findings.append(
        _finding(
            "atlas.health.status",
            sample.atlas_health_status == "healthy",
            "Atlas health status is healthy.",
            (
                "Atlas health status is not healthy: "
                f"{sample.atlas_health_status}"
            ),
        )
    )

    findings.append(
        _finding(
            "atlas.health.score",
            sample.atlas_health_score == 100,
            "Atlas health score is 100.",
            (
                "Atlas health score is not 100: "
                f"{sample.atlas_health_score}"
            ),
        )
    )

    findings.append(
        _finding(
            "containers.count",
            (
                sample.running_containers
                == contract.expected_running_containers
            ),
            "Expected production container count is running.",
            (
                "Unexpected running container count: "
                f"{sample.running_containers}; expected "
                f"{contract.expected_running_containers}"
            ),
        )
    )

    findings.append(
        _finding(
            "containers.unhealthy",
            sample.unhealthy_containers == 0,
            "No unhealthy Docker containers were observed.",
            (
                "Unhealthy Docker containers observed: "
                f"{sample.unhealthy_containers}"
            ),
        )
    )

    non_running = tuple(
        item.name
        for item in sample.containers
        if item.status != "running"
    )

    findings.append(
        _finding(
            "containers.status",
            not non_running,
            "Every collected Docker container is running.",
            "Non-running containers: " + ", ".join(non_running),
        )
    )

    restarted = tuple(
        item.name
        for item in sample.containers
        if item.restart_count != 0
    )

    findings.append(
        _finding(
            "containers.restarts",
            not restarted,
            "No Docker container restart was observed.",
            "Containers with restart count: " + ", ".join(restarted),
        )
    )

    oom = tuple(
        item.name
        for item in sample.containers
        if item.oom_killed
    )

    findings.append(
        _finding(
            "containers.oom",
            not oom,
            "No Docker container OOM kill was observed.",
            "OOM-killed containers: " + ", ".join(oom),
        )
    )

    findings.append(
        _finding(
            "filesystem.root",
            sample.root_usage_percent < MAX_ROOT_USAGE_PERCENT,
            (
                "Root filesystem remains below "
                f"{MAX_ROOT_USAGE_PERCENT}%."
            ),
            (
                "Root filesystem reached "
                f"{sample.root_usage_percent}%."
            ),
        )
    )

    findings.append(
        _finding(
            "filesystem.storage",
            sample.storage_usage_percent < MAX_STORAGE_USAGE_PERCENT,
            (
                "Atlas storage remains below "
                f"{MAX_STORAGE_USAGE_PERCENT}%."
            ),
            (
                "Atlas storage reached "
                f"{sample.storage_usage_percent}%."
            ),
        )
    )

    bus = sample.runtime_bus

    identity_ok = (
        bus.journal_uid == EXPECTED_JOURNAL_UID
        and bus.journal_gid == EXPECTED_JOURNAL_GID
        and bus.journal_mode == EXPECTED_JOURNAL_MODE
    )

    findings.append(
        _finding(
            "runtime_bus.identity",
            identity_ok,
            "Runtime Bus journal ownership and mode are preserved.",
            (
                "Runtime Bus journal contract changed: "
                f"uid={bus.journal_uid} "
                f"gid={bus.journal_gid} "
                f"mode={bus.journal_mode}"
            ),
        )
    )

    findings.append(
        _finding(
            "runtime_bus.readable",
            bus.journal_readable,
            "Notifications can read the Runtime Bus journal.",
            "Notifications cannot read the Runtime Bus journal.",
        )
    )

    findings.append(
        _finding(
            "runtime_bus.read_only",
            not bus.journal_writable,
            "Notifications cannot write the Runtime Bus journal.",
            "Notifications can write the Runtime Bus journal.",
        )
    )

    findings.append(
        _finding(
            "notifications.heartbeat",
            (
                bus.heartbeat_age_seconds
                < MAX_HEARTBEAT_AGE_SECONDS
            ),
            "Notifications heartbeat is fresh.",
            (
                "Notifications heartbeat is stale: "
                f"{bus.heartbeat_age_seconds}s"
            ),
        )
    )

    ari = sample.ari

    findings.append(
        _finding(
            "ari.score",
            ari.score >= MIN_ARI_SCORE,
            "ARI score has not degraded below the frozen baseline.",
            (
                "ARI score degraded below baseline: "
                f"{ari.score}"
            ),
        )
    )

    unexpected_warnings = tuple(
        warning
        for warning in ari.warnings
        if warning not in BASELINE_ARI_WARNINGS
    )

    findings.append(
        _finding(
            "ari.warnings",
            not unexpected_warnings,
            "ARI has no warnings beyond the frozen baseline.",
            (
                "Unexpected ARI warnings: "
                + " | ".join(unexpected_warnings)
            ),
        )
    )

    return SustainedUseEvaluation(
        findings=tuple(findings),
    )


def _scheduler_map(
    sample: SustainedUseSample,
) -> dict[str, Any]:
    return {
        item.name: item
        for item in sample.schedulers
    }


def _tv_difference(
    sample: SustainedUseSample,
) -> int | None:
    filesystem = sample.ari.tv_filesystem_count
    jellyfin = sample.ari.tv_jellyfin_count

    if filesystem is None or jellyfin is None:
        return None

    return abs(
        jellyfin - filesystem
    )


def evaluate_history(
    samples: tuple[SustainedUseSample, ...],
    contract: SustainedUseContract,
) -> SustainedUseEvaluation:
    """Evaluate sustained behavior across an ordered Q.6 history."""

    if not isinstance(samples, tuple):
        raise TypeError(
            "samples must be a tuple",
        )

    if not samples:
        raise ValueError(
            "samples cannot be empty",
        )

    if not all(
        isinstance(item, SustainedUseSample)
        for item in samples
    ):
        raise TypeError(
            "samples must contain SustainedUseSample values",
        )

    if not isinstance(contract, SustainedUseContract):
        raise TypeError(
            "contract must be a SustainedUseContract",
        )

    findings: list[SustainedUseFinding] = []

    commit_ok = all(
        item.git_commit == contract.git_commit
        for item in samples
    )

    findings.append(
        _finding(
            "history.git.commit",
            commit_ok,
            "Every sustained-use sample uses the certified Git commit.",
            "One or more sustained-use samples use another Git commit.",
        )
    )

    timestamps = tuple(
        item.generated_at
        for item in samples
    )

    ordered = timestamps == tuple(
        sorted(timestamps)
    )

    findings.append(
        _finding(
            "history.order",
            ordered,
            "Sustained-use samples are chronologically ordered.",
            "Sustained-use sample timestamps are not ordered.",
        )
    )

    baseline = samples[0]
    final = samples[-1]

    journal_monotonic = all(
        later.runtime_bus.journal_lines
        >= earlier.runtime_bus.journal_lines
        for earlier, later in zip(
            samples,
            samples[1:],
        )
    )

    findings.append(
        _finding(
            "runtime_bus.journal.monotonic",
            journal_monotonic,
            "Runtime Bus journal line count never moved backward.",
            "Runtime Bus journal line count moved backward.",
        )
    )

    cursor_monotonic = all(
        later.runtime_bus.cursor_value
        >= earlier.runtime_bus.cursor_value
        for earlier, later in zip(
            samples,
            samples[1:],
        )
    )

    findings.append(
        _finding(
            "runtime_bus.cursor.monotonic",
            cursor_monotonic,
            "Notifications cursor never moved backward.",
            "Notifications cursor moved backward.",
        )
    )

    findings.append(
        _finding(
            "runtime_bus.final_backlog",
            final.runtime_bus.backlog == 0,
            "Notifications finishes the Q.6 window caught up.",
            (
                "Notifications finishes with Runtime Bus backlog: "
                f"{final.runtime_bus.backlog}"
            ),
        )
    )

    baseline_schedulers = _scheduler_map(
        baseline,
    )
    final_schedulers = _scheduler_map(
        final,
    )

    watched_names = tuple(
        sorted(
            set(baseline_schedulers)
            | set(final_schedulers)
        )
    )

    scheduler_presence_ok = all(
        name in baseline_schedulers
        and name in final_schedulers
        for name in watched_names
    )

    findings.append(
        _finding(
            "scheduler.presence",
            scheduler_presence_ok,
            "Watched schedulers are present at T0 and final sample.",
            "A watched scheduler is missing from T0 or final sample.",
        )
    )

    scheduler_failures_stable = True
    scheduler_run_counts_monotonic = True
    scheduler_progress = True

    for name in watched_names:
        if (
            name not in baseline_schedulers
            or name not in final_schedulers
        ):
            scheduler_failures_stable = False
            scheduler_run_counts_monotonic = False
            scheduler_progress = False
            continue

        previous_run_count = None
        previous_failure_count = None

        for sample in samples:
            current = _scheduler_map(sample).get(name)

            if current is None:
                scheduler_failures_stable = False
                scheduler_run_counts_monotonic = False
                continue

            if previous_run_count is not None:
                if current.run_count < previous_run_count:
                    scheduler_run_counts_monotonic = False

                if current.failure_count > previous_failure_count:
                    scheduler_failures_stable = False

            previous_run_count = current.run_count
            previous_failure_count = current.failure_count

        start = baseline_schedulers[name]
        end = final_schedulers[name]

        if end.run_count <= start.run_count:
            scheduler_progress = False

        if end.failure_count != start.failure_count:
            scheduler_failures_stable = False

    findings.append(
        _finding(
            "scheduler.run_count.monotonic",
            scheduler_run_counts_monotonic,
            "Scheduler run counts never moved backward.",
            "A scheduler run count moved backward.",
        )
    )

    findings.append(
        _finding(
            "scheduler.failures",
            scheduler_failures_stable,
            "Scheduler failure counts did not increase.",
            "A scheduler failure count increased.",
        )
    )

    findings.append(
        _finding(
            "scheduler.progress",
            scheduler_progress,
            "Every watched scheduler progressed during Q.6.",
            "One or more watched schedulers did not progress during Q.6.",
        )
    )

    ari_score_ok = all(
        item.ari.score >= baseline.ari.score
        for item in samples
    )

    findings.append(
        _finding(
            "ari.score.temporal",
            ari_score_ok,
            "ARI score never fell below T0.",
            "ARI score fell below the T0 baseline.",
        )
    )

    baseline_warnings = set(
        baseline.ari.warnings
    )

    ari_warning_ok = all(
        set(item.ari.warnings).issubset(
            baseline_warnings
        )
        for item in samples
    )

    findings.append(
        _finding(
            "ari.warnings.temporal",
            ari_warning_ok,
            "ARI warning set never expanded beyond T0.",
            "ARI warning set expanded beyond T0.",
        )
    )

    baseline_tv_difference = _tv_difference(
        baseline,
    )

    tv_difference_ok = True

    if baseline_tv_difference is not None:
        for sample in samples:
            difference = _tv_difference(
                sample,
            )

            if (
                difference is not None
                and difference > baseline_tv_difference
            ):
                tv_difference_ok = False
                break

    findings.append(
        _finding(
            "ari.tv_sync.temporal",
            tv_difference_ok,
            "TV synchronization discrepancy did not worsen.",
            "TV synchronization discrepancy worsened.",
        )
    )

    return SustainedUseEvaluation(
        findings=tuple(findings),
    )
