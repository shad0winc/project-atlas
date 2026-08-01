"""Read-only Docker Compose foundation for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from json import JSONDecodeError, loads
from pathlib import Path
import subprocess
from typing import Any

from atlas.service_lifecycle.models import (
    ManagedService,
    ServiceHealth,
    ServiceLifecycleError,
    ServiceRuntime,
)
from atlas.service_lifecycle.provider import ServiceLifecycleProvider


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
        """Return one service's runtime state."""

        raise DockerComposeProviderError(
            "Docker Compose runtime inspection is not implemented yet",
        )

    def inspect_health(
        self,
        identifier: str,
    ) -> ServiceHealth:
        """Return one service's normalized health evaluation."""

        raise DockerComposeProviderError(
            "Docker Compose health inspection is not implemented yet",
        )

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
