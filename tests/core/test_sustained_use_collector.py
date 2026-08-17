from __future__ import annotations

import json
from subprocess import CompletedProcess

import pytest

import atlas.sustained_use.collector as collector
from atlas.sustained_use import (
    AtlasHealthObservation,
    FilesystemObservation,
    SustainedUseCollectionError,
)


def result(
    stdout: str,
) -> CompletedProcess[str]:
    return CompletedProcess(
        args=("test",),
        returncode=0,
        stdout=stdout,
        stderr="",
    )


def test_health_observation_normalizes_status() -> None:
    observation = AtlasHealthObservation(
        status="HEALTHY",
        score=100,
    )

    assert observation.status == "healthy"
    assert observation.score == 100


def test_collect_atlas_health_parses_compact_json(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        collector,
        "_run",
        lambda command: result(
            json.dumps(
                {
                    "status": "healthy",
                    "score": 100,
                }
            )
        ),
    )

    observation = collector.collect_atlas_health()

    assert observation.status == "healthy"
    assert observation.score == 100


def test_collect_atlas_health_rejects_invalid_json(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        collector,
        "_run",
        lambda command: result("not-json"),
    )

    with pytest.raises(
        SustainedUseCollectionError,
        match="invalid JSON",
    ):
        collector.collect_atlas_health()


def test_parse_docker_health_none_contract() -> None:
    observation = collector._parse_docker_inspect(
        [
            {
                "Id": "abc123",
                "Name": "/prowlarr",
                "RestartCount": 0,
                "State": {
                    "Status": "running",
                    "OOMKilled": False,
                    "StartedAt": "2026-08-13T00:11:15Z",
                },
            }
        ]
    )

    assert observation.name == "prowlarr"
    assert observation.health == "none"
    assert observation.restart_count == 0
    assert observation.oom_killed is False


def test_parse_docker_health_healthy_contract() -> None:
    observation = collector._parse_docker_inspect(
        [
            {
                "Id": "abc123",
                "Name": "/atlas-api",
                "RestartCount": 0,
                "State": {
                    "Status": "running",
                    "OOMKilled": False,
                    "StartedAt": "2026-08-13T01:16:15Z",
                    "Health": {
                        "Status": "healthy",
                    },
                },
            }
        ]
    )

    assert observation.health == "healthy"


def test_collect_containers_is_name_sorted(
    monkeypatch,
) -> None:
    responses = {
        (
            "docker",
            "ps",
            "--format",
            "{{.Names}}",
        ): result(
            "prowlarr\natlas-api\n"
        ),
        (
            "docker",
            "inspect",
            "atlas-api",
        ): result(
            json.dumps(
                [
                    {
                        "Id": "api",
                        "Name": "/atlas-api",
                        "RestartCount": 0,
                        "State": {
                            "Status": "running",
                            "OOMKilled": False,
                            "StartedAt": (
                                "2026-08-13T01:16:15Z"
                            ),
                            "Health": {
                                "Status": "healthy",
                            },
                        },
                    }
                ]
            )
        ),
        (
            "docker",
            "inspect",
            "prowlarr",
        ): result(
            json.dumps(
                [
                    {
                        "Id": "prowlarr",
                        "Name": "/prowlarr",
                        "RestartCount": 0,
                        "State": {
                            "Status": "running",
                            "OOMKilled": False,
                            "StartedAt": (
                                "2026-08-13T00:11:15Z"
                            ),
                        },
                    }
                ]
            )
        ),
    }

    monkeypatch.setattr(
        collector,
        "_run",
        lambda command: responses[tuple(command)],
    )

    observations = collector.collect_containers()

    assert tuple(
        item.name
        for item in observations
    ) == (
        "atlas-api",
        "prowlarr",
    )


def test_filesystem_observation_validates_percent() -> None:
    observation = FilesystemObservation(
        path="/",
        usage_percent=63,
    )

    assert observation.path == "/"
    assert observation.usage_percent == 63


def test_collect_filesystem_parses_df(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        collector,
        "_run",
        lambda command: result(
            "Filesystem 1024-blocks Used Available Capacity Mounted on\n"
            "/dev/root 1000 630 370 63% /\n"
        ),
    )

    observation = collector.collect_filesystem("/")

    assert observation.path == "/"
    assert observation.usage_percent == 63


def test_parse_scheduler_healthy_contract() -> None:
    observation = collector._parse_scheduler_payload(
        {
            "name": "operations.collect",
            "enabled": True,
            "status": "healthy",
            "due": True,
            "run_count": 1,
            "failure_count": 0,
            "last_success": (
                "2026-08-04T00:15:52.899808+00:00"
            ),
            "next_run": (
                "2026-08-04T01:15:52.899808+00:00"
            ),
        }
    )

    assert observation.name == "operations.collect"
    assert observation.status == "healthy"
    assert observation.due is True
    assert observation.run_count == 1
    assert observation.failure_count == 0


def test_parse_scheduler_never_run_contract() -> None:
    observation = collector._parse_scheduler_payload(
        {
            "name": "sports.maintenance",
            "enabled": True,
            "status": "never_run",
            "due": True,
            "run_count": 0,
            "failure_count": 0,
            "next_run": (
                "2026-08-17T14:42:25.029029+00:00"
            ),
        }
    )

    assert observation.name == "sports.maintenance"
    assert observation.status == "never_run"
    assert observation.run_count == 0
    assert observation.last_success is None


def test_collect_scheduler_uses_inspect_only(
    monkeypatch,
) -> None:
    calls = []

    def fake_run(command):
        calls.append(tuple(command))

        return result(
            json.dumps(
                {
                    "name": "operations.collect",
                    "enabled": True,
                    "status": "healthy",
                    "due": True,
                    "run_count": 1,
                    "failure_count": 0,
                    "last_success": (
                        "2026-08-04T00:15:52.899808+00:00"
                    ),
                    "next_run": (
                        "2026-08-04T01:15:52.899808+00:00"
                    ),
                }
            )
        )

    monkeypatch.setattr(
        collector,
        "_run",
        fake_run,
    )

    observation = collector.collect_scheduler(
        "operations.collect"
    )

    assert observation.name == "operations.collect"

    assert calls == [
        (
            "atlas",
            "scheduler",
            "inspect",
            "operations.collect",
        )
    ]


def test_collect_schedulers_is_deterministic(
    monkeypatch,
) -> None:
    calls = []

    def fake_collect(name):
        calls.append(name)

        if name == "operations.collect":
            return collector.SchedulerObservation(
                name=name,
                enabled=True,
                status="healthy",
                due=True,
                run_count=1,
                failure_count=0,
                last_success="2026-08-04T00:15:52Z",
                next_run="2026-08-04T01:15:52Z",
            )

        return collector.SchedulerObservation(
            name=name,
            enabled=True,
            status="never_run",
            due=True,
            run_count=0,
            failure_count=0,
            last_success=None,
            next_run="2026-08-17T14:42:25Z",
        )

    monkeypatch.setattr(
        collector,
        "collect_scheduler",
        fake_collect,
    )

    observations = collector.collect_schedulers(
        (
            "sports.maintenance",
            "operations.collect",
        )
    )

    assert tuple(
        item.name
        for item in observations
    ) == (
        "operations.collect",
        "sports.maintenance",
    )

    assert calls == [
        "operations.collect",
        "sports.maintenance",
    ]


def test_collect_schedulers_rejects_empty_input() -> None:
    with pytest.raises(
        SustainedUseCollectionError,
        match="at least one scheduler name",
    ):
        collector.collect_schedulers(())


def test_runtime_bus_collects_reader_contract(
    tmp_path,
    monkeypatch,
) -> None:
    event_log = tmp_path / "events.jsonl"
    cursor = tmp_path / "notifications.cursor"
    heartbeat = tmp_path / "worker-heartbeat"

    event_log.write_text(
        '{"id": 1}\n{"id": 2}\n{"id": 3}\n',
        encoding="utf-8",
    )
    cursor.write_text(
        "3\n",
        encoding="utf-8",
    )
    heartbeat.write_text(
        "ok\n",
        encoding="utf-8",
    )

    heartbeat.touch()

    calls = []

    def fake_status(command):
        calls.append(tuple(command))

        if "-r" in command:
            return 0

        if "-w" in command:
            return 1

        raise AssertionError(command)

    monkeypatch.setattr(
        collector,
        "_run_status",
        fake_status,
    )

    heartbeat_mtime = heartbeat.stat().st_mtime

    observation = collector.collect_runtime_bus(
        event_log=event_log,
        cursor=cursor,
        heartbeat=heartbeat,
        notifications_container="worker",
        now_epoch=heartbeat_mtime + 5,
    )

    assert observation.journal_lines == 3
    assert observation.cursor_value == 3
    assert observation.backlog == 0
    assert observation.journal_readable is True
    assert observation.journal_writable is False
    assert observation.heartbeat_age_seconds == 5

    assert len(calls) == 2


def test_runtime_bus_derives_backlog(
    tmp_path,
    monkeypatch,
) -> None:
    event_log = tmp_path / "events.jsonl"
    cursor = tmp_path / "notifications.cursor"
    heartbeat = tmp_path / "worker-heartbeat"

    event_log.write_text(
        "1\n2\n3\n4\n5\n",
        encoding="utf-8",
    )
    cursor.write_text(
        "3\n",
        encoding="utf-8",
    )
    heartbeat.write_text(
        "ok\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        collector,
        "_run_status",
        lambda command: 0 if "-r" in command else 1,
    )

    observation = collector.collect_runtime_bus(
        event_log=event_log,
        cursor=cursor,
        heartbeat=heartbeat,
        now_epoch=heartbeat.stat().st_mtime,
    )

    assert observation.journal_lines == 5
    assert observation.cursor_value == 3
    assert observation.backlog == 2


def test_runtime_bus_rejects_cursor_beyond_tail(
    tmp_path,
    monkeypatch,
) -> None:
    event_log = tmp_path / "events.jsonl"
    cursor = tmp_path / "notifications.cursor"
    heartbeat = tmp_path / "worker-heartbeat"

    event_log.write_text(
        "1\n",
        encoding="utf-8",
    )
    cursor.write_text(
        "2\n",
        encoding="utf-8",
    )
    heartbeat.write_text(
        "ok\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        collector,
        "_run_status",
        lambda command: 0,
    )

    with pytest.raises(
        SustainedUseCollectionError,
        match="cursor exceeds event journal tail",
    ):
        collector.collect_runtime_bus(
            event_log=event_log,
            cursor=cursor,
            heartbeat=heartbeat,
        )


def test_runtime_bus_rejects_missing_files(
    tmp_path,
) -> None:
    with pytest.raises(
        SustainedUseCollectionError,
        match="event journal is missing",
    ):
        collector.collect_runtime_bus(
            event_log=tmp_path / "missing-events",
            cursor=tmp_path / "cursor",
            heartbeat=tmp_path / "heartbeat",
        )


def test_runtime_bus_cursor_must_be_integer(
    tmp_path,
) -> None:
    event_log = tmp_path / "events.jsonl"
    cursor = tmp_path / "notifications.cursor"
    heartbeat = tmp_path / "worker-heartbeat"

    event_log.write_text(
        "1\n",
        encoding="utf-8",
    )
    cursor.write_text(
        "not-an-integer\n",
        encoding="utf-8",
    )
    heartbeat.write_text(
        "ok\n",
        encoding="utf-8",
    )

    with pytest.raises(
        SustainedUseCollectionError,
        match="Notifications cursor must contain an integer",
    ):
        collector.collect_runtime_bus(
            event_log=event_log,
            cursor=cursor,
            heartbeat=heartbeat,
        )


ARI_REPORT = """Atlas Retention Intelligence Report
-----------------------------------

Jellyfin Counts
---------------
Movies:      0
Series:      3
Episodes:    23
Songs:       0

Libraries
---------
Movies:        0
TV:            1
Anime Movies:  0
Anime TV:      2

Atlas Health
------------
Score : 80 / 100
Status: Warning

Platform
--------
✓ Storage utilization

Warnings
--------
- Library synchronization failed

Forecast
--------
Storage Available : 1.6TB
"""


def test_parse_ari_frozen_baseline() -> None:
    observation = collector._parse_ari_report(
        ARI_REPORT,
    )

    assert observation.status == "warning"
    assert observation.score == 80
    assert observation.warnings == (
        "Library synchronization failed",
    )
    assert observation.tv_filesystem_count == 1
    assert observation.tv_jellyfin_count == 3
    assert observation.tv_synchronized is False


def test_parse_ari_supports_healthy_sync() -> None:
    report = (
        ARI_REPORT
        .replace(
            "Series:      3",
            "Series:      1",
        )
        .replace(
            "Score : 80 / 100",
            "Score : 100 / 100",
        )
        .replace(
            "Status: Warning",
            "Status: Healthy",
        )
        .replace(
            "- Library synchronization failed\n",
            "",
        )
    )

    observation = collector._parse_ari_report(
        report,
    )

    assert observation.status == "healthy"
    assert observation.score == 100
    assert observation.warnings == ()
    assert observation.tv_synchronized is True


def test_parse_ari_requires_score() -> None:
    report = ARI_REPORT.replace(
        "Score : 80 / 100\n",
        "",
    )

    with pytest.raises(
        SustainedUseCollectionError,
        match="missing health score",
    ):
        collector._parse_ari_report(
            report,
        )


def test_parse_ari_requires_status() -> None:
    report = ARI_REPORT.replace(
        "Status: Warning\n",
        "",
    )

    with pytest.raises(
        SustainedUseCollectionError,
        match="missing health status",
    ):
        collector._parse_ari_report(
            report,
        )


def test_collect_ari_uses_report_only(
    monkeypatch,
) -> None:
    calls = []

    def fake_run(command):
        calls.append(tuple(command))

        return result(
            ARI_REPORT,
        )

    monkeypatch.setattr(
        collector,
        "_run",
        fake_run,
    )

    observation = collector.collect_ari()

    assert observation.score == 80

    assert calls == [
        (
            "atlas",
            "ari",
            "report",
        )
    ]


def test_collect_sample_assembles_all_providers(
    monkeypatch,
) -> None:
    from atlas.sustained_use import (
        AriObservation,
        AtlasHealthObservation,
        ContainerObservation,
        FilesystemObservation,
        RuntimeBusObservation,
        SchedulerObservation,
    )

    monkeypatch.setattr(
        collector,
        "_run",
        lambda command: result(
            (
                "b695c8d0e3bd01b974c55a57dc12df980b8a3e08\n"
            )
        )
        if tuple(command) == (
            "git",
            "rev-parse",
            "HEAD",
        )
        else (_ for _ in ()).throw(
            AssertionError(command)
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_atlas_health",
        lambda: AtlasHealthObservation(
            status="healthy",
            score=100,
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_containers",
        lambda: (
            ContainerObservation(
                name="atlas-api",
                container_id="api",
                status="running",
                health="healthy",
                restart_count=0,
                oom_killed=False,
                started_at="2026-08-13T01:16:15Z",
            ),
            ContainerObservation(
                name="prowlarr",
                container_id="prowlarr",
                status="running",
                health="none",
                restart_count=0,
                oom_killed=False,
                started_at="2026-08-13T00:11:15Z",
            ),
        ),
    )

    def fake_filesystem(path):
        return FilesystemObservation(
            path=str(path),
            usage_percent=(
                63
                if str(path) == "/"
                else 8
            ),
        )

    monkeypatch.setattr(
        collector,
        "collect_filesystem",
        fake_filesystem,
    )

    monkeypatch.setattr(
        collector,
        "collect_schedulers",
        lambda names: (
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
            SchedulerObservation(
                name="sports.maintenance",
                enabled=True,
                status="never_run",
                due=True,
                run_count=0,
                failure_count=0,
                last_success=None,
                next_run="2026-08-17T15:12:42Z",
            ),
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_runtime_bus",
        lambda: RuntimeBusObservation(
            journal_lines=215,
            cursor_value=215,
            journal_uid=0,
            journal_gid=20000,
            journal_mode=660,
            journal_readable=True,
            journal_writable=False,
            heartbeat_age_seconds=0,
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_ari",
        lambda: AriObservation(
            status="warning",
            score=80,
            warnings=(
                "Library synchronization failed",
            ),
            tv_filesystem_count=1,
            tv_jellyfin_count=3,
        ),
    )

    sample = collector.collect_sample()

    assert sample.git_commit == (
        "b695c8d0e3bd01b974c55a57dc12df980b8a3e08"
    )
    assert sample.atlas_health_status == "healthy"
    assert sample.atlas_health_score == 100
    assert sample.running_containers == 2
    assert sample.unhealthy_containers == 0
    assert sample.root_usage_percent == 63
    assert sample.storage_usage_percent == 8
    assert sample.containers[1].health == "none"
    assert sample.runtime_bus.backlog == 0
    assert sample.ari.score == 80


def test_collect_sample_counts_unhealthy_containers(
    monkeypatch,
) -> None:
    from atlas.sustained_use import (
        AriObservation,
        AtlasHealthObservation,
        ContainerObservation,
        FilesystemObservation,
        RuntimeBusObservation,
    )

    monkeypatch.setattr(
        collector,
        "_run",
        lambda command: result(
            "b695c8d0e3bd01b974c55a57dc12df980b8a3e08\n"
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_atlas_health",
        lambda: AtlasHealthObservation(
            status="warning",
            score=99,
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_containers",
        lambda: (
            ContainerObservation(
                name="broken",
                container_id="broken",
                status="running",
                health="unhealthy",
                restart_count=0,
                oom_killed=False,
                started_at="2026-08-17T12:00:00Z",
            ),
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_filesystem",
        lambda path: FilesystemObservation(
            path=str(path),
            usage_percent=10,
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_schedulers",
        lambda names: (),
    )

    monkeypatch.setattr(
        collector,
        "collect_runtime_bus",
        lambda: RuntimeBusObservation(
            journal_lines=1,
            cursor_value=1,
            journal_uid=0,
            journal_gid=20000,
            journal_mode=660,
            journal_readable=True,
            journal_writable=False,
            heartbeat_age_seconds=1,
        ),
    )

    monkeypatch.setattr(
        collector,
        "collect_ari",
        lambda: AriObservation(
            status="healthy",
            score=100,
            warnings=(),
        ),
    )

    sample = collector.collect_sample(
        scheduler_names=("ignored",),
    )

    assert sample.running_containers == 1
    assert sample.unhealthy_containers == 1
