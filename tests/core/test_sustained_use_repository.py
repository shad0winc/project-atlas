from __future__ import annotations

import json

import pytest

from atlas.sustained_use import (
    AriObservation,
    ContainerObservation,
    FileSustainedUseRepository,
    RuntimeBusObservation,
    SchedulerObservation,
    SustainedUseRepositoryError,
    SustainedUseSample,
    SustainedUseSampleNotFoundError,
)


COMMIT = "b695c8d0e3bd01b974c55a57dc12df980b8a3e08"


def sample(
    generated_at: str = "2026-08-17T14:42:24Z",
) -> SustainedUseSample:
    return SustainedUseSample(
        generated_at=generated_at,
        git_commit=COMMIT,
        atlas_health_status="healthy",
        atlas_health_score=100,
        running_containers=22,
        unhealthy_containers=0,
        root_usage_percent=63,
        storage_usage_percent=8,
        containers=(
            ContainerObservation(
                name="atlas-api",
                container_id="abc123",
                status="running",
                health="healthy",
                restart_count=0,
                oom_killed=False,
                started_at="2026-08-13T01:16:15Z",
            ),
        ),
        schedulers=(
            SchedulerObservation(
                name="operations.collect",
                enabled=True,
                status="healthy",
                due=True,
                run_count=1,
                failure_count=0,
                last_success="2026-08-04T00:15:52Z",
                next_run="2026-08-04T01:15:52Z",
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


def test_save_persists_history_and_latest(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    value = sample()

    snapshot_path = repository.save(value)

    assert snapshot_path.exists()
    assert repository.latest_path.exists()
    assert repository.latest() == value
    assert repository.history() == (value,)

    payload = json.loads(
        snapshot_path.read_text(encoding="utf-8")
    )

    assert payload == value.to_dict()


def test_history_is_newest_first(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    older = sample(
        "2026-08-17T14:00:00Z",
    )
    newer = sample(
        "2026-08-17T14:15:00Z",
    )

    repository.save(older)
    repository.save(newer)

    assert repository.history() == (
        newer,
        older,
    )

    assert repository.history(limit=1) == (
        newer,
    )


def test_duplicate_snapshot_is_rejected(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    value = sample()

    repository.save(value)

    with pytest.raises(
        SustainedUseRepositoryError,
        match="already exists",
    ):
        repository.save(value)


def test_empty_repository_has_no_history(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    assert repository.history() == ()


def test_latest_missing_raises(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    with pytest.raises(
        SustainedUseSampleNotFoundError,
        match="latest sustained-use sample was not found",
    ):
        repository.latest()


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        True,
    ],
)
def test_history_rejects_invalid_limit(
    tmp_path,
    limit,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="positive integer",
    ):
        repository.history(limit=limit)


def test_latest_rejects_invalid_json(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    repository.latest_path.parent.mkdir(
        parents=True,
    )

    repository.latest_path.write_text(
        "not-json\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="invalid JSON",
    ):
        repository.latest()


def test_latest_rejects_invalid_model_payload(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    repository.latest_path.parent.mkdir(
        parents=True,
    )

    repository.latest_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="sample is invalid",
    ):
        repository.latest()


def test_save_requires_sample_model(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="sample must be a SustainedUseSample",
    ):
        repository.save({})


def q6_session(
    *,
    status: str = "active",
    completed_at: str | None = None,
):
    from atlas.sustained_use import SustainedUseSession

    return SustainedUseSession(
        run_id="q6-20260817T160000Z",
        git_commit=COMMIT,
        started_at="2026-08-17T16:00:00Z",
        scheduled_end_at="2026-08-19T16:00:00Z",
        duration_seconds=172800,
        interval_seconds=900,
        expected_sample_count=193,
        expected_running_containers=22,
        status=status,
        completed_at=completed_at,
    )


def test_create_and_read_session(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    value = q6_session()

    path = repository.create_session(value)

    assert path == repository.session_path
    assert path.exists()
    assert repository.session() == value


def test_create_session_is_single_use(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    repository.create_session(
        q6_session(),
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="session already exists",
    ):
        repository.create_session(
            q6_session(),
        )


def test_missing_session_raises(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    with pytest.raises(
        SustainedUseSampleNotFoundError,
        match="session was not found",
    ):
        repository.session()


@pytest.mark.parametrize(
    "status",
    [
        "completed",
        "failed",
        "aborted",
    ],
)
def test_session_can_transition_out_of_active(
    tmp_path,
    status,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    repository.create_session(
        q6_session(),
    )

    completed = q6_session(
        status=status,
        completed_at="2026-08-19T16:00:00Z",
    )

    repository.update_session(
        completed,
    )

    assert repository.session() == completed


def test_session_boundary_cannot_change(
    tmp_path,
) -> None:
    from dataclasses import replace

    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    original = q6_session()

    repository.create_session(original)

    changed = replace(
        q6_session(
            status="completed",
            completed_at="2026-08-19T16:00:00Z",
        ),
        git_commit="a" * 40,
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="boundary fields cannot change",
    ):
        repository.update_session(changed)

    assert repository.session() == original


def test_active_to_active_update_is_rejected(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    repository.create_session(
        q6_session(),
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="transition out of active",
    ):
        repository.update_session(
            q6_session(),
        )


def test_completed_session_cannot_be_updated_again(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    completed = q6_session(
        status="completed",
        completed_at="2026-08-19T16:00:00Z",
    )

    repository.create_session(
        q6_session(),
    )

    repository.update_session(
        completed,
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="only an active",
    ):
        repository.update_session(
            completed,
        )


def test_invalid_session_json_is_rejected(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    repository.session_path.parent.mkdir(
        parents=True,
    )

    repository.session_path.write_text(
        "not-json\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SustainedUseRepositoryError,
        match="invalid JSON",
    ):
        repository.session()
