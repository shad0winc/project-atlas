"""Shared health data model and foundational Atlas health report."""

from __future__ import annotations

import argparse
import json
import os
import platform
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


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


def collect_foundation_health(project_dir: str | Path | None = None) -> HealthReport:
    """Collect low-risk foundational checks without replacing doctor or verify."""

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

    if root.is_dir():
        report.add(
            HealthCheck(
                name="Project Directory",
                category="core",
                status=HealthStatus.HEALTHY,
                message="Atlas project directory is accessible",
                details={"path": str(root)},
            )
        )
    else:
        report.add(
            HealthCheck(
                name="Project Directory",
                category="core",
                status=HealthStatus.CRITICAL,
                message="Atlas project directory is missing",
                details={"path": str(root)},
            )
        )

    config_file = root / "config" / "atlas.conf"
    report.add(
        HealthCheck(
            name="Atlas Configuration",
            category="core",
            status=(HealthStatus.HEALTHY if config_file.is_file() else HealthStatus.CRITICAL),
            message=(
                "Atlas configuration file is present"
                if config_file.is_file()
                else "Atlas configuration file is missing"
            ),
            details={"path": str(config_file)},
        )
    )

    return report


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Emit the foundational Atlas health report")
    parser.add_argument("--compact", action="store_true", help="emit compact JSON")
    parser.add_argument("--project-dir", help="override the Atlas project directory")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = collect_foundation_health(args.project_dir)
    print(report.to_json(indent=None if args.compact else 2))
    return 0 if report.status is not HealthStatus.CRITICAL else 1


if __name__ == "__main__":
    raise SystemExit(main())
