"""Normalized read-only Docker provider for Atlas Operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Any, Protocol

from .docker import (
    DockerCollectorError,
    DockerCommandRunner,
)


class DockerProviderContractError(DockerCollectorError):
    """Raised when Docker returns an invalid provider contract."""


class DockerRunner(Protocol):
    """Read-only command-runner contract consumed by DockerProvider."""

    def version(self) -> dict[str, Any]:
        """Return Docker version information."""

    def info(self) -> dict[str, Any]:
        """Return Docker daemon information."""

    def ps(self) -> list[dict[str, Any]]:
        """Return Docker container summaries."""

    def inspect(self, container: str) -> dict[str, Any]:
        """Return Docker inspection data for one container."""


@dataclass(frozen=True, slots=True)
class DockerMountSnapshot:
    """Normalized Docker mount attachment."""

    mount_type: str
    source: str
    destination: str
    read_only: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "mount_type",
            _required_text(
                self.mount_type,
                "mount_type",
            ).lower(),
        )
        object.__setattr__(
            self,
            "source",
            _required_text(
                self.source,
                "source",
            ),
        )
        object.__setattr__(
            self,
            "destination",
            _required_text(
                self.destination,
                "destination",
            ),
        )
        object.__setattr__(
            self,
            "read_only",
            _required_boolean(
                self.read_only,
                "read_only",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.mount_type,
            "source": self.source,
            "destination": self.destination,
            "read_only": self.read_only,
        }


@dataclass(frozen=True, slots=True)
class DockerNetworkSnapshot:
    """Normalized Docker network attachment."""

    name: str
    network_id: str
    ip_address: str | None
    gateway: str | None
    aliases: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "name",
            _required_text(
                self.name,
                "name",
            ),
        )
        object.__setattr__(
            self,
            "network_id",
            _required_text(
                self.network_id,
                "network_id",
            ),
        )
        object.__setattr__(
            self,
            "ip_address",
            _optional_text(
                self.ip_address,
                "ip_address",
            ),
        )
        object.__setattr__(
            self,
            "gateway",
            _optional_text(
                self.gateway,
                "gateway",
            ),
        )

        aliases = tuple(
            sorted(
                {
                    _required_text(
                        alias,
                        "aliases[]",
                    )
                    for alias in self.aliases
                },
                key=str.casefold,
            )
        )

        object.__setattr__(
            self,
            "aliases",
            aliases,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "network_id": self.network_id,
            "ip_address": self.ip_address,
            "gateway": self.gateway,
            "aliases": list(self.aliases),
        }


@dataclass(frozen=True, slots=True)
class DockerPortSnapshot:
    """Normalized Docker container-port publication."""

    container_port: int
    protocol: str
    host_ip: str | None
    host_port: int | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "container_port",
            _positive_integer(
                self.container_port,
                "container_port",
            ),
        )
        object.__setattr__(
            self,
            "protocol",
            _required_text(
                self.protocol,
                "protocol",
            ).lower(),
        )
        object.__setattr__(
            self,
            "host_ip",
            _optional_text(
                self.host_ip,
                "host_ip",
            ),
        )

        if self.host_port is not None:
            object.__setattr__(
                self,
                "host_port",
                _positive_integer(
                    self.host_port,
                    "host_port",
                ),
            )

    @property
    def published(self) -> bool:
        return self.host_port is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "container_port": self.container_port,
            "protocol": self.protocol,
            "host_ip": self.host_ip,
            "host_port": self.host_port,
            "published": self.published,
        }


@dataclass(frozen=True, slots=True)
class DockerContainerSnapshot:
    """Normalized runtime snapshot for one Docker container."""

    container_id: str
    name: str
    image: str
    image_id: str
    state: str
    health: str | None
    running: bool
    restarting: bool
    oom_killed: bool
    exit_code: int
    restart_count: int
    restart_policy: str
    restart_maximum_retry_count: int
    created_at: str
    started_at: str | None
    finished_at: str | None
    memory_limit_bytes: int
    nano_cpus: int
    cpu_limit: float | None
    pids_limit: int | None
    mounts: tuple[DockerMountSnapshot, ...]
    networks: tuple[DockerNetworkSnapshot, ...]
    ports: tuple[DockerPortSnapshot, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "container_id",
            "name",
            "image",
            "image_id",
            "state",
            "restart_policy",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        health = _optional_text(
            self.health,
            "health",
        )

        object.__setattr__(
            self,
            "health",
            health.lower() if health else None,
        )
        object.__setattr__(
            self,
            "state",
            self.state.lower(),
        )
        object.__setattr__(
            self,
            "restart_policy",
            self.restart_policy.lower(),
        )

        for field_name in (
            "running",
            "restarting",
            "oom_killed",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_boolean(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        object.__setattr__(
            self,
            "exit_code",
            _non_negative_integer(
                self.exit_code,
                "exit_code",
            ),
        )
        object.__setattr__(
            self,
            "restart_count",
            _non_negative_integer(
                self.restart_count,
                "restart_count",
            ),
        )
        object.__setattr__(
            self,
            "restart_maximum_retry_count",
            _non_negative_integer(
                self.restart_maximum_retry_count,
                "restart_maximum_retry_count",
            ),
        )
        object.__setattr__(
            self,
            "created_at",
            _required_timestamp(
                self.created_at,
                "created_at",
            ),
        )
        object.__setattr__(
            self,
            "started_at",
            _optional_timestamp(
                self.started_at,
                "started_at",
            ),
        )
        object.__setattr__(
            self,
            "finished_at",
            _optional_timestamp(
                self.finished_at,
                "finished_at",
            ),
        )
        object.__setattr__(
            self,
            "memory_limit_bytes",
            _non_negative_integer(
                self.memory_limit_bytes,
                "memory_limit_bytes",
            ),
        )
        object.__setattr__(
            self,
            "nano_cpus",
            _non_negative_integer(
                self.nano_cpus,
                "nano_cpus",
            ),
        )
        object.__setattr__(
            self,
            "cpu_limit",
            _optional_positive_number(
                self.cpu_limit,
                "cpu_limit",
            ),
        )
        object.__setattr__(
            self,
            "pids_limit",
            _optional_positive_integer(
                self.pids_limit,
                "pids_limit",
            ),
        )

        expected_cpu_limit = (
            self.nano_cpus / 1_000_000_000
            if self.nano_cpus
            else None
        )

        if self.cpu_limit != expected_cpu_limit:
            raise DockerProviderContractError(
                "cpu_limit must match nano_cpus",
            )

        mounts = _validated_children(
            self.mounts,
            DockerMountSnapshot,
            "mounts",
        )
        networks = _validated_children(
            self.networks,
            DockerNetworkSnapshot,
            "networks",
        )
        ports = _validated_children(
            self.ports,
            DockerPortSnapshot,
            "ports",
        )

        mount_destinations = [
            mount.destination
            for mount in mounts
        ]

        if len(mount_destinations) != len(
            set(mount_destinations)
        ):
            raise DockerProviderContractError(
                "mount destinations must be unique",
            )

        network_names = [
            network.name
            for network in networks
        ]

        if len(network_names) != len(
            set(network_names)
        ):
            raise DockerProviderContractError(
                "network names must be unique",
            )

        port_keys = [
            (
                port.container_port,
                port.protocol,
                port.host_ip,
                port.host_port,
            )
            for port in ports
        ]

        if len(port_keys) != len(set(port_keys)):
            raise DockerProviderContractError(
                "port mappings must be unique",
            )

        object.__setattr__(
            self,
            "mounts",
            tuple(
                sorted(
                    mounts,
                    key=lambda mount: (
                        mount.destination,
                        mount.source,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "networks",
            tuple(
                sorted(
                    networks,
                    key=lambda network: (
                        network.name.casefold(),
                        network.network_id,
                    ),
                )
            ),
        )
        object.__setattr__(
            self,
            "ports",
            tuple(
                sorted(
                    ports,
                    key=lambda port: (
                        port.container_port,
                        port.protocol,
                        port.host_ip or "",
                        port.host_port or 0,
                    ),
                )
            ),
        )

        if self.restarting and not self.running:
            raise DockerProviderContractError(
                "restarting containers must also be running",
            )

        if self.running and self.started_at is None:
            raise DockerProviderContractError(
                "running containers require started_at",
            )

        if self.running and self.finished_at is not None:
            object.__setattr__(
                self,
                "finished_at",
                None,
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized runtime snapshot."""

        return {
            "container_id": self.container_id,
            "name": self.name,
            "image": self.image,
            "image_id": self.image_id,
            "state": self.state,
            "health": self.health,
            "running": self.running,
            "restarting": self.restarting,
            "oom_killed": self.oom_killed,
            "exit_code": self.exit_code,
            "restart_count": self.restart_count,
            "restart_policy": self.restart_policy,
            "restart_maximum_retry_count": (
                self.restart_maximum_retry_count
            ),
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "resources": {
                "memory_limit_bytes": self.memory_limit_bytes,
                "nano_cpus": self.nano_cpus,
                "cpu_limit": self.cpu_limit,
                "pids_limit": self.pids_limit,
            },
            "mounts": [
                mount.to_dict()
                for mount in self.mounts
            ],
            "networks": [
                network.to_dict()
                for network in self.networks
            ],
            "ports": [
                port.to_dict()
                for port in self.ports
            ],
        }


@dataclass(frozen=True, slots=True)
class DockerContainerSummary:
    """Normalized summary for one Docker container."""

    container_id: str
    name: str
    image: str
    state: str
    status: str

    def __post_init__(self) -> None:
        for field_name in (
            "container_id",
            "name",
            "image",
            "state",
            "status",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(
                    getattr(self, field_name),
                    field_name,
                ),
            )

    def to_dict(self) -> dict[str, str]:
        """Serialize the normalized container summary."""

        return {
            "container_id": self.container_id,
            "name": self.name,
            "image": self.image,
            "state": self.state,
            "status": self.status,
        }


@dataclass(frozen=True, slots=True)
class DockerEngineSnapshot:
    """Normalized Docker Engine and daemon state."""

    client_version: str
    server_version: str
    daemon_name: str
    operating_system: str
    architecture: str
    storage_driver: str
    cpu_count: int
    memory_bytes: int
    containers_total: int
    containers_running: int
    containers_paused: int
    containers_stopped: int

    def __post_init__(self) -> None:
        for field_name in (
            "client_version",
            "server_version",
            "daemon_name",
            "operating_system",
            "architecture",
            "storage_driver",
        ):
            object.__setattr__(
                self,
                field_name,
                _required_text(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        for field_name in (
            "cpu_count",
            "memory_bytes",
            "containers_total",
            "containers_running",
            "containers_paused",
            "containers_stopped",
        ):
            object.__setattr__(
                self,
                field_name,
                _non_negative_integer(
                    getattr(self, field_name),
                    field_name,
                ),
            )

        if self.cpu_count == 0:
            raise DockerProviderContractError(
                "cpu_count must be greater than zero",
            )

        if self.memory_bytes == 0:
            raise DockerProviderContractError(
                "memory_bytes must be greater than zero",
            )

        state_total = (
            self.containers_running
            + self.containers_paused
            + self.containers_stopped
        )

        if state_total != self.containers_total:
            raise DockerProviderContractError(
                "container state counts must equal containers_total",
            )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized Docker engine snapshot."""

        return {
            "client_version": self.client_version,
            "server_version": self.server_version,
            "daemon_name": self.daemon_name,
            "operating_system": self.operating_system,
            "architecture": self.architecture,
            "storage_driver": self.storage_driver,
            "cpu_count": self.cpu_count,
            "memory_bytes": self.memory_bytes,
            "containers": {
                "total": self.containers_total,
                "running": self.containers_running,
                "paused": self.containers_paused,
                "stopped": self.containers_stopped,
            },
        }


@dataclass(frozen=True, slots=True)
class DockerProvider:
    """Normalize Docker CLI data into provider-neutral snapshots."""

    runner: DockerRunner = DockerCommandRunner()

    def container(
        self,
        identity: str,
    ) -> DockerContainerSnapshot:
        """Return one normalized Docker container snapshot."""

        payload = self.runner.inspect(identity)

        if not isinstance(payload, dict):
            raise DockerProviderContractError(
                "runner.inspect() must return an object",
            )

        state = _required_mapping(
            payload.get("State"),
            "inspect.State",
        )
        config = _required_mapping(
            payload.get("Config"),
            "inspect.Config",
        )
        host_config = _required_mapping(
            payload.get("HostConfig"),
            "inspect.HostConfig",
        )

        health_payload = state.get("Health")

        if health_payload is None:
            health = None
        else:
            health_object = _required_mapping(
                health_payload,
                "inspect.State.Health",
            )
            health = _required_text(
                health_object.get("Status"),
                "inspect.State.Health.Status",
            )

        restart_policy = _required_mapping(
            host_config.get("RestartPolicy"),
            "inspect.HostConfig.RestartPolicy",
        )

        mounts = _normalize_mounts(
            payload.get("Mounts", []),
        )
        networks = _normalize_networks(
            payload.get("NetworkSettings", {}),
        )
        ports = _normalize_ports(
            config.get("ExposedPorts"),
            payload.get("NetworkSettings", {}),
        )

        name = _required_text(
            payload.get("Name"),
            "inspect.Name",
        ).removeprefix("/")

        return DockerContainerSnapshot(
            container_id=_required_text(
                payload.get("Id"),
                "inspect.Id",
            ),
            name=_required_text(
                name,
                "inspect.Name",
            ),
            image=_required_text(
                config.get("Image"),
                "inspect.Config.Image",
            ),
            image_id=_required_text(
                payload.get("Image"),
                "inspect.Image",
            ),
            state=_required_text(
                state.get("Status"),
                "inspect.State.Status",
            ),
            health=health,
            running=_required_boolean(
                state.get("Running"),
                "inspect.State.Running",
            ),
            restarting=_required_boolean(
                state.get("Restarting"),
                "inspect.State.Restarting",
            ),
            oom_killed=_required_boolean(
                state.get("OOMKilled"),
                "inspect.State.OOMKilled",
            ),
            exit_code=_non_negative_integer(
                state.get("ExitCode"),
                "inspect.State.ExitCode",
            ),
            restart_count=_non_negative_integer(
                payload.get("RestartCount"),
                "inspect.RestartCount",
            ),
            restart_policy=_required_text(
                restart_policy.get("Name"),
                "inspect.HostConfig.RestartPolicy.Name",
            ),
            restart_maximum_retry_count=_non_negative_integer(
                restart_policy.get("MaximumRetryCount", 0),
                (
                    "inspect.HostConfig.RestartPolicy."
                    "MaximumRetryCount"
                ),
            ),
            created_at=_required_timestamp(
                payload.get("Created"),
                "inspect.Created",
            ),
            started_at=_optional_timestamp(
                state.get("StartedAt"),
                "inspect.State.StartedAt",
            ),
            finished_at=_optional_timestamp(
                state.get("FinishedAt"),
                "inspect.State.FinishedAt",
            ),
            memory_limit_bytes=_non_negative_integer(
                host_config.get("Memory", 0),
                "inspect.HostConfig.Memory",
            ),
            nano_cpus=_non_negative_integer(
                host_config.get("NanoCpus", 0),
                "inspect.HostConfig.NanoCpus",
            ),
            cpu_limit=(
                host_config.get("NanoCpus", 0)
                / 1_000_000_000
                if host_config.get("NanoCpus", 0)
                else None
            ),
            pids_limit=_optional_positive_integer(
                host_config.get("PidsLimit"),
                "inspect.HostConfig.PidsLimit",
            ),
            mounts=mounts,
            networks=networks,
            ports=ports,
        )

    def containers(self) -> tuple[DockerContainerSummary, ...]:
        """Return deterministic normalized container summaries."""

        records = self.runner.ps()

        if not isinstance(records, list):
            raise DockerProviderContractError(
                "runner.ps() must return a list",
            )

        summaries: list[DockerContainerSummary] = []

        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise DockerProviderContractError(
                    f"runner.ps()[{index}] must be an object",
                )

            summaries.append(
                DockerContainerSummary(
                    container_id=_required_text(
                        record.get("ID"),
                        f"runner.ps()[{index}].ID",
                    ),
                    name=_required_text(
                        record.get("Names"),
                        f"runner.ps()[{index}].Names",
                    ),
                    image=_required_text(
                        record.get("Image"),
                        f"runner.ps()[{index}].Image",
                    ),
                    state=_required_text(
                        record.get("State"),
                        f"runner.ps()[{index}].State",
                    ).lower(),
                    status=_required_text(
                        record.get("Status"),
                        f"runner.ps()[{index}].Status",
                    ),
                )
            )

        container_ids = [
            summary.container_id
            for summary in summaries
        ]
        names = [
            summary.name
            for summary in summaries
        ]

        if len(container_ids) != len(set(container_ids)):
            raise DockerProviderContractError(
                "container summaries must have unique IDs",
            )

        if len(names) != len(set(names)):
            raise DockerProviderContractError(
                "container summaries must have unique names",
            )

        return tuple(
            sorted(
                summaries,
                key=lambda summary: (
                    summary.name.casefold(),
                    summary.container_id,
                ),
            )
        )

    def engine(self) -> DockerEngineSnapshot:
        """Return one normalized Docker Engine snapshot."""

        version = self.runner.version()
        info = self.runner.info()

        client = _required_mapping(
            version.get("Client"),
            "version.Client",
        )
        server = _required_mapping(
            version.get("Server"),
            "version.Server",
        )

        return DockerEngineSnapshot(
            client_version=_required_text(
                client.get("Version"),
                "version.Client.Version",
            ),
            server_version=_required_text(
                server.get("Version"),
                "version.Server.Version",
            ),
            daemon_name=_required_text(
                info.get("Name"),
                "info.Name",
            ),
            operating_system=_required_text(
                info.get("OperatingSystem"),
                "info.OperatingSystem",
            ),
            architecture=_required_text(
                info.get("Architecture"),
                "info.Architecture",
            ),
            storage_driver=_required_text(
                info.get("Driver"),
                "info.Driver",
            ),
            cpu_count=_non_negative_integer(
                info.get("NCPU"),
                "info.NCPU",
            ),
            memory_bytes=_non_negative_integer(
                info.get("MemTotal"),
                "info.MemTotal",
            ),
            containers_total=_non_negative_integer(
                info.get("Containers"),
                "info.Containers",
            ),
            containers_running=_non_negative_integer(
                info.get("ContainersRunning"),
                "info.ContainersRunning",
            ),
            containers_paused=_non_negative_integer(
                info.get("ContainersPaused"),
                "info.ContainersPaused",
            ),
            containers_stopped=_non_negative_integer(
                info.get("ContainersStopped"),
                "info.ContainersStopped",
            ),
        )


def _required_mapping(
    value: object,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DockerProviderContractError(
            f"{field_name} must be an object",
        )

    return value


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise DockerProviderContractError(
            f"{field_name} must be text",
        )

    normalized = value.strip()

    if not normalized:
        raise DockerProviderContractError(
            f"{field_name} is required",
        )

    return normalized


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_text(
        value,
        field_name,
    )


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    normalized = _optional_timestamp(
        value,
        field_name,
    )

    if normalized is None:
        raise DockerProviderContractError(
            f"{field_name} is required",
        )

    return normalized


def _optional_timestamp(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise DockerProviderContractError(
            f"{field_name} must be timestamp text or null",
        )

    normalized = value.strip()

    if not normalized:
        raise DockerProviderContractError(
            f"{field_name} must not be blank",
        )

    if normalized.startswith("0001-01-01T00:00:00"):
        return None

    candidate = (
        normalized[:-1] + "+00:00"
        if normalized.endswith("Z")
        else normalized
    )

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise DockerProviderContractError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise DockerProviderContractError(
            f"{field_name} must include a timezone",
        )

    utc = parsed.astimezone(timezone.utc)

    return utc.isoformat().replace("+00:00", "Z")


def _optional_positive_number(
    value: object,
    field_name: str,
) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool) or not isinstance(
        value,
        (int, float),
    ):
        raise DockerProviderContractError(
            f"{field_name} must be a number or null",
        )

    normalized = float(value)

    if not math.isfinite(normalized) or normalized <= 0:
        raise DockerProviderContractError(
            f"{field_name} must be finite and greater than zero",
        )

    return normalized


def _optional_positive_integer(
    value: object,
    field_name: str,
) -> int | None:
    if value in (None, 0):
        return None

    if isinstance(value, bool) or not isinstance(value, int):
        raise DockerProviderContractError(
            f"{field_name} must be an integer or null",
        )

    if value < 0:
        raise DockerProviderContractError(
            f"{field_name} must be greater than zero",
        )

    return value


def _positive_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DockerProviderContractError(
            f"{field_name} must be an integer",
        )

    if value <= 0:
        raise DockerProviderContractError(
            f"{field_name} must be greater than zero",
        )

    return value


def _validated_children(
    value: object,
    child_type: type,
    field_name: str,
) -> tuple[Any, ...]:
    if not isinstance(value, tuple):
        raise DockerProviderContractError(
            f"{field_name} must be a tuple",
        )

    for index, child in enumerate(value):
        if not isinstance(child, child_type):
            raise DockerProviderContractError(
                f"{field_name}[{index}] must be "
                f"{child_type.__name__}",
            )

    return value


def _required_boolean(
    value: object,
    field_name: str,
) -> bool:
    if not isinstance(value, bool):
        raise DockerProviderContractError(
            f"{field_name} must be a boolean",
        )

    return value


def _non_negative_integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DockerProviderContractError(
            f"{field_name} must be an integer",
        )

    if value < 0:
        raise DockerProviderContractError(
            f"{field_name} must not be negative",
        )

    return value


def _normalize_mounts(
    value: object,
) -> tuple[DockerMountSnapshot, ...]:
    if not isinstance(value, list):
        raise DockerProviderContractError(
            "inspect.Mounts must be a list",
        )

    results: list[DockerMountSnapshot] = []

    for index, item in enumerate(value):
        mapping = _required_mapping(
            item,
            f"inspect.Mounts[{index}]",
        )

        results.append(
            DockerMountSnapshot(
                mount_type=_required_text(
                    mapping.get("Type"),
                    f"inspect.Mounts[{index}].Type",
                ),
                source=_required_text(
                    mapping.get("Source"),
                    f"inspect.Mounts[{index}].Source",
                ),
                destination=_required_text(
                    mapping.get("Destination"),
                    (
                        f"inspect.Mounts[{index}]."
                        "Destination"
                    ),
                ),
                read_only=not _required_boolean(
                    mapping.get("RW"),
                    f"inspect.Mounts[{index}].RW",
                ),
            )
        )

    return tuple(results)


def _normalize_networks(
    value: object,
) -> tuple[DockerNetworkSnapshot, ...]:
    settings = _required_mapping(
        value,
        "inspect.NetworkSettings",
    )
    networks = _required_mapping(
        settings.get("Networks", {}),
        "inspect.NetworkSettings.Networks",
    )

    results: list[DockerNetworkSnapshot] = []

    for name, raw_network in networks.items():
        network = _required_mapping(
            raw_network,
            (
                "inspect.NetworkSettings.Networks."
                f"{name}"
            ),
        )

        aliases_value = network.get("Aliases") or []

        if not isinstance(aliases_value, list):
            raise DockerProviderContractError(
                "network aliases must be a list",
            )

        results.append(
            DockerNetworkSnapshot(
                name=_required_text(
                    name,
                    "network name",
                ),
                network_id=_required_text(
                    network.get("NetworkID"),
                    f"network {name} ID",
                ),
                ip_address=_optional_text(
                    network.get("IPAddress") or None,
                    f"network {name} IP address",
                ),
                gateway=_optional_text(
                    network.get("Gateway") or None,
                    f"network {name} gateway",
                ),
                aliases=tuple(aliases_value),
            )
        )

    return tuple(results)


def _normalize_ports(
    exposed_value: object,
    network_settings_value: object,
) -> tuple[DockerPortSnapshot, ...]:
    if exposed_value is None:
        exposed: dict[str, Any] = {}
    else:
        exposed = _required_mapping(
            exposed_value,
            "inspect.Config.ExposedPorts",
        )

    network_settings = _required_mapping(
        network_settings_value,
        "inspect.NetworkSettings",
    )
    published = _required_mapping(
        network_settings.get("Ports", {}),
        "inspect.NetworkSettings.Ports",
    )

    port_keys = set(exposed) | set(published)
    results: list[DockerPortSnapshot] = []

    for port_key in port_keys:
        port_text, separator, protocol = port_key.partition("/")

        if not separator:
            raise DockerProviderContractError(
                f"invalid Docker port key: {port_key}",
            )

        try:
            container_port = int(port_text)
        except ValueError as exc:
            raise DockerProviderContractError(
                f"invalid Docker container port: {port_text}",
            ) from exc

        bindings = published.get(port_key)

        if bindings is None:
            results.append(
                DockerPortSnapshot(
                    container_port=container_port,
                    protocol=protocol,
                    host_ip=None,
                    host_port=None,
                )
            )
            continue

        if not isinstance(bindings, list):
            raise DockerProviderContractError(
                f"port bindings for {port_key} must be a list",
            )

        for index, binding_value in enumerate(bindings):
            binding = _required_mapping(
                binding_value,
                f"port {port_key}[{index}]",
            )

            host_port_text = _required_text(
                binding.get("HostPort"),
                f"port {port_key}[{index}].HostPort",
            )

            try:
                host_port = int(host_port_text)
            except ValueError as exc:
                raise DockerProviderContractError(
                    f"invalid host port: {host_port_text}",
                ) from exc

            results.append(
                DockerPortSnapshot(
                    container_port=container_port,
                    protocol=protocol,
                    host_ip=_optional_text(
                        binding.get("HostIp") or None,
                        f"port {port_key}[{index}].HostIp",
                    ),
                    host_port=host_port,
                )
            )

    return tuple(results)
