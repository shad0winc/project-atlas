"""Tests for Atlas Portal scheduler widget contracts."""

from __future__ import annotations

from pydantic import ValidationError
import pytest

from atlas_api.schemas.portal_dashboard import (
    PortalSchedulerFailureResponse,
    PortalSchedulerSummaryResponse,
)


def test_available_scheduler_state_is_valid() -> None:
    response = PortalSchedulerSummaryResponse(
        status="available",
        registered_count=5,
        enabled_count=5,
        disabled_count=0,
        due_count=0,
        running_count=0,
        failed_count=0,
        last_run_at="2026-08-04T04:30:00Z",
        next_run_at="2026-08-04T05:00:00Z",
    )

    assert response.status == "available"
    assert response.failed_count == 0


def test_unavailable_scheduler_state_is_valid() -> None:
    response = PortalSchedulerSummaryResponse(
        status="unavailable",
        detail="Scheduler runtime state unavailable.",
    )

    assert response.status == "unavailable"
    assert response.detail is not None


def test_available_scheduler_requires_metrics() -> None:
    with pytest.raises(
        ValidationError,
    ):
        PortalSchedulerSummaryResponse(
            status="available",
        )


def test_unavailable_scheduler_rejects_metrics() -> None:
    with pytest.raises(
        ValidationError,
    ):
        PortalSchedulerSummaryResponse(
            status="unavailable",
            detail="Unavailable",
            registered_count=1,
        )


def test_recent_failures_are_bounded_contract_objects() -> None:
    failure = PortalSchedulerFailureResponse(
        task_name="operations.collect",
        failed_at="2026-08-04T04:00:00Z",
        error="Collection failed.",
    )

    response = PortalSchedulerSummaryResponse(
        status="available",
        registered_count=1,
        enabled_count=1,
        disabled_count=0,
        due_count=0,
        running_count=0,
        failed_count=1,
        recent_failures=(
            failure,
        ),
    )

    assert response.recent_failures[0].task_name == (
        "operations.collect"
    )


def test_scheduler_json_serialization() -> None:
    response = PortalSchedulerSummaryResponse(
        status="available",
        registered_count=1,
        enabled_count=1,
        disabled_count=0,
        due_count=0,
        running_count=0,
        failed_count=0,
        recent_failures=(),
    )

    payload = response.model_dump(
        mode="json",
    )

    assert payload["recent_failures"] == []
