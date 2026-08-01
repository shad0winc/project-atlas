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
        """Return configured Compose services.

        Service discovery will be implemented in the next provider increment.
        """

        raise DockerComposeProviderError(
            "Docker Compose service discovery is not implemented yet",
        )

    def inspect_service(
        self,
        identifier: str,
    ) -> ManagedService:
        """Return one configured Compose service."""

        raise DockerComposeProviderError(
            "Docker Compose service inspection is not implemented yet",
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
