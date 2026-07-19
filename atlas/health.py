"""Shared Atlas health model, collectors, and report renderers."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence


class HealthStatus(str, Enum):
    """Supported Atlas health states ordered from best to worst."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


_STATUS_SCORE = {
    HealthStatus.HEALTHY: 100,
    HealthStatus.WARNING: 50,
    HealthStatus.UNKNOWN: 25,
    HealthStatus.CRITICAL: 0,
}

_STATUS_SEVERITY = {
    HealthStatus.HEALTHY: 0,
    HealthStatus.UNKNOWN: 1,
    HealthStatus.WARNING: 2,
    HealthStatus.CRITICAL: 3,
}

CommandRunner = Callable[[Sequence[str]], subprocess.CompletedProcess[str]]


def _require_text(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class HealthCheck:
    """One normalized Atlas health check result."""

    name: str
    category: str
    status: HealthStatus | str
    message: str = ""
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "name", _require_text(self.name, "name"))
        object.__setattr__(self, "category", _require_text(self.category, "category"))

        try:
            status = HealthStatus(self.status)
        except (TypeError, ValueError) as exc:
            allowed = ", ".join(item.value for item in HealthStatus)
            raise ValueError(f"status must be one of: {allowed}") from exc
        object.__setattr__(self, "status", status)

        if not isinstance(self.message, str):
            raise TypeError("message must be a string")
        if not isinstance(self.details, Mapping):
            raise TypeError("details must be a mapping")
        object.__setattr__(self, "details", dict(self.details))

    @property
    def score(self) -> int:
        return _STATUS_SCORE[self.status]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "status": self.status.value,
            "message": self.message,
            "details": dict(self.details),
        }


@dataclass(slots=True)
class HealthReport:
    """Aggregate health checks into a deterministic machine-readable report."""

    checks: list[HealthCheck] = field(default_factory=list)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )

    def __post_init__(self) -> None:
        self.checks = list(self.checks)
        if any(not isinstance(check, HealthCheck) for check in self.checks):
            raise TypeError("checks must contain HealthCheck instances")
        self.generated_at = _require_text(self.generated_at, "generated_at")

    def add(self, check: HealthCheck) -> HealthCheck:
        if not isinstance(check, HealthCheck):
            raise TypeError("check must be a HealthCheck")
        self.checks.append(check)
        return check

    def extend(self, checks: Iterable[HealthCheck]) -> None:
        for check in checks:
            self.add(check)

    @property
    def status(self) -> HealthStatus:
        if not self.checks:
            return HealthStatus.UNKNOWN
        return max(self.checks, key=lambda check: _STATUS_SEVERITY[check.status]).status

    @property
    def score(self) -> int:
        if not self.checks:
            return 0
        return round(sum(check.score for check in self.checks) / len(self.checks))

    def category_scores(self) -> dict[str, int]:
        categories: dict[str, list[int]] = {}
        for check in self.checks:
            categories.setdefault(check.category, []).append(check.score)
        return {
            category: round(sum(scores) / len(scores))
            for category, scores in sorted(categories.items())
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "generated_at": self.generated_at,
            "status": self.status.value,
            "score": self.score,
            "category_scores": self.category_scores(),
            "checks": [check.to_dict() for check in self.checks],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def _run(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command), capture_output=True, text=True, timeout=10, check=False
    )


def _command_check(
    *,
    name: str,
    category: str,
    command: Sequence[str],
    success_message: str,
    failure_message: str,
    runner: CommandRunner,
    failure_status: HealthStatus = HealthStatus.CRITICAL,
) -> HealthCheck:
    try:
        result = runner(command)
    except (OSError, subprocess.SubprocessError) as exc:
        return HealthCheck(
            name=name,
            category=category,
            status=failure_status,
            message=failure_message,
            details={"error": str(exc)},
        )

    details: dict[str, Any] = {"returncode": result.returncode}
    output = (result.stdout or result.stderr).strip()
    if output:
        details["output"] = output.splitlines()[0][:300]

    return HealthCheck(
        name=name,
        category=category,
        status=(HealthStatus.HEALTHY if result.returncode == 0 else failure_status),
        message=(success_message if result.returncode == 0 else failure_message),
        details=details,
    )


def _path_check(name: str, category: str, path: Path, *, directory: bool = False) -> HealthCheck:
    exists = path.is_dir() if directory else path.exists()
    return HealthCheck(
        name=name,
        category=category,
        status=HealthStatus.HEALTHY if exists else HealthStatus.CRITICAL,
        message=f"{name} is present" if exists else f"{name} is missing",
        details={"path": str(path)},
    )


def _writable_check(path: Path) -> HealthCheck:
    probe = path / ".atlas-health-write-test"
    try:
        probe.touch(exist_ok=False)
        probe.unlink()
    except OSError as exc:
        return HealthCheck(
            name=f"Writable: {path.name}",
            category="storage",
            status=HealthStatus.CRITICAL,
            message="Storage path is not writable",
            details={"path": str(path), "error": str(exc)},
        )
    return HealthCheck(
        name=f"Writable: {path.name}",
        category="storage",
        status=HealthStatus.HEALTHY,
        message="Storage path is writable",
        details={"path": str(path)},
    )


def collect_foundation_health(project_dir: str | Path | None = None) -> HealthReport:
    """Collect foundational Core checks."""

    configured_dir = project_dir or os.environ.get("ATLAS_PROJECT_DIR", "/opt/project-atlas")
    root = Path(configured_dir)
    report = HealthReport()
    report.add(
        HealthCheck(
            name="Python Runtime",
            category="core",
            status=HealthStatus.HEALTHY,
            message="Python runtime is available",
            details={"version": platform.python_version()},
        )
    )
    report.add(_path_check("Project Directory", "core", root, directory=True))
    report.add(_path_check("Atlas Configuration", "core", root / "config" / "atlas.conf"))
    return report


def collect_operational_health(
    *,
    project_dir: str | Path | None = None,
    storage_root: str | Path | None = None,
    media_root: str | Path | None = None,
    downloads_root: str | Path | None = None,
    runner: CommandRunner = _run,
) -> HealthReport:
    """Collect the shared operational checks used by Atlas diagnostics."""

    root = Path(project_dir or os.environ.get("ATLAS_PROJECT_DIR", "/opt/project-atlas"))
    storage = Path(storage_root or "/mnt/storage")
    media = Path(media_root or storage / "media")
    downloads = Path(downloads_root or storage / "downloads")
    report = collect_foundation_health(root)

    report.add(
        _command_check(
            name="Docker Engine",
            category="infrastructure",
            command=("docker", "info"),
            success_message="Docker daemon is reachable",
            failure_message="Docker daemon is unavailable",
            runner=runner,
        )
    )
    report.add(
        _command_check(
            name="Docker Compose",
            category="infrastructure",
            command=("docker", "compose", "version"),
            success_message="Docker Compose is available",
            failure_message="Docker Compose is unavailable",
            runner=runner,
        )
    )
    report.add(_path_check("Storage Root", "infrastructure", storage, directory=True))

    gpu = Path("/dev/dri/renderD128")
    report.add(
        HealthCheck(
            name="Intel GPU",
            category="infrastructure",
            status=HealthStatus.HEALTHY if gpu.exists() else HealthStatus.WARNING,
            message="Intel render device is available" if gpu.exists() else "Intel render device is unavailable",
            details={"path": str(gpu)},
        )
    )

    git_check = _command_check(
        name="Git Working Tree",
        category="core",
        command=("git", "-C", str(root), "status", "--porcelain"),
        success_message="Git working tree inspected",
        failure_message="Git working tree could not be inspected",
        runner=runner,
        failure_status=HealthStatus.WARNING,
    )
    if git_check.status is HealthStatus.HEALTHY and git_check.details.get("output"):
        git_check = HealthCheck(
            name="Git Working Tree",
            category="core",
            status=HealthStatus.WARNING,
            message="Git working tree has uncommitted changes",
            details=git_check.details,
        )
    elif git_check.status is HealthStatus.HEALTHY:
        git_check = HealthCheck(
            name="Git Working Tree",
            category="core",
            status=HealthStatus.HEALTHY,
            message="Git working tree is clean",
            details=git_check.details,
        )
    report.add(git_check)

    for service in (
        "jellyfin", "jellyseerr", "prowlarr", "sonarr", "sonarr-anime",
        "radarr", "radarr-anime", "gluetun", "qbittorrent", "homepage",
    ):
        report.add(
            _command_check(
                name=service,
                category="services",
                command=("docker", "inspect", "-f", "{{.State.Running}}", service),
                success_message=f"{service} container is running",
                failure_message=f"{service} container is not running",
                runner=runner,
            )
        )

    for path in (
        media / "Movies",
        media / "TV",
        media / "Anime Movies",
        media / "Anime TV",
        downloads,
    ):
        report.add(_writable_check(path))

    for relative in (
        "VERSION", "CHARTER.md", "ROADMAP.md", "CHANGELOG.md",
        "docs/BUILD_LOG.md", "docs/MATURITY.md", "docs/INDEXERS.md",
    ):
        report.add(_path_check(relative, "project", root / relative))

    return report


def render_text(report: HealthReport) -> str:
    """Render a concise human-readable diagnostic report."""

    symbols = {
        HealthStatus.HEALTHY: "OK",
        HealthStatus.WARNING: "WARN",
        HealthStatus.CRITICAL: "FAIL",
        HealthStatus.UNKNOWN: "UNKNOWN",
    }
    grouped: dict[str, list[HealthCheck]] = {}
    for check in report.checks:
        grouped.setdefault(check.category, []).append(check)

    lines = ["Project Atlas", "Simplicity Meets Ingenuity", "", "Atlas Health Diagnostics", ""]
    for category, checks in grouped.items():
        lines.extend((category.replace("_", " ").title(), "-" * len(category)))
        for check in checks:
            lines.append(f"  {symbols[check.status]:<7} {check.name}: {check.message}")
        lines.append("")

    lines.append(f"Overall Status: {report.status.value.upper()}")
    lines.append(f"Overall Score:  {report.score}%")
    for category, score in report.category_scores().items():
        lines.append(f"  {category.replace('_', ' ').title():<16} {score}%")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Collect and render Atlas health diagnostics")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument("--format", choices=("json", "text"), default="json")
    parser.add_argument("--project-dir", help="override the Atlas project directory")
    parser.add_argument("--storage-root", help="override the Atlas storage root")
    parser.add_argument("--media-root", help="override the Atlas media root")
    parser.add_argument("--downloads-root", help="override the Atlas downloads root")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = collect_operational_health(
        project_dir=args.project_dir,
        storage_root=args.storage_root,
        media_root=args.media_root,
        downloads_root=args.downloads_root,
    )
    print(render_text(report) if args.format == "text" else report.to_json(indent=None if args.compact else 2))
    return 0 if report.status is not HealthStatus.CRITICAL else 1


if __name__ == "__main__":
    raise SystemExit(main())
