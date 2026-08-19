from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from atlas.sustained_use import (
    AriObservation,
    ContainerObservation,
    FileSustainedUseRepository,
    RuntimeBusObservation,
    SchedulerObservation,
    SustainedUseContract,
    SustainedUseSample,
    SustainedUseSession,
)
from atlas.sustained_use.scheduled_sample import (
    ScheduledSampleOutcome,
    main,
    run_scheduled_sample,
)


COMMIT = "b695c8d0e3bd01b974c55a57dc12df980b8a3e08"


def sample(
    generated_at: str,
    *,
    atlas_status: str = "healthy",
    atlas_score: int = 100,
) -> SustainedUseSample:
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
        generated_at=generated_at,
        git_commit=COMMIT,
        atlas_health_status=atlas_status,
        atlas_health_score=atlas_score,
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
                run_count=1,
                failure_count=0,
                last_success=generated_at,
                next_run=generated_at,
            ),
            SchedulerObservation(
                name="sports.maintenance",
                enabled=True,
                status="healthy",
                due=False,
                run_count=1,
                failure_count=0,
                last_success=generated_at,
                next_run=generated_at,
            ),
        ),
        runtime_bus=RuntimeBusObservation(
            journal_lines=215,
            cursor_value=215,
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


def active_session() -> SustainedUseSession:
    contract = SustainedUseContract(
        git_commit=COMMIT,
    )

    return SustainedUseSession.from_contract(
        run_id="q6-test",
        started_at="2026-08-17T16:00:00Z",
        scheduled_end_at="2026-08-19T16:00:00Z",
        contract=contract,
    )


def repository_with_t0(tmp_path):
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    repository.create_session(
        active_session(),
    )

    repository.save(
        sample(
            "2026-08-17T16:00:00Z",
        )
    )

    return repository


def test_no_session_is_successful_noop(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    outcome = run_scheduled_sample(
        repository=repository,
        now=datetime(
            2026,
            8,
            17,
            16,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert outcome.action == "no_session"
    assert outcome.sample_count == 0
    assert outcome.passed is None


def test_active_session_does_not_duplicate_t0(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: (_ for _ in ()).throw(
            AssertionError(
                "collector must not run"
            )
        ),
        now=datetime(
            2026,
            8,
            17,
            16,
            0,
            10,
            tzinfo=timezone.utc,
        ),
    )

    assert outcome.action == "not_due"
    assert outcome.sample_count == 1
    assert outcome.next_sample_number == 2
    assert outcome.expected_at == (
        "2026-08-17T16:15:00Z"
    )
    assert len(repository.history()) == 1


def test_active_session_samples_at_fixed_interval(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    due = sample(
        "2026-08-17T16:15:00Z",
    )

    outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: due,
        now=datetime(
            2026,
            8,
            17,
            16,
            15,
            tzinfo=timezone.utc,
        ),
    )

    assert outcome.action == "sampled"
    assert outcome.sample_count == 2
    assert outcome.passed is True
    assert outcome.next_sample_number == 2
    assert outcome.expected_at == (
        "2026-08-17T16:15:00Z"
    )
    assert outcome.lateness_seconds == 0
    assert repository.history()[0] == due


def test_bounded_dispatch_lateness_is_accepted(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    delayed = sample(
        "2026-08-17T16:17:00Z",
    )

    outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: delayed,
        now=datetime(
            2026,
            8,
            17,
            16,
            17,
            tzinfo=timezone.utc,
        ),
    )

    assert outcome.action == "sampled"
    assert outcome.sample_count == 2
    assert outcome.expected_at == (
        "2026-08-17T16:15:00Z"
    )
    assert outcome.lateness_seconds == 120
    assert repository.history()[0] == delayed


def test_previous_late_sample_does_not_shift_next_slot(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    second = sample(
        "2026-08-17T16:16:30Z",
    )

    first_outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: second,
        now=datetime(
            2026,
            8,
            17,
            16,
            16,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert first_outcome.action == "sampled"
    assert first_outcome.expected_at == (
        "2026-08-17T16:15:00Z"
    )

    third = sample(
        "2026-08-17T16:32:00Z",
    )

    second_outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: third,
        now=datetime(
            2026,
            8,
            17,
            16,
            32,
            tzinfo=timezone.utc,
        ),
    )

    assert second_outcome.action == "sampled"
    assert second_outcome.sample_count == 3

    # The previous sample was collected at 16:16:30, but
    # sample 3 remains anchored to T0 + 1800 seconds.
    assert second_outcome.expected_at == (
        "2026-08-17T16:30:00Z"
    )
    assert second_outcome.lateness_seconds == 120
    assert repository.history()[0] == third


def test_missed_slot_is_hard_failure_without_collection(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: (_ for _ in ()).throw(
            AssertionError(
                "missed slot must not collect"
            )
        ),
        now=datetime(
            2026,
            8,
            17,
            16,
            18,
            1,
            tzinfo=timezone.utc,
        ),
    )

    assert outcome.action == "missed"
    assert outcome.sample_count == 1
    assert outcome.next_sample_number == 2
    assert outcome.expected_at == (
        "2026-08-17T16:15:00Z"
    )
    assert outcome.lateness_seconds == 181
    assert len(repository.history()) == 1


def test_whole_missed_interval_is_not_backfilled(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: (_ for _ in ()).throw(
            AssertionError(
                "backfill must not occur"
            )
        ),
        now=datetime(
            2026,
            8,
            17,
            16,
            31,
            tzinfo=timezone.utc,
        ),
    )

    assert outcome.action == "missed"
    assert outcome.sample_count == 1

    # Sample 2 remains the failed required slot. Atlas must not
    # leap forward and synthesize sample 3.
    assert outcome.next_sample_number == 2
    assert outcome.expected_at == (
        "2026-08-17T16:15:00Z"
    )
    assert len(repository.history()) == 1


def test_repeated_60_second_polling_is_idempotent(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    for minute in range(1, 15):
        outcome = run_scheduled_sample(
            repository=repository,
            collector=lambda: (_ for _ in ()).throw(
                AssertionError(
                    "collector must not run before fixed slot"
                )
            ),
            now=datetime(
                2026,
                8,
                17,
                16,
                minute,
                tzinfo=timezone.utc,
            ),
        )

        assert outcome.action == "not_due"
        assert outcome.sample_count == 1

    assert len(repository.history()) == 1


def test_real_production_drift_shape_does_not_accumulate(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    observations = (
        (
            datetime(
                2026,
                8,
                17,
                16,
                16,
                30,
                tzinfo=timezone.utc,
            ),
            "2026-08-17T16:16:30Z",
            "2026-08-17T16:15:00Z",
        ),
        (
            datetime(
                2026,
                8,
                17,
                16,
                31,
                30,
                tzinfo=timezone.utc,
            ),
            "2026-08-17T16:31:30Z",
            "2026-08-17T16:30:00Z",
        ),
        (
            datetime(
                2026,
                8,
                17,
                16,
                46,
                30,
                tzinfo=timezone.utc,
            ),
            "2026-08-17T16:46:30Z",
            "2026-08-17T16:45:00Z",
        ),
        (
            datetime(
                2026,
                8,
                17,
                17,
                1,
                30,
                tzinfo=timezone.utc,
            ),
            "2026-08-17T17:01:30Z",
            "2026-08-17T17:00:00Z",
        ),
    )

    for now, generated_at, expected_at in observations:
        value = sample(
            generated_at,
        )

        outcome = run_scheduled_sample(
            repository=repository,
            collector=lambda value=value: value,
            now=now,
        )

        assert outcome.action == "sampled"
        assert outcome.expected_at == expected_at
        assert outcome.lateness_seconds == 90

    assert len(repository.history()) == 5


def test_failed_hard_evaluation_is_persisted(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    failed = sample(
        "2026-08-17T16:15:00Z",
        atlas_status="warning",
        atlas_score=99,
    )

    outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: failed,
        now=datetime(
            2026,
            8,
            17,
            16,
            15,
            tzinfo=timezone.utc,
        ),
    )

    assert outcome.action == "sampled"
    assert outcome.passed is False
    assert repository.history()[0] == failed


def test_inactive_session_is_successful_noop(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    current = repository.session()

    repository.update_session(
        replace(
            current,
            status="completed",
            completed_at="2026-08-19T16:00:00Z",
        )
    )

    outcome = run_scheduled_sample(
        repository=repository,
        collector=lambda: (_ for _ in ()).throw(
            AssertionError(
                "collector must not run"
            )
        ),
        now=datetime(
            2026,
            8,
            19,
            16,
            15,
            tzinfo=timezone.utc,
        ),
    )

    assert outcome.action == "inactive"
    assert outcome.passed is None


def test_naive_scheduler_time_is_rejected(
    tmp_path,
) -> None:
    repository = repository_with_t0(
        tmp_path,
    )

    with pytest.raises(
        Exception,
        match="timezone",
    ):
        run_scheduled_sample(
            repository=repository,
            now=datetime(
                2026,
                8,
                17,
                16,
                15,
            ),
        )


def test_cli_no_session_exits_zero(
    tmp_path,
    capsys,
) -> None:
    result = main(
        [
            "--root",
            str(tmp_path / "q6"),
            "--json",
        ]
    )

    captured = capsys.readouterr()

    assert result == 0
    assert captured.err == ""
    assert '"action":"no_session"' in captured.out


def test_missed_action_has_failure_exit_semantics(
    monkeypatch,
    tmp_path,
    capsys,
) -> None:
    import atlas.sustained_use.scheduled_sample as module

    monkeypatch.setattr(
        module,
        "run_scheduled_sample",
        lambda **kwargs: ScheduledSampleOutcome(
            action="missed",
            sample_count=1,
            expected_sample_count=193,
            next_sample_number=2,
            expected_at="2026-08-17T16:15:00Z",
            lateness_seconds=181,
        ),
    )

    result = main(
        [
            "--root",
            str(tmp_path / "q6"),
            "--json",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert captured.err == ""
    assert '"action":"missed"' in captured.out
    assert '"next_sample_number":2' in captured.out
