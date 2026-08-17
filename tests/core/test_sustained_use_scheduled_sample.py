from __future__ import annotations

from dataclasses import replace
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
)
from atlas.sustained_use.scheduled_sample import (
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
            AssertionError("collector must not run")
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
    assert len(repository.history()) == 1


def test_active_session_samples_at_interval(
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
    assert repository.history()[0] == due


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
            AssertionError("collector must not run")
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
