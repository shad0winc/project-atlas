"""Read-only system collector for Atlas Operations."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import os
from pathlib import Path
import platform
import socket
from typing import Protocol, TypeVar

from atlas.operations.models import (
    OperationFinding,
    OperationsSection,
    OperationsSectionId,
    OperationsSeverity,
    OperationsStatus,
)

from .base import OperationsCollector


_T = TypeVar("_T")


class SystemProvider(Protocol):
    """Provider contract supplying read-only host information."""

    def hostname(self) -> str:
        """Return the system hostname."""

    def operating_system(self) -> str:
        """Return the operating-system identity."""

    def kernel_release(self) -> str:
        """Return the running kernel release."""

    def uptime_seconds(self) -> float:
        """Return system uptime in seconds."""

    def cpu_count(self) -> int:
        """Return the logical CPU count."""

    def cpu_model(self) -> str:
        """Return the CPU model."""

    def memory_bytes(self) -> tuple[int, int, int]:
        """Return total, used, and available memory bytes."""


@dataclass(frozen=True, slots=True)
class HostSystemProvider:
    """Linux host provider using standard read-only interfaces."""

    proc_root: Path = Path("/proc")
    os_release_path: Path = Path("/etc/os-release")

    def hostname(self) -> str:
        return socket.gethostname().strip()

    def operating_system(self) -> str:
        values = _parse_key_value_file(self.os_release_path)

        return (
            values.get("PRETTY_NAME")
            or values.get("NAME")
            or platform.system()
        ).strip()

    def kernel_release(self) -> str:
        return platform.release().strip()

    def uptime_seconds(self) -> float:
        value = (
            self.proc_root / "uptime"
        ).read_text(encoding="utf-8").split()[0]

        uptime = float(value)

        if uptime < 0:
            raise ValueError("uptime must not be negative")

        return uptime

    def cpu_count(self) -> int:
        count = os.cpu_count()

        if count is None or count <= 0:
            raise ValueError("CPU count is unavailable")

        return count

    def cpu_model(self) -> str:
        cpuinfo = (
            self.proc_root / "cpuinfo"
        ).read_text(encoding="utf-8")

        candidates: dict[str, str] = {}

        for line in cpuinfo.splitlines():
            key, separator, value = line.partition(":")

            if not separator:
                continue

            normalized_key = key.strip().lower()
            normalized_value = value.strip()

            if (
                normalized_key
                in {
                    "model name",
                    "hardware",
                    "cpu model",
                }
                and normalized_value
                and normalized_key not in candidates
            ):
                candidates[normalized_key] = normalized_value

        for key in (
            "model name",
            "hardware",
            "cpu model",
        ):
            if key in candidates:
                return candidates[key]

        processor = platform.processor().strip()

        if processor and not processor.isdigit():
            return processor

        raise ValueError("CPU model is unavailable")

    def memory_bytes(self) -> tuple[int, int, int]:
        values: dict[str, int] = {}

        text = (
            self.proc_root / "meminfo"
        ).read_text(encoding="utf-8")

        for line in text.splitlines():
            key, separator, raw_value = line.partition(":")

            if not separator:
                continue

            parts = raw_value.strip().split()

            if not parts:
                continue

            values[key.strip()] = int(parts[0]) * 1024

        total = values.get("MemTotal")
        available = values.get("MemAvailable")

        if total is None or available is None:
            raise ValueError(
                "memory totals are unavailable",
            )

        used = total - available

        if total <= 0 or available < 0 or used < 0:
            raise ValueError(
                "memory values are invalid",
            )

        return total, used, available


@dataclass(frozen=True, slots=True)
class SystemCollector(OperationsCollector):
    """Collect normalized host-system Operations findings."""

    section_id: OperationsSectionId | str = OperationsSectionId.SYSTEM
    name: str = "System"
    timeout_seconds: float = 10.0
    description: str | None = (
        "Host operating-system and resource information"
    )
    provider: SystemProvider = field(
        default_factory=HostSystemProvider,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        super(SystemCollector, self).__post_init__()

        if self.section_id is not OperationsSectionId.SYSTEM:
            raise ValueError(
                "SystemCollector must use the system section",
            )

    def collect(self) -> OperationsSection:
        """Collect one deterministic system section."""

        findings = (
            self._text_finding(
                identifier="system.hostname",
                name="Hostname",
                source=self.provider.hostname,
                label="Hostname",
            ),
            self._text_finding(
                identifier="system.operating-system",
                name="Operating System",
                source=self.provider.operating_system,
                label="Operating system",
            ),
            self._text_finding(
                identifier="system.kernel",
                name="Kernel",
                source=self.provider.kernel_release,
                label="Kernel",
            ),
            self._uptime_finding(),
            self._cpu_finding(),
            self._memory_finding(),
        )

        return OperationsSection(
            identifier=self.section_id,
            name=self.name,
            description=self.description,
            findings=findings,
        )

    def _text_finding(
        self,
        *,
        identifier: str,
        name: str,
        source: Callable[[], str],
        label: str,
    ) -> OperationFinding:
        try:
            value = source().strip()

            if not value:
                raise ValueError(
                    f"{label.lower()} is empty",
                )

            return _healthy_finding(
                identifier=identifier,
                name=name,
                message=f"{label}: {value}",
                metadata={"value": value},
            )
        except Exception as exc:
            return _unknown_finding(
                identifier=identifier,
                name=name,
                message=f"{label} is unavailable",
                error=exc,
            )

    def _uptime_finding(self) -> OperationFinding:
        try:
            seconds = float(
                self.provider.uptime_seconds()
            )

            if seconds < 0:
                raise ValueError(
                    "uptime must not be negative",
                )

            return _healthy_finding(
                identifier="system.uptime",
                name="Uptime",
                message=(
                    "System uptime: "
                    f"{_format_duration(seconds)}"
                ),
                metadata={
                    "seconds": round(seconds, 3),
                },
            )
        except Exception as exc:
            return _unknown_finding(
                identifier="system.uptime",
                name="Uptime",
                message="System uptime is unavailable",
                error=exc,
            )

    def _cpu_finding(self) -> OperationFinding:
        try:
            count = int(self.provider.cpu_count())
            model = self.provider.cpu_model().strip()

            if count <= 0:
                raise ValueError(
                    "CPU count must be positive",
                )

            if not model:
                raise ValueError(
                    "CPU model is empty",
                )

            return _healthy_finding(
                identifier="system.cpu",
                name="CPU",
                message=f"{model} ({count} logical CPUs)",
                metadata={
                    "logical_count": count,
                    "model": model,
                },
            )
        except Exception as exc:
            return _unknown_finding(
                identifier="system.cpu",
                name="CPU",
                message="CPU information is unavailable",
                error=exc,
            )

    def _memory_finding(self) -> OperationFinding:
        try:
            total, used, available = (
                self.provider.memory_bytes()
            )

            if (
                total <= 0
                or used < 0
                or available < 0
                or used + available != total
            ):
                raise ValueError(
                    "memory values are inconsistent",
                )

            percent_used = round(
                used / total * 100,
                2,
            )

            return _healthy_finding(
                identifier="system.memory",
                name="Memory",
                message=(
                    f"Memory usage: {percent_used:.2f}%"
                ),
                metadata={
                    "available_bytes": available,
                    "percent_used": percent_used,
                    "total_bytes": total,
                    "used_bytes": used,
                },
            )
        except Exception as exc:
            return _unknown_finding(
                identifier="system.memory",
                name="Memory",
                message="Memory information is unavailable",
                error=exc,
            )


def _healthy_finding(
    *,
    identifier: str,
    name: str,
    message: str,
    metadata: dict[str, object],
) -> OperationFinding:
    return OperationFinding(
        identifier=identifier,
        name=name,
        status=OperationsStatus.HEALTHY,
        severity=OperationsSeverity.INFO,
        message=message,
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
            "error": str(error).strip()
            or error.__class__.__name__,
        },
    )


def _parse_key_value_file(
    path: Path,
) -> dict[str, str]:
    values: dict[str, str] = {}

    for line in path.read_text(
        encoding="utf-8",
    ).splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        key, separator, value = stripped.partition("=")

        if not separator:
            continue

        values[key.strip()] = (
            value.strip()
            .strip('"')
            .strip("'")
        )

    return values


def _format_duration(seconds: float) -> str:
    total_seconds = int(seconds)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, remaining_seconds = divmod(
        remainder,
        60,
    )

    parts: list[str] = []

    if days:
        parts.append(f"{days}d")

    if hours or days:
        parts.append(f"{hours}h")

    if minutes or hours or days:
        parts.append(f"{minutes}m")

    parts.append(f"{remaining_seconds}s")

    return " ".join(parts)
