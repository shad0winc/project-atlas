"""Tests for the normalized Atlas Docker provider."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.operations.collectors import (
    DockerContainerSnapshot,
    DockerContainerSummary,
    DockerEngineSnapshot,
    DockerMountSnapshot,
    DockerNetworkSnapshot,
    DockerPortSnapshot,
    DockerProvider,
    DockerProviderContractError,
)


class FakeDockerRunner:
    """Deterministic Docker runner used by provider tests."""

    def version(self) -> dict[str, object]:
        return {
            "Client": {
                "Version": " 28.3.3 ",
            },
            "Server": {
                "Version": " 28.3.3 ",
            },
        }

    def info(self) -> dict[str, object]:
        return {
            "Name": " docker ",
            "OperatingSystem": " Debian GNU/Linux 13 ",
            "Architecture": " x86_64 ",
            "Driver": " overlay2 ",
            "NCPU": 8,
            "MemTotal": 24 * 1024**3,
            "Containers": 30,
            "ContainersRunning": 28,
            "ContainersPaused": 0,
            "ContainersStopped": 2,
        }

    def inspect(
        self,
        container: str,
    ) -> dict[str, object]:
        return {
            "Id": "abc123",
            "Name": "/atlas-api",
            "Image": "sha256:image123",
            "Created": "2026-08-03T15:00:00-04:00",
            "RestartCount": 2,
            "State": {
                "Status": "running",
                "Running": True,
                "Restarting": False,
                "OOMKilled": False,
                "ExitCode": 0,
                "StartedAt": "2026-08-03T19:01:00Z",
                "FinishedAt": "0001-01-01T00:00:00Z",
                "Health": {
                    "Status": "healthy",
                },
            },
            "Config": {
                "Image": "atlas-api:local",
                "ExposedPorts": {
                    "8000/tcp": {},
                },
            },
            "Mounts": [
                {
                    "Type": "bind",
                    "Source": "/opt/project-atlas",
                    "Destination": "/app",
                    "RW": False,
                },
            ],
            "NetworkSettings": {
                "Networks": {
                    "atlas-ingress": {
                        "NetworkID": "network123",
                        "IPAddress": "172.20.0.3",
                        "Gateway": "172.20.0.1",
                        "Aliases": [
                            "api",
                            "atlas-api",
                        ],
                    },
                },
                "Ports": {
                    "8000/tcp": None,
                },
            },
            "HostConfig": {
                "Memory": 1073741824,
                "NanoCpus": 2000000000,
                "PidsLimit": 512,
                "RestartPolicy": {
                    "Name": "unless-stopped",
                    "MaximumRetryCount": 0,
                },
            },
        }

    def ps(self) -> list[dict[str, object]]:
        return [
            {
                "ID": "bbb222",
                "Names": " jellyfin ",
                "Image": " jellyfin/jellyfin:latest ",
                "State": " RUNNING ",
                "Status": " Up 2 hours ",
            },
            {
                "ID": "aaa111",
                "Names": " atlas-api ",
                "Image": " atlas-api:local ",
                "State": " running ",
                "Status": " Up 10 minutes (healthy) ",
            },
        ]


def provider(
    runner: object | None = None,
) -> DockerProvider:
    return DockerProvider(
        runner=(
            runner
            if runner is not None
            else FakeDockerRunner()
        ),
    )


def test_engine_snapshot_normalizes_values() -> None:
    result = provider().engine()

    assert result.client_version == "28.3.3"
    assert result.server_version == "28.3.3"
    assert result.daemon_name == "docker"
    assert result.operating_system == "Debian GNU/Linux 13"
    assert result.architecture == "x86_64"
    assert result.storage_driver == "overlay2"
    assert result.cpu_count == 8
    assert result.memory_bytes == 24 * 1024**3
    assert result.containers_total == 30
    assert result.containers_running == 28
    assert result.containers_paused == 0
    assert result.containers_stopped == 2


def test_engine_snapshot_serialization() -> None:
    result = provider().engine()

    assert result.to_dict() == {
        "client_version": "28.3.3",
        "server_version": "28.3.3",
        "daemon_name": "docker",
        "operating_system": "Debian GNU/Linux 13",
        "architecture": "x86_64",
        "storage_driver": "overlay2",
        "cpu_count": 8,
        "memory_bytes": 24 * 1024**3,
        "containers": {
            "total": 30,
            "running": 28,
            "paused": 0,
            "stopped": 2,
        },
    }


def test_engine_snapshot_is_immutable() -> None:
    result = provider().engine()

    with pytest.raises(FrozenInstanceError):
        result.cpu_count = 16  # type: ignore[misc]


def test_provider_calls_version_and_info_once() -> None:
    calls: list[str] = []

    class RecordingRunner(FakeDockerRunner):
        def version(self):
            calls.append("version")
            return super().version()

        def info(self):
            calls.append("info")
            return super().info()

    provider(RecordingRunner()).engine()

    assert calls == [
        "version",
        "info",
    ]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("NCPU", 0, "cpu_count must be greater than zero"),
        (
            "MemTotal",
            0,
            "memory_bytes must be greater than zero",
        ),
        ("Containers", -1, "info.Containers must not be negative"),
        ("ContainersRunning", True, "must be an integer"),
    ),
)
def test_provider_rejects_invalid_integer_contracts(
    field: str,
    value: object,
    message: str,
) -> None:
    class InvalidRunner(FakeDockerRunner):
        def info(self):
            result = super().info()
            result[field] = value
            return result

    with pytest.raises(
        DockerProviderContractError,
        match=message,
    ):
        provider(InvalidRunner()).engine()


@pytest.mark.parametrize(
    ("section", "value", "message"),
    (
        ("Client", None, "version.Client must be an object"),
        ("Server", [], "version.Server must be an object"),
    ),
)
def test_provider_rejects_invalid_version_sections(
    section: str,
    value: object,
    message: str,
) -> None:
    class InvalidRunner(FakeDockerRunner):
        def version(self):
            result = super().version()
            result[section] = value
            return result

    with pytest.raises(
        DockerProviderContractError,
        match=message,
    ):
        provider(InvalidRunner()).engine()


def test_provider_rejects_inconsistent_container_counts() -> None:
    class InvalidRunner(FakeDockerRunner):
        def info(self):
            result = super().info()
            result["ContainersStopped"] = 3
            return result

    with pytest.raises(
        DockerProviderContractError,
        match=(
            "container state counts must equal containers_total"
        ),
    ):
        provider(InvalidRunner()).engine()


def test_provider_preserves_runner_errors() -> None:
    from atlas.operations.collectors import DockerCollectorError

    class FailingRunner(FakeDockerRunner):
        def version(self):
            raise DockerCollectorError("Docker unavailable")

    with pytest.raises(
        DockerCollectorError,
        match="Docker unavailable",
    ):
        provider(FailingRunner()).engine()


def test_public_docker_provider_exports() -> None:
    from atlas.operations import collectors

    assert collectors.DockerProvider is DockerProvider
    assert collectors.DockerEngineSnapshot is DockerEngineSnapshot
    assert (
        collectors.DockerProviderContractError
        is DockerProviderContractError
    )
    assert collectors.DockerRunner is not None


def test_container_summary_normalizes_values() -> None:
    result = DockerContainerSummary(
        container_id=" abc123 ",
        name=" atlas-api ",
        image=" atlas-api:local ",
        state=" RUNNING ",
        status=" Up 10 minutes (healthy) ",
    )

    assert result.container_id == "abc123"
    assert result.name == "atlas-api"
    assert result.image == "atlas-api:local"
    assert result.state == "RUNNING"
    assert result.status == "Up 10 minutes (healthy)"


def test_container_summary_serialization() -> None:
    result = DockerContainerSummary(
        container_id="abc123",
        name="atlas-api",
        image="atlas-api:local",
        state="running",
        status="Up 10 minutes (healthy)",
    )

    assert result.to_dict() == {
        "container_id": "abc123",
        "name": "atlas-api",
        "image": "atlas-api:local",
        "state": "running",
        "status": "Up 10 minutes (healthy)",
    }


def test_container_summary_is_immutable() -> None:
    result = DockerContainerSummary(
        container_id="abc123",
        name="atlas-api",
        image="atlas-api:local",
        state="running",
        status="Up 10 minutes",
    )

    with pytest.raises(FrozenInstanceError):
        result.name = "changed"  # type: ignore[misc]


def test_provider_normalizes_and_orders_containers() -> None:
    result = provider().containers()

    assert tuple(
        container.name
        for container in result
    ) == (
        "atlas-api",
        "jellyfin",
    )

    assert result[0].to_dict() == {
        "container_id": "aaa111",
        "name": "atlas-api",
        "image": "atlas-api:local",
        "state": "running",
        "status": "Up 10 minutes (healthy)",
    }

    assert result[1].state == "running"


def test_provider_returns_empty_container_inventory() -> None:
    class EmptyRunner(FakeDockerRunner):
        def ps(self):
            return []

    assert provider(EmptyRunner()).containers() == ()


@pytest.mark.parametrize(
    ("records", "message"),
    (
        (
            None,
            r"runner\.ps\(\) must return a list",
        ),
        (
            ["invalid"],
            r"runner\.ps\(\)\[0\] must be an object",
        ),
        (
            [
                {
                    "ID": "",
                    "Names": "atlas-api",
                    "Image": "atlas-api:local",
                    "State": "running",
                    "Status": "Up",
                }
            ],
            r"runner\.ps\(\)\[0\]\.ID is required",
        ),
    ),
)
def test_provider_rejects_invalid_container_records(
    records: object,
    message: str,
) -> None:
    class InvalidRunner(FakeDockerRunner):
        def ps(self):
            return records

    with pytest.raises(
        DockerProviderContractError,
        match=message,
    ):
        provider(InvalidRunner()).containers()


def test_provider_rejects_duplicate_container_ids() -> None:
    class DuplicateRunner(FakeDockerRunner):
        def ps(self):
            records = super().ps()
            records[1]["ID"] = records[0]["ID"]
            return records

    with pytest.raises(
        DockerProviderContractError,
        match="unique IDs",
    ):
        provider(DuplicateRunner()).containers()


def test_provider_rejects_duplicate_container_names() -> None:
    class DuplicateRunner(FakeDockerRunner):
        def ps(self):
            records = super().ps()
            records[1]["Names"] = records[0]["Names"]
            return records

    with pytest.raises(
        DockerProviderContractError,
        match="unique names",
    ):
        provider(DuplicateRunner()).containers()


def test_public_container_summary_export() -> None:
    from atlas.operations import collectors

    assert (
        collectors.DockerContainerSummary
        is DockerContainerSummary
    )


def test_container_snapshot_normalizes_runtime_state() -> None:
    result = provider().container("atlas-api")

    assert result.container_id == "abc123"
    assert result.name == "atlas-api"
    assert result.image == "atlas-api:local"
    assert result.image_id == "sha256:image123"
    assert result.state == "running"
    assert result.health == "healthy"
    assert result.running is True
    assert result.restarting is False
    assert result.oom_killed is False
    assert result.exit_code == 0
    assert result.restart_count == 2
    assert result.restart_policy == "unless-stopped"
    assert result.restart_maximum_retry_count == 0
    assert result.created_at == "2026-08-03T19:00:00Z"
    assert result.started_at == "2026-08-03T19:01:00Z"
    assert result.finished_at is None
    assert result.memory_limit_bytes == 1073741824
    assert result.nano_cpus == 2000000000
    assert result.cpu_limit == 2.0
    assert result.pids_limit == 512


def test_container_snapshot_serialization() -> None:
    result = provider().container("atlas-api")

    assert result.to_dict() == {
        "container_id": "abc123",
        "name": "atlas-api",
        "image": "atlas-api:local",
        "image_id": "sha256:image123",
        "state": "running",
        "health": "healthy",
        "running": True,
        "restarting": False,
        "oom_killed": False,
        "exit_code": 0,
        "restart_count": 2,
        "restart_policy": "unless-stopped",
        "restart_maximum_retry_count": 0,
        "created_at": "2026-08-03T19:00:00Z",
        "started_at": "2026-08-03T19:01:00Z",
        "finished_at": None,
        "resources": {
            "memory_limit_bytes": 1073741824,
            "nano_cpus": 2000000000,
            "cpu_limit": 2.0,
            "pids_limit": 512,
        },
        "mounts": [
            {
                "type": "bind",
                "source": "/opt/project-atlas",
                "destination": "/app",
                "read_only": True,
            },
        ],
        "networks": [
            {
                "name": "atlas-ingress",
                "network_id": "network123",
                "ip_address": "172.20.0.3",
                "gateway": "172.20.0.1",
                "aliases": [
                    "api",
                    "atlas-api",
                ],
            },
        ],
        "ports": [
            {
                "container_port": 8000,
                "protocol": "tcp",
                "host_ip": None,
                "host_port": None,
                "published": False,
            },
        ],
    }


def test_container_snapshot_is_immutable() -> None:
    result = provider().container("atlas-api")

    with pytest.raises(FrozenInstanceError):
        result.state = "exited"  # type: ignore[misc]


def test_container_snapshot_allows_missing_healthcheck() -> None:
    class NoHealthRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["State"]["Health"] = None
            return result

    result = provider(NoHealthRunner()).container(
        "jellyfin",
    )

    assert result.health is None


@pytest.mark.parametrize(
    ("field_path", "value", "message"),
    (
        (
            ("State", "Running"),
            "true",
            "inspect.State.Running must be a boolean",
        ),
        (
            ("State", "ExitCode"),
            -1,
            "inspect.State.ExitCode must not be negative",
        ),
        (
            ("RestartCount",),
            True,
            "inspect.RestartCount must be an integer",
        ),
        (
            ("Config", "Image"),
            "",
            "inspect.Config.Image is required",
        ),
    ),
)
def test_provider_rejects_invalid_snapshot_contracts(
    field_path: tuple[str, ...],
    value: object,
    message: str,
) -> None:
    class InvalidRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)

            target = result

            for key in field_path[:-1]:
                target = target[key]

            target[field_path[-1]] = value
            return result

    with pytest.raises(
        DockerProviderContractError,
        match=message,
    ):
        provider(InvalidRunner()).container("atlas-api")


def test_provider_rejects_restarting_nonrunning_container() -> None:
    class InvalidRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["State"]["Running"] = False
            result["State"]["Restarting"] = True
            return result

    with pytest.raises(
        DockerProviderContractError,
        match="restarting containers must also be running",
    ):
        provider(InvalidRunner()).container("atlas-api")


def test_provider_rejects_invalid_inspect_result() -> None:
    class InvalidRunner(FakeDockerRunner):
        def inspect(self, container: str):
            return []

    with pytest.raises(
        DockerProviderContractError,
        match=r"runner\.inspect\(\) must return an object",
    ):
        provider(InvalidRunner()).container("atlas-api")


def test_public_container_snapshot_export() -> None:
    from atlas.operations import collectors

    assert (
        collectors.DockerContainerSnapshot
        is DockerContainerSnapshot
    )


def test_container_snapshot_normalizes_timestamp_offsets() -> None:
    result = provider().container("atlas-api")

    assert result.created_at == "2026-08-03T19:00:00Z"
    assert result.started_at == "2026-08-03T19:01:00Z"
    assert result.finished_at is None


def test_container_snapshot_normalizes_unlimited_resources() -> None:
    class UnlimitedRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["HostConfig"]["Memory"] = 0
            result["HostConfig"]["NanoCpus"] = 0
            result["HostConfig"]["PidsLimit"] = 0
            return result

    snapshot = provider(UnlimitedRunner()).container(
        "jellyfin",
    )

    assert snapshot.memory_limit_bytes == 0
    assert snapshot.nano_cpus == 0
    assert snapshot.cpu_limit is None
    assert snapshot.pids_limit is None


def test_container_snapshot_accepts_stopped_timestamps() -> None:
    class StoppedRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["State"]["Status"] = "exited"
            result["State"]["Running"] = False
            result["State"]["Health"] = None
            result["State"]["FinishedAt"] = (
                "2026-08-03T20:00:00+00:00"
            )
            return result

    snapshot = provider(StoppedRunner()).container(
        "atlas-api",
    )

    assert snapshot.running is False
    assert snapshot.finished_at == "2026-08-03T20:00:00Z"


@pytest.mark.parametrize(
    ("field_path", "value", "message"),
    (
        (
            ("Created",),
            "2026-08-03T19:00:00",
            "inspect.Created must include a timezone",
        ),
        (
            ("State", "StartedAt"),
            "not-a-timestamp",
            "inspect.State.StartedAt must be an ISO-8601 timestamp",
        ),
        (
            ("HostConfig", "Memory"),
            -1,
            "inspect.HostConfig.Memory must not be negative",
        ),
        (
            ("HostConfig", "NanoCpus"),
            True,
            "inspect.HostConfig.NanoCpus must be an integer",
        ),
        (
            ("HostConfig", "PidsLimit"),
            -1,
            "inspect.HostConfig.PidsLimit must be greater than zero",
        ),
    ),
)
def test_provider_rejects_invalid_time_resource_contracts(
    field_path: tuple[str, ...],
    value: object,
    message: str,
) -> None:
    class InvalidRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            target = result

            for key in field_path[:-1]:
                target = target[key]

            target[field_path[-1]] = value
            return result

    with pytest.raises(
        DockerProviderContractError,
        match=message,
    ):
        provider(InvalidRunner()).container("atlas-api")


def test_running_snapshot_normalizes_finished_timestamp() -> None:
    class PreviousLifecycleRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["State"]["FinishedAt"] = (
                "2026-08-03T20:00:00Z"
            )
            return result

    snapshot = provider(
        PreviousLifecycleRunner(),
    ).container("atlas-api")

    assert snapshot.running is True
    assert snapshot.finished_at is None


def test_running_snapshot_requires_started_timestamp() -> None:
    class InvalidRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["State"]["StartedAt"] = (
                "0001-01-01T00:00:00Z"
            )
            return result

    with pytest.raises(
        DockerProviderContractError,
        match="running containers require started_at",
    ):
        provider(InvalidRunner()).container("atlas-api")


def test_container_snapshot_normalizes_topology() -> None:
    result = provider().container("atlas-api")

    assert result.mounts == (
        DockerMountSnapshot(
            mount_type="bind",
            source="/opt/project-atlas",
            destination="/app",
            read_only=True,
        ),
    )

    assert result.networks == (
        DockerNetworkSnapshot(
            name="atlas-ingress",
            network_id="network123",
            ip_address="172.20.0.3",
            gateway="172.20.0.1",
            aliases=(
                "api",
                "atlas-api",
            ),
        ),
    )

    assert result.ports == (
        DockerPortSnapshot(
            container_port=8000,
            protocol="tcp",
            host_ip=None,
            host_port=None,
        ),
    )


def test_container_snapshot_serializes_topology() -> None:
    payload = provider().container("atlas-api").to_dict()

    assert payload["mounts"] == [
        {
            "type": "bind",
            "source": "/opt/project-atlas",
            "destination": "/app",
            "read_only": True,
        }
    ]

    assert payload["networks"][0]["name"] == "atlas-ingress"

    assert payload["ports"] == [
        {
            "container_port": 8000,
            "protocol": "tcp",
            "host_ip": None,
            "host_port": None,
            "published": False,
        }
    ]


def test_port_snapshot_reports_published_state() -> None:
    result = DockerPortSnapshot(
        container_port=443,
        protocol="tcp",
        host_ip="0.0.0.0",
        host_port=443,
    )

    assert result.published is True


def test_network_aliases_are_sorted_and_unique() -> None:
    result = DockerNetworkSnapshot(
        name="atlas-ingress",
        network_id="network123",
        ip_address=None,
        gateway=None,
        aliases=(
            "portal",
            "api",
            "portal",
        ),
    )

    assert result.aliases == (
        "api",
        "portal",
    )


def test_topology_children_are_immutable() -> None:
    result = provider().container("atlas-api")

    with pytest.raises(FrozenInstanceError):
        result.mounts[0].source = "/changed"  # type: ignore[misc]


def test_provider_accepts_empty_topology() -> None:
    class EmptyTopologyRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["Mounts"] = []
            result["NetworkSettings"] = {
                "Networks": {},
                "Ports": {},
            }
            result["Config"]["ExposedPorts"] = None
            return result

    snapshot = provider(
        EmptyTopologyRunner(),
    ).container("atlas-api")

    assert snapshot.mounts == ()
    assert snapshot.networks == ()
    assert snapshot.ports == ()


def test_provider_rejects_duplicate_mount_destinations() -> None:
    class DuplicateRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            duplicate = dict(result["Mounts"][0])
            duplicate["Source"] = "/other"
            result["Mounts"].append(duplicate)
            return result

    with pytest.raises(
        DockerProviderContractError,
        match="mount destinations must be unique",
    ):
        provider(DuplicateRunner()).container("atlas-api")


def test_provider_rejects_invalid_mount_shape() -> None:
    class InvalidRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["Mounts"] = {}
            return result

    with pytest.raises(
        DockerProviderContractError,
        match="inspect.Mounts must be a list",
    ):
        provider(InvalidRunner()).container("atlas-api")


def test_provider_rejects_invalid_network_aliases() -> None:
    class InvalidRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["NetworkSettings"]["Networks"][
                "atlas-ingress"
            ]["Aliases"] = "atlas-api"
            return result

    with pytest.raises(
        DockerProviderContractError,
        match="network aliases must be a list",
    ):
        provider(InvalidRunner()).container("atlas-api")


def test_provider_rejects_invalid_port_key() -> None:
    class InvalidRunner(FakeDockerRunner):
        def inspect(self, container: str):
            result = super().inspect(container)
            result["Config"]["ExposedPorts"] = {
                "invalid": {},
            }
            result["NetworkSettings"]["Ports"] = {}
            return result

    with pytest.raises(
        DockerProviderContractError,
        match="invalid Docker port key",
    ):
        provider(InvalidRunner()).container("atlas-api")


def test_public_topology_exports() -> None:
    from atlas.operations import collectors

    assert collectors.DockerMountSnapshot is DockerMountSnapshot
    assert (
        collectors.DockerNetworkSnapshot
        is DockerNetworkSnapshot
    )
    assert collectors.DockerPortSnapshot is DockerPortSnapshot
