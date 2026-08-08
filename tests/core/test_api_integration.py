"""Integration tests for the Project Atlas API foundation."""

from __future__ import annotations

import json

from atlas.api import (
    ApiError,
    ApiFailureResponse,
    ApiSuccessResponse,
    to_api_json,
    to_api_value,
)
from atlas.operations import (
    OperationFinding,
    OperationsComparisonService,
    OperationsReport,
    OperationsSection,
)


GENERATED_AT = "2026-08-04T00:00:00Z"


def report(
    *,
    report_id: str,
    generated_at: str,
    warning: bool,
) -> OperationsReport:
    finding = OperationFinding(
        identifier="system.memory",
        name="Memory",
        status="warning" if warning else "healthy",
        severity="warning" if warning else "info",
        message=(
            "Memory usage is elevated"
            if warning
            else "Memory usage is healthy"
        ),
        metadata={
            "percent": 90 if warning else 40,
        },
    )

    return OperationsReport(
        report_id=report_id,
        hostname="docker",
        atlas_version="0.9.0-rc.1",
        git_commit="80cf3c7b",
        generated_at=generated_at,
        sections=(
            OperationsSection(
                identifier="system",
                name="System",
                findings=(finding,),
            ),
        ),
    )


def test_success_response_serializes_operations_report() -> None:
    operations_report = report(
        report_id="latest-report",
        generated_at="2026-08-04T00:00:00Z",
        warning=False,
    )

    response = ApiSuccessResponse(
        data={
            "report": operations_report,
        },
        generated_at=GENERATED_AT,
    )

    payload = to_api_value(response)

    assert payload["success"] is True
    assert payload["schema_version"] == 1
    assert payload["api_version"] == "v1"

    serialized_report = payload["data"]["report"]

    assert serialized_report["report_id"] == "latest-report"
    assert serialized_report["status"] == "healthy"
    assert serialized_report["score"] == 100
    assert serialized_report["sections"][0]["identifier"] == (
        "system"
    )


def test_success_response_serializes_operations_history() -> None:
    reports = (
        report(
            report_id="newest-report",
            generated_at="2026-08-04T00:00:00Z",
            warning=False,
        ),
        report(
            report_id="older-report",
            generated_at="2026-08-03T23:00:00Z",
            warning=True,
        ),
    )

    response = ApiSuccessResponse(
        data={
            "count": len(reports),
            "reports": reports,
        },
        generated_at=GENERATED_AT,
    )

    payload = to_api_value(response)

    assert payload["data"]["count"] == 2
    assert [
        item["report_id"]
        for item in payload["data"]["reports"]
    ] == [
        "newest-report",
        "older-report",
    ]


def test_success_response_serializes_operations_comparison() -> None:
    previous = report(
        report_id="previous-report",
        generated_at="2026-08-03T23:00:00Z",
        warning=False,
    )
    current = report(
        report_id="current-report",
        generated_at="2026-08-04T00:00:00Z",
        warning=True,
    )

    comparison = OperationsComparisonService().compare(
        previous,
        current,
    )

    response = ApiSuccessResponse(
        data={
            "comparison": comparison,
        },
        generated_at=GENERATED_AT,
    )

    payload = to_api_value(response)
    serialized = payload["data"]["comparison"]

    assert serialized["previous"]["report_id"] == (
        "previous-report"
    )
    assert serialized["current"]["report_id"] == (
        "current-report"
    )
    assert serialized["summary"]["changed_count"] == 1
    assert serialized["summary"]["difference_count"] == 1
    assert serialized["summary"]["score_delta"] == -50


def test_api_json_renders_complete_operations_contract() -> None:
    operations_report = report(
        report_id="json-report",
        generated_at=GENERATED_AT,
        warning=False,
    )

    response = ApiSuccessResponse(
        data={
            "report": operations_report,
        },
        generated_at=GENERATED_AT,
    )

    rendered = to_api_json(
        response,
        indent=None,
    )
    payload = json.loads(rendered)

    assert rendered.startswith(
        '{"api_version":"v1",'
    )
    assert payload["data"]["report"]["report_id"] == (
        "json-report"
    )
    assert payload["generated_at"] == GENERATED_AT


def test_failure_response_serializes_domain_context() -> None:
    response = ApiFailureResponse(
        error=ApiError(
            code="operations_report_not_found",
            message="Operations report was not found",
            details={
                "report_id": "missing-report",
                "resource": "operations_report",
            },
        ),
        generated_at=GENERATED_AT,
    )

    payload = to_api_value(response)

    assert payload == {
        "api_version": "v1",
        "error": {
            "code": "operations_report_not_found",
            "details": {
                "report_id": "missing-report",
                "resource": "operations_report",
            },
            "message": "Operations report was not found",
        },
        "generated_at": GENERATED_AT,
        "schema_version": 1,
        "success": False,
    }


def test_api_foundation_does_not_mutate_domain_contract() -> None:
    operations_report = report(
        report_id="immutable-report",
        generated_at=GENERATED_AT,
        warning=False,
    )
    before = operations_report.to_dict()

    response = ApiSuccessResponse(
        data={
            "report": operations_report,
        },
        generated_at=GENERATED_AT,
    )

    to_api_value(response)
    to_api_json(response)

    assert operations_report.to_dict() == before
