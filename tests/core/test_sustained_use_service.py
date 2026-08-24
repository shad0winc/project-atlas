from __future__ import annotations

from dataclasses import replace

from atlas.sustained_use import (
    AriObservation,
    ContainerObservation,
    FileSustainedUseRepository,
    RuntimeBusObservation,
    SustainedUseContract,
    SustainedUseSample,
    SustainedUseService,
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
        generated_at="2026-08-17T16:00:00Z",
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


def test_service_collects_evaluates_and_saves(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    value = sample()

    service = SustainedUseService(
        contract=contract(),
        repository=repository,
        collector=lambda: value,
    )

    result = service.run_once()

    assert result.sample == value
    assert result.passed is True
    assert result.evaluation.failed_codes == ()
    assert result.snapshot_path.exists()

    assert repository.latest() == value
    assert repository.history() == (value,)


def test_failed_evaluation_is_still_persisted(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    value = replace(
        sample(),
        atlas_health_status="warning",
        atlas_health_score=99,
    )

    service = SustainedUseService(
        contract=contract(),
        repository=repository,
        collector=lambda: value,
    )

    result = service.run_once()

    assert result.passed is False
    assert "atlas.health.status" in (
        result.evaluation.failed_codes
    )
    assert "atlas.health.score" in (
        result.evaluation.failed_codes
    )

    assert result.snapshot_path.exists()
    assert repository.latest() == value


def test_wrong_git_commit_is_persisted_as_failure(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    value = replace(
        sample(),
        git_commit="a" * 40,
    )

    service = SustainedUseService(
        contract=contract(),
        repository=repository,
        collector=lambda: value,
    )

    result = service.run_once()

    assert result.passed is False
    assert "git.commit" in result.evaluation.failed_codes
    assert repository.latest() == value


def test_collector_must_return_sample(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    service = SustainedUseService(
        contract=contract(),
        repository=repository,
        collector=lambda: {},
    )

    try:
        service.run_once()
    except TypeError as error:
        assert "collector must return" in str(error)
    else:
        raise AssertionError(
            "TypeError was not raised"
        )

    assert repository.history() == ()


def test_collection_failure_writes_nothing(
    tmp_path,
) -> None:
    repository = FileSustainedUseRepository(
        tmp_path / "sustained-use",
    )

    def broken_collector():
        raise RuntimeError("collection failed")

    service = SustainedUseService(
        contract=contract(),
        repository=repository,
        collector=broken_collector,
    )

    try:
        service.run_once()
    except RuntimeError as error:
        assert str(error) == "collection failed"
    else:
        raise AssertionError(
            "RuntimeError was not raised"
        )

    assert repository.history() == ()
