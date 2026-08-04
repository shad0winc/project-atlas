"""Tests for aggregate Atlas Portal dashboard schemas."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from atlas_api import schemas
from atlas_api.schemas.dashboard import (
    DashboardMetricResponse,
    DashboardSummaryResponse,
)
from atlas_api.schemas.dashboard_media import (
    DashboardMediaSummaryResponse,
    MediaLibraryResponse,
)
from atlas_api.schemas.health import HealthResponse
from atlas_api.schemas.portal_dashboard import (
    PortalDashboardResponse,
    PortalOperationsAttentionResponse,
    PortalOperationsComparisonResponse,
    PortalOperationsReportSummaryResponse,
    PortalOperationsSummaryResponse,
)


GENERATED_AT = "2026-08-04T04:00:00Z"


def operational_summary() -> DashboardSummaryResponse:
    return DashboardSummaryResponse(
        generated_at=GENERATED_AT,
        metrics=(
            DashboardMetricResponse(
                id="system-health",
                label="System health",
                value="100%",
                description="Aggregate Atlas health.",
                status="healthy",
                detail="4 checks",
            ),
        ),
    )


def media_summary() -> DashboardMediaSummaryResponse:
    return DashboardMediaSummaryResponse(
        generated_at=GENERATED_AT,
        libraries=(
            MediaLibraryResponse(
                id="movies",
                label="Movies",
                count=12,
                status="available",
                detail=None,
            ),
        ),
    )


def operations_report() -> dict[str, object]:
    return {
        "report_id": "operations-latest",
        "hostname": "docker",
        "status": "warning",
        "score": 75,
        "generated_at": GENERATED_AT,
    }


def report_summary() -> PortalOperationsReportSummaryResponse:
    return PortalOperationsReportSummaryResponse(
        status="warning",
        score=75,
        attention_count=1,
        generated_at=GENERATED_AT,
    )


def available_comparison() -> PortalOperationsComparisonResponse:
    return PortalOperationsComparisonResponse(
        status="available",
        score_delta=-25,
        attention_delta=1,
        added_count=0,
        removed_count=0,
        changed_count=1,
        unchanged_count=0,
        difference_count=1,
    )


def unavailable_comparison() -> PortalOperationsComparisonResponse:
    return PortalOperationsComparisonResponse(
        status="unavailable",
        detail=(
            "At least two persisted Operations reports "
            "are required for comparison."
        ),
    )


def attention_finding() -> PortalOperationsAttentionResponse:
    return PortalOperationsAttentionResponse(
        section="system",
        identifier="system.memory",
        name="Memory",
        status="warning",
        severity="warning",
        message="Memory usage is elevated",
        recommendation="Review memory usage.",
    )


def test_available_comparison_is_stable() -> None:
    assert available_comparison().model_dump() == {
        "status": "available",
        "score_delta": -25,
        "attention_delta": 1,
        "added_count": 0,
        "removed_count": 0,
        "changed_count": 1,
        "unchanged_count": 0,
        "difference_count": 1,
        "detail": None,
    }


def test_unavailable_comparison_is_stable() -> None:
    assert unavailable_comparison().model_dump() == {
        "status": "unavailable",
        "score_delta": None,
        "attention_delta": None,
        "added_count": None,
        "removed_count": None,
        "changed_count": None,
        "unchanged_count": None,
        "difference_count": None,
        "detail": (
            "At least two persisted Operations reports "
            "are required for comparison."
        ),
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (
            {
                "status": "available",
                "score_delta": 0,
                "attention_delta": 0,
                "added_count": 0,
                "removed_count": 0,
                "changed_count": None,
                "unchanged_count": 0,
                "difference_count": 0,
            },
            "available comparison requires all metrics",
        ),
        (
            {
                "status": "available",
                "score_delta": 0,
                "attention_delta": 0,
                "added_count": 0,
                "removed_count": 0,
                "changed_count": 0,
                "unchanged_count": 0,
                "difference_count": 0,
                "detail": "Unexpected detail",
            },
            "available comparison cannot include detail",
        ),
        (
            {
                "status": "available",
                "score_delta": 0,
                "attention_delta": 0,
                "added_count": 1,
                "removed_count": 1,
                "changed_count": 1,
                "unchanged_count": 0,
                "difference_count": 2,
            },
            "difference_count must equal",
        ),
        (
            {
                "status": "unavailable",
                "score_delta": 0,
                "detail": "Unavailable",
            },
            "unavailable comparison cannot include metrics",
        ),
        (
            {
                "status": "unavailable",
                "detail": "   ",
            },
            "unavailable comparison requires detail",
        ),
    ),
)
def test_comparison_rejects_contradictory_state(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        PortalOperationsComparisonResponse.model_validate(
            payload,
        )


def test_available_operations_section_is_stable() -> None:
    section = PortalOperationsSummaryResponse(
        status="available",
        report=operations_report(),
        summary=report_summary(),
        comparison=available_comparison(),
        recent_attention=(attention_finding(),),
    )

    assert section.model_dump(mode="json") == {
        "status": "available",
        "report": operations_report(),
        "detail": None,
        "summary": {
            "status": "warning",
            "score": 75,
            "attention_count": 1,
            "generated_at": GENERATED_AT,
        },
        "comparison": available_comparison().model_dump(),
        "recent_attention": [
            attention_finding().model_dump(),
        ],
    }


def test_unavailable_operations_section_is_stable() -> None:
    section = PortalOperationsSummaryResponse(
        status="unavailable",
        report=None,
        detail="No persisted Operations report is available.",
        summary=None,
        comparison=unavailable_comparison(),
        recent_attention=(),
    )

    assert section.model_dump(mode="json") == {
        "status": "unavailable",
        "report": None,
        "detail": (
            "No persisted Operations report is available."
        ),
        "summary": None,
        "comparison": unavailable_comparison().model_dump(),
        "recent_attention": [],
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (
            {
                "status": "available",
                "report": None,
                "summary": report_summary().model_dump(),
                "comparison": available_comparison().model_dump(),
            },
            "available Operations state requires a report",
        ),
        (
            {
                "status": "available",
                "report": operations_report(),
                "detail": "Unexpected detail",
                "summary": report_summary().model_dump(),
                "comparison": available_comparison().model_dump(),
            },
            "available Operations state cannot include detail",
        ),
        (
            {
                "status": "available",
                "report": operations_report(),
                "summary": None,
                "comparison": available_comparison().model_dump(),
            },
            "available Operations state requires a summary",
        ),
        (
            {
                "status": "unavailable",
                "report": operations_report(),
                "detail": "Unavailable",
                "comparison": unavailable_comparison().model_dump(),
            },
            "unavailable Operations state cannot include a report",
        ),
        (
            {
                "status": "unavailable",
                "report": None,
                "detail": "Unavailable",
                "summary": report_summary().model_dump(),
                "comparison": unavailable_comparison().model_dump(),
            },
            "unavailable Operations state cannot include a summary",
        ),
        (
            {
                "status": "unavailable",
                "report": None,
                "detail": "Unavailable",
                "summary": None,
                "comparison": unavailable_comparison().model_dump(),
                "recent_attention": [
                    attention_finding().model_dump(),
                ],
            },
            "unavailable Operations state cannot include attention",
        ),
    ),
)
def test_operations_section_rejects_contradictory_state(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        PortalOperationsSummaryResponse.model_validate(
            payload,
        )


def test_portal_dashboard_serialization_is_stable() -> None:
    dashboard = PortalDashboardResponse(
        health=HealthResponse(
            status="ok",
            service="atlas-api",
            api_version="v1",
        ),
        operational=operational_summary(),
        media=media_summary(),
        operations=PortalOperationsSummaryResponse(
            status="available",
            report=operations_report(),
            summary=report_summary(),
            comparison=available_comparison(),
            recent_attention=(attention_finding(),),
        ),
    )

    serialized = dashboard.model_dump(mode="json")

    assert serialized["health"] == {
        "status": "ok",
        "service": "atlas-api",
        "api_version": "v1",
    }
    assert serialized["operations"]["summary"] == {
        "status": "warning",
        "score": 75,
        "attention_count": 1,
        "generated_at": GENERATED_AT,
    }
    assert serialized["operations"]["comparison"][
        "difference_count"
    ] == 1
    assert serialized["operations"]["recent_attention"] == [
        attention_finding().model_dump(),
    ]


def test_portal_dashboard_forbids_extra_fields() -> None:
    payload = {
        "health": {
            "status": "ok",
            "service": "atlas-api",
            "api_version": "v1",
        },
        "operational": operational_summary().model_dump(),
        "media": media_summary().model_dump(),
        "operations": {
            "status": "unavailable",
            "report": None,
            "detail": "Unavailable",
            "summary": None,
            "comparison": unavailable_comparison().model_dump(),
            "recent_attention": [],
        },
        "unexpected": True,
    }

    with pytest.raises(ValidationError):
        PortalDashboardResponse.model_validate(payload)


def test_schema_package_exports_portal_contracts() -> None:
    expected = {
        "PortalDashboardResponse",
        "PortalOperationsAttentionResponse",
        "PortalOperationsComparisonResponse",
        "PortalOperationsReportSummaryResponse",
        "PortalOperationsStatus",
        "PortalOperationsSummaryResponse",
        "PortalSectionStatus",
    }

    assert expected.issubset(set(schemas.__all__))
