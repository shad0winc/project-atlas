from __future__ import annotations

import pytest

from atlas.sustained_use import (
    AriObservation,
    ContainerObservation,
    RuntimeBusObservation,
    SchedulerObservation,
    SustainedUseContract,
    SustainedUseModelError,
    SustainedUseSample,
)


COMMIT = "b695c8d0e3bd01b974c55a57dc12df980b8a3e08"


def test_default_contract_freezes_q6_policy() -> None:
    contract = SustainedUseContract(
        git_commit=COMMIT,
    )

    assert contract.duration_seconds == 172800
    assert contract.interval_seconds == 900
    assert contract.expected_running_containers == 22
    assert contract.expected_sample_count == 193


def test_contract_normalizes_git_commit() -> None:
    contract = SustainedUseContract(
        git_commit=COMMIT.upper(),
    )

    assert contract.git_commit == COMMIT


def test_contract_round_trip_is_deterministic() -> None:
    original = SustainedUseContract(
        git_commit=COMMIT,
    )

    payload = original.to_dict()
    rebuilt = SustainedUseContract.from_dict(payload)

    assert rebuilt == original
    assert payload["expected_sample_count"] == 193


@pytest.mark.parametrize(
    "commit",
    [
        "",
        "abc123",
        "g" * 40,
        None,
    ],
)
def test_contract_rejects_invalid_git_commit(commit) -> None:
    with pytest.raises(
        SustainedUseModelError,
        match="git_commit",
    ):
        SustainedUseContract(
            git_commit=commit,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("duration_seconds", 0),
        ("duration_seconds", -1),
        ("interval_seconds", 0),
        ("interval_seconds", -1),
        ("expected_running_containers", 0),
        ("expected_running_containers", -1),
    ],
)
def test_contract_rejects_non_positive_integers(
    field: str,
    value: int,
) -> None:
    kwargs = {
        "git_commit": COMMIT,
        field: value,
    }

    with pytest.raises(
        SustainedUseModelError,
        match=field,
    ):
        SustainedUseContract(**kwargs)


def test_contract_rejects_non_divisible_cadence() -> None:
    with pytest.raises(
        SustainedUseModelError,
        match="evenly divisible",
    ):
        SustainedUseContract(
            git_commit=COMMIT,
            duration_seconds=1000,
            interval_seconds=900,
        )


def test_contract_rejects_wrong_schema_version() -> None:
    with pytest.raises(
        SustainedUseModelError,
        match="schema_version",
    ):
        SustainedUseContract(
            git_commit=COMMIT,
            schema_version=2,
        )


@pytest.mark.parametrize(
    "health",
    [
        "healthy",
        "unhealthy",
        "starting",
        "none",
        "unknown",
    ],
)
def test_container_accepts_supported_health_states(
    health: str,
) -> None:
    observation = ContainerObservation(
        name="atlas-api",
        container_id="abc123",
        status="running",
        health=health,
        restart_count=0,
        oom_killed=False,
        started_at="2026-08-17T12:00:00+00:00",
    )

    assert observation.health == health


def test_container_health_none_is_distinct_from_unhealthy() -> None:
    observation = ContainerObservation(
        name="prowlarr",
        container_id="def456",
        status="running",
        health="none",
        restart_count=0,
        oom_killed=False,
        started_at="2026-08-13T00:11:15+00:00",
    )

    assert observation.status == "running"
    assert observation.health == "none"
    assert observation.restart_count == 0
    assert observation.oom_killed is False


def test_container_round_trip_normalizes_timestamp() -> None:
    original = ContainerObservation(
        name="atlas-api",
        container_id="abc123",
        status="RUNNING",
        health="HEALTHY",
        restart_count=0,
        oom_killed=False,
        started_at="2026-08-17T08:00:00-04:00",
    )

    rebuilt = ContainerObservation.from_dict(
        original.to_dict(),
    )

    assert rebuilt == original
    assert original.status == "running"
    assert original.health == "healthy"
    assert original.started_at == "2026-08-17T12:00:00Z"


def test_container_rejects_negative_restart_count() -> None:
    with pytest.raises(
        SustainedUseModelError,
        match="restart_count",
    ):
        ContainerObservation(
            name="atlas-api",
            container_id="abc123",
            status="running",
            health="healthy",
            restart_count=-1,
            oom_killed=False,
            started_at="2026-08-17T12:00:00Z",
        )


def test_runtime_bus_derives_zero_backlog() -> None:
    observation = RuntimeBusObservation(
        journal_lines=215,
        cursor_value=215,
        journal_uid=0,
        journal_gid=20000,
        journal_mode=660,
        journal_readable=True,
        journal_writable=False,
        heartbeat_age_seconds=1,
    )

    assert observation.backlog == 0
    assert observation.to_dict()["backlog"] == 0


def test_runtime_bus_derives_positive_backlog() -> None:
    observation = RuntimeBusObservation(
        journal_lines=220,
        cursor_value=215,
        journal_uid=0,
        journal_gid=20000,
        journal_mode=660,
        journal_readable=True,
        journal_writable=False,
        heartbeat_age_seconds=2,
    )

    assert observation.backlog == 5


def test_runtime_bus_round_trip() -> None:
    original = RuntimeBusObservation(
        journal_lines=215,
        cursor_value=215,
        journal_uid=0,
        journal_gid=20000,
        journal_mode=660,
        journal_readable=True,
        journal_writable=False,
        heartbeat_age_seconds=1,
    )

    rebuilt = RuntimeBusObservation.from_dict(
        original.to_dict(),
    )

    assert rebuilt == original


def test_runtime_bus_rejects_cursor_beyond_journal_tail() -> None:
    with pytest.raises(
        SustainedUseModelError,
        match="cursor_value cannot exceed journal_lines",
    ):
        RuntimeBusObservation(
            journal_lines=215,
            cursor_value=216,
            journal_uid=0,
            journal_gid=20000,
            journal_mode=660,
            journal_readable=True,
            journal_writable=False,
            heartbeat_age_seconds=1,
        )


def test_scheduler_healthy_observation_round_trip() -> None:
    original = SchedulerObservation(
        name="operations.collect",
        enabled=True,
        status="healthy",
        due=True,
        run_count=1,
        failure_count=0,
        last_success="2026-08-04T00:15:52.899808+00:00",
        next_run="2026-08-04T01:15:52.899808+00:00",
    )

    rebuilt = SchedulerObservation.from_dict(
        original.to_dict(),
    )

    assert rebuilt == original
    assert original.status == "healthy"
    assert original.run_count == 1
    assert original.failure_count == 0


def test_scheduler_never_run_contract() -> None:
    observation = SchedulerObservation(
        name="sports.maintenance",
        enabled=True,
        status="never_run",
        due=True,
        run_count=0,
        failure_count=0,
        last_success=None,
        next_run="2026-08-17T14:42:25.029029+00:00",
    )

    assert observation.enabled is True
    assert observation.status == "never_run"
    assert observation.due is True
    assert observation.run_count == 0
    assert observation.failure_count == 0
    assert observation.last_success is None


def test_scheduler_normalizes_timestamps_to_utc() -> None:
    observation = SchedulerObservation(
        name="operations.collect",
        enabled=True,
        status="healthy",
        due=False,
        run_count=2,
        failure_count=0,
        last_success="2026-08-17T10:00:00-04:00",
        next_run="2026-08-17T11:00:00-04:00",
    )

    assert observation.last_success == "2026-08-17T14:00:00Z"
    assert observation.next_run == "2026-08-17T15:00:00Z"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("run_count", -1),
        ("failure_count", -1),
    ],
)
def test_scheduler_rejects_negative_counters(
    field: str,
    value: int,
) -> None:
    kwargs = {
        "name": "operations.collect",
        "enabled": True,
        "status": "healthy",
        "due": False,
        "run_count": 1,
        "failure_count": 0,
        field: value,
    }

    with pytest.raises(
        SustainedUseModelError,
        match=field,
    ):
        SchedulerObservation(**kwargs)


def test_scheduler_requires_boolean_due() -> None:
    with pytest.raises(
        SustainedUseModelError,
        match="due must be a boolean",
    ):
        SchedulerObservation(
            name="operations.collect",
            enabled=True,
            status="healthy",
            due="true",
            run_count=1,
            failure_count=0,
        )


def test_ari_frozen_warning_baseline() -> None:
    observation = AriObservation(
        status="warning",
        score=80,
        warnings=(
            "Library synchronization failed",
        ),
        tv_filesystem_count=1,
        tv_jellyfin_count=3,
    )

    assert observation.status == "warning"
    assert observation.score == 80
    assert observation.warnings == (
        "Library synchronization failed",
    )
    assert observation.tv_filesystem_count == 1
    assert observation.tv_jellyfin_count == 3
    assert observation.tv_synchronized is False


def test_ari_round_trip_is_deterministic() -> None:
    original = AriObservation(
        status="WARNING",
        score=80,
        warnings=(
            "Library synchronization failed",
        ),
        tv_filesystem_count=1,
        tv_jellyfin_count=3,
    )

    payload = original.to_dict()
    rebuilt = AriObservation.from_dict(payload)

    assert rebuilt == original
    assert payload["status"] == "warning"
    assert payload["tv_synchronized"] is False


def test_ari_synchronized_counts_are_derived() -> None:
    observation = AriObservation(
        status="healthy",
        score=100,
        warnings=(),
        tv_filesystem_count=3,
        tv_jellyfin_count=3,
    )

    assert observation.tv_synchronized is True


def test_ari_sync_state_is_unknown_without_counts() -> None:
    observation = AriObservation(
        status="warning",
        score=80,
        warnings=("Some warning",),
    )

    assert observation.tv_synchronized is None


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("score", -1),
        ("score", 101),
        ("tv_filesystem_count", -1),
        ("tv_jellyfin_count", -1),
    ],
)
def test_ari_rejects_invalid_numeric_values(
    field: str,
    value: int,
) -> None:
    kwargs = {
        "status": "warning",
        "score": 80,
        "warnings": (
            "Library synchronization failed",
        ),
        field: value,
    }

    with pytest.raises(
        SustainedUseModelError,
        match=field,
    ):
        AriObservation(**kwargs)


def test_ari_rejects_non_tuple_warning_constructor() -> None:
    with pytest.raises(
        SustainedUseModelError,
        match="warnings must be a tuple",
    ):
        AriObservation(
            status="warning",
            score=80,
            warnings=[
                "Library synchronization failed",
            ],
        )


def test_ari_from_dict_requires_warning_array() -> None:
    with pytest.raises(
        SustainedUseModelError,
        match="warnings must be an array",
    ):
        AriObservation.from_dict(
            {
                "status": "warning",
                "score": 80,
                "warnings": (
                    "Library synchronization failed",
                ),
            }
        )


def _sample_container(
    name: str = "atlas-api",
) -> ContainerObservation:
    return ContainerObservation(
        name=name,
        container_id=f"{name}-id",
        status="running",
        health="healthy",
        restart_count=0,
        oom_killed=False,
        started_at="2026-08-17T12:00:00Z",
    )


def _sample_scheduler(
    name: str = "operations.collect",
) -> SchedulerObservation:
    return SchedulerObservation(
        name=name,
        enabled=True,
        status="healthy",
        due=True,
        run_count=1,
        failure_count=0,
        last_success="2026-08-17T12:00:00Z",
        next_run="2026-08-17T13:00:00Z",
    )


def _sample_runtime_bus() -> RuntimeBusObservation:
    return RuntimeBusObservation(
        journal_lines=215,
        cursor_value=215,
        journal_uid=0,
        journal_gid=20000,
        journal_mode=660,
        journal_readable=True,
        journal_writable=False,
        heartbeat_age_seconds=1,
    )


def _sample_ari() -> AriObservation:
    return AriObservation(
        status="warning",
        score=80,
        warnings=(
            "Library synchronization failed",
        ),
        tv_filesystem_count=1,
        tv_jellyfin_count=3,
    )


def _sample() -> SustainedUseSample:
    return SustainedUseSample(
        generated_at="2026-08-17T14:42:24-04:00",
        git_commit=COMMIT,
        atlas_health_status="healthy",
        atlas_health_score=100,
        running_containers=22,
        unhealthy_containers=0,
        root_usage_percent=63,
        storage_usage_percent=8,
        containers=(
            _sample_container(),
            ContainerObservation(
                name="prowlarr",
                container_id="prowlarr-id",
                status="running",
                health="none",
                restart_count=0,
                oom_killed=False,
                started_at="2026-08-13T00:11:15Z",
            ),
        ),
        schedulers=(
            _sample_scheduler(),
            SchedulerObservation(
                name="sports.maintenance",
                enabled=True,
                status="never_run",
                due=True,
                run_count=0,
                failure_count=0,
                last_success=None,
                next_run="2026-08-17T14:42:25Z",
            ),
        ),
        runtime_bus=_sample_runtime_bus(),
        ari=_sample_ari(),
    )


def test_sample_round_trip_is_deterministic() -> None:
    original = _sample()

    payload = original.to_dict()
    rebuilt = SustainedUseSample.from_dict(payload)

    assert rebuilt == original
    assert rebuilt.generated_at.endswith("Z")
    assert rebuilt.runtime_bus.backlog == 0
    assert rebuilt.ari.status == "warning"
    assert rebuilt.containers[1].health == "none"


def test_sample_preserves_health_and_storage_baseline() -> None:
    observation = _sample()

    assert observation.atlas_health_status == "healthy"
    assert observation.atlas_health_score == 100
    assert observation.running_containers == 22
    assert observation.unhealthy_containers == 0
    assert observation.root_usage_percent == 63
    assert observation.storage_usage_percent == 8


def test_sample_rejects_duplicate_container_names() -> None:
    original = _sample()

    with pytest.raises(
        SustainedUseModelError,
        match="container names must be unique",
    ):
        SustainedUseSample(
            generated_at=original.generated_at,
            git_commit=original.git_commit,
            atlas_health_status=original.atlas_health_status,
            atlas_health_score=original.atlas_health_score,
            running_containers=original.running_containers,
            unhealthy_containers=original.unhealthy_containers,
            root_usage_percent=original.root_usage_percent,
            storage_usage_percent=original.storage_usage_percent,
            containers=(
                _sample_container(),
                _sample_container(),
            ),
            schedulers=original.schedulers,
            runtime_bus=original.runtime_bus,
            ari=original.ari,
        )


def test_sample_rejects_duplicate_scheduler_names() -> None:
    original = _sample()

    with pytest.raises(
        SustainedUseModelError,
        match="scheduler names must be unique",
    ):
        SustainedUseSample(
            generated_at=original.generated_at,
            git_commit=original.git_commit,
            atlas_health_status=original.atlas_health_status,
            atlas_health_score=original.atlas_health_score,
            running_containers=original.running_containers,
            unhealthy_containers=original.unhealthy_containers,
            root_usage_percent=original.root_usage_percent,
            storage_usage_percent=original.storage_usage_percent,
            containers=original.containers,
            schedulers=(
                _sample_scheduler(),
                _sample_scheduler(),
            ),
            runtime_bus=original.runtime_bus,
            ari=original.ari,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("atlas_health_score", 101),
        ("running_containers", -1),
        ("unhealthy_containers", -1),
        ("root_usage_percent", 101),
        ("storage_usage_percent", 101),
    ],
)
def test_sample_rejects_invalid_scalar_values(
    field: str,
    value: int,
) -> None:
    original = _sample()

    kwargs = {
        "generated_at": original.generated_at,
        "git_commit": original.git_commit,
        "atlas_health_status": original.atlas_health_status,
        "atlas_health_score": original.atlas_health_score,
        "running_containers": original.running_containers,
        "unhealthy_containers": original.unhealthy_containers,
        "root_usage_percent": original.root_usage_percent,
        "storage_usage_percent": original.storage_usage_percent,
        "containers": original.containers,
        "schedulers": original.schedulers,
        "runtime_bus": original.runtime_bus,
        "ari": original.ari,
        field: value,
    }

    with pytest.raises(
        SustainedUseModelError,
        match=field,
    ):
        SustainedUseSample(**kwargs)


def test_sample_from_dict_validates_child_payloads() -> None:
    payload = _sample().to_dict()

    payload["containers"][0]["restart_count"] = -1

    with pytest.raises(
        SustainedUseModelError,
        match="restart_count",
    ):
        SustainedUseSample.from_dict(payload)


def test_session_from_contract_freezes_q6_window() -> None:
    from atlas.sustained_use import SustainedUseSession

    contract = SustainedUseContract(
        git_commit=COMMIT,
    )

    session = SustainedUseSession.from_contract(
        run_id="q6-20260817T160000Z",
        started_at="2026-08-17T16:00:00Z",
        scheduled_end_at="2026-08-19T16:00:00Z",
        contract=contract,
    )

    assert session.git_commit == COMMIT
    assert session.duration_seconds == 172800
    assert session.interval_seconds == 900
    assert session.expected_sample_count == 193
    assert session.expected_running_containers == 22
    assert session.status == "active"
    assert session.completed_at is None


def test_session_round_trip_is_deterministic() -> None:
    from atlas.sustained_use import SustainedUseSession

    original = SustainedUseSession(
        run_id="q6-test",
        git_commit=COMMIT,
        started_at="2026-08-17T16:00:00Z",
        scheduled_end_at="2026-08-19T16:00:00Z",
        duration_seconds=172800,
        interval_seconds=900,
        expected_sample_count=193,
        expected_running_containers=22,
    )

    rebuilt = SustainedUseSession.from_dict(
        original.to_dict(),
    )

    assert rebuilt == original


def test_completed_session_requires_completion_timestamp() -> None:
    from atlas.sustained_use import SustainedUseSession

    with pytest.raises(
        SustainedUseModelError,
        match="requires completed_at",
    ):
        SustainedUseSession(
            run_id="q6-test",
            git_commit=COMMIT,
            started_at="2026-08-17T16:00:00Z",
            scheduled_end_at="2026-08-19T16:00:00Z",
            duration_seconds=172800,
            interval_seconds=900,
            expected_sample_count=193,
            expected_running_containers=22,
            status="completed",
        )


def test_active_session_rejects_completion_timestamp() -> None:
    from atlas.sustained_use import SustainedUseSession

    with pytest.raises(
        SustainedUseModelError,
        match="active session cannot",
    ):
        SustainedUseSession(
            run_id="q6-test",
            git_commit=COMMIT,
            started_at="2026-08-17T16:00:00Z",
            scheduled_end_at="2026-08-19T16:00:00Z",
            duration_seconds=172800,
            interval_seconds=900,
            expected_sample_count=193,
            expected_running_containers=22,
            status="active",
            completed_at="2026-08-19T16:00:00Z",
        )


def test_session_rejects_wrong_expected_sample_count() -> None:
    from atlas.sustained_use import SustainedUseSession

    with pytest.raises(
        SustainedUseModelError,
        match="expected_sample_count",
    ):
        SustainedUseSession(
            run_id="q6-test",
            git_commit=COMMIT,
            started_at="2026-08-17T16:00:00Z",
            scheduled_end_at="2026-08-19T16:00:00Z",
            duration_seconds=172800,
            interval_seconds=900,
            expected_sample_count=192,
            expected_running_containers=22,
        )


def test_session_rejects_wrong_end_timestamp() -> None:
    from atlas.sustained_use import SustainedUseSession

    with pytest.raises(
        SustainedUseModelError,
        match="scheduled_end_at",
    ):
        SustainedUseSession(
            run_id="q6-test",
            git_commit=COMMIT,
            started_at="2026-08-17T16:00:00Z",
            scheduled_end_at="2026-08-19T15:00:00Z",
            duration_seconds=172800,
            interval_seconds=900,
            expected_sample_count=193,
            expected_running_containers=22,
        )
