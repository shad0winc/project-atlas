"""Tests for the Atlas Docker Operations collector."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.operations import (
    OperationsSectionId,
    OperationsStatus,
)
from atlas.operations.collectors import (
    DEFAULT_DOCKER_GOVERNANCE_POLICY,
    DockerCollector,
    DockerContainerSnapshot,
    DockerContainerSummary,
    DockerEngineSnapshot,
    DockerGovernanceRule,
    DockerOperationsProvider,
)


def engine_snapshot() -> DockerEngineSnapshot:
    return DockerEngineSnapshot(
        client_version="28.3.3",
        server_version="28.3.3",
        daemon_name="docker",
        operating_system="Debian GNU/Linux 13",
        architecture="x86_64",
        storage_driver="overlay2",
        cpu_count=8,
        memory_bytes=24 * 1024**3,
        containers_total=2,
        containers_running=2,
        containers_paused=0,
        containers_stopped=0,
    )


def container_summary(
    name: str,
    *,
    container_id: str,
    state: str = "running",
) -> DockerContainerSummary:
    return DockerContainerSummary(
        container_id=container_id,
        name=name,
        image=f"{name}:latest",
        state=state,
        status=(
            "Up 10 minutes"
            if state == "running"
            else "Exited (0) 2 minutes ago"
        ),
    )


def container_snapshot(
    name: str,
    *,
    container_id: str,
    running: bool = True,
    restarting: bool = False,
    health: str | None = "healthy",
    oom_killed: bool = False,
    exit_code: int = 0,
    restart_count: int = 0,
    memory_limit_bytes: int = 1024**3,
    cpu_limit: float | None = 1.0,
    pids_limit: int | None = 256,
) -> DockerContainerSnapshot:
    return DockerContainerSnapshot(
        container_id=container_id,
        name=name,
        image=f"{name}:latest",
        image_id=f"sha256:{container_id}",
        state="running" if running else "exited",
        health=health,
        running=running,
        restarting=restarting,
        oom_killed=oom_killed,
        exit_code=exit_code,
        restart_count=restart_count,
        restart_policy="unless-stopped",
        restart_maximum_retry_count=0,
        created_at="2026-08-03T16:00:00Z",
        started_at=(
            "2026-08-03T16:01:00Z"
            if running
            else "2026-08-03T16:01:00Z"
        ),
        finished_at=(
            None
            if running
            else "2026-08-03T17:00:00Z"
        ),
        memory_limit_bytes=memory_limit_bytes,
        nano_cpus=(
            int(cpu_limit * 1_000_000_000)
            if cpu_limit is not None
            else 0
        ),
        cpu_limit=cpu_limit,
        pids_limit=pids_limit,
        mounts=(),
        networks=(),
        ports=(),
    )


class FakeDockerOperationsProvider:
    """Deterministic provider used by collector tests."""

    def engine(self) -> DockerEngineSnapshot:
        return engine_snapshot()

    def containers(self) -> tuple[DockerContainerSummary, ...]:
        return (
            container_summary(
                "atlas-api",
                container_id="aaa111",
            ),
            container_summary(
                "jellyfin",
                container_id="bbb222",
            ),
        )

    def container(
        self,
        identity: str,
    ) -> DockerContainerSnapshot:
        values = {
            "atlas-api": "aaa111",
            "jellyfin": "bbb222",
        }

        return container_snapshot(
            identity,
            container_id=values[identity],
        )


def docker_collector(
    provider: object | None = None,
) -> DockerCollector:
    return DockerCollector(
        provider=(
            provider
            if provider is not None
            else FakeDockerOperationsProvider()
        ),
    )


def finding(result, identifier: str):
    return next(
        item
        for item in result.findings
        if item.identifier == identifier
    )


def test_docker_collector_metadata() -> None:
    result = docker_collector()

    assert result.section_id is OperationsSectionId.CONTAINERS
    assert result.name == "Containers"
    assert result.timeout_seconds == 10.0
    assert result.description == (
        "Docker Engine availability and container inventory"
    )


def test_docker_collector_returns_canonical_section() -> None:
    result = docker_collector().collect_checked()

    assert result.identifier is OperationsSectionId.CONTAINERS
    assert result.name == "Containers"
    assert tuple(
        item.identifier
        for item in result.findings
    ) == (
        "docker.engine",
        "docker.inventory",
        "docker.runtime",
        "docker.health",
        "docker.restarts",
        "docker.oom",
        "docker.exit",
        "docker.governance",
    )


def test_engine_finding_is_healthy() -> None:
    result = docker_collector().collect()
    engine = finding(result, "docker.engine")

    assert engine.status is OperationsStatus.HEALTHY
    assert engine.message == (
        "Docker Engine is available: server 28.3.3"
    )
    assert engine.metadata["client_version"] == "28.3.3"
    assert engine.metadata["server_version"] == "28.3.3"
    assert engine.metadata["cpu_count"] == 8


def test_inventory_finding_is_healthy() -> None:
    result = docker_collector().collect()
    inventory = finding(result, "docker.inventory")

    assert inventory.status is OperationsStatus.HEALTHY
    assert inventory.message == (
        "All 2 Docker containers are running"
    )
    assert inventory.metadata == {
        "container_count": 2,
        "container_names": [
            "atlas-api",
            "jellyfin",
        ],
        "non_running_count": 0,
        "non_running_names": [],
        "running_count": 2,
    }


def test_inventory_warns_for_nonrunning_container() -> None:
    class StoppedProvider(FakeDockerOperationsProvider):
        def containers(self):
            return (
                container_summary(
                    "atlas-api",
                    container_id="aaa111",
                ),
                container_summary(
                    "jellyfin",
                    container_id="bbb222",
                    state="exited",
                ),
            )

    result = docker_collector(StoppedProvider()).collect()
    inventory = finding(result, "docker.inventory")

    assert inventory.status is OperationsStatus.WARNING
    assert inventory.action_required is True
    assert inventory.metadata["non_running_names"] == [
        "jellyfin",
    ]
    assert inventory.recommendation is not None


def test_engine_failure_degrades_only_engine_finding() -> None:
    class FailingProvider(FakeDockerOperationsProvider):
        def engine(self):
            raise RuntimeError("Docker daemon unavailable")

    result = docker_collector(FailingProvider()).collect()

    assert finding(
        result,
        "docker.engine",
    ).status is OperationsStatus.UNKNOWN

    assert finding(
        result,
        "docker.inventory",
    ).status is OperationsStatus.HEALTHY


def test_inventory_failure_degrades_only_inventory_finding() -> None:
    class FailingProvider(FakeDockerOperationsProvider):
        def containers(self):
            raise RuntimeError("inventory unavailable")

    result = docker_collector(FailingProvider()).collect()

    assert finding(
        result,
        "docker.engine",
    ).status is OperationsStatus.HEALTHY

    inventory = finding(result, "docker.inventory")

    assert inventory.status is OperationsStatus.UNKNOWN
    assert inventory.metadata == {
        "error": "inventory unavailable",
    }


def test_provider_sources_are_called_once() -> None:
    calls: list[str] = []

    class RecordingProvider(FakeDockerOperationsProvider):
        def engine(self):
            calls.append("engine")
            return super().engine()

        def containers(self):
            calls.append("containers")
            return super().containers()

        def container(self, identity: str):
            calls.append(f"container:{identity}")
            return super().container(identity)

    docker_collector(RecordingProvider()).collect()

    assert calls == [
        "engine",
        "containers",
        "container:atlas-api",
        "container:jellyfin",
    ]


def test_docker_collector_rejects_wrong_section() -> None:
    with pytest.raises(
        ValueError,
        match="must use the containers section",
    ):
        DockerCollector(
            section_id="services",
            provider=FakeDockerOperationsProvider(),
        )


@pytest.mark.parametrize(
    "provider",
    (
        object(),
        None,
    ),
)
def test_docker_collector_rejects_invalid_provider(
    provider: object | None,
) -> None:
    with pytest.raises(ValueError):
        DockerCollector(
            provider=provider,  # type: ignore[arg-type]
        )


def test_docker_collector_is_immutable() -> None:
    result = docker_collector()

    with pytest.raises(FrozenInstanceError):
        result.name = "Changed"  # type: ignore[misc]


def test_public_docker_collector_exports() -> None:
    from atlas.operations import collectors

    assert collectors.DockerCollector is DockerCollector
    assert (
        collectors.DockerOperationsProvider
        is DockerOperationsProvider
    )


def test_runtime_finding_is_healthy() -> None:
    result = docker_collector().collect()
    runtime = finding(result, "docker.runtime")

    assert runtime.status is OperationsStatus.HEALTHY
    assert runtime.metadata["inspected_count"] == 2
    assert runtime.metadata["non_running_count"] == 0
    assert runtime.metadata["restarting_count"] == 0


def test_runtime_warns_for_nonrunning_snapshot() -> None:
    class StoppedProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "jellyfin":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    running=False,
                    health=None,
                )

            return snapshot

    runtime = finding(
        docker_collector(StoppedProvider()).collect(),
        "docker.runtime",
    )

    assert runtime.status is OperationsStatus.WARNING
    assert runtime.metadata["non_running_names"] == [
        "jellyfin",
    ]


def test_runtime_is_critical_for_restarting_container() -> None:
    class RestartingProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "atlas-api":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    restarting=True,
                )

            return snapshot

    runtime = finding(
        docker_collector(RestartingProvider()).collect(),
        "docker.runtime",
    )

    assert runtime.status is OperationsStatus.CRITICAL
    assert runtime.metadata["restarting_names"] == [
        "atlas-api",
    ]


def test_health_finding_is_healthy() -> None:
    health = finding(
        docker_collector().collect(),
        "docker.health",
    )

    assert health.status is OperationsStatus.HEALTHY
    assert health.metadata["healthy_count"] == 2
    assert health.metadata["unhealthy_count"] == 0


def test_health_is_critical_for_unhealthy_container() -> None:
    class UnhealthyProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "jellyfin":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    health="unhealthy",
                )

            return snapshot

    health = finding(
        docker_collector(UnhealthyProvider()).collect(),
        "docker.health",
    )

    assert health.status is OperationsStatus.CRITICAL
    assert health.metadata["unhealthy_names"] == [
        "jellyfin",
    ]


def test_health_warns_while_healthcheck_is_starting() -> None:
    class StartingProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "atlas-api":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    health="starting",
                )

            return snapshot

    health = finding(
        docker_collector(StartingProvider()).collect(),
        "docker.health",
    )

    assert health.status is OperationsStatus.WARNING
    assert health.metadata["starting_names"] == [
        "atlas-api",
    ]


def test_missing_healthcheck_remains_informational() -> None:
    class NoHealthProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            return container_snapshot(
                identity,
                container_id=snapshot.container_id,
                health=None,
            )

    health = finding(
        docker_collector(NoHealthProvider()).collect(),
        "docker.health",
    )

    assert health.status is OperationsStatus.HEALTHY
    assert health.metadata["without_healthcheck_count"] == 2


def test_single_inspection_failure_degrades_runtime_and_health() -> None:
    class InspectionFailureProvider(
        FakeDockerOperationsProvider
    ):
        def container(self, identity: str):
            if identity == "jellyfin":
                raise RuntimeError("inspection unavailable")

            return super().container(identity)

    result = docker_collector(
        InspectionFailureProvider()
    ).collect()

    runtime = finding(result, "docker.runtime")
    health = finding(result, "docker.health")

    assert runtime.status is OperationsStatus.UNKNOWN
    assert health.status is OperationsStatus.UNKNOWN

    assert runtime.metadata["inspection_errors"] == {
        "jellyfin": "inspection unavailable",
    }
    assert health.metadata["inspection_errors"] == {
        "jellyfin": "inspection unavailable",
    }


def test_inventory_failure_degrades_all_container_findings() -> None:
    class InventoryFailureProvider(
        FakeDockerOperationsProvider
    ):
        def containers(self):
            raise RuntimeError("inventory unavailable")

    result = docker_collector(
        InventoryFailureProvider()
    ).collect()

    assert finding(
        result,
        "docker.engine",
    ).status is OperationsStatus.HEALTHY

    for identifier in (
        "docker.inventory",
        "docker.runtime",
        "docker.health",
    ):
        assert finding(
            result,
            identifier,
        ).status is OperationsStatus.UNKNOWN


def test_restart_finding_is_healthy() -> None:
    result = docker_collector().collect()
    restart = finding(result, "docker.restarts")

    assert restart.status is OperationsStatus.HEALTHY
    assert restart.metadata["warning_threshold"] == 3
    assert restart.metadata["critical_threshold"] == 10


def test_restart_finding_warns_at_threshold() -> None:
    class RestartProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "jellyfin":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    restart_count=3,
                )

            return snapshot

    restart = finding(
        docker_collector(RestartProvider()).collect(),
        "docker.restarts",
    )

    assert restart.status is OperationsStatus.WARNING
    assert restart.metadata["warning_names"] == [
        "jellyfin",
    ]


def test_restart_finding_is_critical_at_threshold() -> None:
    class RestartProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "atlas-api":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    restart_count=10,
                )

            return snapshot

    restart = finding(
        docker_collector(RestartProvider()).collect(),
        "docker.restarts",
    )

    assert restart.status is OperationsStatus.CRITICAL
    assert restart.metadata["critical_names"] == [
        "atlas-api",
    ]


def test_oom_finding_is_healthy() -> None:
    oom = finding(
        docker_collector().collect(),
        "docker.oom",
    )

    assert oom.status is OperationsStatus.HEALTHY
    assert oom.metadata["oom_killed_count"] == 0


def test_oom_finding_is_critical() -> None:
    class OomProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "jellyfin":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    oom_killed=True,
                )

            return snapshot

    oom = finding(
        docker_collector(OomProvider()).collect(),
        "docker.oom",
    )

    assert oom.status is OperationsStatus.CRITICAL
    assert oom.metadata["oom_killed_names"] == [
        "jellyfin",
    ]


def test_exit_finding_is_healthy() -> None:
    exit_finding = finding(
        docker_collector().collect(),
        "docker.exit",
    )

    assert exit_finding.status is OperationsStatus.HEALTHY
    assert exit_finding.metadata["failed_count"] == 0


def test_exit_finding_warns_for_clean_stop() -> None:
    class StoppedProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "jellyfin":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    running=False,
                    health=None,
                    exit_code=0,
                )

            return snapshot

    exit_finding = finding(
        docker_collector(StoppedProvider()).collect(),
        "docker.exit",
    )

    assert exit_finding.status is OperationsStatus.WARNING
    assert exit_finding.metadata[
        "cleanly_stopped_names"
    ] == ["jellyfin"]


def test_exit_finding_is_critical_for_failed_stop() -> None:
    class FailedProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "atlas-api":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    running=False,
                    health=None,
                    exit_code=137,
                )

            return snapshot

    exit_finding = finding(
        docker_collector(FailedProvider()).collect(),
        "docker.exit",
    )

    assert exit_finding.status is OperationsStatus.CRITICAL
    assert exit_finding.metadata["failed_exit_codes"] == {
        "atlas-api": 137,
    }


def test_inspection_failure_degrades_all_failure_findings() -> None:
    class FailureProvider(FakeDockerOperationsProvider):
        def container(self, identity: str):
            if identity == "jellyfin":
                raise RuntimeError("inspection unavailable")

            return super().container(identity)

    result = docker_collector(FailureProvider()).collect()

    for identifier in (
        "docker.restarts",
        "docker.oom",
        "docker.exit",
    ):
        item = finding(result, identifier)

        assert item.status is OperationsStatus.UNKNOWN
        assert item.metadata["inspection_errors"] == {
            "jellyfin": "inspection unavailable",
        }


@pytest.mark.parametrize(
    ("warning", "critical"),
    (
        (0, 10),
        (3, 3),
        (10, 3),
        (True, 10),
        (3, False),
    ),
)
def test_collector_rejects_invalid_restart_thresholds(
    warning: object,
    critical: object,
) -> None:
    with pytest.raises(ValueError):
        DockerCollector(
            provider=FakeDockerOperationsProvider(),
            restart_warning_threshold=warning,  # type: ignore[arg-type]
            restart_critical_threshold=critical,  # type: ignore[arg-type]
        )


def governance_policy() -> tuple[DockerGovernanceRule, ...]:
    return (
        DockerGovernanceRule(
            container_name="atlas-api",
            memory_limit_bytes=1024**3,
            cpu_limit=2.0,
            pids_limit=512,
        ),
        DockerGovernanceRule(
            container_name="jellyfin",
            memory_limit_bytes=1024**3,
            cpu_limit=1.0,
            pids_limit=256,
        ),
    )


class GovernedProvider(FakeDockerOperationsProvider):
    def container(self, identity: str):
        snapshot = super().container(identity)

        if identity == "atlas-api":
            return container_snapshot(
                identity,
                container_id=snapshot.container_id,
                memory_limit_bytes=1024**3,
                cpu_limit=2.0,
                pids_limit=512,
            )

        return snapshot


def governed_collector(
    provider: object | None = None,
) -> DockerCollector:
    return DockerCollector(
        provider=(
            provider
            if provider is not None
            else GovernedProvider()
        ),
        governance_policy=governance_policy(),
    )


def test_governance_rule_normalizes_and_serializes() -> None:
    result = DockerGovernanceRule(
        container_name=" atlas-api ",
        memory_limit_bytes=1024,
        cpu_limit=2,
        pids_limit=512,
    )

    assert result.container_name == "atlas-api"
    assert result.cpu_limit == 2.0
    assert result.to_dict() == {
        "container_name": "atlas-api",
        "memory_limit_bytes": 1024,
        "cpu_limit": 2.0,
        "pids_limit": 512,
    }


def test_governance_finding_is_healthy() -> None:
    governance = finding(
        governed_collector().collect(),
        "docker.governance",
    )

    assert governance.status is OperationsStatus.HEALTHY
    assert governance.metadata["compliant_names"] == [
        "atlas-api",
        "jellyfin",
    ]
    assert governance.metadata["mismatch_count"] == 0
    assert governance.metadata["missing_ceiling_count"] == 0


def test_governance_ignores_unmanaged_containers() -> None:
    governance = finding(
        DockerCollector(
            provider=FakeDockerOperationsProvider(),
            governance_policy=(
                DockerGovernanceRule(
                    container_name="atlas-api",
                    memory_limit_bytes=1024**3,
                    cpu_limit=1.0,
                    pids_limit=256,
                ),
            ),
        ).collect(),
        "docker.governance",
    )

    assert governance.status is OperationsStatus.HEALTHY
    assert governance.metadata["ungoverned_names"] == [
        "jellyfin",
    ]


def test_governance_warns_for_missing_ceiling() -> None:
    class MissingCeilingProvider(GovernedProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "atlas-api":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    memory_limit_bytes=0,
                    cpu_limit=2.0,
                    pids_limit=512,
                )

            return snapshot

    governance = finding(
        governed_collector(
            MissingCeilingProvider()
        ).collect(),
        "docker.governance",
    )

    assert governance.status is OperationsStatus.WARNING
    assert governance.metadata["missing_ceilings"] == {
        "atlas-api": ["memory"],
    }


def test_governance_is_critical_for_mismatch() -> None:
    class MismatchProvider(GovernedProvider):
        def container(self, identity: str):
            snapshot = super().container(identity)

            if identity == "atlas-api":
                return container_snapshot(
                    identity,
                    container_id=snapshot.container_id,
                    memory_limit_bytes=512 * 1024**2,
                    cpu_limit=2.0,
                    pids_limit=512,
                )

            return snapshot

    governance = finding(
        governed_collector(
            MismatchProvider()
        ).collect(),
        "docker.governance",
    )

    assert governance.status is OperationsStatus.CRITICAL

    assert governance.metadata["mismatches"] == {
        "atlas-api": {
            "memory_limit_bytes": {
                "expected": 1024**3,
                "actual": 512 * 1024**2,
            },
        },
    }


def test_governance_is_critical_for_missing_container() -> None:
    policy = (
        DockerGovernanceRule(
            container_name="atlas-api",
            memory_limit_bytes=1024**3,
            cpu_limit=1.0,
            pids_limit=256,
        ),
        DockerGovernanceRule(
            container_name="atlas-portal",
            memory_limit_bytes=1536 * 1024**2,
            cpu_limit=2.0,
            pids_limit=512,
        ),
    )

    governance = finding(
        DockerCollector(
            provider=FakeDockerOperationsProvider(),
            governance_policy=policy,
        ).collect(),
        "docker.governance",
    )

    assert governance.status is OperationsStatus.CRITICAL
    assert governance.metadata[
        "missing_container_names"
    ] == ["atlas-portal"]


def test_governance_inspection_failure_is_unknown() -> None:
    class FailureProvider(GovernedProvider):
        def container(self, identity: str):
            if identity == "atlas-api":
                raise RuntimeError("inspection unavailable")

            return super().container(identity)

    governance = finding(
        governed_collector(
            FailureProvider()
        ).collect(),
        "docker.governance",
    )

    assert governance.status is OperationsStatus.UNKNOWN
    assert governance.metadata["inspection_errors"] == {
        "atlas-api": "inspection unavailable",
    }


def test_inventory_failure_degrades_governance() -> None:
    class FailureProvider(GovernedProvider):
        def containers(self):
            raise RuntimeError("inventory unavailable")

    governance = finding(
        governed_collector(
            FailureProvider()
        ).collect(),
        "docker.governance",
    )

    assert governance.status is OperationsStatus.UNKNOWN


@pytest.mark.parametrize(
    "rule",
    (
        DockerGovernanceRule(
            container_name="atlas-api",
            memory_limit_bytes=1,
            cpu_limit=1.0,
            pids_limit=1,
        ),
        "invalid",
    ),
)
def test_collector_validates_governance_policy_children(
    rule: object,
) -> None:
    if isinstance(rule, DockerGovernanceRule):
        policy = (
            rule,
            rule,
        )
    else:
        policy = (rule,)

    with pytest.raises(ValueError):
        DockerCollector(
            provider=FakeDockerOperationsProvider(),
            governance_policy=policy,  # type: ignore[arg-type]
        )


def test_default_governance_policy_is_exported() -> None:
    from atlas.operations import collectors

    assert (
        collectors.DEFAULT_DOCKER_GOVERNANCE_POLICY
        is DEFAULT_DOCKER_GOVERNANCE_POLICY
    )
    assert collectors.DockerGovernanceRule is DockerGovernanceRule
