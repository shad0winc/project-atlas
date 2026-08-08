"""Tests for startup-policy finding and report contracts."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from atlas.service_lifecycle.models import (
    ServiceLifecycleError,
)
from atlas.service_lifecycle.startup_policy_models import (
    StartupPolicyFinding,
    StartupPolicyReport,
    StartupPolicySeverity,
)


EVALUATED_AT = "2026-08-04T16:00:00+00:00"


def finding(
    identifier: str = "portal.restart-policy",
    *,
    severity: StartupPolicySeverity | str = (
        StartupPolicySeverity.WARNING
    ),
    service_identifier: str | None = "portal",
) -> StartupPolicyFinding:
    return StartupPolicyFinding(
        identifier=identifier,
        code="restart-policy-missing",
        severity=severity,
        message="Portal has no restart policy.",
        service_identifier=service_identifier,
        recommendation=(
            "Configure an approved restart policy."
        ),
        details={
            "restart_policy": None,
        },
    )


def test_finding_normalizes_fields() -> None:
    result = StartupPolicyFinding(
        identifier=" Portal.Restart-Policy ",
        code=" Restart-Policy-Missing ",
        severity=" WARNING ",
        message="  Portal has no restart policy. ",
        service_identifier=" PORTAL ",
        recommendation=" Configure a restart policy. ",
        details={
            " source ": "compose",
        },
    )

    assert result.identifier == "portal.restart-policy"
    assert result.code == "restart-policy-missing"
    assert result.severity is StartupPolicySeverity.WARNING
    assert result.message == "Portal has no restart policy."
    assert result.service_identifier == "portal"
    assert (
        result.recommendation
        == "Configure a restart policy."
    )
    assert result.details == {
        "source": "compose",
    }
    assert isinstance(
        result.details,
        MappingProxyType,
    )
    assert result.requires_attention is True


@pytest.mark.parametrize(
    "severity",
    tuple(StartupPolicySeverity),
)
def test_finding_accepts_supported_severity(
    severity: StartupPolicySeverity,
) -> None:
    result = finding(
        severity=severity,
    )

    assert result.severity is severity


@pytest.mark.parametrize(
    "severity",
    (
        "",
        "healthy",
        "unknown",
        None,
        True,
    ),
)
def test_finding_rejects_invalid_severity(
    severity: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="supported startup policy severity",
    ):
        StartupPolicyFinding(
            identifier="portal.restart",
            code="restart-policy",
            severity=severity,  # type: ignore[arg-type]
            message="Invalid.",
        )


def test_info_finding_does_not_require_attention() -> None:
    result = finding(
        severity=StartupPolicySeverity.INFO,
    )

    assert result.requires_attention is False


def test_finding_serializes_normalized_contract() -> None:
    result = finding()

    assert result.to_dict() == {
        "identifier": "portal.restart-policy",
        "code": "restart-policy-missing",
        "severity": "warning",
        "message": "Portal has no restart policy.",
        "service_identifier": "portal",
        "recommendation": (
            "Configure an approved restart policy."
        ),
        "requires_attention": True,
        "details": {
            "restart_policy": None,
        },
    }


def test_report_sorts_findings_deterministically() -> None:
    report = StartupPolicyReport(
        findings=(
            finding(
                "z.info",
                severity=StartupPolicySeverity.INFO,
                service_identifier="zulu",
            ),
            finding(
                "b.warning",
                severity=StartupPolicySeverity.WARNING,
                service_identifier="beta",
            ),
            finding(
                "a.critical",
                severity=StartupPolicySeverity.CRITICAL,
                service_identifier="alpha",
            ),
            finding(
                "a.error",
                severity=StartupPolicySeverity.ERROR,
                service_identifier="alpha",
            ),
            finding(
                "a.warning",
                severity=StartupPolicySeverity.WARNING,
                service_identifier="alpha",
            ),
        ),
        provider="docker-compose",
        evaluated_at=EVALUATED_AT,
    )

    assert tuple(
        item.identifier
        for item in report.findings
    ) == (
        "a.critical",
        "a.error",
        "a.warning",
        "b.warning",
        "z.info",
    )


@pytest.mark.parametrize(
    ("severity", "expected_status", "expected_passed"),
    (
        (
            StartupPolicySeverity.INFO,
            "healthy",
            True,
        ),
        (
            StartupPolicySeverity.WARNING,
            "degraded",
            True,
        ),
        (
            StartupPolicySeverity.ERROR,
            "unhealthy",
            False,
        ),
        (
            StartupPolicySeverity.CRITICAL,
            "critical",
            False,
        ),
    ),
)
def test_report_derives_status_and_passed(
    severity: StartupPolicySeverity,
    expected_status: str,
    expected_passed: bool,
) -> None:
    report = StartupPolicyReport(
        findings=(
            finding(
                severity=severity,
            ),
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert report.status == expected_status
    assert report.passed is expected_passed


def test_empty_report_is_healthy_and_passes() -> None:
    report = StartupPolicyReport(
        evaluated_at=EVALUATED_AT,
    )

    assert report.status == "healthy"
    assert report.passed is True
    assert report.requires_attention is False
    assert report.attention == ()
    assert report.counts == {
        "info": 0,
        "warning": 0,
        "error": 0,
        "critical": 0,
    }


def test_report_exposes_attention_and_counts() -> None:
    report = StartupPolicyReport(
        findings=(
            finding(
                "portal.info",
                severity=StartupPolicySeverity.INFO,
            ),
            finding(
                "portal.warning",
                severity=StartupPolicySeverity.WARNING,
            ),
            finding(
                "portal.error",
                severity=StartupPolicySeverity.ERROR,
            ),
        ),
        evaluated_at=EVALUATED_AT,
    )

    assert report.requires_attention is True
    assert tuple(
        item.identifier
        for item in report.attention
    ) == (
        "portal.error",
        "portal.warning",
    )
    assert report.counts == {
        "info": 1,
        "warning": 1,
        "error": 1,
        "critical": 0,
    }


def test_report_rejects_duplicate_identifiers() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="unique identifiers",
    ):
        StartupPolicyReport(
            findings=(
                finding(),
                finding(),
            ),
            evaluated_at=EVALUATED_AT,
        )


def test_report_requires_finding_tuple() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="findings must be a tuple",
    ):
        StartupPolicyReport(
            findings=[],  # type: ignore[arg-type]
            evaluated_at=EVALUATED_AT,
        )


@pytest.mark.parametrize(
    "evaluated_at",
    (
        "",
        "not-a-timestamp",
        "2026-08-04T16:00:00",
    ),
)
def test_report_requires_timezone_aware_timestamp(
    evaluated_at: str,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="evaluated_at",
    ):
        StartupPolicyReport(
            evaluated_at=evaluated_at,
        )


def test_report_normalizes_timestamp_to_utc() -> None:
    report = StartupPolicyReport(
        evaluated_at="2026-08-04T12:00:00-04:00",
    )

    assert report.evaluated_at == EVALUATED_AT


def test_report_serializes_complete_contract() -> None:
    report = StartupPolicyReport(
        findings=(
            finding(),
        ),
        provider="Docker-Compose",
        evaluated_at=EVALUATED_AT,
    )

    assert report.to_dict() == {
        "provider": "docker-compose",
        "status": "degraded",
        "passed": True,
        "requires_attention": True,
        "finding_count": 1,
        "counts": {
            "info": 0,
            "warning": 1,
            "error": 0,
            "critical": 0,
        },
        "attention_findings": [
            "portal.restart-policy",
        ],
        "findings": [
            finding().to_dict(),
        ],
        "evaluated_at": EVALUATED_AT,
    }
