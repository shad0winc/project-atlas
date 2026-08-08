"""Tests for Service Lifecycle maintenance-history contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    MaintenanceAction,
    MaintenanceRecord,
    MaintenanceReport,
    MaintenanceResult,
    ServiceLifecycleError,
)


STARTED = "2026-08-02T02:20:00Z"
COMPLETED = "2026-08-02T02:20:05Z"


def make_record(**overrides: object) -> MaintenanceRecord:
    values: dict[str, object] = {
        "service_identifier": "sonarr",
        "service_name": "Sonarr",
        "action": MaintenanceAction.HEALTH_CHECK,
        "result": MaintenanceResult.SUCCESS,
        "started_at": STARTED,
        "completed_at": COMPLETED,
        "provider": "docker-compose",
        "summary": "Health inspection completed.",
        "details": {"source": "service-doctor"},
    }
    values.update(overrides)
    return MaintenanceRecord(**values)  # type: ignore[arg-type]


def test_maintenance_record_is_immutable() -> None:
    record = make_record()

    with pytest.raises(FrozenInstanceError):
        record.result = MaintenanceResult.FAILED  # type: ignore[misc]


def test_maintenance_record_normalizes_contract() -> None:
    record = make_record(
        service_identifier=" SONARR ",
        service_name="  Sonarr  ",
        action=" HEALTH-CHECK ",
        result=" SUCCESS ",
        provider=" DOCKER-COMPOSE ",
        started_at="2026-08-01T22:20:00-04:00",
        completed_at="2026-08-01T22:20:05-04:00",
        summary="  Health inspection completed.  ",
    )

    assert record.service_identifier == "sonarr"
    assert record.service_name == "Sonarr"
    assert record.action is MaintenanceAction.HEALTH_CHECK
    assert record.result is MaintenanceResult.SUCCESS
    assert record.provider == "docker-compose"
    assert record.started_at == STARTED
    assert record.completed_at == COMPLETED
    assert record.summary == "Health inspection completed."


def test_maintenance_record_duration_and_flags() -> None:
    record = make_record()

    assert record.duration_seconds == 5.0
    assert record.succeeded is True
    assert record.failed is False


def test_incomplete_record_has_no_duration() -> None:
    record = make_record(
        completed_at=None,
        result=MaintenanceResult.UNKNOWN,
    )

    assert record.duration_seconds is None


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        (
            "service_identifier",
            "bad/value",
            "invalid service_identifier",
        ),
        (
            "service_name",
            "   ",
            "service_name must be non-empty text",
        ),
        ("action", "deploy", "invalid action"),
        ("result", "ok", "invalid result"),
        ("provider", "bad/provider", "invalid provider"),
        (
            "started_at",
            "2026-08-02T02:20:00",
            "started_at must include a timezone",
        ),
    ],
)
def test_maintenance_record_rejects_invalid_scalars(
    field_name: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ServiceLifecycleError, match=message):
        make_record(**{field_name: value})


def test_maintenance_record_rejects_invalid_details() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="details must be an object",
    ):
        make_record(details=[("source", "doctor")])


def test_maintenance_record_rejects_completion_before_start() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="completed_at must not be before started_at",
    ):
        make_record(
            completed_at="2026-08-02T02:19:59Z",
        )


def test_maintenance_record_serializes() -> None:
    payload = make_record().to_dict()

    assert payload["service_identifier"] == "sonarr"
    assert payload["action"] == "health-check"
    assert payload["result"] == "success"
    assert payload["duration_seconds"] == 5.0
    assert payload["succeeded"] is True
    assert payload["failed"] is False
    assert payload["details"] == {
        "source": "service-doctor",
    }


def test_maintenance_report_is_immutable() -> None:
    report = MaintenanceReport()

    with pytest.raises(FrozenInstanceError):
        report.provider = "other"  # type: ignore[misc]


def test_maintenance_report_empty_contract() -> None:
    report = MaintenanceReport(
        provider="unknown",
        generated_at=STARTED,
    )

    assert report.records == ()
    assert report.latest_record is None
    assert report.latest_success is None
    assert report.latest_failure is None
    assert report.requires_attention is False
    assert report.counts == {
        "success": 0,
        "failed": 0,
        "partial": 0,
        "skipped": 0,
        "unknown": 0,
    }


def test_maintenance_report_orders_newest_first() -> None:
    older = make_record(
        service_identifier="older",
        service_name="Older",
        started_at="2026-08-02T02:10:00Z",
        completed_at="2026-08-02T02:10:05Z",
    )
    newer = make_record(
        service_identifier="newer",
        service_name="Newer",
        started_at="2026-08-02T02:30:00Z",
        completed_at="2026-08-02T02:30:05Z",
    )

    report = MaintenanceReport(
        records=[older, newer],  # type: ignore[arg-type]
        provider="docker-compose",
        generated_at="2026-08-02T02:40:00Z",
    )

    assert report.records == (newer, older)
    assert report.latest_record is newer


def test_maintenance_report_aggregates_latest_results() -> None:
    success = make_record(
        service_identifier="success",
        service_name="Success",
        result=MaintenanceResult.SUCCESS,
        started_at="2026-08-02T02:20:00Z",
        completed_at="2026-08-02T02:20:05Z",
    )
    failure = make_record(
        service_identifier="failure",
        service_name="Failure",
        result=MaintenanceResult.FAILED,
        started_at="2026-08-02T02:30:00Z",
        completed_at="2026-08-02T02:30:05Z",
    )
    partial = make_record(
        service_identifier="partial",
        service_name="Partial",
        result=MaintenanceResult.PARTIAL,
        started_at="2026-08-02T02:40:00Z",
        completed_at="2026-08-02T02:40:05Z",
    )

    report = MaintenanceReport(
        records=(success, failure, partial),
        provider="docker-compose",
        generated_at="2026-08-02T02:50:00Z",
    )

    assert report.latest_record is partial
    assert report.latest_success is success
    assert report.latest_failure is failure
    assert report.requires_attention is True
    assert report.counts["success"] == 1
    assert report.counts["failed"] == 1
    assert report.counts["partial"] == 1


def test_maintenance_report_rejects_invalid_collection() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="records must be a collection",
    ):
        MaintenanceReport(records="record")  # type: ignore[arg-type]


def test_maintenance_report_rejects_invalid_children() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="records must contain MaintenanceRecord objects",
    ):
        MaintenanceReport(records=("record",))  # type: ignore[arg-type]


def test_maintenance_report_normalizes_metadata() -> None:
    report = MaintenanceReport(
        records=(),
        provider=" DOCKER-COMPOSE ",
        generated_at="2026-08-01T22:20:00-04:00",
    )

    assert report.provider == "docker-compose"
    assert report.generated_at == STARTED


def test_maintenance_report_serializes() -> None:
    record = make_record()
    payload = MaintenanceReport(
        records=(record,),
        provider="docker-compose",
        generated_at="2026-08-02T02:30:00Z",
    ).to_dict()

    assert payload["provider"] == "docker-compose"
    assert payload["total_records"] == 1
    assert payload["requires_attention"] is False
    assert payload["latest_record"]["service_identifier"] == "sonarr"
    assert payload["records"][0]["action"] == "health-check"


@pytest.mark.parametrize(
    "action",
    list(MaintenanceAction),
)
def test_all_maintenance_actions_serialize(
    action: MaintenanceAction,
) -> None:
    assert make_record(action=action).to_dict()["action"] == action.value


@pytest.mark.parametrize(
    "result",
    list(MaintenanceResult),
)
def test_all_maintenance_results_serialize(
    result: MaintenanceResult,
) -> None:
    assert make_record(result=result).to_dict()["result"] == result.value
