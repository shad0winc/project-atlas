"""Read-only Docker command adapter for Atlas Operations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
import json
import math
import re
import subprocess
from typing import Any


_CONTAINER_IDENTITY_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$",
)


class DockerCollectorError(RuntimeError):
    """Raised when the Docker command adapter cannot complete."""


class DockerCommandRunner:
    """Read-only boundary between Atlas Operations and the Docker CLI."""

    def __init__(
        self,
        *,
        timeout_seconds: float = 10.0,
        executor: Callable[..., subprocess.CompletedProcess[str]] = (
            subprocess.run
        ),
    ) -> None:
        if (
            isinstance(timeout_seconds, bool)
            or not isinstance(timeout_seconds, (int, float))
        ):
            raise DockerCollectorError(
                "timeout_seconds must be a number",
            )

        normalized_timeout = float(timeout_seconds)

        if (
            not math.isfinite(normalized_timeout)
            or normalized_timeout <= 0
        ):
            raise DockerCollectorError(
                "timeout_seconds must be finite and greater than zero",
            )

        if not callable(executor):
            raise DockerCollectorError(
                "executor must be callable",
            )

        self.timeout_seconds = normalized_timeout
        self._executor = executor

    def _run_json(
        self,
        *arguments: str,
    ) -> Any:
        """Execute a read-only Docker command and return parsed JSON."""

        command: Sequence[str] = (
            "docker",
            *arguments,
        )

        try:
            completed = self._executor(
                list(command),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DockerCollectorError(
                "Docker CLI is not installed or not available",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerCollectorError(
                "Docker command timed out after "
                f"{self.timeout_seconds:g} seconds",
            ) from exc
        except OSError as exc:
            raise DockerCollectorError(
                f"Docker command could not be executed: {exc}",
            ) from exc

        if not isinstance(
            completed,
            subprocess.CompletedProcess,
        ):
            raise DockerCollectorError(
                "Docker executor returned an invalid result",
            )

        if completed.returncode != 0:
            detail = (
                (completed.stderr or "").strip()
                or (completed.stdout or "").strip()
                or "unknown Docker error"
            )

            raise DockerCollectorError(
                "Docker command failed with exit code "
                f"{completed.returncode}: {detail}",
            )

        output = (completed.stdout or "").strip()

        if not output:
            raise DockerCollectorError(
                "Docker command returned empty output",
            )

        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise DockerCollectorError(
                "Docker command returned invalid JSON",
            ) from exc


    def _run_json_lines(
        self,
        *arguments: str,
    ) -> list[dict[str, Any]]:
        """Execute Docker and parse one JSON object per output line."""

        command: Sequence[str] = (
            "docker",
            *arguments,
        )

        try:
            completed = self._executor(
                list(command),
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise DockerCollectorError(
                "Docker CLI is not installed or not available",
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerCollectorError(
                "Docker command timed out after "
                f"{self.timeout_seconds:g} seconds",
            ) from exc
        except OSError as exc:
            raise DockerCollectorError(
                f"Docker command could not be executed: {exc}",
            ) from exc

        if not isinstance(
            completed,
            subprocess.CompletedProcess,
        ):
            raise DockerCollectorError(
                "Docker executor returned an invalid result",
            )

        if completed.returncode != 0:
            detail = (
                (completed.stderr or "").strip()
                or (completed.stdout or "").strip()
                or "unknown Docker error"
            )

            raise DockerCollectorError(
                "Docker command failed with exit code "
                f"{completed.returncode}: {detail}",
            )

        output = (completed.stdout or "").strip()

        if not output:
            return []

        records: list[dict[str, Any]] = []

        for line_number, line in enumerate(
            output.splitlines(),
            start=1,
        ):
            stripped = line.strip()

            if not stripped:
                continue

            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise DockerCollectorError(
                    "Docker command returned invalid JSON "
                    f"on line {line_number}",
                ) from exc

            if not isinstance(payload, dict):
                raise DockerCollectorError(
                    "Docker JSON-lines output must contain "
                    f"objects; line {line_number} was "
                    f"{type(payload).__name__}",
                )

            records.append(payload)

        return records


    def version(self) -> dict[str, Any]:
        """Return normalized Docker version information."""

        payload = self._run_json(
            "version",
            "--format",
            "{{json .}}",
        )

        if not isinstance(payload, dict):
            raise DockerCollectorError(
                "Docker version output must be an object",
            )

        return payload

    def info(self) -> dict[str, Any]:
        """Return normalized Docker daemon information."""

        payload = self._run_json(
            "info",
            "--format",
            "{{json .}}",
        )

        if not isinstance(payload, dict):
            raise DockerCollectorError(
                "Docker info output must be an object",
            )

        return payload

    def ps(self) -> list[dict[str, Any]]:
        """Return normalized Docker container summaries."""

        return self._run_json_lines(
            "ps",
            "-a",
            "--no-trunc",
            "--format",
            "{{json .}}",
        )

    def inspect(self, container: str) -> dict[str, Any]:
        """Return normalized inspection data for one container."""

        identity = _required_container_identity(container)

        payload = self._run_json(
            "inspect",
            "--format",
            "{{json .}}",
            identity,
        )

        if not isinstance(payload, dict):
            raise DockerCollectorError(
                "Docker inspect output must be an object",
            )

        return payload


def _required_container_identity(value: object) -> str:
    """Normalize and validate a Docker container name or identifier."""

    if not isinstance(value, str):
        raise DockerCollectorError(
            "container identity must be text",
        )

    normalized = value.strip()

    if not normalized:
        raise DockerCollectorError(
            "container identity is required",
        )

    if not _CONTAINER_IDENTITY_PATTERN.fullmatch(normalized):
        raise DockerCollectorError(
            "container identity contains unsupported characters",
        )

    return normalized
