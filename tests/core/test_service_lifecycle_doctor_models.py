"""Tests for normalized Service Doctor domain contracts."""

from __future__ import annotations

import pytest

from atlas.service_lifecycle import (
    DoctorCategory,
    DoctorFinding,
    DoctorReport,
    DoctorSeverity,
    ServiceLifecycleError,
)


TIMESTAMP = "2026-08-02T00:00:00Z"


def make_finding(**overrides: object) -> DoctorFinding:
    values: dict[str, object] = {
        "identifier": "sonarr-health-unhealthy",
        "severity": DoctorSeverity.ERROR,
        "category": DoctorCategory.HEALTH,
        "code": "health.unhealthy",
        "message": "Service health is unhealthy.",
        "service_identifier": "sonarr",
        "details": {"health": "unhealthy"},
        "created_at": TIMESTAMP,
    }
    values.update(overrides)
    return DoctorFinding(**values)  # type: ignore[arg-type]


def test_finding_normalizes_inputs_and_serializes() -> None:
    finding = make_finding(
        identifier="  SONARR-HEALTH-UNHEALTHY  ",
        severity=" ERROR ",
        category=" HEALTH ",
        code=" HEALTH.UNHEALTHY ",
        message="  Service health is unhealthy.  ",
        service_identifier=" SONARR ",
        created_at="2026-08-01T20:00:00-04:00",
    )

    assert finding.identifier == "sonarr-health-unhealthy"
    assert finding.severity is DoctorSeverity.ERROR
    assert finding.category is DoctorCategory.HEALTH
    assert finding.code == "health.unhealthy"
    assert finding.message == "Service health is unhealthy."
    assert finding.service_identifier == "sonarr"
    assert finding.created_at == TIMESTAMP
    assert finding.requires_attention is True
    assert finding.to_dict() == {
        "identifier": "sonarr-health-unhealthy",
        "severity": "error",
        "category": "health",
        "code": "health.unhealthy",
        "message": "Service health is unhealthy.",
        "service_identifier": "sonarr",
        "requires_attention": True,
        "details": {"health": "unhealthy"},
        "created_at": TIMESTAMP,
    }


@pytest.mark.parametrize(
    ("severity", "requires_attention"),
    [
        (DoctorSeverity.INFO, False),
        (DoctorSeverity.WARNING, True),
        (DoctorSeverity.ERROR, True),
        (DoctorSeverity.CRITICAL, True),
    ],
)
def test_finding_attention_contract(
    severity: DoctorSeverity,
    requires_attention: bool,
) -> None:
    assert make_finding(severity=severity).requires_attention is requires_attention


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("identifier", "bad/value", "invalid identifier"),
        ("severity", "notice", "invalid severity"),
        ("category", "docker", "invalid category"),
        ("code", "bad value", "invalid code"),
        ("message", "   ", "message must be non-empty text"),
        (
            "service_identifier",
            "bad/value",
            "invalid service_identifier",
        ),
        (
            "created_at",
            "2026-08-02T00:00:00",
            "created_at must include a timezone",
        ),
    ],
)
def test_finding_rejects_invalid_contracts(
    field_name: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ServiceLifecycleError, match=message):
        make_finding(**{field_name: value})


def test_finding_requires_details_mapping() -> None:
    with pytest.raises(ServiceLifecycleError, match="details must be an object"):
        make_finding(details=[("health", "unhealthy")])


@pytest.mark.parametrize(
    ("severities", "expected"),
    [
        ((), "healthy"),
        ((DoctorSeverity.INFO,), "healthy"),
        ((DoctorSeverity.WARNING,), "degraded"),
        ((DoctorSeverity.ERROR,), "unhealthy"),
        ((DoctorSeverity.CRITICAL,), "critical"),
        (
            (DoctorSeverity.INFO, DoctorSeverity.ERROR),
            "unhealthy",
        ),
    ],
)
def test_report_status_uses_highest_severity(
    severities: tuple[DoctorSeverity, ...],
    expected: str,
) -> None:
    findings = tuple(
        make_finding(
            identifier=f"finding-{index}",
            severity=severity,
        )
        for index, severity in enumerate(severities, start=1)
    )

    report = DoctorReport(
        findings=findings,
        provider="docker-compose",
        evaluated_at=TIMESTAMP,
    )

    assert report.status == expected


def test_report_normalizes_orders_and_serializes_findings() -> None:
    info = make_finding(
        identifier="info-finding",
        severity=DoctorSeverity.INFO,
        category=DoctorCategory.OBSERVABILITY,
        code="healthcheck.present",
    )
    critical = make_finding(
        identifier="critical-finding",
        severity=DoctorSeverity.CRITICAL,
        category=DoctorCategory.RUNTIME,
        code="runtime.restart-loop",
    )
    warning = make_finding(
        identifier="warning-finding",
        severity=DoctorSeverity.WARNING,
        category=DoctorCategory.CONFIGURATION,
        code="healthcheck.missing",
    )

    report = DoctorReport(
        findings=[info, warning, critical],  # type: ignore[arg-type]
        provider=" DOCKER-COMPOSE ",
        evaluated_at="2026-08-01T20:00:00-04:00",
    )

    assert report.findings == (critical, warning, info)
    assert report.provider == "docker-compose"
    assert report.evaluated_at == TIMESTAMP
    assert report.requires_attention is True
    assert report.attention == (critical, warning)
    assert report.counts == {
        "info": 1,
        "warning": 1,
        "error": 0,
        "critical": 1,
    }

    payload = report.to_dict()
    assert payload["status"] == "critical"
    assert payload["total_findings"] == 3
    assert payload["requires_attention"] is True
    assert [
        item["identifier"]
        for item in payload["findings"]
    ] == [
        "critical-finding",
        "warning-finding",
        "info-finding",
    ]


def test_report_requires_finding_collection() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="findings must be a collection",
    ):
        DoctorReport(findings="finding")  # type: ignore[arg-type]


def test_report_requires_finding_children() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="findings must contain DoctorFinding objects",
    ):
        DoctorReport(findings=("finding",))  # type: ignore[arg-type]


def test_report_rejects_duplicate_finding_identities() -> None:
    finding = make_finding()

    with pytest.raises(
        ServiceLifecycleError,
        match="doctor findings must have unique identifiers",
    ):
        DoctorReport(findings=(finding, finding))
