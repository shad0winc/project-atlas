"""Runtime metadata contracts for Project Atlas Operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
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


@dataclass(frozen=True, slots=True)
class HostOperationsContextProvider:
    """Collect Operations metadata from the local Atlas installation."""

    project_root: Path = Path("/opt/project-atlas")
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
