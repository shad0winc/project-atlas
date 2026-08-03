"""Normalized Operations domain models for Project Atlas."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
import re
from typing import Any


_IDENTIFIER_PATTERN = re.compile(
    r"^[a-z0-9](?:[a-z0-9._:-]*[a-z0-9])?$",
)
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,64}$")


class OperationsModelError(ValueError):
    """Raised when an Operations domain model contains invalid data."""


OPERATIONS_SCHEMA_VERSION = 1


class OperationsSectionId(str, Enum):
    """Canonical section identities for Atlas Operations reports."""

    SYSTEM = "system"
    CONTAINERS = "containers"
    SERVICES = "services"
    STORAGE = "storage"
    INGRESS = "ingress"
    MEDIA = "media"
    REQUESTS = "requests"
    NOTIFICATIONS = "notifications"
    RETENTION = "retention"
    CLEANUP = "cleanup"
    ARI = "ari"
    SPORTS = "sports"
    FORECAST = "forecast"
    USERS = "users"
    BACKUP = "backup"
    SCHEDULER = "scheduler"


class OperationsStatus(str, Enum):
    """Normalized operational states from best to worst."""

    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class OperationsSeverity(str, Enum):
    """Normalized finding severity used for presentation and escalation."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


_STATUS_SCORE: dict[OperationsStatus, int] = {
    OperationsStatus.HEALTHY: 100,
    OperationsStatus.WARNING: 50,
    OperationsStatus.UNKNOWN: 25,
    OperationsStatus.CRITICAL: 0,
}

_STATUS_SEVERITY: dict[OperationsStatus, int] = {
    OperationsStatus.HEALTHY: 0,
    OperationsStatus.UNKNOWN: 1,
    OperationsStatus.WARNING: 2,
    OperationsStatus.CRITICAL: 3,
}

_SECTION_ORDER: dict[OperationsSectionId, int] = {
    section_id: index
    for index, section_id in enumerate(OperationsSectionId)
}

_ATTENTION_ORDER: dict[OperationsSeverity, int] = {
    OperationsSeverity.CRITICAL: 0,
    OperationsSeverity.WARNING: 1,
    OperationsSeverity.INFO: 2,
}


@dataclass(frozen=True, slots=True)
class OperationFinding:
    """One normalized Operations report finding."""

    identifier: str
    name: str
    status: OperationsStatus | str
    severity: OperationsSeverity | str
    message: str
    recommendation: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        identifier = _required_identifier(
            self.identifier,
            "identifier",
        )
        name = _required_text(
            self.name,
            "name",
        )
        status = _normalize_status(
            self.status,
            "status",
        )
        severity = _normalize_severity(
            self.severity,
            "severity",
        )
        message = _required_text(
            self.message,
            "message",
        )
        recommendation = _optional_text(
            self.recommendation,
            "recommendation",
        )
        metadata = _normalize_metadata(
            self.metadata,
            "metadata",
        )

        if (
            status is OperationsStatus.CRITICAL
            and severity is not OperationsSeverity.CRITICAL
        ):
            raise OperationsModelError(
                "critical findings must use critical severity",
            )

        if (
            status is OperationsStatus.WARNING
            and severity is OperationsSeverity.INFO
        ):
            raise OperationsModelError(
                "warning findings must not use info severity",
            )

        object.__setattr__(
            self,
            "identifier",
            identifier,
        )
        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "status",
            status,
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
            "recommendation",
            recommendation,
        )
        object.__setattr__(
            self,
            "metadata",
            metadata,
        )

    @property
    def score(self) -> int:
        """Return the normalized score associated with this finding."""

        return _STATUS_SCORE[self.status]

    @property
    def action_required(self) -> bool:
        """Return whether this finding requires administrator attention."""

        return (
            self.status
            in {
                OperationsStatus.WARNING,
                OperationsStatus.CRITICAL,
            }
            or self.severity
            in {
                OperationsSeverity.WARNING,
                OperationsSeverity.CRITICAL,
            }
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized finding contract."""

        return {
            "identifier": self.identifier,
            "name": self.name,
            "status": self.status.value,
            "severity": self.severity.value,
            "score": self.score,
            "action_required": self.action_required,
            "message": self.message,
            "recommendation": self.recommendation,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True, slots=True)
class OperationsSection:
    """One normalized section within an Operations report."""

    identifier: OperationsSectionId | str
    name: str
    findings: tuple[OperationFinding, ...] = ()
    description: str | None = None

    def __post_init__(self) -> None:
        identifier = _normalize_section_id(
            self.identifier,
            "identifier",
        )
        name = _required_text(
            self.name,
            "name",
        )
        findings = _normalize_findings(
            self.findings,
            "findings",
        )
        description = _optional_text(
            self.description,
            "description",
        )

        finding_identifiers = [
            finding.identifier
            for finding in findings
        ]

        if len(finding_identifiers) != len(set(finding_identifiers)):
            raise OperationsModelError(
                "findings must have unique identifiers",
            )

        object.__setattr__(
            self,
            "identifier",
            identifier,
        )
        object.__setattr__(
            self,
            "name",
            name,
        )
        object.__setattr__(
            self,
            "findings",
            findings,
        )
        object.__setattr__(
            self,
            "description",
            description,
        )

    @property
    def status(self) -> OperationsStatus:
        """Return the most severe status in this section."""

        if not self.findings:
            return OperationsStatus.UNKNOWN

        return max(
            self.findings,
            key=lambda finding: _STATUS_SEVERITY[finding.status],
        ).status

    @property
    def score(self) -> int:
        """Return the rounded average score for all findings."""

        if not self.findings:
            return 0

        return round(
            sum(finding.score for finding in self.findings)
            / len(self.findings)
        )

    @property
    def healthy_count(self) -> int:
        return self._status_count(OperationsStatus.HEALTHY)

    @property
    def warning_count(self) -> int:
        return self._status_count(OperationsStatus.WARNING)

    @property
    def critical_count(self) -> int:
        return self._status_count(OperationsStatus.CRITICAL)

    @property
    def unknown_count(self) -> int:
        return self._status_count(OperationsStatus.UNKNOWN)

    @property
    def attention_findings(self) -> tuple[OperationFinding, ...]:
        """Return findings that require administrator attention."""

        return tuple(
            finding
            for finding in self.findings
            if finding.action_required
        )

    def _status_count(
        self,
        status: OperationsStatus,
    ) -> int:
        return sum(
            finding.status is status
            for finding in self.findings
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized section contract."""

        return {
            "identifier": self.identifier.value,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "score": self.score,
            "finding_count": len(self.findings),
            "status_counts": {
                "healthy": self.healthy_count,
                "warning": self.warning_count,
                "critical": self.critical_count,
                "unknown": self.unknown_count,
            },
            "attention_findings": [
                finding.identifier
                for finding in self.attention_findings
            ],
            "findings": [
                finding.to_dict()
                for finding in self.findings
            ],
        }


@dataclass(frozen=True, slots=True)
class OperationsSummary:
    """Normalized aggregate summary for an Operations report."""

    status: OperationsStatus | str
    score: int
    section_count: int
    finding_count: int
    healthy_count: int
    warning_count: int
    critical_count: int
    unknown_count: int
    attention_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "status",
            _normalize_status(self.status, "status"),
        )

        for field_name in (
            "section_count",
            "finding_count",
            "healthy_count",
            "warning_count",
            "critical_count",
            "unknown_count",
            "attention_count",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise OperationsModelError(
                    f"{field_name} must be a non-negative integer",
                )

        if isinstance(self.score, bool) or not isinstance(self.score, int):
            raise OperationsModelError("score must be an integer")

        if not 0 <= self.score <= 100:
            raise OperationsModelError(
                "score must be between 0 and 100",
            )

        status_total = (
            self.healthy_count
            + self.warning_count
            + self.critical_count
            + self.unknown_count
        )

        if status_total != self.finding_count:
            raise OperationsModelError(
                "status counts must equal finding_count",
            )

        if self.attention_count > self.finding_count:
            raise OperationsModelError(
                "attention_count must not exceed finding_count",
            )

    @classmethod
    def from_sections(
        cls,
        sections: tuple[OperationsSection, ...],
    ) -> "OperationsSummary":
        """Build a deterministic summary from normalized sections."""

        findings = tuple(
            finding
            for section in sections
            for finding in section.findings
        )

        if findings:
            status = max(
                findings,
                key=lambda finding: _STATUS_SEVERITY[finding.status],
            ).status
            score = round(
                sum(finding.score for finding in findings)
                / len(findings)
            )
        else:
            status = OperationsStatus.UNKNOWN
            score = 0

        return cls(
            status=status,
            score=score,
            section_count=len(sections),
            finding_count=len(findings),
            healthy_count=sum(
                finding.status is OperationsStatus.HEALTHY
                for finding in findings
            ),
            warning_count=sum(
                finding.status is OperationsStatus.WARNING
                for finding in findings
            ),
            critical_count=sum(
                finding.status is OperationsStatus.CRITICAL
                for finding in findings
            ),
            unknown_count=sum(
                finding.status is OperationsStatus.UNKNOWN
                for finding in findings
            ),
            attention_count=sum(
                finding.action_required
                for finding in findings
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the normalized Operations summary."""

        return {
            "status": self.status.value,
            "score": self.score,
            "section_count": self.section_count,
            "finding_count": self.finding_count,
            "status_counts": {
                "healthy": self.healthy_count,
                "warning": self.warning_count,
                "critical": self.critical_count,
                "unknown": self.unknown_count,
            },
            "attention_count": self.attention_count,
        }


@dataclass(frozen=True, slots=True)
class OperationsReport:
    """Canonical normalized Project Atlas Operations report."""

    report_id: str
    hostname: str
    atlas_version: str
    git_commit: str
    sections: tuple[OperationsSection, ...] = ()
    generated_at: str = field(default_factory=lambda: _now_timestamp())

    def __post_init__(self) -> None:
        report_id = _required_identifier(self.report_id, "report_id")
        hostname = _required_text(self.hostname, "hostname").lower()
        atlas_version = _required_text(
            self.atlas_version,
            "atlas_version",
        )
        git_commit = _required_git_commit(
            self.git_commit,
            "git_commit",
        )
        sections = tuple(
            sorted(
                _normalize_sections(self.sections, "sections"),
                key=lambda section: _SECTION_ORDER[section.identifier],
            )
        )
        generated_at = _required_timestamp(
            self.generated_at,
            "generated_at",
        )

        identifiers = [section.identifier for section in sections]
        if len(identifiers) != len(set(identifiers)):
            raise OperationsModelError(
                "sections must have unique identifiers",
            )

        finding_identifiers = [
            finding.identifier
            for section in sections
            for finding in section.findings
        ]

        if len(finding_identifiers) != len(set(finding_identifiers)):
            raise OperationsModelError(
                "findings must have globally unique identifiers",
            )

        object.__setattr__(self, "report_id", report_id)
        object.__setattr__(self, "hostname", hostname)
        object.__setattr__(self, "atlas_version", atlas_version)
        object.__setattr__(self, "git_commit", git_commit)
        object.__setattr__(self, "sections", sections)
        object.__setattr__(self, "generated_at", generated_at)

    @property
    def summary(self) -> OperationsSummary:
        """Return the aggregate report summary."""

        return OperationsSummary.from_sections(self.sections)

    @property
    def status(self) -> OperationsStatus:
        return self.summary.status

    @property
    def score(self) -> int:
        return self.summary.score

    @property
    def attention_findings(self) -> tuple[OperationFinding, ...]:
        """Return attention findings in deterministic priority order."""

        indexed = (
            (section, finding)
            for section in self.sections
            for finding in section.attention_findings
        )

        return tuple(
            finding
            for section, finding in sorted(
                indexed,
                key=lambda item: (
                    _ATTENTION_ORDER[item[1].severity],
                    _SECTION_ORDER[item[0].identifier],
                    item[1].identifier,
                ),
            )
        )

    def _finding_section(
        self,
        target: OperationFinding,
    ) -> OperationsSectionId:
        for section in self.sections:
            if target in section.findings:
                return section.identifier

        raise OperationsModelError(
            "finding does not belong to this report",
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize the complete Operations report contract."""

        return {
            "schema_version": OPERATIONS_SCHEMA_VERSION,
            "report_id": self.report_id,
            "generated_at": self.generated_at,
            "hostname": self.hostname,
            "atlas_version": self.atlas_version,
            "git_commit": self.git_commit,
            "status": self.status.value,
            "score": self.score,
            "summary": self.summary.to_dict(),
            "attention_findings": [
                {
                    "section": self._finding_section(finding).value,
                    "identifier": finding.identifier,
                }
                for finding in self.attention_findings
            ],
            "sections": [
                section.to_dict()
                for section in self.sections
            ],
        }

    def to_json(self, *, indent: int | None = 2) -> str:
        """Serialize the report as deterministic JSON."""

        return json.dumps(
            self.to_dict(),
            indent=indent,
            sort_keys=True,
        )


def _required_text(
    value: object,
    field_name: str,
) -> str:
    if not isinstance(value, str):
        raise OperationsModelError(
            f"{field_name} must be text",
        )

    normalized = value.strip()

    if not normalized:
        raise OperationsModelError(
            f"{field_name} is required",
        )

    return normalized


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


def _required_identifier(
    value: object,
    field_name: str,
) -> str:
    normalized = (
        _required_text(
            value,
            field_name,
        )
        .lower()
        .replace(" ", "-")
        .replace("_", "-")
    )

    if not _IDENTIFIER_PATTERN.fullmatch(normalized):
        raise OperationsModelError(
            f"{field_name} contains unsupported characters",
        )

    return normalized


def _normalize_status(
    value: object,
    field_name: str,
) -> OperationsStatus:
    if isinstance(value, OperationsStatus):
        return value

    if not isinstance(value, str):
        raise OperationsModelError(
            f"{field_name} must be OperationsStatus or text",
        )

    normalized = (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    try:
        return OperationsStatus(normalized)
    except ValueError as exc:
        raise OperationsModelError(
            f"{field_name} is not supported: {value!r}",
        ) from exc


def _normalize_severity(
    value: object,
    field_name: str,
) -> OperationsSeverity:
    if isinstance(value, OperationsSeverity):
        return value

    if not isinstance(value, str):
        raise OperationsModelError(
            f"{field_name} must be OperationsSeverity or text",
        )

    normalized = (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    try:
        return OperationsSeverity(normalized)
    except ValueError as exc:
        raise OperationsModelError(
            f"{field_name} is not supported: {value!r}",
        ) from exc


def _normalize_metadata(
    value: object,
    field_name: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise OperationsModelError(
            f"{field_name} must be an object",
        )

    normalized: dict[str, Any] = {}

    for key, metadata_value in value.items():
        normalized_key = _required_text(
            key,
            f"{field_name} key",
        )

        if normalized_key in normalized:
            raise OperationsModelError(
                f"{field_name} contains duplicate key: "
                f"{normalized_key}",
            )

        normalized[normalized_key] = metadata_value

    return {
        key: normalized[key]
        for key in sorted(normalized)
    }


def _normalize_findings(
    value: object,
    field_name: str,
) -> tuple[OperationFinding, ...]:
    if not isinstance(value, (list, tuple)):
        raise OperationsModelError(
            f"{field_name} must be a list or tuple",
        )

    findings = tuple(value)

    for index, finding in enumerate(findings):
        if not isinstance(finding, OperationFinding):
            raise OperationsModelError(
                f"{field_name}[{index}] must be an OperationFinding",
            )

    return findings


def _normalize_sections(
    value: object,
    field_name: str,
) -> tuple[OperationsSection, ...]:
    if not isinstance(value, (list, tuple)):
        raise OperationsModelError(
            f"{field_name} must be a list or tuple",
        )

    sections = tuple(value)

    for index, section in enumerate(sections):
        if not isinstance(section, OperationsSection):
            raise OperationsModelError(
                f"{field_name}[{index}] must be an OperationsSection",
            )

    return sections


def _required_git_commit(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(value, field_name).lower()

    if not _GIT_COMMIT_PATTERN.fullmatch(normalized):
        raise OperationsModelError(
            f"{field_name} must be a hexadecimal Git commit",
        )

    return normalized


def _now_timestamp() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _required_timestamp(
    value: object,
    field_name: str,
) -> str:
    normalized = _required_text(value, field_name)
    candidate = (
        normalized[:-1] + "+00:00"
        if normalized.endswith("Z")
        else normalized
    )

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError as exc:
        raise OperationsModelError(
            f"{field_name} must be an ISO-8601 timestamp",
        ) from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise OperationsModelError(
            f"{field_name} must include a timezone",
        )

    return (
        parsed.astimezone(timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _normalize_section_id(
    value: object,
    field_name: str,
) -> OperationsSectionId:
    if isinstance(value, OperationsSectionId):
        return value

    if not isinstance(value, str):
        raise OperationsModelError(
            f"{field_name} must be OperationsSectionId or text",
        )

    normalized = (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    try:
        return OperationsSectionId(normalized)
    except ValueError as exc:
        raise OperationsModelError(
            f"{field_name} is not a supported Operations section: "
            f"{value!r}",
        ) from exc
