"""Docker runtime collector for Project Atlas Operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from atlas.operations.models import (
    OperationFinding,
    OperationsSection,
    OperationsSectionId,
    OperationsSeverity,
    OperationsStatus,
)

from .base import OperationsCollector
from .docker_provider import (
    DockerContainerSnapshot,
    DockerContainerSummary,
    DockerEngineSnapshot,
    DockerProvider,
)


@dataclass(frozen=True, slots=True)
class DockerGovernanceRule:
    """Expected resource ceilings for one Docker container."""

    container_name: str
    memory_limit_bytes: int
    cpu_limit: float
    pids_limit: int

    def __post_init__(self) -> None:
        name = self.container_name.strip()

        if not name:
            raise ValueError(
                "container_name is required",
            )

        if (
            isinstance(self.memory_limit_bytes, bool)
            or not isinstance(self.memory_limit_bytes, int)
            or self.memory_limit_bytes <= 0
        ):
            raise ValueError(
                "memory_limit_bytes must be a positive integer",
            )

        if (
            isinstance(self.cpu_limit, bool)
            or not isinstance(self.cpu_limit, (int, float))
            or float(self.cpu_limit) <= 0
        ):
            raise ValueError(
                "cpu_limit must be a positive number",
            )

        if (
            isinstance(self.pids_limit, bool)
            or not isinstance(self.pids_limit, int)
            or self.pids_limit <= 0
        ):
            raise ValueError(
                "pids_limit must be a positive integer",
            )

        object.__setattr__(
            self,
            "container_name",
            name,
        )
        object.__setattr__(
            self,
            "cpu_limit",
            float(self.cpu_limit),
        )

    def to_dict(self) -> dict[str, int | float | str]:
        """Serialize the expected governance contract."""

        return {
            "container_name": self.container_name,
            "memory_limit_bytes": self.memory_limit_bytes,
            "cpu_limit": self.cpu_limit,
            "pids_limit": self.pids_limit,
        }


DEFAULT_DOCKER_GOVERNANCE_POLICY = (
    DockerGovernanceRule(
        container_name="atlas-caddy",
        memory_limit_bytes=512 * 1024**2,
        cpu_limit=1.0,
        pids_limit=256,
    ),
    DockerGovernanceRule(
        container_name="atlas-api",
        memory_limit_bytes=1024 * 1024**2,
        cpu_limit=2.0,
        pids_limit=512,
    ),
    DockerGovernanceRule(
        container_name="atlas-portal",
        memory_limit_bytes=1536 * 1024**2,
        cpu_limit=2.0,
        pids_limit=512,
    ),
)


class DockerOperationsProvider(Protocol):
    """Normalized Docker data consumed by DockerCollector."""

    def engine(self) -> DockerEngineSnapshot:
        """Return one normalized Docker Engine snapshot."""

    def containers(self) -> tuple[DockerContainerSummary, ...]:
        """Return deterministic normalized container summaries."""

    def container(
        self,
        identity: str,
    ) -> DockerContainerSnapshot:
        """Return one normalized container runtime snapshot."""


@dataclass(frozen=True, slots=True)
class DockerCollector(OperationsCollector):
    """Collect normalized Docker Operations findings."""

    section_id: OperationsSectionId | str = (
        OperationsSectionId.CONTAINERS
    )
    name: str = "Containers"
    timeout_seconds: float = 10.0
    description: str | None = (
        "Docker Engine availability and container inventory"
    )
    provider: DockerOperationsProvider = field(
        default_factory=DockerProvider,
        repr=False,
        compare=False,
    )
    restart_warning_threshold: int = 3
    restart_critical_threshold: int = 10
    governance_policy: tuple[DockerGovernanceRule, ...] = (
        DEFAULT_DOCKER_GOVERNANCE_POLICY
    )

    def __post_init__(self) -> None:
        super(DockerCollector, self).__post_init__()

        if self.section_id is not OperationsSectionId.CONTAINERS:
            raise ValueError(
                "DockerCollector must use the containers section",
            )

        if not callable(getattr(self.provider, "engine", None)):
            raise ValueError(
                "provider must define engine()",
            )

        if not callable(getattr(self.provider, "containers", None)):
            raise ValueError(
                "provider must define containers()",
            )

        if not callable(getattr(self.provider, "container", None)):
            raise ValueError(
                "provider must define container()",
            )

        for field_name in (
            "restart_warning_threshold",
            "restart_critical_threshold",
        ):
            value = getattr(self, field_name)

            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(
                    f"{field_name} must be an integer",
                )

            if value <= 0:
                raise ValueError(
                    f"{field_name} must be greater than zero",
                )

        if (
            self.restart_critical_threshold
            <= self.restart_warning_threshold
        ):
            raise ValueError(
                "restart_critical_threshold must be greater than "
                "restart_warning_threshold",
            )

        if not isinstance(self.governance_policy, tuple):
            raise ValueError(
                "governance_policy must be a tuple",
            )

        for index, rule in enumerate(self.governance_policy):
            if not isinstance(rule, DockerGovernanceRule):
                raise ValueError(
                    "governance_policy"
                    f"[{index}] must be DockerGovernanceRule",
                )

        policy_names = [
            rule.container_name
            for rule in self.governance_policy
        ]

        if len(policy_names) != len(set(policy_names)):
            raise ValueError(
                "governance_policy container names must be unique",
            )

    def collect(self) -> OperationsSection:
        """Collect deterministic Docker Operations findings."""

        engine_finding = self._engine_finding()

        try:
            containers = self.provider.containers()
        except Exception as exc:
            inventory_finding = _unknown_finding(
                identifier="docker.inventory",
                name="Container Inventory",
                message="Docker container inventory is unavailable",
                error=exc,
            )
            runtime_finding = _unknown_finding(
                identifier="docker.runtime",
                name="Container Runtime",
                message="Docker container runtime is unavailable",
                error=exc,
            )
            health_finding = _unknown_finding(
                identifier="docker.health",
                name="Container Health",
                message="Docker container health is unavailable",
                error=exc,
            )
            restart_finding = _unknown_finding(
                identifier="docker.restarts",
                name="Container Restarts",
                message="Docker restart history is unavailable",
                error=exc,
            )
            oom_finding = _unknown_finding(
                identifier="docker.oom",
                name="Container OOM State",
                message="Docker OOM state is unavailable",
                error=exc,
            )
            exit_finding = _unknown_finding(
                identifier="docker.exit",
                name="Container Exit State",
                message="Docker exit state is unavailable",
                error=exc,
            )
            governance_finding = _unknown_finding(
                identifier="docker.governance",
                name="Container Resource Governance",
                message=(
                    "Docker resource governance is unavailable"
                ),
                error=exc,
            )
        else:
            inventory_finding = self._inventory_finding(
                containers,
            )
            snapshots, inspection_errors = (
                self._inspect_containers(containers)
            )
            runtime_finding = self._runtime_finding(
                containers,
                snapshots,
                inspection_errors,
            )
            health_finding = self._health_finding(
                containers,
                snapshots,
                inspection_errors,
            )
            restart_finding = self._restart_finding(
                containers,
                snapshots,
                inspection_errors,
            )
            oom_finding = self._oom_finding(
                containers,
                snapshots,
                inspection_errors,
            )
            exit_finding = self._exit_finding(
                containers,
                snapshots,
                inspection_errors,
            )
            governance_finding = self._governance_finding(
                containers,
                snapshots,
                inspection_errors,
            )

        return OperationsSection(
            identifier=self.section_id,
            name=self.name,
            description=self.description,
            findings=(
                engine_finding,
                inventory_finding,
                runtime_finding,
                health_finding,
                restart_finding,
                oom_finding,
                exit_finding,
                governance_finding,
            ),
        )

    def _engine_finding(self) -> OperationFinding:
        try:
            engine = self.provider.engine()

            return OperationFinding(
                identifier="docker.engine",
                name="Docker Engine",
                status=OperationsStatus.HEALTHY,
                severity=OperationsSeverity.INFO,
                message=(
                    "Docker Engine is available: "
                    f"server {engine.server_version}"
                ),
                metadata={
                    "architecture": engine.architecture,
                    "client_version": engine.client_version,
                    "cpu_count": engine.cpu_count,
                    "daemon_name": engine.daemon_name,
                    "memory_bytes": engine.memory_bytes,
                    "operating_system": engine.operating_system,
                    "server_version": engine.server_version,
                    "storage_driver": engine.storage_driver,
                },
            )
        except Exception as exc:
            return _unknown_finding(
                identifier="docker.engine",
                name="Docker Engine",
                message="Docker Engine information is unavailable",
                error=exc,
            )

    def _inventory_finding(
        self,
        containers: tuple[DockerContainerSummary, ...],
    ) -> OperationFinding:
        try:
            running = tuple(
                container
                for container in containers
                if container.state == "running"
            )
            non_running = tuple(
                container
                for container in containers
                if container.state != "running"
            )

            metadata = {
                "container_count": len(containers),
                "container_names": [
                    container.name
                    for container in containers
                ],
                "non_running_count": len(non_running),
                "non_running_names": [
                    container.name
                    for container in non_running
                ],
                "running_count": len(running),
            }

            if non_running:
                return OperationFinding(
                    identifier="docker.inventory",
                    name="Container Inventory",
                    status=OperationsStatus.WARNING,
                    severity=OperationsSeverity.WARNING,
                    message=(
                        f"{len(non_running)} of {len(containers)} "
                        "Docker containers are not running"
                    ),
                    recommendation=(
                        "Review the non-running containers and confirm "
                        "whether they should be started or removed."
                    ),
                    metadata=metadata,
                )

            return OperationFinding(
                identifier="docker.inventory",
                name="Container Inventory",
                status=OperationsStatus.HEALTHY,
                severity=OperationsSeverity.INFO,
                message=(
                    f"All {len(containers)} Docker containers "
                    "are running"
                ),
                metadata=metadata,
            )
        except Exception as exc:
            return _unknown_finding(
                identifier="docker.inventory",
                name="Container Inventory",
                message="Docker container inventory is unavailable",
                error=exc,
            )

    def _inspect_containers(
        self,
        containers: tuple[DockerContainerSummary, ...],
    ) -> tuple[
        tuple[DockerContainerSnapshot, ...],
        dict[str, str],
    ]:
        snapshots: list[DockerContainerSnapshot] = []
        errors: dict[str, str] = {}

        for container in containers:
            try:
                snapshots.append(
                    self.provider.container(container.name)
                )
            except Exception as exc:
                errors[container.name] = (
                    str(exc).strip()
                    or exc.__class__.__name__
                )

        return (
            tuple(
                sorted(
                    snapshots,
                    key=lambda snapshot: (
                        snapshot.name.casefold(),
                        snapshot.container_id,
                    ),
                )
            ),
            dict(
                sorted(
                    errors.items(),
                    key=lambda item: item[0].casefold(),
                )
            ),
        )

    def _runtime_finding(
        self,
        containers: tuple[DockerContainerSummary, ...],
        snapshots: tuple[DockerContainerSnapshot, ...],
        inspection_errors: dict[str, str],
    ) -> OperationFinding:
        restarting = tuple(
            snapshot
            for snapshot in snapshots
            if snapshot.restarting
        )
        non_running = tuple(
            snapshot
            for snapshot in snapshots
            if not snapshot.running
        )

        metadata = {
            "container_count": len(containers),
            "inspected_count": len(snapshots),
            "inspection_error_count": len(inspection_errors),
            "inspection_errors": inspection_errors,
            "non_running_count": len(non_running),
            "non_running_names": [
                snapshot.name
                for snapshot in non_running
            ],
            "restarting_count": len(restarting),
            "restarting_names": [
                snapshot.name
                for snapshot in restarting
            ],
        }

        if restarting:
            return OperationFinding(
                identifier="docker.runtime",
                name="Container Runtime",
                status=OperationsStatus.CRITICAL,
                severity=OperationsSeverity.CRITICAL,
                message=(
                    f"{len(restarting)} Docker containers "
                    "are restarting"
                ),
                recommendation=(
                    "Review the restarting containers, their logs, "
                    "dependencies, and restart policies."
                ),
                metadata=metadata,
            )

        if non_running:
            return OperationFinding(
                identifier="docker.runtime",
                name="Container Runtime",
                status=OperationsStatus.WARNING,
                severity=OperationsSeverity.WARNING,
                message=(
                    f"{len(non_running)} Docker containers "
                    "are not running"
                ),
                recommendation=(
                    "Review the stopped containers and confirm "
                    "whether they should be running."
                ),
                metadata=metadata,
            )

        if inspection_errors:
            return OperationFinding(
                identifier="docker.runtime",
                name="Container Runtime",
                status=OperationsStatus.UNKNOWN,
                severity=OperationsSeverity.INFO,
                message=(
                    "Docker runtime state could not be verified for "
                    f"{len(inspection_errors)} containers"
                ),
                metadata=metadata,
            )

        return OperationFinding(
            identifier="docker.runtime",
            name="Container Runtime",
            status=OperationsStatus.HEALTHY,
            severity=OperationsSeverity.INFO,
            message=(
                f"All {len(snapshots)} inspected Docker containers "
                "are running"
            ),
            metadata=metadata,
        )

    def _health_finding(
        self,
        containers: tuple[DockerContainerSummary, ...],
        snapshots: tuple[DockerContainerSnapshot, ...],
        inspection_errors: dict[str, str],
    ) -> OperationFinding:
        unhealthy = tuple(
            snapshot
            for snapshot in snapshots
            if snapshot.health == "unhealthy"
        )
        starting = tuple(
            snapshot
            for snapshot in snapshots
            if snapshot.health == "starting"
        )
        healthy = tuple(
            snapshot
            for snapshot in snapshots
            if snapshot.health == "healthy"
        )
        without_healthcheck = tuple(
            snapshot
            for snapshot in snapshots
            if snapshot.health is None
        )

        metadata = {
            "container_count": len(containers),
            "healthy_count": len(healthy),
            "healthy_names": [
                snapshot.name
                for snapshot in healthy
            ],
            "inspection_error_count": len(inspection_errors),
            "inspection_errors": inspection_errors,
            "starting_count": len(starting),
            "starting_names": [
                snapshot.name
                for snapshot in starting
            ],
            "unhealthy_count": len(unhealthy),
            "unhealthy_names": [
                snapshot.name
                for snapshot in unhealthy
            ],
            "without_healthcheck_count": len(
                without_healthcheck
            ),
            "without_healthcheck_names": [
                snapshot.name
                for snapshot in without_healthcheck
            ],
        }

        if unhealthy:
            return OperationFinding(
                identifier="docker.health",
                name="Container Health",
                status=OperationsStatus.CRITICAL,
                severity=OperationsSeverity.CRITICAL,
                message=(
                    f"{len(unhealthy)} Docker containers "
                    "are unhealthy"
                ),
                recommendation=(
                    "Review the unhealthy containers, Docker health "
                    "logs, service logs, and dependencies."
                ),
                metadata=metadata,
            )

        if starting:
            return OperationFinding(
                identifier="docker.health",
                name="Container Health",
                status=OperationsStatus.WARNING,
                severity=OperationsSeverity.WARNING,
                message=(
                    f"{len(starting)} Docker containers have "
                    "health checks still starting"
                ),
                recommendation=(
                    "Allow the containers to finish starting and "
                    "review them if the state does not clear."
                ),
                metadata=metadata,
            )

        if inspection_errors:
            return OperationFinding(
                identifier="docker.health",
                name="Container Health",
                status=OperationsStatus.UNKNOWN,
                severity=OperationsSeverity.INFO,
                message=(
                    "Docker health state could not be verified for "
                    f"{len(inspection_errors)} containers"
                ),
                metadata=metadata,
            )

        return OperationFinding(
            identifier="docker.health",
            name="Container Health",
            status=OperationsStatus.HEALTHY,
            severity=OperationsSeverity.INFO,
            message=(
                "No unhealthy Docker containers were detected"
            ),
            metadata=metadata,
        )


    def _restart_finding(
        self,
        containers: tuple[DockerContainerSummary, ...],
        snapshots: tuple[DockerContainerSnapshot, ...],
        inspection_errors: dict[str, str],
    ) -> OperationFinding:
        critical = tuple(
            snapshot
            for snapshot in snapshots
            if (
                snapshot.restart_count
                >= self.restart_critical_threshold
            )
        )
        warning = tuple(
            snapshot
            for snapshot in snapshots
            if (
                self.restart_warning_threshold
                <= snapshot.restart_count
                < self.restart_critical_threshold
            )
        )

        restart_counts = {
            snapshot.name: snapshot.restart_count
            for snapshot in snapshots
            if snapshot.restart_count > 0
        }

        metadata = {
            "container_count": len(containers),
            "critical_count": len(critical),
            "critical_names": [
                snapshot.name
                for snapshot in critical
            ],
            "inspection_error_count": len(inspection_errors),
            "inspection_errors": inspection_errors,
            "restart_counts": restart_counts,
            "warning_count": len(warning),
            "warning_names": [
                snapshot.name
                for snapshot in warning
            ],
            "warning_threshold": self.restart_warning_threshold,
            "critical_threshold": self.restart_critical_threshold,
        }

        if critical:
            return OperationFinding(
                identifier="docker.restarts",
                name="Container Restarts",
                status=OperationsStatus.CRITICAL,
                severity=OperationsSeverity.CRITICAL,
                message=(
                    f"{len(critical)} Docker containers exceed the "
                    "critical restart threshold"
                ),
                recommendation=(
                    "Review container logs, dependencies, health "
                    "checks, and restart policies."
                ),
                metadata=metadata,
            )

        if warning:
            return OperationFinding(
                identifier="docker.restarts",
                name="Container Restarts",
                status=OperationsStatus.WARNING,
                severity=OperationsSeverity.WARNING,
                message=(
                    f"{len(warning)} Docker containers exceed the "
                    "restart warning threshold"
                ),
                recommendation=(
                    "Review recent container failures and confirm "
                    "the restart counts are expected."
                ),
                metadata=metadata,
            )

        if inspection_errors:
            return OperationFinding(
                identifier="docker.restarts",
                name="Container Restarts",
                status=OperationsStatus.UNKNOWN,
                severity=OperationsSeverity.INFO,
                message=(
                    "Docker restart history could not be verified for "
                    f"{len(inspection_errors)} containers"
                ),
                metadata=metadata,
            )

        return OperationFinding(
            identifier="docker.restarts",
            name="Container Restarts",
            status=OperationsStatus.HEALTHY,
            severity=OperationsSeverity.INFO,
            message=(
                "No Docker containers exceed the configured "
                "restart thresholds"
            ),
            metadata=metadata,
        )

    def _oom_finding(
        self,
        containers: tuple[DockerContainerSummary, ...],
        snapshots: tuple[DockerContainerSnapshot, ...],
        inspection_errors: dict[str, str],
    ) -> OperationFinding:
        oom_killed = tuple(
            snapshot
            for snapshot in snapshots
            if snapshot.oom_killed
        )

        metadata = {
            "container_count": len(containers),
            "inspection_error_count": len(inspection_errors),
            "inspection_errors": inspection_errors,
            "oom_killed_count": len(oom_killed),
            "oom_killed_names": [
                snapshot.name
                for snapshot in oom_killed
            ],
        }

        if oom_killed:
            return OperationFinding(
                identifier="docker.oom",
                name="Container OOM State",
                status=OperationsStatus.CRITICAL,
                severity=OperationsSeverity.CRITICAL,
                message=(
                    f"{len(oom_killed)} Docker containers were "
                    "terminated by the OOM killer"
                ),
                recommendation=(
                    "Review memory limits, host memory pressure, "
                    "container logs, and workload sizing."
                ),
                metadata=metadata,
            )

        if inspection_errors:
            return OperationFinding(
                identifier="docker.oom",
                name="Container OOM State",
                status=OperationsStatus.UNKNOWN,
                severity=OperationsSeverity.INFO,
                message=(
                    "Docker OOM state could not be verified for "
                    f"{len(inspection_errors)} containers"
                ),
                metadata=metadata,
            )

        return OperationFinding(
            identifier="docker.oom",
            name="Container OOM State",
            status=OperationsStatus.HEALTHY,
            severity=OperationsSeverity.INFO,
            message="No Docker containers report an OOM kill",
            metadata=metadata,
        )

    def _exit_finding(
        self,
        containers: tuple[DockerContainerSummary, ...],
        snapshots: tuple[DockerContainerSnapshot, ...],
        inspection_errors: dict[str, str],
    ) -> OperationFinding:
        failed = tuple(
            snapshot
            for snapshot in snapshots
            if (
                not snapshot.running
                and snapshot.exit_code != 0
            )
        )
        cleanly_stopped = tuple(
            snapshot
            for snapshot in snapshots
            if (
                not snapshot.running
                and snapshot.exit_code == 0
            )
        )

        metadata = {
            "cleanly_stopped_count": len(cleanly_stopped),
            "cleanly_stopped_names": [
                snapshot.name
                for snapshot in cleanly_stopped
            ],
            "container_count": len(containers),
            "failed_count": len(failed),
            "failed_exit_codes": {
                snapshot.name: snapshot.exit_code
                for snapshot in failed
            },
            "failed_names": [
                snapshot.name
                for snapshot in failed
            ],
            "inspection_error_count": len(inspection_errors),
            "inspection_errors": inspection_errors,
        }

        if failed:
            return OperationFinding(
                identifier="docker.exit",
                name="Container Exit State",
                status=OperationsStatus.CRITICAL,
                severity=OperationsSeverity.CRITICAL,
                message=(
                    f"{len(failed)} stopped Docker containers have "
                    "non-zero exit codes"
                ),
                recommendation=(
                    "Review the failed containers' logs, exit codes, "
                    "dependencies, and startup configuration."
                ),
                metadata=metadata,
            )

        if cleanly_stopped:
            return OperationFinding(
                identifier="docker.exit",
                name="Container Exit State",
                status=OperationsStatus.WARNING,
                severity=OperationsSeverity.WARNING,
                message=(
                    f"{len(cleanly_stopped)} Docker containers are "
                    "cleanly stopped"
                ),
                recommendation=(
                    "Confirm that the stopped containers are "
                    "intentionally offline."
                ),
                metadata=metadata,
            )

        if inspection_errors:
            return OperationFinding(
                identifier="docker.exit",
                name="Container Exit State",
                status=OperationsStatus.UNKNOWN,
                severity=OperationsSeverity.INFO,
                message=(
                    "Docker exit state could not be verified for "
                    f"{len(inspection_errors)} containers"
                ),
                metadata=metadata,
            )

        return OperationFinding(
            identifier="docker.exit",
            name="Container Exit State",
            status=OperationsStatus.HEALTHY,
            severity=OperationsSeverity.INFO,
            message="No stopped Docker containers were detected",
            metadata=metadata,
        )


    def _governance_finding(
        self,
        containers: tuple[DockerContainerSummary, ...],
        snapshots: tuple[DockerContainerSnapshot, ...],
        inspection_errors: dict[str, str],
    ) -> OperationFinding:
        snapshot_by_name = {
            snapshot.name: snapshot
            for snapshot in snapshots
        }
        policy_by_name = {
            rule.container_name: rule
            for rule in self.governance_policy
        }

        missing_containers: list[str] = []
        missing_ceilings: dict[str, list[str]] = {}
        mismatches: dict[str, dict[str, object]] = {}
        compliant: list[str] = []

        for name, rule in policy_by_name.items():
            snapshot = snapshot_by_name.get(name)

            if snapshot is None:
                if name not in inspection_errors:
                    missing_containers.append(name)
                continue

            missing_fields: list[str] = []

            if snapshot.memory_limit_bytes == 0:
                missing_fields.append("memory")

            if snapshot.cpu_limit is None:
                missing_fields.append("cpu")

            if snapshot.pids_limit is None:
                missing_fields.append("pids")

            if missing_fields:
                missing_ceilings[name] = missing_fields
                continue

            differences: dict[str, object] = {}

            if (
                snapshot.memory_limit_bytes
                != rule.memory_limit_bytes
            ):
                differences["memory_limit_bytes"] = {
                    "expected": rule.memory_limit_bytes,
                    "actual": snapshot.memory_limit_bytes,
                }

            if snapshot.cpu_limit != rule.cpu_limit:
                differences["cpu_limit"] = {
                    "expected": rule.cpu_limit,
                    "actual": snapshot.cpu_limit,
                }

            if snapshot.pids_limit != rule.pids_limit:
                differences["pids_limit"] = {
                    "expected": rule.pids_limit,
                    "actual": snapshot.pids_limit,
                }

            if differences:
                mismatches[name] = differences
            else:
                compliant.append(name)

        governed_names = set(policy_by_name)
        ungoverned = sorted(
            (
                snapshot.name
                for snapshot in snapshots
                if snapshot.name not in governed_names
            ),
            key=str.casefold,
        )

        relevant_inspection_errors = {
            name: error
            for name, error in inspection_errors.items()
            if name in governed_names
        }

        metadata = {
            "compliant_count": len(compliant),
            "compliant_names": sorted(
                compliant,
                key=str.casefold,
            ),
            "container_count": len(containers),
            "governed_count": len(policy_by_name),
            "inspection_error_count": len(
                relevant_inspection_errors
            ),
            "inspection_errors": dict(
                sorted(
                    relevant_inspection_errors.items(),
                    key=lambda item: item[0].casefold(),
                )
            ),
            "mismatch_count": len(mismatches),
            "mismatches": dict(
                sorted(
                    mismatches.items(),
                    key=lambda item: item[0].casefold(),
                )
            ),
            "missing_ceiling_count": len(missing_ceilings),
            "missing_ceilings": dict(
                sorted(
                    missing_ceilings.items(),
                    key=lambda item: item[0].casefold(),
                )
            ),
            "missing_container_count": len(missing_containers),
            "missing_container_names": sorted(
                missing_containers,
                key=str.casefold,
            ),
            "policy": [
                rule.to_dict()
                for rule in self.governance_policy
            ],
            "ungoverned_count": len(ungoverned),
            "ungoverned_names": ungoverned,
        }

        if mismatches or missing_containers:
            affected = len(mismatches) + len(missing_containers)

            return OperationFinding(
                identifier="docker.governance",
                name="Container Resource Governance",
                status=OperationsStatus.CRITICAL,
                severity=OperationsSeverity.CRITICAL,
                message=(
                    f"{affected} governed Docker containers do not "
                    "match the expected resource contract"
                ),
                recommendation=(
                    "Review the deployed Compose resource ceilings "
                    "and restore the expected governance contract."
                ),
                metadata=metadata,
            )

        if missing_ceilings:
            return OperationFinding(
                identifier="docker.governance",
                name="Container Resource Governance",
                status=OperationsStatus.WARNING,
                severity=OperationsSeverity.WARNING,
                message=(
                    f"{len(missing_ceilings)} governed Docker "
                    "containers are missing resource ceilings"
                ),
                recommendation=(
                    "Add the missing memory, CPU, or PID ceilings "
                    "and redeploy the affected containers."
                ),
                metadata=metadata,
            )

        if relevant_inspection_errors:
            return OperationFinding(
                identifier="docker.governance",
                name="Container Resource Governance",
                status=OperationsStatus.UNKNOWN,
                severity=OperationsSeverity.INFO,
                message=(
                    "Resource governance could not be verified for "
                    f"{len(relevant_inspection_errors)} governed "
                    "containers"
                ),
                metadata=metadata,
            )

        return OperationFinding(
            identifier="docker.governance",
            name="Container Resource Governance",
            status=OperationsStatus.HEALTHY,
            severity=OperationsSeverity.INFO,
            message=(
                f"All {len(compliant)} governed Docker containers "
                "match their expected resource ceilings"
            ),
            metadata=metadata,
        )


def _unknown_finding(
    *,
    identifier: str,
    name: str,
    message: str,
    error: Exception,
) -> OperationFinding:
    return OperationFinding(
        identifier=identifier,
        name=name,
        status=OperationsStatus.UNKNOWN,
        severity=OperationsSeverity.INFO,
        message=message,
        metadata={
            "error": (
                str(error).strip()
                or error.__class__.__name__
            ),
        },
    )
