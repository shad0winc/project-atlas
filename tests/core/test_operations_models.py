"""Tests for normalized Atlas Operations domain models."""

from dataclasses import FrozenInstanceError
import json

import pytest

from atlas.operations import (
    OPERATIONS_SCHEMA_VERSION,
    OperationFinding,
    OperationsModelError,
    OperationsReport,
    OperationsSection,
    OperationsSectionId,
    OperationsSeverity,
    OperationsStatus,
    OperationsSummary,
)


def finding(
    identifier: str = "docker-engine",
    *,
    status: OperationsStatus | str = OperationsStatus.HEALTHY,
    severity: OperationsSeverity | str = OperationsSeverity.INFO,
    message: str = "Docker is healthy",
) -> OperationFinding:
    return OperationFinding(
        identifier=identifier,
        name=identifier.replace("-", " ").title(),
        status=status,
        severity=severity,
        message=message,
    )


def test_finding_normalizes_values() -> None:
    result = OperationFinding(
        identifier=" Docker Engine ",
        name=" Docker Engine ",
        status=" HEALTHY ",
        severity=" INFO ",
        message=" Docker is available ",
        recommendation=" Review during maintenance ",
        metadata={
            "z": 2,
            "a": 1,
        },
    )

    assert result.identifier == "docker-engine"
    assert result.name == "Docker Engine"
    assert result.status is OperationsStatus.HEALTHY
    assert result.severity is OperationsSeverity.INFO
    assert result.message == "Docker is available"
    assert result.recommendation == "Review during maintenance"
    assert tuple(result.metadata) == ("a", "z")


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        (OperationsStatus.HEALTHY, 100),
        (OperationsStatus.WARNING, 50),
        (OperationsStatus.UNKNOWN, 25),
        (OperationsStatus.CRITICAL, 0),
    ],
)
def test_finding_score(
    status: OperationsStatus,
    expected: int,
) -> None:
    severity = (
        OperationsSeverity.CRITICAL
        if status is OperationsStatus.CRITICAL
        else OperationsSeverity.WARNING
        if status is OperationsStatus.WARNING
        else OperationsSeverity.INFO
    )

    assert finding(
        status=status,
        severity=severity,
    ).score == expected


@pytest.mark.parametrize(
    ("status", "severity", "expected"),
    [
        ("healthy", "info", False),
        ("unknown", "info", False),
        ("healthy", "warning", True),
        ("warning", "warning", True),
        ("critical", "critical", True),
    ],
)
def test_finding_action_required(
    status: str,
    severity: str,
    expected: bool,
) -> None:
    assert finding(
        status=status,
        severity=severity,
    ).action_required is expected


def test_finding_rejects_critical_status_without_critical_severity() -> None:
    with pytest.raises(
        OperationsModelError,
        match="critical findings must use critical severity",
    ):
        finding(
            status="critical",
            severity="warning",
        )


def test_finding_rejects_warning_status_with_info_severity() -> None:
    with pytest.raises(
        OperationsModelError,
        match="warning findings must not use info severity",
    ):
        finding(
            status="warning",
            severity="info",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("identifier", ""),
        ("name", " "),
        ("message", None),
    ],
)
def test_finding_rejects_invalid_required_text(
    field: str,
    value: object,
) -> None:
    values = {
        "identifier": "docker-engine",
        "name": "Docker Engine",
        "status": "healthy",
        "severity": "info",
        "message": "Docker is available",
    }
    values[field] = value

    with pytest.raises(OperationsModelError):
        OperationFinding(**values)


def test_finding_rejects_unsupported_identifier() -> None:
    with pytest.raises(
        OperationsModelError,
        match="unsupported characters",
    ):
        finding(identifier="docker/engine")


def test_finding_rejects_invalid_status() -> None:
    with pytest.raises(
        OperationsModelError,
        match="status is not supported",
    ):
        finding(status="broken")


def test_finding_rejects_invalid_severity() -> None:
    with pytest.raises(
        OperationsModelError,
        match="severity is not supported",
    ):
        finding(severity="emergency")


def test_finding_rejects_non_mapping_metadata() -> None:
    with pytest.raises(
        OperationsModelError,
        match="metadata must be an object",
    ):
        OperationFinding(
            identifier="docker-engine",
            name="Docker Engine",
            status="healthy",
            severity="info",
            message="Docker is available",
            metadata=[],
        )


def test_finding_serialization_is_deterministic() -> None:
    result = OperationFinding(
        identifier="docker-engine",
        name="Docker Engine",
        status="warning",
        severity="warning",
        message="Docker needs attention",
        recommendation="Inspect Docker",
        metadata={
            "version": "28",
            "provider": "docker",
        },
    )

    assert result.to_dict() == {
        "identifier": "docker-engine",
        "name": "Docker Engine",
        "status": "warning",
        "severity": "warning",
        "score": 50,
        "action_required": True,
        "message": "Docker needs attention",
        "recommendation": "Inspect Docker",
        "metadata": {
            "provider": "docker",
            "version": "28",
        },
    }


def test_finding_is_immutable() -> None:
    result = finding()

    with pytest.raises(FrozenInstanceError):
        result.name = "Changed"  # type: ignore[misc]


def test_section_normalizes_identity_and_children() -> None:
    result = OperationsSection(
        identifier=" SERVICES ",
        name=" Core Infrastructure ",
        description=" Foundational checks ",
        findings=[
            finding(),
        ],
    )

    assert result.identifier is OperationsSectionId.SERVICES
    assert result.name == "Core Infrastructure"
    assert result.description == "Foundational checks"
    assert isinstance(result.findings, tuple)


def test_empty_section_is_unknown_with_zero_score() -> None:
    result = OperationsSection(
        identifier="system",
        name="Empty",
    )

    assert result.status is OperationsStatus.UNKNOWN
    assert result.score == 0
    assert result.healthy_count == 0
    assert result.warning_count == 0
    assert result.critical_count == 0
    assert result.unknown_count == 0
    assert result.attention_findings == ()


def test_section_uses_most_severe_status() -> None:
    result = OperationsSection(
        identifier="system",
        name="Platform",
        findings=(
            finding("healthy", status="healthy"),
            finding(
                "unknown",
                status="unknown",
            ),
            finding(
                "warning",
                status="warning",
                severity="warning",
            ),
            finding(
                "critical",
                status="critical",
                severity="critical",
            ),
        ),
    )

    assert result.status is OperationsStatus.CRITICAL


def test_section_calculates_score_and_counts() -> None:
    result = OperationsSection(
        identifier="system",
        name="Platform",
        findings=(
            finding("healthy", status="healthy"),
            finding(
                "warning",
                status="warning",
                severity="warning",
            ),
            finding(
                "critical",
                status="critical",
                severity="critical",
            ),
            finding(
                "unknown",
                status="unknown",
            ),
        ),
    )

    assert result.score == 44
    assert result.healthy_count == 1
    assert result.warning_count == 1
    assert result.critical_count == 1
    assert result.unknown_count == 1


def test_section_returns_attention_findings() -> None:
    warning = finding(
        "warning",
        status="warning",
        severity="warning",
    )
    critical = finding(
        "critical",
        status="critical",
        severity="critical",
    )

    result = OperationsSection(
        identifier="system",
        name="Platform",
        findings=(
            finding("healthy"),
            warning,
            critical,
        ),
    )

    assert result.attention_findings == (
        warning,
        critical,
    )


def test_section_rejects_invalid_child_contract() -> None:
    with pytest.raises(
        OperationsModelError,
        match=r"findings\[0\] must be an OperationFinding",
    ):
        OperationsSection(
            identifier="system",
            name="Platform",
            findings=("invalid",),  # type: ignore[arg-type]
        )


def test_section_rejects_duplicate_finding_identifiers() -> None:
    with pytest.raises(
        OperationsModelError,
        match="unique identifiers",
    ):
        OperationsSection(
            identifier="system",
            name="Platform",
            findings=(
                finding("docker"),
                finding("docker"),
            ),
        )


def test_section_serialization_is_deterministic() -> None:
    warning = finding(
        "docker-engine",
        status="warning",
        severity="warning",
        message="Docker needs attention",
    )

    result = OperationsSection(
        identifier="system",
        name="Infrastructure",
        description="Core infrastructure checks",
        findings=(warning,),
    )

    assert result.to_dict() == {
        "identifier": "system",
        "name": "Infrastructure",
        "description": "Core infrastructure checks",
        "status": "warning",
        "score": 50,
        "finding_count": 1,
        "status_counts": {
            "healthy": 0,
            "warning": 1,
            "critical": 0,
            "unknown": 0,
        },
        "attention_findings": [
            "docker-engine",
        ],
        "findings": [
            warning.to_dict(),
        ],
    }


def test_section_is_immutable() -> None:
    result = OperationsSection(
        identifier="system",
        name="Platform",
    )

    with pytest.raises(FrozenInstanceError):
        result.name = "Changed"  # type: ignore[misc]


def test_public_package_exports() -> None:
    from atlas import operations

    assert operations.OperationFinding is OperationFinding
    assert operations.OperationsModelError is OperationsModelError
    assert operations.OperationsSection is OperationsSection
    assert operations.OperationsSeverity is OperationsSeverity
    assert operations.OperationsStatus is OperationsStatus


def test_summary_from_sections_aggregates_findings() -> None:
    sections = (
        OperationsSection(
            identifier="system",
            name="Infrastructure",
            findings=(
                finding("docker"),
                finding(
                    "storage",
                    status="warning",
                    severity="warning",
                ),
            ),
        ),
        OperationsSection(
            identifier="ingress",
            name="Ingress",
            findings=(
                finding(
                    "caddy",
                    status="critical",
                    severity="critical",
                ),
                finding("portal", status="unknown"),
            ),
        ),
    )

    result = OperationsSummary.from_sections(sections)

    assert result.status is OperationsStatus.CRITICAL
    assert result.score == 44
    assert result.section_count == 2
    assert result.finding_count == 4
    assert result.healthy_count == 1
    assert result.warning_count == 1
    assert result.critical_count == 1
    assert result.unknown_count == 1
    assert result.attention_count == 2


def test_empty_summary_is_unknown() -> None:
    result = OperationsSummary.from_sections(())

    assert result.status is OperationsStatus.UNKNOWN
    assert result.score == 0
    assert result.section_count == 0
    assert result.finding_count == 0


def test_summary_rejects_inconsistent_status_counts() -> None:
    with pytest.raises(
        OperationsModelError,
        match="status counts must equal finding_count",
    ):
        OperationsSummary(
            status="healthy",
            score=100,
            section_count=1,
            finding_count=2,
            healthy_count=1,
            warning_count=0,
            critical_count=0,
            unknown_count=0,
            attention_count=0,
        )


def test_summary_serialization() -> None:
    result = OperationsSummary.from_sections(
        (
            OperationsSection(
                identifier="system",
                name="Core",
                findings=(finding(),),
            ),
        )
    )

    assert result.to_dict() == {
        "status": "healthy",
        "score": 100,
        "section_count": 1,
        "finding_count": 1,
        "status_counts": {
            "healthy": 1,
            "warning": 0,
            "critical": 0,
            "unknown": 0,
        },
        "attention_count": 0,
    }


def operations_report(
    *,
    sections: tuple[OperationsSection, ...] = (),
    generated_at: str = "2026-08-03T12:00:00-04:00",
) -> OperationsReport:
    return OperationsReport(
        report_id="daily-operations",
        hostname=" Docker ",
        atlas_version=" 0.9.0 ",
        git_commit="3A5E3B22",
        sections=sections,
        generated_at=generated_at,
    )


def test_report_normalizes_identity_and_timestamp() -> None:
    result = operations_report()

    assert result.report_id == "daily-operations"
    assert result.hostname == "docker"
    assert result.atlas_version == "0.9.0"
    assert result.git_commit == "3a5e3b22"
    assert result.generated_at == "2026-08-03T16:00:00Z"
    assert result.status is OperationsStatus.UNKNOWN
    assert result.score == 0


def test_report_validates_section_children() -> None:
    with pytest.raises(
        OperationsModelError,
        match=r"sections\[0\] must be an OperationsSection",
    ):
        operations_report(
            sections=("invalid",),  # type: ignore[arg-type]
        )


def test_report_rejects_duplicate_sections() -> None:
    section = OperationsSection(
        identifier="system",
        name="System",
    )

    with pytest.raises(
        OperationsModelError,
        match="unique identifiers",
    ):
        operations_report(sections=(section, section))


@pytest.mark.parametrize(
    "commit",
    (
        "",
        "not-a-commit",
        "123456",
        "xyz7890",
    ),
)
def test_report_rejects_invalid_git_commit(commit: str) -> None:
    with pytest.raises(OperationsModelError):
        OperationsReport(
            report_id="daily",
            hostname="docker",
            atlas_version="0.9.0",
            git_commit=commit,
        )


def test_report_requires_timezone_aware_timestamp() -> None:
    with pytest.raises(
        OperationsModelError,
        match="must include a timezone",
    ):
        operations_report(
            generated_at="2026-08-03T12:00:00",
        )


def test_report_exposes_attention_findings() -> None:
    warning = finding(
        "storage",
        status="warning",
        severity="warning",
    )

    result = operations_report(
        sections=(
            OperationsSection(
                identifier="storage",
                name="Storage",
                findings=(warning,),
            ),
        )
    )

    assert result.attention_findings == (warning,)
    assert result.status is OperationsStatus.WARNING
    assert result.score == 50


def test_report_serialization_and_json_are_deterministic() -> None:
    result = operations_report(
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(finding(),),
            ),
        )
    )

    payload = result.to_dict()

    assert payload["schema_version"] == 1
    assert payload["status"] == "healthy"
    assert payload["score"] == 100
    assert payload["summary"]["finding_count"] == 1
    assert payload["sections"][0]["identifier"] == "system"
    assert payload["attention_findings"] == []

    compact = result.to_json(indent=None)
    assert json.loads(compact) == payload


def test_report_is_immutable() -> None:
    result = operations_report()

    with pytest.raises(FrozenInstanceError):
        result.hostname = "changed"  # type: ignore[misc]


def test_operations_schema_version_is_stable() -> None:
    assert OPERATIONS_SCHEMA_VERSION == 1


def test_section_normalizes_canonical_identifier() -> None:
    result = OperationsSection(
        identifier=" NOTIFICATIONS ",
        name="Notifications",
    )

    assert result.identifier is OperationsSectionId.NOTIFICATIONS
    assert result.to_dict()["identifier"] == "notifications"


def test_section_accepts_enum_identifier() -> None:
    result = OperationsSection(
        identifier=OperationsSectionId.STORAGE,
        name="Storage",
    )

    assert result.identifier is OperationsSectionId.STORAGE


def test_section_rejects_unknown_identifier() -> None:
    with pytest.raises(
        OperationsModelError,
        match="not a supported Operations section",
    ):
        OperationsSection(
            identifier="something-new",
            name="Unknown",
        )


def test_report_orders_sections_canonically() -> None:
    result = operations_report(
        sections=(
            OperationsSection(
                identifier="notifications",
                name="Notifications",
            ),
            OperationsSection(
                identifier="system",
                name="System",
            ),
            OperationsSection(
                identifier="storage",
                name="Storage",
            ),
            OperationsSection(
                identifier="ingress",
                name="Ingress",
            ),
        )
    )

    assert tuple(
        section.identifier
        for section in result.sections
    ) == (
        OperationsSectionId.SYSTEM,
        OperationsSectionId.STORAGE,
        OperationsSectionId.INGRESS,
        OperationsSectionId.NOTIFICATIONS,
    )


def test_report_serializes_canonical_section_order() -> None:
    result = operations_report(
        sections=(
            OperationsSection(
                identifier="backup",
                name="Backup",
            ),
            OperationsSection(
                identifier="containers",
                name="Containers",
            ),
            OperationsSection(
                identifier="system",
                name="System",
            ),
        )
    )

    assert [
        section["identifier"]
        for section in result.to_dict()["sections"]
    ] == [
        "system",
        "containers",
        "backup",
    ]


def test_report_uses_schema_version_constant() -> None:
    assert (
        operations_report().to_dict()["schema_version"]
        == OPERATIONS_SCHEMA_VERSION
    )


def test_report_rejects_duplicate_findings_across_sections() -> None:
    first = finding(
        "shared-health",
        status="warning",
        severity="warning",
    )
    second = finding(
        "shared-health",
        status="critical",
        severity="critical",
    )

    with pytest.raises(
        OperationsModelError,
        match="globally unique identifiers",
    ):
        operations_report(
            sections=(
                OperationsSection(
                    identifier="system",
                    name="System",
                    findings=(first,),
                ),
                OperationsSection(
                    identifier="services",
                    name="Services",
                    findings=(second,),
                ),
            )
        )


def test_report_allows_distinct_findings_across_sections() -> None:
    result = operations_report(
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(finding("system-health"),),
            ),
            OperationsSection(
                identifier="services",
                name="Services",
                findings=(finding("service-health"),),
            ),
        )
    )

    assert result.summary.finding_count == 2


def test_report_orders_attention_findings_deterministically() -> None:
    critical_storage = finding(
        "disk-health",
        status="critical",
        severity="critical",
    )
    critical_ingress = finding(
        "caddy-health",
        status="critical",
        severity="critical",
    )
    warning_system_z = finding(
        "z-warning",
        status="warning",
        severity="warning",
    )
    warning_system_a = finding(
        "a-warning",
        status="warning",
        severity="warning",
    )
    warning_notifications = finding(
        "discord-health",
        status="warning",
        severity="warning",
    )

    result = operations_report(
        sections=(
            OperationsSection(
                identifier="notifications",
                name="Notifications",
                findings=(warning_notifications,),
            ),
            OperationsSection(
                identifier="ingress",
                name="Ingress",
                findings=(critical_ingress,),
            ),
            OperationsSection(
                identifier="system",
                name="System",
                findings=(
                    warning_system_z,
                    warning_system_a,
                ),
            ),
            OperationsSection(
                identifier="storage",
                name="Storage",
                findings=(critical_storage,),
            ),
        )
    )

    assert result.attention_findings == (
        critical_storage,
        critical_ingress,
        warning_system_a,
        warning_system_z,
        warning_notifications,
    )


def test_report_serializes_qualified_attention_references() -> None:
    warning = finding(
        "disk-threshold",
        status="warning",
        severity="warning",
    )

    result = operations_report(
        sections=(
            OperationsSection(
                identifier="storage",
                name="Storage",
                findings=(warning,),
            ),
        )
    )

    assert result.to_dict()["attention_findings"] == [
        {
            "section": "storage",
            "identifier": "disk-threshold",
        }
    ]


def test_operation_finding_from_dict_round_trip() -> None:
    finding = OperationFinding(
        identifier="system.hostname",
        name="Hostname",
        status="healthy",
        severity="info",
        message="Hostname: docker",
        metadata={
            "hostname": "docker",
        },
    )

    restored = OperationFinding.from_dict(
        finding.to_dict(),
    )

    assert restored == finding
    assert restored.to_dict() == finding.to_dict()


def test_operation_finding_from_dict_normalizes_inputs() -> None:
    finding = OperationFinding.from_dict(
        {
            "identifier": " System_Hostname ",
            "name": " Hostname ",
            "status": " HEALTHY ",
            "severity": " INFO ",
            "message": " Hostname: Docker ",
            "recommendation": None,
            "metadata": {
                "hostname": "docker",
            },
        }
    )

    assert finding.identifier == "system-hostname"
    assert finding.name == "Hostname"
    assert finding.status is OperationsStatus.HEALTHY
    assert finding.severity is OperationsSeverity.INFO
    assert finding.message == "Hostname: Docker"


def test_operation_finding_from_dict_ignores_derived_fields() -> None:
    finding = OperationFinding.from_dict(
        {
            "identifier": "system.hostname",
            "name": "Hostname",
            "status": "healthy",
            "severity": "info",
            "message": "Hostname: docker",
            "metadata": {},
            "score": 0,
            "action_required": True,
        }
    )

    assert finding.score == 100
    assert finding.action_required is False


def test_operation_finding_from_dict_rejects_non_object() -> None:
    with pytest.raises(
        OperationsModelError,
        match="finding payload must be an object",
    ):
        OperationFinding.from_dict(
            [],  # type: ignore[arg-type]
        )


def test_operation_finding_from_dict_validates_contract() -> None:
    with pytest.raises(
        OperationsModelError,
        match="identifier must be text",
    ):
        OperationFinding.from_dict(
            {
                "name": "Hostname",
                "status": "healthy",
                "severity": "info",
                "message": "Hostname: docker",
            }
        )


def test_operations_section_from_dict_round_trip() -> None:
    section = OperationsSection(
        identifier="system",
        name="System",
        description="Host operating-system information",
        findings=(
            OperationFinding(
                identifier="system.hostname",
                name="Hostname",
                status="healthy",
                severity="info",
                message="Hostname: docker",
            ),
        ),
    )

    restored = OperationsSection.from_dict(
        section.to_dict(),
    )

    assert restored == section
    assert restored.to_dict() == section.to_dict()


def test_operations_section_from_dict_normalizes_inputs() -> None:
    section = OperationsSection.from_dict(
        {
            "identifier": " SYSTEM ",
            "name": " System ",
            "description": " Host information ",
            "findings": [
                {
                    "identifier": "system.hostname",
                    "name": "Hostname",
                    "status": "healthy",
                    "severity": "info",
                    "message": "Hostname: docker",
                    "metadata": {},
                },
            ],
        }
    )

    assert section.identifier is OperationsSectionId.SYSTEM
    assert section.name == "System"
    assert section.description == "Host information"
    assert len(section.findings) == 1


def test_operations_section_from_dict_ignores_derived_fields() -> None:
    section = OperationsSection.from_dict(
        {
            "identifier": "system",
            "name": "System",
            "description": None,
            "status": "critical",
            "score": 0,
            "finding_count": 99,
            "status_counts": {
                "healthy": 0,
                "warning": 0,
                "critical": 99,
                "unknown": 0,
            },
            "attention_findings": [
                "system.hostname",
            ],
            "findings": [
                {
                    "identifier": "system.hostname",
                    "name": "Hostname",
                    "status": "healthy",
                    "severity": "info",
                    "message": "Hostname: docker",
                    "metadata": {},
                    "score": 0,
                    "action_required": True,
                },
            ],
        }
    )

    assert section.status is OperationsStatus.HEALTHY
    assert section.score == 100
    assert section.healthy_count == 1
    assert section.critical_count == 0
    assert section.attention_findings == ()


def test_operations_section_from_dict_rejects_non_object() -> None:
    with pytest.raises(
        OperationsModelError,
        match="section payload must be an object",
    ):
        OperationsSection.from_dict(
            [],  # type: ignore[arg-type]
        )


def test_operations_section_from_dict_rejects_non_list_findings() -> None:
    with pytest.raises(
        OperationsModelError,
        match="section findings must be a list or tuple",
    ):
        OperationsSection.from_dict(
            {
                "identifier": "system",
                "name": "System",
                "findings": {},
            }
        )


def test_operations_section_from_dict_validates_child_contracts() -> None:
    with pytest.raises(
        OperationsModelError,
        match="finding payload must be an object",
    ):
        OperationsSection.from_dict(
            {
                "identifier": "system",
                "name": "System",
                "findings": [
                    [],
                ],
            }
        )


def test_operations_section_from_dict_validates_identity() -> None:
    with pytest.raises(
        OperationsModelError,
        match="identifier is not a supported Operations section",
    ):
        OperationsSection.from_dict(
            {
                "identifier": "unsupported",
                "name": "Unsupported",
                "findings": [],
            }
        )


def test_operations_report_from_dict_round_trip() -> None:
    report = OperationsReport(
        report_id="nightly-operations",
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="491e0a77",
        generated_at="2026-08-03T22:00:00Z",
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(
                    OperationFinding(
                        identifier="system.hostname",
                        name="Hostname",
                        status="healthy",
                        severity="info",
                        message="Hostname: docker",
                    ),
                ),
            ),
        ),
    )

    restored = OperationsReport.from_dict(
        report.to_dict(),
    )

    assert restored == report
    assert restored.to_dict() == report.to_dict()


def test_operations_report_from_dict_normalizes_inputs() -> None:
    report = OperationsReport.from_dict(
        {
            "schema_version": OPERATIONS_SCHEMA_VERSION,
            "report_id": " Nightly_Operations ",
            "hostname": " DOCKER ",
            "atlas_version": " 0.9.0-rc.1 ",
            "git_commit": " 491E0A77 ",
            "generated_at": "2026-08-03T18:00:00-04:00",
            "sections": [],
        }
    )

    assert report.report_id == "nightly-operations"
    assert report.hostname == "docker"
    assert report.atlas_version == "0.9.0-rc.1"
    assert report.git_commit == "491e0a77"
    assert report.generated_at == "2026-08-03T22:00:00Z"


def test_operations_report_from_dict_ignores_derived_fields() -> None:
    report = OperationsReport.from_dict(
        {
            "schema_version": OPERATIONS_SCHEMA_VERSION,
            "report_id": "operations-report",
            "hostname": "docker",
            "atlas_version": "0.9.0-rc.1",
            "git_commit": "491e0a77",
            "generated_at": "2026-08-03T22:00:00Z",
            "status": "critical",
            "score": 0,
            "summary": {
                "status": "critical",
                "score": 0,
                "section_count": 99,
                "finding_count": 99,
            },
            "attention_findings": [
                {
                    "section": "system",
                    "identifier": "system.hostname",
                },
            ],
            "sections": [
                {
                    "identifier": "system",
                    "name": "System",
                    "findings": [
                        {
                            "identifier": "system.hostname",
                            "name": "Hostname",
                            "status": "healthy",
                            "severity": "info",
                            "message": "Hostname: docker",
                            "metadata": {},
                        },
                    ],
                },
            ],
        }
    )

    assert report.status is OperationsStatus.HEALTHY
    assert report.score == 100
    assert report.summary.section_count == 1
    assert report.summary.finding_count == 1
    assert report.attention_findings == ()


def test_operations_report_from_dict_rejects_non_object() -> None:
    with pytest.raises(
        OperationsModelError,
        match="report payload must be an object",
    ):
        OperationsReport.from_dict(
            [],  # type: ignore[arg-type]
        )


def test_operations_report_from_dict_requires_schema_version() -> None:
    with pytest.raises(
        OperationsModelError,
        match="schema_version is not supported",
    ):
        OperationsReport.from_dict(
            {
                "report_id": "operations-report",
                "hostname": "docker",
                "atlas_version": "0.9.0-rc.1",
                "git_commit": "491e0a77",
                "generated_at": "2026-08-03T22:00:00Z",
                "sections": [],
            }
        )


def test_operations_report_from_dict_rejects_future_schema() -> None:
    with pytest.raises(
        OperationsModelError,
        match="schema_version is not supported",
    ):
        OperationsReport.from_dict(
            {
                "schema_version": OPERATIONS_SCHEMA_VERSION + 1,
                "report_id": "operations-report",
                "hostname": "docker",
                "atlas_version": "0.9.0-rc.1",
                "git_commit": "491e0a77",
                "generated_at": "2026-08-03T22:00:00Z",
                "sections": [],
            }
        )


def test_operations_report_from_dict_rejects_non_list_sections() -> None:
    with pytest.raises(
        OperationsModelError,
        match="report sections must be a list or tuple",
    ):
        OperationsReport.from_dict(
            {
                "schema_version": OPERATIONS_SCHEMA_VERSION,
                "report_id": "operations-report",
                "hostname": "docker",
                "atlas_version": "0.9.0-rc.1",
                "git_commit": "491e0a77",
                "generated_at": "2026-08-03T22:00:00Z",
                "sections": {},
            }
        )


def test_operations_report_from_dict_validates_child_contracts() -> None:
    with pytest.raises(
        OperationsModelError,
        match="section payload must be an object",
    ):
        OperationsReport.from_dict(
            {
                "schema_version": OPERATIONS_SCHEMA_VERSION,
                "report_id": "operations-report",
                "hostname": "docker",
                "atlas_version": "0.9.0-rc.1",
                "git_commit": "491e0a77",
                "generated_at": "2026-08-03T22:00:00Z",
                "sections": [
                    [],
                ],
            }
        )


def test_operations_report_from_dict_validates_report_contract() -> None:
    with pytest.raises(
        OperationsModelError,
        match="report_id must be text",
    ):
        OperationsReport.from_dict(
            {
                "schema_version": OPERATIONS_SCHEMA_VERSION,
                "hostname": "docker",
                "atlas_version": "0.9.0-rc.1",
                "git_commit": "491e0a77",
                "generated_at": "2026-08-03T22:00:00Z",
                "sections": [],
            }
        )
