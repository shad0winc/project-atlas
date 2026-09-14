"""Runtime metadata contracts for Project Atlas Operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
from pathlib import Path
import subprocess
from typing import Any, Protocol

from .collectors import HostSystemProvider
from .models import OperationsReport


class OperationsContextError(RuntimeError):
    """Raised when Operations runtime context cannot be collected."""


@dataclass(frozen=True, slots=True)
class OperationsContext:
    """Normalized metadata required to construct an Operations report."""

    report_id: str
    hostname: str
    atlas_version: str
    git_commit: str
    generated_at: str

    def __post_init__(self) -> None:
        try:
            normalized = OperationsReport(
                report_id=self.report_id,
                hostname=self.hostname,
                atlas_version=self.atlas_version,
                git_commit=self.git_commit,
                generated_at=self.generated_at,
            )
        except Exception as exc:
            raise OperationsContextError(
                f"invalid Operations runtime context: {exc}",
            ) from exc

        object.__setattr__(
            self,
            "report_id",
            normalized.report_id,
        )
        object.__setattr__(
            self,
            "hostname",
            normalized.hostname,
        )
        object.__setattr__(
            self,
            "atlas_version",
            normalized.atlas_version,
        )
        object.__setattr__(
            self,
            "git_commit",
            normalized.git_commit,
        )
        object.__setattr__(
            self,
            "generated_at",
            normalized.generated_at,
        )

    def to_dict(self) -> dict[str, str]:
        """Serialize the normalized runtime context."""

        return {
            "report_id": self.report_id,
            "hostname": self.hostname,
            "atlas_version": self.atlas_version,
            "git_commit": self.git_commit,
            "generated_at": self.generated_at,
        }


class OperationsContextProvider(Protocol):
    """Provider contract for Operations report runtime metadata."""

    def context(
        self,
        *,
        report_id: str = "operations-report",
    ) -> OperationsContext:
        """Return normalized Operations report metadata."""


class HostnameProvider(Protocol):
    """Minimal hostname source consumed by the context provider."""

    def hostname(self) -> str:
        """Return the current host name."""


Clock = Callable[[], datetime]
CommandExecutor = Callable[
    ...,
    subprocess.CompletedProcess[str],
]


def _default_project_root() -> Path:
    """Return the configured Atlas project root."""

    configured = os.environ.get(
        "ATLAS_PROJECT_DIR",
    )

    if configured is None:
        return Path("/opt/project-atlas")

    normalized = configured.strip()

    if not normalized:
        raise OperationsContextError(
            "ATLAS_PROJECT_DIR cannot be empty",
        )

    return Path(normalized)


@dataclass(frozen=True, slots=True)
class HostOperationsContextProvider:
    """Collect Operations metadata from the local Atlas installation."""

    project_root: Path = field(
        default_factory=_default_project_root,
    )
    hostname_provider: HostnameProvider = field(
        default_factory=HostSystemProvider,
        repr=False,
        compare=False,
    )
    clock: Clock = field(
        default=lambda: datetime.now(timezone.utc),
        repr=False,
        compare=False,
    )
    executor: CommandExecutor = field(
        default=subprocess.run,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        root = Path(self.project_root)

        if not callable(
            getattr(self.hostname_provider, "hostname", None)
        ):
            raise OperationsContextError(
                "hostname_provider must define hostname()",
            )

        if not callable(self.clock):
            raise OperationsContextError(
                "clock must be callable",
            )

        if not callable(self.executor):
            raise OperationsContextError(
                "executor must be callable",
            )

        object.__setattr__(
            self,
            "project_root",
            root,
        )

    def context(
        self,
        *,
        report_id: str = "operations-report",
    ) -> OperationsContext:
        """Collect and normalize local Atlas runtime metadata."""

        hostname = self._hostname()
        atlas_version = self._atlas_version()
        git_commit = self._git_commit()
        generated_at = self._generated_at()

        return OperationsContext(
            report_id=report_id,
            hostname=hostname,
            atlas_version=atlas_version,
            git_commit=git_commit,
            generated_at=generated_at,
        )

    def _hostname(self) -> str:
        try:
            hostname = self.hostname_provider.hostname()
        except Exception as exc:
            raise OperationsContextError(
                f"hostname could not be collected: {exc}",
            ) from exc

        return hostname

    def _atlas_version(self) -> str:
        version_path = self.project_root / "VERSION"

        try:
            version = version_path.read_text(
                encoding="utf-8",
            ).strip()
        except OSError as exc:
            raise OperationsContextError(
                f"Atlas version could not be read from "
                f"{version_path}: {exc}",
            ) from exc

        if not version:
            raise OperationsContextError(
                f"Atlas version file is empty: {version_path}",
            )

        return version

    def _git_commit(self) -> str:
        try:
            completed = self.executor(
                [
                    "git",
                    "rev-parse",
                    "--short",
                    "HEAD",
                ],
                cwd=self.project_root,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as exc:
            deployment_commit = (
                self._immutable_deployment_commit()
            )

            if deployment_commit is not None:
                return deployment_commit

            raise OperationsContextError(
                "Git executable is unavailable",
            ) from exc
        except OSError as exc:
            raise OperationsContextError(
                f"Git commit could not be collected: {exc}",
            ) from exc

        if not isinstance(
            completed,
            subprocess.CompletedProcess,
        ):
            raise OperationsContextError(
                "Git executor returned an invalid result",
            )

        if completed.returncode != 0:
            deployment_commit = (
                self._immutable_deployment_commit()
            )

            if deployment_commit is not None:
                return deployment_commit

            detail = (
                (completed.stderr or "").strip()
                or (completed.stdout or "").strip()
                or "unknown Git error"
            )

            raise OperationsContextError(
                "Git commit discovery failed with exit code "
                f"{completed.returncode}: {detail}",
            )

        commit = (completed.stdout or "").strip()

        if not commit:
            raise OperationsContextError(
                "Git commit discovery returned empty output",
            )

        return commit

    def _immutable_deployment_commit(
        self,
    ) -> str | None:
        deployment_marker = (
            self.project_root
            / ".atlas-deployment-id"
        )

        if not deployment_marker.is_file():
            return None

        try:
            deployment_id = (
                deployment_marker.read_text(
                    encoding="utf-8",
                ).strip()
            )
        except OSError as exc:
            raise OperationsContextError(
                "Atlas immutable deployment identity "
                f"could not be read: {exc}",
            ) from exc

        if (
            not deployment_id
            or "/" in deployment_id
            or ".." in deployment_id
        ):
            raise OperationsContextError(
                "Atlas immutable deployment identity "
                "is invalid",
            )

        configured_runtime_root = os.environ.get(
            "ATLAS_RUNTIME_CONFIG_DIR",
            "/mnt/storage/configs/atlas",
        ).strip()

        if not configured_runtime_root:
            raise OperationsContextError(
                "ATLAS_RUNTIME_CONFIG_DIR cannot be empty",
            )

        deployment_root = (
            Path(configured_runtime_root)
            / "deployments"
        )

        current_path = deployment_root / "current"
        record = (
            deployment_root
            / "records"
            / deployment_id
        )
        status_path = record / "status"
        metadata_path = record / "metadata"

        try:
            current = current_path.read_text(
                encoding="utf-8",
            ).strip()

            status = status_path.read_text(
                encoding="utf-8",
            ).strip()

            metadata_lines = metadata_path.read_text(
                encoding="utf-8",
            ).splitlines()
        except OSError as exc:
            raise OperationsContextError(
                "Atlas immutable deployment provenance "
                f"could not be read: {exc}",
            ) from exc

        if current != deployment_id:
            raise OperationsContextError(
                "Atlas immutable deployment provenance "
                "does not match the current deployment",
            )

        if status != "verified":
            raise OperationsContextError(
                "Atlas immutable deployment provenance "
                "is not verified",
            )

        metadata: dict[str, str] = {}

        for line in metadata_lines:
            key, separator, value = line.partition("=")

            if not separator:
                continue

            metadata[key.strip()] = value.strip()

        target_commit = metadata.get(
            "target_commit",
            "",
        )

        if (
            len(target_commit) != 40
            or any(
                character not in "0123456789abcdefABCDEF"
                for character in target_commit
            )
        ):
            raise OperationsContextError(
                "Atlas immutable deployment target commit "
                "is invalid",
            )

        return target_commit[:8]

    def _generated_at(self) -> str:
        try:
            value = self.clock()
        except Exception as exc:
            raise OperationsContextError(
                f"Operations clock failed: {exc}",
            ) from exc

        if not isinstance(value, datetime):
            raise OperationsContextError(
                "clock must return a datetime",
            )

        if value.tzinfo is None:
            raise OperationsContextError(
                "clock must return a timezone-aware datetime",
            )

        return (
            value.astimezone(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
