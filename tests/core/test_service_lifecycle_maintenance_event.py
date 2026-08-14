"""Tests for lifecycle MaintenanceEvent."""

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    MaintenanceEvent,
    MaintenanceResult,
    ServiceLifecycleError,
)


def make_event(**overrides):
    payload = {
        "event_id": "event-001",
        "service_identifier": "sonarr",
        "operation_type": "update",
        "requested_by": "administrator",
        "started_at": "2026-08-14T03:00:00Z",
        "completed_at": "2026-08-14T03:00:05Z",
        "previous_state": {"state": "running"},
        "resulting_state": {"state": "running"},
        "outcome": MaintenanceResult.SUCCESS,
        "warnings": (),
        "errors": (),
        "rollback_information": {},
        "correlation_id": "corr-001",
    }
    payload.update(overrides)
    return MaintenanceEvent(**payload)


def test_event_normalizes_identity_and_timestamps():
    event = make_event(
        event_id=" EVENT-001 ",
        service_identifier=" SONARR ",
        started_at="2026-08-13T23:00:00-04:00",
    )

    assert event.event_id == "event-001"
    assert event.service_identifier == "sonarr"
    assert event.started_at == "2026-08-14T03:00:00Z"


def test_event_is_immutable():
    event = make_event()

    with pytest.raises(FrozenInstanceError):
        event.event_id = "changed"


def test_event_validates_previous_state():
    with pytest.raises(
        ServiceLifecycleError,
        match="previous_state must be an object",
    ):
        make_event(previous_state="running")


def test_event_validates_resulting_state():
    with pytest.raises(
        ServiceLifecycleError,
        match="resulting_state must be an object or null",
    ):
        make_event(resulting_state="running")


def test_event_rejects_reverse_time():
    with pytest.raises(
        ServiceLifecycleError,
        match="must not precede",
    ):
        make_event(
            started_at="2026-08-14T03:00:05Z",
            completed_at="2026-08-14T03:00:00Z",
        )


def test_event_serializes_adr_fields():
    payload = make_event(
        warnings=("warning",),
        errors=("error",),
        rollback_information={
            "performed": False,
        },
    ).to_dict()

    assert payload == {
        "event_id": "event-001",
        "service_identifier": "sonarr",
        "operation_type": "update",
        "requested_by": "administrator",
        "started_at": "2026-08-14T03:00:00Z",
        "completed_at": "2026-08-14T03:00:05Z",
        "previous_state": {"state": "running"},
        "resulting_state": {"state": "running"},
        "outcome": "success",
        "warnings": ["warning"],
        "errors": ["error"],
        "rollback_information": {
            "performed": False,
        },
        "correlation_id": "corr-001",
    }
