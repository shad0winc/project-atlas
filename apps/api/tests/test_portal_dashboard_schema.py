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
        "status": "healthy",
        "score": 100,
        "generated_at": GENERATED_AT,
    }


def test_available_operations_section_is_stable() -> None:
    section = PortalOperationsSummaryResponse(
        status="available",
        report=operations_report(),
    )

    assert section.model_dump() == {
        "status": "available",
        "report": operations_report(),
        "detail": None,
    }


def test_unavailable_operations_section_is_stable() -> None:
    section = PortalOperationsSummaryResponse(
        status="unavailable",
        report=None,
        detail="No persisted Operations report is available.",
    )

    assert section.model_dump() == {
        "status": "unavailable",
        "report": None,
        "detail": (
            "No persisted Operations report is available."
        ),
    }


@pytest.mark.parametrize(
    ("payload", "message"),
    (
        (
            {
                "status": "available",
                "report": None,
                "detail": None,
            },
            "available Operations state requires a report",
        ),
        (
            {
                "status": "available",
                "report": operations_report(),
                "detail": "Unexpected detail",
            },
            "available Operations state cannot include detail",
        ),
        (
            {
                "status": "unavailable",
                "report": operations_report(),
                "detail": "Unavailable",
            },
            "unavailable Operations state cannot include a report",
        ),
        (
            {
                "status": "unavailable",
                "report": None,
                "detail": "   ",
            },
            "unavailable Operations state requires detail",
        ),
    ),
)
def test_operations_section_rejects_contradictory_state(
    payload: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=message,
    ):
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
        ),
    )

    assert dashboard.model_dump(mode="json") == {
        "health": {
            "status": "ok",
            "service": "atlas-api",
            "api_version": "v1",
        },
        "operational": {
            "generated_at": GENERATED_AT,
            "metrics": [
                {
                    "id": "system-health",
                    "label": "System health",
                    "value": "100%",
                    "description": "Aggregate Atlas health.",
                    "status": "healthy",
                    "detail": "4 checks",
                },
            ],
        },
        "media": {
            "generated_at": GENERATED_AT,
            "libraries": [
                {
                    "id": "movies",
                    "label": "Movies",
                    "count": 12,
                    "status": "available",
                    "detail": None,
                },
            ],
        },
        "operations": {
            "status": "available",
            "report": operations_report(),
            "detail": None,
        },
    }


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
        },
        "unexpected": True,
    }

    with pytest.raises(ValidationError):
        PortalDashboardResponse.model_validate(payload)


def test_schema_package_exports_portal_contracts() -> None:
    assert (
        schemas.PortalDashboardResponse
        is PortalDashboardResponse
    )
    assert (
        schemas.PortalOperationsSummaryResponse
        is PortalOperationsSummaryResponse
    )
    assert "PortalSectionStatus" in schemas.__all__
