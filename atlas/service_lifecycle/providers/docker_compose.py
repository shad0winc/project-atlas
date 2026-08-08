"""Read-only Docker Compose foundation for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from json import JSONDecodeError, loads
from pathlib import Path
import subprocess
from typing import Any

from atlas.service_lifecycle.models import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRuntime,
)
from atlas.service_lifecycle.provider import ServiceLifecycleProvider
from atlas.service_lifecycle.startup_models import (
    ServiceStartupContract,
    ServiceStartupDependency,
    StartupDependencyCondition,
)
from atlas.service_lifecycle.update_models import (
    ImageReference,
    ServiceUpdate,
    UpdateStatus,
)


class DockerComposeProviderError(ServiceLifecycleError):
    """Raised when read-only Docker Compose inspection fails."""


@dataclass(frozen=True)
class DockerComposeProvider(ServiceLifecycleProvider):
    """Read-only infrastructure provider backed by Docker Compose."""

    compose_file: str | Path
    project_directory: str | Path | None = None
    timeout: float = 15.0
    environment: Mapping[str, str] | None = field(
        default=None,
        repr=False,
    )

    def __post_init__(self) -> None:
        compose_file = _normalize_compose_file(
            self.compose_file,
        )

        project_directory = _normalize_project_directory(
            self.project_directory,
            compose_file=compose_file,
        )

        if (
            isinstance(self.timeout, bool)
            or not isinstance(self.timeout, (int, float))
            or self.timeout <= 0
        ):
            raise DockerComposeProviderError(
                "timeout must be a positive number",
            )

        environment = self.environment

        if environment is not None:
            if not isinstance(environment, Mapping):
                raise DockerComposeProviderError(
                    "environment must be an object or null",
                )

            normalized_environment: dict[str, str] = {}

            for key, value in environment.items():
                if (
                    not isinstance(key, str)
                    or not key.strip()
                    or not isinstance(value, str)
                ):
                    raise DockerComposeProviderError(
                        "environment must contain string keys and values",
                    )

                normalized_environment[key.strip()] = value

            environment = normalized_environment

        object.__setattr__(
            self,
            "compose_file",
            compose_file,
        )
        object.__setattr__(
            self,
            "project_directory",
            project_directory,
        )
        object.__setattr__(
            self,
            "timeout",
            float(self.timeout),
        )
        object.__setattr__(
            self,
            "environment",
            environment,
        )

    def list_services(self) -> Sequence[ManagedService]:
        """Return configured Compose services as normalized models."""

        payload = self._run_compose_json(
            "config",
            "--format",
            "json",
        )

        if not isinstance(payload, Mapping):
            raise DockerComposeProviderError(
                "Docker Compose configuration must be an object",
            )

        services = payload.get("services")

        if not isinstance(services, Mapping):
            raise DockerComposeProviderError(
                "Docker Compose configuration must contain "
                "a services object",
            )

        project_name = _normalize_project_name(
            payload.get("name"),
            fallback=self.project_directory.name,
        )

        normalized_services: list[ManagedService] = []

        for raw_identifier, raw_configuration in services.items():
            normalized_services.append(
                _normalize_configured_service(
                    raw_identifier,
                    raw_configuration,
                    project_name=project_name,
                )
            )

        return tuple(
            sorted(
                normalized_services,
                key=lambda service: (
                    service.name.casefold(),
                    service.identifier,
                ),
            )
        )

    def inspect_startup_contracts(
        self,
    ) -> tuple[ServiceStartupContract, ...]:
        """Return normalized startup contracts for Compose services."""

        payload = self._run_compose_json(
            "config",
            "--format",
            "json",
        )

        if not isinstance(payload, Mapping):
            raise DockerComposeProviderError(
                "Docker Compose configuration must be an object",
            )

        services = payload.get("services")

        if not isinstance(services, Mapping):
            raise DockerComposeProviderError(
                "Docker Compose configuration must contain "
                "a services object",
            )

        project_name = _normalize_project_name(
            payload.get("name"),
            fallback=self.project_directory.name,
        )

        contracts: list[ServiceStartupContract] = []

        for raw_identifier, raw_configuration in services.items():
            service = _normalize_configured_service(
                raw_identifier,
                raw_configuration,
                project_name=project_name,
            )

            if not isinstance(raw_configuration, Mapping):
                raise DockerComposeProviderError(
                    "Compose service configuration must be an object: "
                    f"{service.identifier}",
                )

            contracts.append(
                _normalize_startup_contract(
                    service,
                    raw_configuration,
                )
            )

        return tuple(
            sorted(
                contracts,
                key=lambda contract: (
                    contract.service.name.casefold(),
                    contract.service.identifier,
                ),
            )
        )

    def inspect_service(
        self,
        identifier: str,
    ) -> ManagedService:
        """Return one configured Compose service by stable identifier."""

        normalized_identifier = _normalize_requested_identifier(
            identifier,
        )

        for service in self.list_services():
            if service.identifier == normalized_identifier:
                return service

        raise DockerComposeProviderError(
            "Docker Compose service was not found: "
            f"{normalized_identifier}",
        )

    def inspect_runtime(
        self,
        identifier: str,
    ) -> ServiceRuntime:
        """Return normalized live runtime state for one service."""

        service = self.inspect_service(identifier)

        container_identifier = self._resolve_container_identifier(
            service,
        )

        payload = self._run_docker_json(
            "inspect",
            container_identifier,
        )

        return _normalize_runtime_payload(
            payload,
            service_identifier=service.identifier,
        )

    def inspect_health(
        self,
        identifier: str,
    ) -> ServiceHealth:
        """Return normalized health for one configured service."""

        normalized_identifier = _normalize_requested_identifier(
            identifier,
        )

        try:
            runtime = self.inspect_runtime(
                normalized_identifier,
            )
        except DockerComposeProviderError as exc:
            message = str(exc)

            if message.startswith(
                "Docker Compose container was not found:"
            ):
                return ServiceHealth(
                    status=ServiceHealthStatus.UNAVAILABLE,
                    score=0,
                    errors=(
                        "Container is not available",
                    ),
                    details={
                        "service_identifier": normalized_identifier,
                        "runtime_state": "unavailable",
                        "docker_health": "unknown",
                        "restart_count": None,
                        "image_reference": None,
                        "exit_code": None,
                        "status_message": message,
                    },
                )

            raise

        return _health_from_runtime(
            runtime,
            service_identifier=normalized_identifier,
        )

    def inspect_update(
        self,
        identifier: str,
    ) -> ServiceUpdate:
        """Return locally verifiable image update metadata."""

        service = self.inspect_service(identifier)
        runtime = self.inspect_runtime(service.identifier)
        current_image = _update_image_from_runtime(runtime)

        if current_image.is_mutable:
            status = UpdateStatus.MUTABLE_TAG
            reason = (
                "The configured image uses the mutable latest tag; "
                "registry comparison has not been performed."
            )
        else:
            status = UpdateStatus.UNKNOWN
            reason = (
                "The local image identity is known, but no registry "
                "comparison has been performed."
            )

        return ServiceUpdate(
            service_identifier=service.identifier,
            service_name=service.name,
            current_image=current_image,
            status=status,
            reason=reason,
            details={
                "source": "local-docker",
                "registry_comparison": False,
                "configured_reference": runtime.image.reference,
                "local_image_id": runtime.image.image_id,
                "local_image_created_at": runtime.image.created_at,
            },
        )

    def _resolve_container_identifier(
        self,
        service: ManagedService,
    ) -> str:
        """Resolve one configured service to a Docker container ID."""

        if not isinstance(service, ManagedService):
            raise DockerComposeProviderError(
                "service must be a ManagedService",
            )

        result = self._run_compose(
            "ps",
            "--all",
            "--quiet",
            service.identifier,
        )

        identifiers = tuple(
            line.strip()
            for line in result.stdout.splitlines()
            if line.strip()
        )

        if not identifiers:
            raise DockerComposeProviderError(
                "Docker Compose container was not found: "
                f"{service.identifier}",
            )

        if len(identifiers) != 1:
            raise DockerComposeProviderError(
                "Docker Compose returned multiple containers: "
                f"{service.identifier}",
            )

        return identifiers[0]

    def _build_docker_command(
        self,
        *arguments: str,
    ) -> tuple[str, ...]:
        """Build one fixed Docker argument list."""

        normalized_arguments = tuple(
            _required_argument(argument)
            for argument in arguments
        )

        return (
            "docker",
            *normalized_arguments,
        )

    def _run_docker(
        self,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        """Execute one read-only Docker command safely."""

        command = self._build_docker_command(
            *arguments,
        )

        try:
            result = subprocess.run(
                command,
                cwd=self.project_directory,
                env=(
                    None
                    if self.environment is None
                    else dict(self.environment)
                ),
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise DockerComposeProviderError(
                "Docker inspection timed out",
            ) from exc
        except FileNotFoundError as exc:
            raise DockerComposeProviderError(
                "Docker executable was not found",
            ) from exc
        except OSError as exc:
            raise DockerComposeProviderError(
                "Docker inspection could not be started",
            ) from exc

        if result.returncode != 0:
            diagnostic = _safe_diagnostic(
                result.stderr,
                result.stdout,
            )

            message = "Docker inspection failed"

            if diagnostic:
                message = f"{message}: {diagnostic}"

            raise DockerComposeProviderError(message)

        return result

    def _run_docker_json(
        self,
        *arguments: str,
    ) -> Any:
        """Execute Docker and decode one JSON response."""

        result = self._run_docker(
            *arguments,
        )

        if not result.stdout.strip():
            raise DockerComposeProviderError(
                "Docker returned an empty JSON response",
            )

        try:
            return loads(result.stdout)
        except JSONDecodeError as exc:
            raise DockerComposeProviderError(
                "Docker returned invalid JSON",
            ) from exc

    def _build_compose_command(
        self,
        *arguments: str,
    ) -> tuple[str, ...]:
        """Build one fixed Docker Compose argument list."""

        normalized_arguments = tuple(
            _required_argument(argument)
            for argument in arguments
        )

        return (
            "docker",
            "compose",
            "--file",
            str(self.compose_file),
            "--project-directory",
            str(self.project_directory),
            *normalized_arguments,
        )

    def _run_compose(
        self,
        *arguments: str,
    ) -> subprocess.CompletedProcess[str]:
        """Execute one read-only Docker Compose command safely."""

        command = self._build_compose_command(
            *arguments,
        )

        try:
            result = subprocess.run(
                command,
                cwd=self.project_directory,
                env=(
                    None
                    if self.environment is None
                    else dict(self.environment)
                ),
                capture_output=True,
                text=True,
                check=False,
                shell=False,
                timeout=self.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise DockerComposeProviderError(
                "Docker Compose inspection timed out",
            ) from exc
        except FileNotFoundError as exc:
            raise DockerComposeProviderError(
                "Docker executable was not found",
            ) from exc
        except OSError as exc:
            raise DockerComposeProviderError(
                "Docker Compose inspection could not be started",
            ) from exc

        if result.returncode != 0:
            diagnostic = _safe_diagnostic(
                result.stderr,
                result.stdout,
            )

            message = "Docker Compose inspection failed"

            if diagnostic:
                message = f"{message}: {diagnostic}"

            raise DockerComposeProviderError(message)

        return result

    def _run_compose_json(
        self,
        *arguments: str,
    ) -> Any:
        """Execute Compose and decode one JSON response."""

        result = self._run_compose(
            *arguments,
        )

        if not result.stdout.strip():
            raise DockerComposeProviderError(
                "Docker Compose returned an empty JSON response",
            )

        try:
            return loads(result.stdout)
        except JSONDecodeError as exc:
            raise DockerComposeProviderError(
                "Docker Compose returned invalid JSON",
            ) from exc


def _health_from_runtime(
    runtime: ServiceRuntime,
    *,
    service_identifier: str,
) -> ServiceHealth:
    if not isinstance(runtime, ServiceRuntime):
        raise DockerComposeProviderError(
            "runtime must be a ServiceRuntime",
        )

    status = ServiceHealthStatus.UNKNOWN
    score = 50
    warnings: list[str] = []
    errors: list[str] = []

    if runtime.state == "running":
        if runtime.health == "healthy":
            status = ServiceHealthStatus.HEALTHY
            score = 100

        elif runtime.health == "starting":
            status = ServiceHealthStatus.DEGRADED
            score = 70
            warnings.append(
                "Docker health check is still starting",
            )

        elif runtime.health == "unhealthy":
            status = ServiceHealthStatus.UNHEALTHY
            score = 25
            errors.append(
                "Docker reported the container as unhealthy",
            )

        elif runtime.health == "unknown":
            status = ServiceHealthStatus.DEGRADED
            score = 85
            warnings.append(
                "No Docker health check is configured",
            )

        else:
            status = ServiceHealthStatus.DEGRADED
            score = 65
            warnings.append(
                "Docker reported an unrecognized health state: "
                f"{runtime.health}",
            )

    elif runtime.state == "restarting":
        status = ServiceHealthStatus.DEGRADED
        score = 60
        warnings.append(
            "Container is restarting",
        )

    elif runtime.state == "paused":
        status = ServiceHealthStatus.DEGRADED
        score = 60
        warnings.append(
            "Container is paused",
        )

    elif runtime.state in {
        "exited",
        "dead",
        "removing",
    }:
        status = ServiceHealthStatus.UNAVAILABLE
        score = 0
        errors.append(
            "Container is not running",
        )

    elif runtime.state == "created":
        status = ServiceHealthStatus.UNAVAILABLE
        score = 10
        errors.append(
            "Container has been created but is not running",
        )

    else:
        warnings.append(
            "Container runtime state is unknown: "
            f"{runtime.state}",
        )

    if runtime.restart_count > 0:
        warnings.append(
            "Container restart count is "
            f"{runtime.restart_count}",
        )

        if status is ServiceHealthStatus.HEALTHY:
            status = ServiceHealthStatus.DEGRADED
            score = min(
                score,
                90,
            )

    details = {
        "service_identifier": service_identifier,
        "runtime_state": runtime.state,
        "docker_health": runtime.health,
        "restart_count": runtime.restart_count,
        "image_reference": runtime.image.reference,
        "exit_code": runtime.exit_code,
        "status_message": runtime.status_message,
        "started_at": runtime.started_at,
        "finished_at": runtime.finished_at,
    }

    try:
        return ServiceHealth(
            status=status,
            score=score,
            warnings=warnings,
            errors=errors,
            details=details,
        )
    except ServiceLifecycleError as exc:
        raise DockerComposeProviderError(
            "Invalid Docker health state: "
            f"{service_identifier}: {exc}",
        ) from exc


def _update_image_from_runtime(
    runtime: ServiceRuntime,
) -> ImageReference:
    """Convert normalized runtime image identity to update identity."""

    if not isinstance(runtime, ServiceRuntime):
        raise DockerComposeProviderError(
            "runtime must be a ServiceRuntime",
        )

    image = runtime.image
    if image.repository is None:
        try:
            return ImageReference.parse(image.reference)
        except ServiceLifecycleError as exc:
            raise DockerComposeProviderError(
                "Docker runtime image reference is invalid: "
                f"{exc}",
            ) from exc

    try:
        return ImageReference(
            repository=image.repository,
            tag=image.tag,
            digest=image.digest,
            raw_reference=image.reference,
        )
    except ServiceLifecycleError as exc:
        raise DockerComposeProviderError(
            "Docker runtime image identity is invalid: "
            f"{exc}",
        ) from exc


def _normalize_runtime_payload(
    payload: object,
    *,
    service_identifier: str,
) -> ServiceRuntime:
    if (
        not isinstance(payload, Sequence)
        or isinstance(payload, (str, bytes))
    ):
        raise DockerComposeProviderError(
            "Docker inspect response must be a collection",
        )

    if len(payload) != 1:
        raise DockerComposeProviderError(
            "Docker inspect response must contain exactly one object",
        )

    container = payload[0]

    if not isinstance(container, Mapping):
        raise DockerComposeProviderError(
            "Docker inspect container must be an object",
        )

    state = container.get("State")
    configuration = container.get("Config")

    if not isinstance(state, Mapping):
        raise DockerComposeProviderError(
            "Docker inspect response must contain a State object",
        )

    if not isinstance(configuration, Mapping):
        raise DockerComposeProviderError(
            "Docker inspect response must contain a Config object",
        )

    image_reference = configuration.get("Image")

    if not isinstance(image_reference, str) or not image_reference.strip():
        raise DockerComposeProviderError(
            "Docker inspect Config.Image must be non-empty text",
        )

    image_id = container.get("Image")

    if image_id is not None and (
        not isinstance(image_id, str)
        or not image_id.strip()
    ):
        raise DockerComposeProviderError(
            "Docker inspect Image must be non-empty text or null",
        )

    repository, tag, digest = _split_image_reference(
        image_reference.strip(),
    )

    runtime_state = _normalize_runtime_state(
        state,
    )
    health_state = _normalize_runtime_health(
        state,
    )
    restart_count = container.get(
        "RestartCount",
        0,
    )
    exit_code = state.get("ExitCode")

    if exit_code is None:
        normalized_exit_code = None
    elif isinstance(exit_code, bool) or not isinstance(exit_code, int):
        raise DockerComposeProviderError(
            "Docker inspect State.ExitCode must be an integer or null",
        )
    else:
        normalized_exit_code = exit_code

    status_message = _docker_status_message(
        state,
        runtime_state=runtime_state,
    )

    try:
        image = ServiceImage(
            reference=image_reference,
            repository=repository,
            tag=tag,
            digest=digest,
            image_id=(
                None
                if image_id is None
                else image_id.strip()
            ),
        )

        runtime = ServiceRuntime(
            state=runtime_state,
            health=health_state,
            image=image,
            restart_count=restart_count,
            started_at=_normalize_docker_timestamp(
                state.get("StartedAt"),
            ),
            finished_at=_normalize_docker_timestamp(
                state.get("FinishedAt"),
            ),
            exit_code=normalized_exit_code,
            status_message=status_message,
        )

        if runtime_state in {"running", "restarting"}:
            runtime = replace(
                runtime,
                finished_at=None,
            )

        return runtime
    except ServiceLifecycleError as exc:
        raise DockerComposeProviderError(
            "Invalid Docker runtime state: "
            f"{service_identifier}: {exc}",
        ) from exc


def _normalize_runtime_state(
    state: Mapping[str, Any],
) -> str:
    if state.get("Dead") is True:
        return "dead"

    if state.get("Restarting") is True:
        return "restarting"

    if state.get("Paused") is True:
        return "paused"

    value = state.get("Status")

    if not isinstance(value, str) or not value.strip():
        raise DockerComposeProviderError(
            "Docker inspect State.Status must be non-empty text",
        )

    return value.strip().casefold()


def _normalize_runtime_health(
    state: Mapping[str, Any],
) -> str:
    health = state.get("Health")

    if health is None:
        return "unknown"

    if not isinstance(health, Mapping):
        raise DockerComposeProviderError(
            "Docker inspect State.Health must be an object or null",
        )

    value = health.get("Status")

    if not isinstance(value, str) or not value.strip():
        raise DockerComposeProviderError(
            "Docker inspect State.Health.Status "
            "must be non-empty text",
        )

    return value.strip().casefold()


def _normalize_docker_timestamp(
    value: object,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise DockerComposeProviderError(
            "Docker timestamps must be text or null",
        )

    normalized = value.strip()

    if not normalized:
        return None

    if normalized.startswith("0001-01-01T00:00:00"):
        return None

    return normalized


def _docker_status_message(
    state: Mapping[str, Any],
    *,
    runtime_state: str,
) -> str:
    error = state.get("Error")

    if isinstance(error, str) and error.strip():
        return error.strip()

    return runtime_state


def _split_image_reference(
    reference: str,
) -> tuple[str, str | None, str | None]:
    if "@sha256:" in reference:
        repository, raw_digest = reference.rsplit(
            "@",
            1,
        )

        return (
            repository,
            None,
            raw_digest,
        )

    final_segment = reference.rsplit(
        "/",
        1,
    )[-1]

    if ":" not in final_segment:
        return (
            reference,
            None,
            None,
        )

    repository, tag = reference.rsplit(
        ":",
        1,
    )

    return (
        repository,
        tag,
        None,
    )


def _normalize_requested_identifier(
    value: object,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DockerComposeProviderError(
            "service identifier must be non-empty text",
        )

    normalized = value.strip().casefold()

    try:
        probe = ManagedService(
            identifier=normalized,
            name="Service",
            provider="docker-compose",
        )
    except ServiceLifecycleError as exc:
        raise DockerComposeProviderError(
            f"invalid service identifier: {normalized}: {exc}",
        ) from exc

    return probe.identifier


def _normalize_configured_service(
    identifier: object,
    configuration: object,
    *,
    project_name: str,
) -> ManagedService:
    if not isinstance(identifier, str) or not identifier.strip():
        raise DockerComposeProviderError(
            "Compose service identifiers must be non-empty strings",
        )

    normalized_identifier = identifier.strip().casefold()

    if not isinstance(configuration, Mapping):
        raise DockerComposeProviderError(
            "Compose service configuration must be an object: "
            f"{normalized_identifier}",
        )

    container_name = configuration.get("container_name")

    if container_name is not None and (
        not isinstance(container_name, str)
        or not container_name.strip()
    ):
        raise DockerComposeProviderError(
            "Compose container_name must be non-empty text or null: "
            f"{normalized_identifier}",
        )

    dependencies = _normalize_compose_dependencies(
        configuration.get("depends_on"),
        service_identifier=normalized_identifier,
    )

    try:
        return ManagedService(
            identifier=normalized_identifier,
            name=_service_display_name(
                normalized_identifier,
            ),
            provider="docker-compose",
            enabled=True,
            compose_project=project_name,
            container_name=(
                None
                if container_name is None
                else container_name.strip()
            ),
            dependencies=dependencies,
        )
    except ServiceLifecycleError as exc:
        raise DockerComposeProviderError(
            "Invalid Compose service configuration: "
            f"{normalized_identifier}: {exc}",
        ) from exc


def _normalize_startup_contract(
    service: ManagedService,
    configuration: Mapping[str, Any],
) -> ServiceStartupContract:
    dependencies = _normalize_startup_dependencies(
        configuration.get("depends_on"),
        service_identifier=service.identifier,
    )

    namespace_target = _normalize_namespace_target(
        configuration.get("network_mode"),
        service_identifier=service.identifier,
    )

    restart_policy = _normalize_restart_policy(
        configuration.get("restart"),
        service_identifier=service.identifier,
    )

    healthcheck_configured = _normalize_healthcheck_presence(
        configuration.get("healthcheck"),
        service_identifier=service.identifier,
    )

    try:
        return ServiceStartupContract(
            service=service,
            dependencies=dependencies,
            namespace_target=namespace_target,
            restart_policy=restart_policy,
            healthcheck_configured=healthcheck_configured,
        )
    except ServiceLifecycleError as exc:
        raise DockerComposeProviderError(
            "Invalid Compose startup configuration: "
            f"{service.identifier}: {exc}",
        ) from exc


def _normalize_startup_dependencies(
    value: object,
    *,
    service_identifier: str,
) -> tuple[ServiceStartupDependency, ...]:
    if value is None:
        return ()

    dependencies: list[ServiceStartupDependency] = []

    if isinstance(value, Mapping):
        raw_entries = value.items()

        for raw_identifier, raw_options in raw_entries:
            identifier = _normalize_dependency_identifier(
                raw_identifier,
                service_identifier=service_identifier,
            )

            condition: object = (
                StartupDependencyCondition.SERVICE_STARTED
            )
            required: object = True

            if raw_options is None:
                pass
            elif isinstance(raw_options, Mapping):
                condition = raw_options.get(
                    "condition",
                    StartupDependencyCondition.SERVICE_STARTED,
                )
                required = raw_options.get(
                    "required",
                    True,
                )
            else:
                raise DockerComposeProviderError(
                    "Compose startup dependency options must be "
                    "an object or null: "
                    f"{service_identifier}: {identifier}",
                )

            try:
                dependencies.append(
                    ServiceStartupDependency(
                        identifier=identifier,
                        condition=condition,
                        required=required,
                    )
                )
            except ServiceLifecycleError as exc:
                raise DockerComposeProviderError(
                    "Invalid Compose startup dependency: "
                    f"{service_identifier}: {identifier}: {exc}",
                ) from exc

    elif (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
    ):
        for raw_identifier in value:
            identifier = _normalize_dependency_identifier(
                raw_identifier,
                service_identifier=service_identifier,
            )

            dependencies.append(
                ServiceStartupDependency(
                    identifier=identifier,
                    condition=(
                        StartupDependencyCondition.SERVICE_STARTED
                    ),
                    required=True,
                )
            )

    else:
        raise DockerComposeProviderError(
            "Compose depends_on must be an object, "
            "a collection, or null: "
            f"{service_identifier}",
        )

    return tuple(dependencies)


def _normalize_dependency_identifier(
    value: object,
    *,
    service_identifier: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DockerComposeProviderError(
            "Compose dependencies must contain "
            "non-empty service identifiers: "
            f"{service_identifier}",
        )

    return value.strip().casefold()


def _normalize_namespace_target(
    value: object,
    *,
    service_identifier: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise DockerComposeProviderError(
            "Compose network_mode must be non-empty text or null: "
            f"{service_identifier}",
        )

    normalized = value.strip()

    if not normalized.casefold().startswith("service:"):
        return None

    target = normalized.split(
        ":",
        1,
    )[1].strip()

    if not target:
        raise DockerComposeProviderError(
            "Compose service network namespace target "
            "must be non-empty: "
            f"{service_identifier}",
        )

    return target.casefold()


def _normalize_restart_policy(
    value: object,
    *,
    service_identifier: str,
) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        raise DockerComposeProviderError(
            "Compose restart policy must be "
            "non-empty text or null: "
            f"{service_identifier}",
        )

    return value.strip().casefold()


def _normalize_healthcheck_presence(
    value: object,
    *,
    service_identifier: str,
) -> bool:
    if value is None:
        return False

    if not isinstance(value, Mapping):
        raise DockerComposeProviderError(
            "Compose healthcheck must be an object or null: "
            f"{service_identifier}",
        )

    disabled = value.get(
        "disable",
        False,
    )

    if not isinstance(disabled, bool):
        raise DockerComposeProviderError(
            "Compose healthcheck disable must be a boolean: "
            f"{service_identifier}",
        )

    return not disabled


def _normalize_compose_dependencies(
    value: object,
    *,
    service_identifier: str,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, Mapping):
        raw_dependencies: object = value.keys()
    elif (
        isinstance(value, Sequence)
        and not isinstance(value, (str, bytes))
    ):
        raw_dependencies = value
    else:
        raise DockerComposeProviderError(
            "Compose depends_on must be an object, "
            "a collection, or null: "
            f"{service_identifier}",
        )

    normalized: set[str] = set()

    for dependency in raw_dependencies:
        if (
            not isinstance(dependency, str)
            or not dependency.strip()
        ):
            raise DockerComposeProviderError(
                "Compose dependencies must contain "
                "non-empty service identifiers: "
                f"{service_identifier}",
            )

        normalized.add(
            dependency.strip().casefold(),
        )

    return tuple(sorted(normalized))


def _normalize_project_name(
    value: object,
    *,
    fallback: str,
) -> str:
    if value is None:
        value = fallback

    if not isinstance(value, str) or not value.strip():
        raise DockerComposeProviderError(
            "Compose project name must be non-empty text",
        )

    return value.strip()


def _service_display_name(
    identifier: str,
) -> str:
    words = [
        word
        for word in identifier.replace("_", "-").split("-")
        if word
    ]

    if not words:
        raise DockerComposeProviderError(
            "Compose service identifier cannot produce a display name",
        )

    return " ".join(
        word[:1].upper() + word[1:]
        for word in words
    )


def _normalize_compose_file(
    value: object,
) -> Path:
    if isinstance(value, bool) or not isinstance(value, (str, Path)):
        raise DockerComposeProviderError(
            "compose_file must be a path",
        )

    path = Path(value).expanduser().resolve()

    if not path.is_file():
        raise DockerComposeProviderError(
            f"compose_file does not exist: {path}",
        )

    if path.suffix.casefold() not in {".yml", ".yaml"}:
        raise DockerComposeProviderError(
            "compose_file must use a .yml or .yaml extension",
        )

    return path


def _normalize_project_directory(
    value: object,
    *,
    compose_file: Path,
) -> Path:
    if value is None:
        return compose_file.parent

    if isinstance(value, bool) or not isinstance(value, (str, Path)):
        raise DockerComposeProviderError(
            "project_directory must be a path or null",
        )

    path = Path(value).expanduser().resolve()

    if not path.is_dir():
        raise DockerComposeProviderError(
            f"project_directory does not exist: {path}",
        )

    return path


def _required_argument(
    value: object,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DockerComposeProviderError(
            "Compose arguments must be non-empty strings",
        )

    normalized = value.strip()

    if "\x00" in normalized:
        raise DockerComposeProviderError(
            "Compose arguments must not contain null bytes",
        )

    return normalized


def _safe_diagnostic(
    stderr: object,
    stdout: object,
) -> str:
    for value in (
        stderr,
        stdout,
    ):
        if not isinstance(value, str):
            continue

        normalized = " ".join(
            value.strip().split(),
        )

        if normalized:
            return normalized[:500]

    return ""
