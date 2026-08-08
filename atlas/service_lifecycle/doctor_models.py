"""Normalized Service Doctor contracts for Atlas Service Lifecycle."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any

from .models import ServiceLifecycleError


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)


class DoctorSeverity(str, Enum):
    """Normalized severity for one Service Doctor finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DoctorCategory(str, Enum):
    """Normalized diagnostic category for Service Doctor findings."""

    HEALTH = "health"
    RUNTIME = "runtime"
    DEPENDENCY = "dependency"
    CONFIGURATION = "configuration"
    UPDATE = "update"
    OBSERVABILITY = "observability"


@dataclass(frozen=True)
class DoctorFinding:
    """One normalized, explainable Service Doctor finding."""

    identifier: str
    severity: DoctorSeverity
    category: DoctorCategory
    code: str
    message: str
    service_identifier: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "identifier",
            _required_identifier(self.identifier, "identifier"),
        )
        object.__setattr__(
            self,
            "severity",
            _normalize_enum(
                self.severity,
                DoctorSeverity,
                "severity",
            ),
        )
        object.__setattr__(
            self,
            "category",
            _normalize_enum(
                self.category,
                DoctorCategory,
                "category",
            ),
        )
        object.__setattr__(
            self,
            "code",
            _required_identifier(self.code, "code"),
        )
        object.__setattr__(
            self,
            "message",
            _required_text(self.message, "message"),
        )
        object.__setattr__(
            self,
            "service_identifier",
            _optional_identifier(
                self.service_identifier,
                "service_identifier",
            ),
        )

        if not isinstance(self.details, Mapping):
            raise ServiceLifecycleError("details must be an object")

        object.__setattr__(self, "details", dict(self.details))
        object.__setattr__(
            self,
            "created_at",
            _required_timestamp(self.created_at, "created_at"),
        )

    @property
    def requires_attention(self) -> bool:
        """Return whether the finding requires administrator attention."""

        return self.severity in {
            DoctorSeverity.WARNING,
            DoctorSeverity.ERROR,
            DoctorSeverity.CRITICAL,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized finding contract."""

        return {
            "identifier": self.identifier,
            "severity": self.severity.value,
            "category": self.category.value,
            "code": self.code,
            "message": self.message,
            "service_identifier": self.service_identifier,
            "requires_attention": self.requires_attention,
            "details": dict(self.details),
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class DoctorReport:
    """Normalized read-only diagnostics report for Atlas infrastructure."""

    findings: tuple[DoctorFinding, ...] = ()
    provider: str = "unknown"
    evaluated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "findings",
            _normalize_findings(self.findings),
        )
        object.__setattr__(
            self,
            "provider",
            _required_identifier(self.provider, "provider"),
        )
        object.__setattr__(
            self,
            "evaluated_at",
            _required_timestamp(self.evaluated_at, "evaluated_at"),
        )

        identifiers = tuple(
            finding.identifier
            for finding in self.findings
        )
        if len(identifiers) != len(set(identifiers)):
            raise ServiceLifecycleError(
                "doctor findings must have unique identifiers",
            )

    @property
    def status(self) -> str:
        """Return the highest normalized report status."""

        severities = {finding.severity for finding in self.findings}
        if DoctorSeverity.CRITICAL in severities:
            return "critical"
        if DoctorSeverity.ERROR in severities:
            return "unhealthy"
        if DoctorSeverity.WARNING in severities:
            return "degraded"
        return "healthy"

    @property
    def requires_attention(self) -> bool:
        """Return whether any finding requires administrator attention."""

        return any(finding.requires_attention for finding in self.findings)

    @property
    def counts(self) -> dict[str, int]:
        """Return deterministic finding counts by severity."""

        counts = {
            severity.value: 0
            for severity in DoctorSeverity
        }
        for finding in self.findings:
            counts[finding.severity.value] += 1
        return counts

    @property
    def attention(self) -> tuple[DoctorFinding, ...]:
        """Return findings that require administrator attention."""

        return tuple(
            finding
            for finding in self.findings
            if finding.requires_attention
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized Service Doctor report."""

        return {
            "status": self.status,
            "provider": self.provider,
            "total_findings": len(self.findings),
            "counts": self.counts,
            "requires_attention": self.requires_attention,
            "attention": [
                finding.to_dict()
                for finding in self.attention
            ],
            "findings": [
                finding.to_dict()
                for finding in self.findings
            ],
            "evaluated_at": self.evaluated_at,
        }


def _normalize_findings(value: object) -> tuple[DoctorFinding, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Iterable):
        raise ServiceLifecycleError(
            "findings must be a collection of DoctorFinding objects",
        )

    findings = tuple(value)
    if any(not isinstance(item, DoctorFinding) for item in findings):
        raise ServiceLifecycleError(
            "findings must contain DoctorFinding objects",
        )

    return tuple(
        sorted(
            findings,
            key=lambda finding: (
                _severity_rank(finding.severity),
                finding.service_identifier or "",
                finding.identifier,
            ),
        )
    )


def _severity_rank(severity: DoctorSeverity) -> int:
    return {
        DoctorSeverity.CRITICAL: 0,
        DoctorSeverity.ERROR: 1,
        DoctorSeverity.WARNING: 2,
        DoctorSeverity.INFO: 3,
    }[severity]


def _normalize_enum(
    value: object,
    enum_type: type[Enum],
    field_name: str,
) -> Enum:
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be non-empty text",
        )

    normalized = value.strip().casefold()
    try:
        return enum_type(normalized)
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"invalid {field_name}: {normalized}",
        ) from exc


def _required_text(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be non-empty text",
        )
    return value.strip()


def _required_identifier(value: object, field_name: str) -> str:
    normalized = _required_text(value, field_name).casefold()
    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ServiceLifecycleError(
            f"invalid {field_name}: {normalized}",
        )
    return normalized


def _optional_identifier(value: object, field_name: str) -> str | None:
    if value is None:
        return None
    return _required_identifier(value, field_name)


def _required_timestamp(value: object, field_name: str) -> str:
    normalized = _required_text(value, field_name)
    try:
        parsed = datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise ServiceLifecycleError(
            f"{field_name} must include a timezone",
        )

    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
