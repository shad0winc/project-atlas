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
    SustainedUseLifecycleError,
    SustainedUseSample,
    finalize_session,
    sample_session,
    start_session,
    status_session,
)


COMMIT = "b695c8d0e3bd01b974c55a57dc12df980b8a3e08"


def contract(
    *,
    duration_seconds: int = 172800,
    interval_seconds: int = 900,
):
    return SustainedUseContract(
        git_commit=COMMIT,
        duration_seconds=duration_seconds,
        interval_seconds=interval_seconds,
    )


def sample(
    generated_at: str,
    *,
    operations_runs: int = 1,
    sports_runs: int = 1,
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
                run_count=operations_runs,
                failure_count=0,
                last_success=generated_at,
                next_run=generated_at,
            ),
            SchedulerObservation(
                name="sports.maintenance",
                enabled=True,
                status="healthy",
                due=False,
                run_count=sports_runs,
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


def test_start_creates_session_and_t0_only_after_pass(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    value = sample(
        "2026-08-17T16:00:00Z",
    )

    result = start_session(
        contract=contract(),
        repository=repository,
        collector=lambda: value,
    )

    assert result.passed is True
    assert result.session.run_id == "q6-20260817T160000Z"
    assert result.session.started_at == value.generated_at
    assert result.session.scheduled_end_at == (
        "2026-08-19T16:00:00Z"
    )

    assert repository.session() == result.session
    assert repository.history() == (value,)


def test_failed_t0_creates_no_session_or_sample(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    value = sample(
        "2026-08-17T16:00:00Z",
        atlas_status="warning",
        atlas_score=99,
    )

    with pytest.raises(
        SustainedUseLifecycleError,
        match="T0 failed strict",
    ):
        start_session(
            contract=contract(),
            repository=repository,
            collector=lambda: value,
        )

    assert repository.history() == ()
    assert repository.session_path.exists() is False


def test_sample_requires_active_session(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    first = sample(
        "2026-08-17T16:00:00Z",
    )

    start = start_session(
        contract=contract(),
        repository=repository,
        collector=lambda: first,
    )

    repository.update_session(
        replace(
            start.session,
            status="completed",
            completed_at="2026-08-19T16:00:00Z",
        )
    )

    with pytest.raises(
        SustainedUseLifecycleError,
        match="not active",
    ):
        sample_session(
            contract=contract(),
            repository=repository,
            collector=lambda: sample(
                "2026-08-17T16:15:00Z",
            ),
        )


def test_sample_persists_hard_failure_evidence(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    start_session(
        contract=contract(),
        repository=repository,
        collector=lambda: sample(
            "2026-08-17T16:00:00Z",
        ),
    )

    failed = sample(
        "2026-08-17T16:15:00Z",
        atlas_status="warning",
        atlas_score=99,
    )

    result = sample_session(
        contract=contract(),
        repository=repository,
        collector=lambda: failed,
    )

    assert result.passed is False
    assert len(repository.history()) == 2


def test_status_reports_progress(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    start_session(
        contract=contract(),
        repository=repository,
        collector=lambda: sample(
            "2026-08-17T16:00:00Z",
        ),
    )

    status = status_session(
        repository=repository,
    )

    assert status.sample_count == 1
    assert status.remaining_samples == 192
    assert status.latest_sample is not None


def test_finalize_refuses_before_scheduled_end(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    start_session(
        contract=contract(),
        repository=repository,
        collector=lambda: sample(
            "2026-08-17T16:00:00Z",
        ),
    )

    with pytest.raises(
        SustainedUseLifecycleError,
        match="scheduled end",
    ):
        finalize_session(
            contract=contract(),
            repository=repository,
            now=datetime(
                2026,
                8,
                18,
                16,
                0,
                tzinfo=timezone.utc,
            ),
        )


def test_finalize_requires_exact_sample_count(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    start_session(
        contract=contract(),
        repository=repository,
        collector=lambda: sample(
            "2026-08-17T16:00:00Z",
        ),
    )

    with pytest.raises(
        SustainedUseLifecycleError,
        match="sample count is incomplete",
    ):
        finalize_session(
            contract=contract(),
            repository=repository,
            now=datetime(
                2026,
                8,
                19,
                16,
                0,
                tzinfo=timezone.utc,
            ),
        )


def test_short_contract_can_finalize_completed(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    short = contract(
        duration_seconds=1800,
        interval_seconds=900,
    )

    start_session(
        contract=short,
        repository=repository,
        collector=lambda: sample(
            "2026-08-17T16:00:00Z",
            operations_runs=1,
            sports_runs=1,
        ),
    )

    sample_session(
        contract=short,
        repository=repository,
        collector=lambda: sample(
            "2026-08-17T16:15:00Z",
            operations_runs=2,
            sports_runs=2,
        ),
    )

    sample_session(
        contract=short,
        repository=repository,
        collector=lambda: sample(
            "2026-08-17T16:30:00Z",
            operations_runs=3,
            sports_runs=3,
        ),
    )

    result = finalize_session(
        contract=short,
        repository=repository,
        now=datetime(
            2026,
            8,
            17,
            16,
            30,
            tzinfo=timezone.utc,
        ),
    )

    assert result.passed is True
    assert result.session.status == "completed"
    assert result.hard_failure_count == 0


def test_build_parser_accepts_lifecycle_commands() -> None:
    from atlas.sustained_use.cli import build_parser

    parser = build_parser()

    for command in (
        "start",
        "sample",
        "status",
        "finalize",
    ):
        args = parser.parse_args(
            [
                "--root",
                "/tmp/q6-test",
                command,
                "--json",
            ]
        )

        assert args.command == command
        assert args.json is True


def test_main_status_reads_temp_repository(
    tmp_path,
    capsys,
) -> None:
    import json

    from atlas.sustained_use.cli import main

    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    value = sample(
        "2026-08-17T16:00:00Z",
    )

    start_session(
        contract=contract(),
        repository=repository,
        collector=lambda: value,
    )

    result = main(
        [
            "--root",
            str(repository.root),
            "status",
            "--json",
        ]
    )

    captured = capsys.readouterr()

    assert result == 0
    assert captured.err == ""

    payload = json.loads(
        captured.out,
    )

    assert payload["command"] == "status"
    assert payload["status"] == "active"
    assert payload["sample_count"] == 1
    assert payload["expected_sample_count"] == 193
    assert payload["remaining_samples"] == 192


def test_main_missing_session_returns_one(
    tmp_path,
    capsys,
) -> None:
    from atlas.sustained_use.cli import main

    result = main(
        [
            "--root",
            str(tmp_path / "missing"),
            "status",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert captured.out == ""
    assert "ERROR:" in captured.err
    assert "session was not found" in captured.err


def test_main_sample_failure_returns_one(
    tmp_path,
    monkeypatch,
    capsys,
) -> None:
    import atlas.sustained_use.cli as cli_module

    repository = FileSustainedUseRepository(
        tmp_path / "q6",
    )

    start_session(
        contract=contract(),
        repository=repository,
        collector=lambda: sample(
            "2026-08-17T16:00:00Z",
        ),
    )

    failed = sample(
        "2026-08-17T16:15:00Z",
        atlas_status="warning",
        atlas_score=99,
    )

    # sample_session's default was bound when defined, so replace
    # the command-layer function at its call boundary.
    original = cli_module.sample_session

    def command_sample_session(
        *,
        contract,
        repository,
    ):
        return original(
            contract=contract,
            repository=repository,
            collector=lambda: failed,
        )

    monkeypatch.setattr(
        cli_module,
        "sample_session",
        command_sample_session,
    )

    result = cli_module.main(
        [
            "--root",
            str(repository.root),
            "sample",
            "--json",
        ]
    )

    captured = capsys.readouterr()

    assert result == 1
    assert captured.err == ""

    payload = __import__("json").loads(
        captured.out,
    )

    assert payload["passed"] is False
    assert "atlas.health.status" in payload["failed_codes"]
