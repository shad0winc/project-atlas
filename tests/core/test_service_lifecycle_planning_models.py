"""Tests for guarded Service Lifecycle planning contracts."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    ImageReference,
    ServiceLifecycleError,
    ServiceUpdateOutcome,
    ServiceUpdatePlan,
    ServiceUpdateResult,
)


CURRENT = ImageReference.parse(
    "registry.example/atlas/service:1.0.0"
)
TARGET = ImageReference.parse(
    "registry.example/atlas/service:1.1.0"
)


def make_plan(**overrides):
    payload = {
        "plan_id": "plan-001",
        "service_identifier": "sonarr",
        "service_name": "Sonarr",
        "current_image": CURRENT,
        "target_image": TARGET,
        "requested_by": "administrator",
        "dependencies": ("prowlarr",),
        "dry_run": True,
        "created_at": "2026-08-14T03:00:00Z",
        "correlation_id": "corr-001",
        "warnings": (),
        "details": {"source": "test"},
    }
    payload.update(overrides)
    return ServiceUpdatePlan(**payload)


def make_result(**overrides):
    payload = {
        "operation_id": "op-001",
        "plan_id": "plan-001",
        "service_identifier": "sonarr",
        "service_name": "Sonarr",
        "outcome": ServiceUpdateOutcome.SUCCEEDED,
        "previous_image": CURRENT,
        "resulting_image": TARGET,
        "started_at": "2026-08-14T03:00:00Z",
        "completed_at": "2026-08-14T03:00:05Z",
        "rollback_performed": False,
        "correlation_id": "corr-001",
    }
    payload.update(overrides)
    return ServiceUpdateResult(**payload)


def test_update_plan_normalizes_identity_and_timestamp():
    plan = make_plan(
        plan_id=" PLAN-001 ",
        service_identifier=" SONARR ",
        created_at="2026-08-13T23:00:00-04:00",
    )

    assert plan.plan_id == "plan-001"
    assert plan.service_identifier == "sonarr"
    assert plan.created_at == "2026-08-14T03:00:00Z"


def test_update_plan_is_immutable():
    plan = make_plan()

    with pytest.raises(FrozenInstanceError):
        plan.plan_id = "changed"


def test_update_plan_requires_dry_run():
    with pytest.raises(
        ServiceLifecycleError,
        match="must be dry-run",
    ):
        make_plan(dry_run=False)


def test_update_plan_rejects_same_image():
    with pytest.raises(
        ServiceLifecycleError,
        match="target_image must differ",
    ):
        make_plan(target_image=CURRENT)


def test_update_plan_rejects_duplicate_dependencies():
    with pytest.raises(
        ServiceLifecycleError,
        match="must not contain duplicates",
    ):
        make_plan(
            dependencies=("prowlarr", "PROWLARR"),
        )


def test_update_plan_serializes():
    payload = make_plan().to_dict()

    assert payload["plan_id"] == "plan-001"
    assert payload["service_identifier"] == "sonarr"
    assert payload["dry_run"] is True
    assert payload["dependencies"] == ["prowlarr"]
    assert payload["current_image"]["tag"] == "1.0.0"
    assert payload["target_image"]["tag"] == "1.1.0"


def test_update_result_normalizes_outcome():
    result = make_result(outcome="SUCCEEDED")

    assert result.outcome is ServiceUpdateOutcome.SUCCEEDED
    assert result.succeeded is True


def test_update_result_rejects_reverse_time():
    with pytest.raises(
        ServiceLifecycleError,
        match="must not precede",
    ):
        make_result(
            started_at="2026-08-14T03:00:05Z",
            completed_at="2026-08-14T03:00:00Z",
        )


def test_update_result_rollback_id_requires_rollback():
    with pytest.raises(
        ServiceLifecycleError,
        match="requires rollback_performed",
    ):
        make_result(
            rollback_operation_id="rollback-001",
        )


def test_rolled_back_result_requires_rollback_performed():
    with pytest.raises(
        ServiceLifecycleError,
        match="requires rollback_performed",
    ):
        make_result(
            outcome=ServiceUpdateOutcome.ROLLED_BACK,
        )


def test_update_result_serializes():
    result = make_result(
        outcome=ServiceUpdateOutcome.ROLLED_BACK,
        resulting_image=CURRENT,
        rollback_performed=True,
        rollback_operation_id="rollback-001",
        warnings=("health validation failed",),
    )

    payload = result.to_dict()

    assert payload["outcome"] == "rolled-back"
    assert payload["succeeded"] is False
    assert payload["rollback_performed"] is True
    assert payload["rollback_operation_id"] == "rollback-001"
