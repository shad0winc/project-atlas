from __future__ import annotations

from datetime import datetime, timezone

from atlas.sustained_use import (
    AriObservation,
    ContainerObservation,
    FileSustainedUseRepository,
    RuntimeBusObservation,
    SchedulerObservation,
    SustainedUseContract,
    SustainedUseSample,
    SustainedUseSession,
    evaluate_fixed_cadence,
    finalize_session,
)


COMMIT = "dad7c6174213200199b06d0d5e33f94ffc2ac401"


def short_contract(
    *,
    sample_count: int = 3,
) -> SustainedUseContract:
    return SustainedUseContract(
        git_commit=COMMIT,
        duration_seconds=(
            (sample_count - 1)
            * 900
        ),
        interval_seconds=900,
        expected_running_containers=22,
    )


def make_session(
    contract: SustainedUseContract,
) -> SustainedUseSession:
    end_minute = (
        (contract.expected_sample_count - 1)
        * 15
    )

    hour = 16 + (
        end_minute // 60
    )

    minute = (
        end_minute % 60
    )

    return SustainedUseSession.from_contract(
        run_id="q6-fixed-cadence-final-test",
        started_at="2026-08-17T16:00:00Z",
        scheduled_end_at=(
            f"2026-08-17T{hour:02d}:{minute:02d}:00Z"
        ),
        contract=contract,
    )


def sample(
    generated_at: str,
    *,
    sequence: int,
) -> SustainedUseSample:
    containers = tuple(
        ContainerObservation(
            name=f"container-{index}",
            container_id=f"id-{index}",
            status="running",
            health="healthy",
            restart_count=0,
            oom_killed=False,
            started_at="2026-08-17T12:00:00Z",
        )
        for index in range(22)
    )

    return SustainedUseSample(
        generated_at=generated_at,
        git_commit=COMMIT,
        atlas_health_status="healthy",
        atlas_health_score=100,
        running_containers=22,
        unhealthy_containers=0,
        root_usage_percent=63,
        storage_usage_percent=8,
        containers=containers,
        schedulers=(
            SchedulerObservation(
                name="operations.collect",
                enabled=True,
                status="healthy",
                due=False,
                run_count=sequence + 1,
                failure_count=0,
                last_success=generated_at,
                next_run=generated_at,
            ),
            SchedulerObservation(
                name="sports.maintenance",
                enabled=True,
                status="healthy",
                due=False,
                run_count=sequence,
                failure_count=0,
                last_success=(
                    generated_at
                    if sequence > 0
                    else None
                ),
                next_run=generated_at,
            ),
        ),
        runtime_bus=RuntimeBusObservation(
            journal_lines=(
                215
                + sequence
            ),
            cursor_value=(
                215
                + sequence
            ),
            journal_uid=0,
            journal_gid=20000,
            journal_mode=660,
            journal_readable=True,
            journal_writable=False,
            heartbeat_age_seconds=1,
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


def evaluate(
    timestamps: tuple[str, ...],
):
    contract = short_contract(
        sample_count=len(timestamps),
    )

    values = tuple(
        sample(
            timestamp,
            sequence=index,
        )
        for index, timestamp in enumerate(
            timestamps
        )
    )

    return evaluate_fixed_cadence(
        values,
        contract,
        started_at="2026-08-17T16:00:00Z",
    )


def test_exact_fixed_slots_pass() -> None:
    evaluation = evaluate(
        (
            "2026-08-17T16:00:00Z",
            "2026-08-17T16:15:00Z",
            "2026-08-17T16:30:00Z",
        )
    )

    assert evaluation.passed is True
    assert evaluation.failed_codes == ()


def test_bounded_lateness_passes() -> None:
    evaluation = evaluate(
        (
            "2026-08-17T16:00:00Z",
            "2026-08-17T16:16:30Z",
            "2026-08-17T16:32:00Z",
        )
    )

    assert evaluation.passed is True


def test_repeated_lateness_does_not_change_expected_slots() -> None:
    evaluation = evaluate(
        (
            "2026-08-17T16:00:00Z",
            "2026-08-17T16:16:30Z",
            "2026-08-17T16:31:30Z",
            "2026-08-17T16:46:30Z",
        )
    )

    assert evaluation.passed is True


def test_accumulating_drift_fails() -> None:
    evaluation = evaluate(
        (
            "2026-08-17T16:00:00Z",
            "2026-08-17T16:16:30Z",
            "2026-08-17T16:33:00Z",
            "2026-08-17T16:49:30Z",
        )
    )

    assert evaluation.passed is False
    assert (
        "history.cadence.fixed_slots"
        in evaluation.failed_codes
    )


def test_real_failed_q6_drift_shape_fails() -> None:
    evaluation = evaluate(
        (
            "2026-08-17T23:20:28.663215Z",
            "2026-08-17T23:36:59.597965Z",
            "2026-08-17T23:53:59.590199Z",
        )
    )

    assert evaluation.passed is False
    assert (
        "history.cadence.fixed_slots"
        in evaluation.failed_codes
    )


def test_early_sample_fails() -> None:
    evaluation = evaluate(
        (
            "2026-08-17T16:00:00Z",
            "2026-08-17T16:14:59Z",
            "2026-08-17T16:30:00Z",
        )
    )

    assert evaluation.passed is False


def test_t0_must_match_session_start() -> None:
    contract = short_contract()

    values = (
        sample(
            "2026-08-17T16:00:01Z",
            sequence=0,
        ),
        sample(
            "2026-08-17T16:15:00Z",
            sequence=1,
        ),
        sample(
            "2026-08-17T16:30:00Z",
            sequence=2,
        ),
    )

    evaluation = evaluate_fixed_cadence(
        values,
        contract,
        started_at="2026-08-17T16:00:00Z",
    )

    assert evaluation.passed is True

    # One second after T0 is within the same bounded slot.
    # A timestamp before T0 is what must never certify.
    before_t0 = (
        sample(
            "2026-08-17T15:59:59Z",
            sequence=0,
        ),
        *values[1:],
    )

    evaluation = evaluate_fixed_cadence(
        before_t0,
        contract,
        started_at="2026-08-17T16:00:00Z",
    )

    assert evaluation.passed is False


def test_finalization_completes_valid_fixed_cadence(
    tmp_path,
) -> None:
    contract = short_contract()

    repository = FileSustainedUseRepository(
        tmp_path / "q6"
    )

    repository.create_session(
        make_session(
            contract
        )
    )

    for index, timestamp in enumerate(
        (
            "2026-08-17T16:00:00Z",
            "2026-08-17T16:16:30Z",
            "2026-08-17T16:32:00Z",
        )
    ):
        repository.save(
            sample(
                timestamp,
                sequence=index,
            )
        )

    result = finalize_session(
        contract=contract,
        repository=repository,
        now=datetime(
            2026,
            8,
            17,
            16,
            32,
            tzinfo=timezone.utc,
        ),
    )

    assert result.passed is True
    assert result.session.status == "completed"
    assert (
        "history.cadence.fixed_slots"
        not in result.temporal_evaluation.failed_codes
    )


def test_finalization_fails_drifting_history(
    tmp_path,
) -> None:
    contract = short_contract()

    repository = FileSustainedUseRepository(
        tmp_path / "q6"
    )

    repository.create_session(
        make_session(
            contract
        )
    )

    for index, timestamp in enumerate(
        (
            "2026-08-17T16:00:00Z",
            "2026-08-17T16:16:30Z",
            "2026-08-17T16:33:30Z",
        )
    ):
        repository.save(
            sample(
                timestamp,
                sequence=index,
            )
        )

    result = finalize_session(
        contract=contract,
        repository=repository,
        now=datetime(
            2026,
            8,
            17,
            16,
            34,
            tzinfo=timezone.utc,
        ),
    )

    assert result.passed is False
    assert result.session.status == "failed"
    assert (
        "history.cadence.fixed_slots"
        in result.temporal_evaluation.failed_codes
    )
