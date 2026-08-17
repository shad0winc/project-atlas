from __future__ import annotations

from dataclasses import replace

from atlas.sustained_use import (
    AriObservation,
    ContainerObservation,
    RuntimeBusObservation,
    SustainedUseContract,
    SustainedUseSample,
    evaluate_sample,
)


COMMIT = "b695c8d0e3bd01b974c55a57dc12df980b8a3e08"


def sample() -> SustainedUseSample:
    containers = tuple(
        ContainerObservation(
            name=f"container-{index}",
            container_id=f"id-{index}",
            status="running",
            health=(
                "none"
                if index < 10
                else "healthy"
            ),
            restart_count=0,
            oom_killed=False,
            started_at="2026-08-17T12:00:00Z",
        )
        for index in range(22)
    )

    return SustainedUseSample(
        generated_at="2026-08-17T15:22:10Z",
        git_commit=COMMIT,
        atlas_health_status="healthy",
        atlas_health_score=100,
        running_containers=22,
        unhealthy_containers=0,
        root_usage_percent=63,
        storage_usage_percent=8,
        containers=containers,
        schedulers=(),
        runtime_bus=RuntimeBusObservation(
            journal_lines=215,
            cursor_value=215,
            journal_uid=0,
            journal_gid=20000,
            journal_mode=660,
            journal_readable=True,
            journal_writable=False,
            heartbeat_age_seconds=2,
        ),
        ari=AriObservation(
            status="warning",
            score=80,
            warnings=(
                "Library synchronization failed",
            ),
            tv_filesystem_count=1,
            tv_jellyfin_count=3,
        ),
    )


def contract() -> SustainedUseContract:
    return SustainedUseContract(
        git_commit=COMMIT,
    )


def test_frozen_baseline_passes_hard_invariants() -> None:
    evaluation = evaluate_sample(
        sample(),
        contract(),
    )

    assert evaluation.passed is True
    assert evaluation.failed_codes == ()


def test_health_none_containers_do_not_fail() -> None:
    evaluation = evaluate_sample(
        sample(),
        contract(),
    )

    assert "containers.unhealthy" not in evaluation.failed_codes
    assert "containers.status" not in evaluation.failed_codes


def test_dirty_worktree_health_state_fails_strict_contract() -> None:
    value = replace(
        sample(),
        atlas_health_status="warning",
        atlas_health_score=99,
    )

    evaluation = evaluate_sample(
        value,
        contract(),
    )

    assert evaluation.passed is False
    assert "atlas.health.status" in evaluation.failed_codes
    assert "atlas.health.score" in evaluation.failed_codes


def test_unexpected_ari_warning_fails() -> None:
    value = sample()

    value = replace(
        value,
        ari=AriObservation(
            status="warning",
            score=80,
            warnings=(
                "Library synchronization failed",
                "Unexpected new warning",
            ),
            tv_filesystem_count=1,
            tv_jellyfin_count=3,
        ),
    )

    evaluation = evaluate_sample(
        value,
        contract(),
    )

    assert "ari.warnings" in evaluation.failed_codes


def test_ari_baseline_warning_is_allowed() -> None:
    evaluation = evaluate_sample(
        sample(),
        contract(),
    )

    assert "ari.score" not in evaluation.failed_codes
    assert "ari.warnings" not in evaluation.failed_codes


def test_restart_is_a_hard_failure() -> None:
    value = sample()

    changed = replace(
        value.containers[0],
        restart_count=1,
    )

    value = replace(
        value,
        containers=(
            changed,
            *value.containers[1:],
        ),
    )

    evaluation = evaluate_sample(
        value,
        contract(),
    )

    assert "containers.restarts" in evaluation.failed_codes


def test_oom_is_a_hard_failure() -> None:
    value = sample()

    changed = replace(
        value.containers[0],
        oom_killed=True,
    )

    value = replace(
        value,
        containers=(
            changed,
            *value.containers[1:],
        ),
    )

    evaluation = evaluate_sample(
        value,
        contract(),
    )

    assert "containers.oom" in evaluation.failed_codes


def test_stale_heartbeat_is_a_hard_failure() -> None:
    value = sample()

    value = replace(
        value,
        runtime_bus=replace(
            value.runtime_bus,
            heartbeat_age_seconds=30,
        ),
    )

    evaluation = evaluate_sample(
        value,
        contract(),
    )

    assert "notifications.heartbeat" in evaluation.failed_codes


def test_root_capacity_threshold_is_strict() -> None:
    value = replace(
        sample(),
        root_usage_percent=85,
    )

    evaluation = evaluate_sample(
        value,
        contract(),
    )

    assert "filesystem.root" in evaluation.failed_codes


def test_wrong_git_commit_fails() -> None:
    value = replace(
        sample(),
        git_commit="a" * 40,
    )

    evaluation = evaluate_sample(
        value,
        contract(),
    )

    assert "git.commit" in evaluation.failed_codes


def history_sample(
    *,
    generated_at: str,
    operations_runs: int,
    sports_runs: int,
    operations_failures: int = 0,
    sports_failures: int = 0,
    journal_lines: int = 215,
    cursor_value: int = 215,
    ari_score: int = 80,
    ari_warnings: tuple[str, ...] = (
        "Library synchronization failed",
    ),
    tv_filesystem_count: int = 1,
    tv_jellyfin_count: int = 3,
) -> SustainedUseSample:
    from atlas.sustained_use import SchedulerObservation

    base = sample()

    return replace(
        base,
        generated_at=generated_at,
        schedulers=(
            SchedulerObservation(
                name="operations.collect",
                enabled=True,
                status="healthy",
                due=False,
                run_count=operations_runs,
                failure_count=operations_failures,
                last_success=generated_at,
                next_run=generated_at,
            ),
            SchedulerObservation(
                name="sports.maintenance",
                enabled=True,
                status=(
                    "healthy"
                    if sports_runs > 0
                    else "never_run"
                ),
                due=False,
                run_count=sports_runs,
                failure_count=sports_failures,
                last_success=(
                    generated_at
                    if sports_runs > 0
                    else None
                ),
                next_run=generated_at,
            ),
        ),
        runtime_bus=replace(
            base.runtime_bus,
            journal_lines=journal_lines,
            cursor_value=cursor_value,
        ),
        ari=AriObservation(
            status=(
                "healthy"
                if ari_score == 100
                else "warning"
            ),
            score=ari_score,
            warnings=ari_warnings,
            tv_filesystem_count=tv_filesystem_count,
            tv_jellyfin_count=tv_jellyfin_count,
        ),
    )


def good_history():
    return (
        history_sample(
            generated_at="2026-08-17T16:00:00Z",
            operations_runs=1,
            sports_runs=0,
            journal_lines=215,
            cursor_value=215,
        ),
        history_sample(
            generated_at="2026-08-18T16:00:00Z",
            operations_runs=25,
            sports_runs=24,
            journal_lines=240,
            cursor_value=239,
        ),
        history_sample(
            generated_at="2026-08-19T16:00:00Z",
            operations_runs=49,
            sports_runs=48,
            journal_lines=260,
            cursor_value=260,
        ),
    )


def test_good_temporal_history_passes() -> None:
    from atlas.sustained_use import evaluate_history

    evaluation = evaluate_history(
        good_history(),
        contract(),
    )

    assert evaluation.passed is True
    assert evaluation.failed_codes == ()


def test_temporal_final_backlog_must_be_zero() -> None:
    from atlas.sustained_use import evaluate_history

    values = list(
        good_history()
    )

    values[-1] = replace(
        values[-1],
        runtime_bus=replace(
            values[-1].runtime_bus,
            cursor_value=259,
        ),
    )

    evaluation = evaluate_history(
        tuple(values),
        contract(),
    )

    assert "runtime_bus.final_backlog" in evaluation.failed_codes


def test_temporal_cursor_cannot_move_backward() -> None:
    from atlas.sustained_use import evaluate_history

    values = list(
        good_history()
    )

    values[1] = replace(
        values[1],
        runtime_bus=replace(
            values[1].runtime_bus,
            cursor_value=210,
        ),
    )

    evaluation = evaluate_history(
        tuple(values),
        contract(),
    )

    assert "runtime_bus.cursor.monotonic" in evaluation.failed_codes


def test_scheduler_must_progress() -> None:
    from atlas.sustained_use import evaluate_history

    values = list(
        good_history()
    )

    baseline_sports = values[0].schedulers[1]

    for index in (1, 2):
        values[index] = replace(
            values[index],
            schedulers=(
                values[index].schedulers[0],
                replace(
                    values[index].schedulers[1],
                    run_count=baseline_sports.run_count,
                    status="never_run",
                    last_success=None,
                ),
            ),
        )

    evaluation = evaluate_history(
        tuple(values),
        contract(),
    )

    assert "scheduler.progress" in evaluation.failed_codes


def test_scheduler_failure_increase_fails() -> None:
    from atlas.sustained_use import evaluate_history

    values = list(
        good_history()
    )

    values[1] = replace(
        values[1],
        schedulers=(
            replace(
                values[1].schedulers[0],
                failure_count=1,
            ),
            values[1].schedulers[1],
        ),
    )

    evaluation = evaluate_history(
        tuple(values),
        contract(),
    )

    assert "scheduler.failures" in evaluation.failed_codes


def test_ari_score_may_not_degrade_from_t0() -> None:
    from atlas.sustained_use import evaluate_history

    values = list(
        good_history()
    )

    values[1] = replace(
        values[1],
        ari=replace(
            values[1].ari,
            score=79,
        ),
    )

    evaluation = evaluate_history(
        tuple(values),
        contract(),
    )

    assert "ari.score.temporal" in evaluation.failed_codes


def test_ari_warning_set_may_not_expand() -> None:
    from atlas.sustained_use import evaluate_history

    values = list(
        good_history()
    )

    values[1] = replace(
        values[1],
        ari=replace(
            values[1].ari,
            warnings=(
                "Library synchronization failed",
                "New warning",
            ),
        ),
    )

    evaluation = evaluate_history(
        tuple(values),
        contract(),
    )

    assert "ari.warnings.temporal" in evaluation.failed_codes


def test_tv_discrepancy_may_not_worsen() -> None:
    from atlas.sustained_use import evaluate_history

    values = list(
        good_history()
    )

    values[1] = replace(
        values[1],
        ari=replace(
            values[1].ari,
            tv_filesystem_count=1,
            tv_jellyfin_count=5,
        ),
    )

    evaluation = evaluate_history(
        tuple(values),
        contract(),
    )

    assert "ari.tv_sync.temporal" in evaluation.failed_codes


def test_history_requires_certified_commit() -> None:
    from atlas.sustained_use import evaluate_history

    values = list(
        good_history()
    )

    values[1] = replace(
        values[1],
        git_commit="a" * 40,
    )

    evaluation = evaluate_history(
        tuple(values),
        contract(),
    )

    assert "history.git.commit" in evaluation.failed_codes
