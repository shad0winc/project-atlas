"""Immutable startup-policy evaluation contracts."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import re
from types import MappingProxyType
from typing import Any

from .models import ServiceLifecycleError


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._-]*[a-z0-9])?$",
)

_SEVERITY_ORDER: dict["StartupPolicySeverity", int] = {}


class StartupPolicySeverity(str, Enum):
    """Normalized severity for one startup-policy finding."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


_SEVERITY_ORDER.update(
    {
        StartupPolicySeverity.CRITICAL: 0,
        StartupPolicySeverity.ERROR: 1,
        StartupPolicySeverity.WARNING: 2,
        StartupPolicySeverity.INFO: 3,
    }
)


@dataclass(frozen=True, slots=True)
class StartupPolicyFinding:
    """One normalized and explainable startup-policy finding."""

    identifier: str
    code: str
    severity: StartupPolicySeverity | str
    message: str
    service_identifier: str | None = None
    recommendation: str | None = None
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier = _required_identifier(
            self.identifier,
            "identifier",
        )
        code = _required_identifier(
            self.code,
            "code",
        )
        severity = _normalize_severity(
            self.severity,
            "severity",
        )
        message = _required_text(
            self.message,
            "message",
        )
        service_identifier = _optional_identifier(
            self.service_identifier,
            "service_identifier",
        )
        recommendation = _optional_text(
            self.recommendation,
            "recommendation",
        )
        details = _normalize_details(
            self.details,
            "details",
        )

        object.__setattr__(
            self,
            "identifier",
            identifier,
        )
        object.__setattr__(
            self,
            "code",
            code,
        )
        object.__setattr__(
            self,
            "severity",
            severity,
        )
        object.__setattr__(
            self,
            "message",
            message,
        )
        object.__setattr__(
            self,
            "service_identifier",
            service_identifier,
        )
        object.__setattr__(
            self,
            "recommendation",
            recommendation,
        )
        object.__setattr__(
            self,
            "details",
            details,
        )

    @property
    def requires_attention(self) -> bool:
        """Return whether this finding needs administrator attention."""

        return self.severity in {
            StartupPolicySeverity.WARNING,
            StartupPolicySeverity.ERROR,
            StartupPolicySeverity.CRITICAL,
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized startup-policy finding."""

        return {
            "identifier": self.identifier,
            "code": self.code,
            "severity": self.severity.value,
            "message": self.message,
            "service_identifier": self.service_identifier,
            "recommendation": self.recommendation,
            "requires_attention": self.requires_attention,
            "details": dict(self.details),
        }


@dataclass(frozen=True, slots=True)
class StartupPolicyReport:
    """Deterministic aggregate startup-policy evaluation."""

    findings: tuple[StartupPolicyFinding, ...] = ()
    provider: str = "docker-compose"
    evaluated_at: str = field(
        default_factory=lambda: _now_timestamp()
    )

    def __post_init__(self) -> None:
        findings = _normalize_findings(
            self.findings,
        )
        provider = _required_identifier(
            self.provider,
            "provider",
        )
        evaluated_at = _required_timestamp(
            self.evaluated_at,
            "evaluated_at",
        )

        identifiers = tuple(
            finding.identifier
            for finding in findings
        )

        if len(identifiers) != len(set(identifiers)):
            raise ServiceLifecycleError(
                "startup policy findings must have "
                "unique identifiers",
            )

        object.__setattr__(
            self,
            "findings",
            findings,
        )
        object.__setattr__(
            self,
            "provider",
            provider,
        )
        object.__setattr__(
            self,
            "evaluated_at",
            evaluated_at,
        )

    @property
    def status(self) -> str:
        """Return the highest normalized report status."""

        severities = {
            finding.severity
            for finding in self.findings
        }

        if StartupPolicySeverity.CRITICAL in severities:
            return "critical"

        if StartupPolicySeverity.ERROR in severities:
            return "unhealthy"

        if StartupPolicySeverity.WARNING in severities:
            return "degraded"

        return "healthy"

    @property
    def passed(self) -> bool:
        """Return whether no error or critical findings exist."""

        return not any(
            finding.severity
            in {
                StartupPolicySeverity.ERROR,
                StartupPolicySeverity.CRITICAL,
            }
            for finding in self.findings
        )

    @property
    def requires_attention(self) -> bool:
        """Return whether any finding requires attention."""

        return any(
            finding.requires_attention
            for finding in self.findings
        )

    @property
    def counts(self) -> dict[str, int]:
        """Return deterministic finding counts by severity."""

        counts = {
            severity.value: 0
            for severity in StartupPolicySeverity
        }

        for finding in self.findings:
            counts[finding.severity.value] += 1

        return counts

    @property
    def attention(self) -> tuple[StartupPolicyFinding, ...]:
        """Return attention findings in deterministic priority order."""

        return tuple(
            finding
            for finding in self.findings
            if finding.requires_attention
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the aggregate startup-policy report."""

        return {
            "provider": self.provider,
            "status": self.status,
            "passed": self.passed,
            "requires_attention": self.requires_attention,
            "finding_count": len(self.findings),
            "counts": self.counts,
            "attention_findings": [
                finding.identifier
                for finding in self.attention
            ],
            "findings": [
                finding.to_dict()
                for finding in self.findings
            ],
            "evaluated_at": self.evaluated_at,
        }


def _normalize_findings(
    value: object,
) -> tuple[StartupPolicyFinding, ...]:
    if not isinstance(value, tuple):
        raise ServiceLifecycleError(
            "startup policy findings must be a tuple "
            "of StartupPolicyFinding",
        )

    if any(
        not isinstance(item, StartupPolicyFinding)
        for item in value
    ):
        raise ServiceLifecycleError(
            "startup policy findings must be a tuple "
            "of StartupPolicyFinding",
        )

    return tuple(
        sorted(
            value,
            key=lambda finding: (
                _SEVERITY_ORDER[finding.severity],
                finding.service_identifier or "",
                finding.identifier,
            ),
        )
    )


def _normalize_severity(
    value: object,
    field_name: str,
) -> StartupPolicySeverity:
    if isinstance(value, StartupPolicySeverity):
        return value

    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} must be a supported "
            "startup policy severity",
        )

    try:
        return StartupPolicySeverity(
            value.strip().casefold()
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be a supported "
            "startup policy severity",
        ) from exc


def _normalize_details(
    value: object,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ServiceLifecycleError(
            f"{field_name} must be an object",
        )

    normalized: dict[str, Any] = {}

    for key, item in value.items():
        normalized_key = _required_text(
            key,
            f"{field_name} key",
        )

        normalized[normalized_key] = item

    return MappingProxyType(normalized)


def _required_identifier(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(
        value,
        field_name,
    ).casefold()

    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise ServiceLifecycleError(
            f"{field_name} must be a normalized identifier",
        )

    return normalized


def _optional_identifier(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_identifier(
        value,
        field_name,
    )


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ServiceLifecycleError(
            f"{field_name} is required",
        )

    return value.strip()


def _optional_text(
    value: object,
    field_name: str,
) -> str | None:
    if value is None:
        return None

    return _required_text(
        value,
        field_name,
    )


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(
        value,
        field_name,
    )

    try:
        parsed = datetime.fromisoformat(
            normalized.replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError as exc:
        raise ServiceLifecycleError(
            f"{field_name} must be a valid timestamp",
        ) from exc

    if parsed.tzinfo is None:
        raise ServiceLifecycleError(
            f"{field_name} must include a timezone",
        )

    return parsed.astimezone(UTC).isoformat()


def _now_timestamp() -> str:
    return datetime.now(UTC).isoformat()
