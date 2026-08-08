"""Tests for immutable restart-recovery contracts."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    ManagedService,
    ServiceHealth,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRecoveryObservation,
    ServiceRecoveryResult,
    ServiceRecoveryStatus,
    ServiceRuntime,
)


BEFORE_TIME = "2026-08-05T00:00:00Z"
AFTER_TIME = "2026-08-05T00:05:00Z"
EVALUATED_TIME = "2026-08-05T00:06:00Z"


def make_service(**overrides: object) -> ManagedService:
    values: dict[str, object] = {
        "identifier": "sonarr",
        "name": "Sonarr",
        "provider": "docker-compose",
    }
    values.update(overrides)
    return ManagedService(**values)  # type: ignore[arg-type]


def make_runtime(**overrides: object) -> ServiceRuntime:
    values: dict[str, object] = {
        "state": "running",
        "health": "healthy",
        "image": ServiceImage(reference="example/sonarr:latest"),
        "restart_count": 0,
        "started_at": "2026-08-04T23:00:00Z",
    }
    values.update(overrides)
    return ServiceRuntime(**values)  # type: ignore[arg-type]


def make_health(**overrides: object) -> ServiceHealth:
    values: dict[str, object] = {
        "status": "healthy",
        "details": {"service_identifier": "sonarr"},
        "evaluated_at": BEFORE_TIME,
    }
    values.update(overrides)
    return ServiceHealth(**values)  # type: ignore[arg-type]


def make_observation(**overrides: object) -> ServiceRecoveryObservation:
    values: dict[str, object] = {
        "service": make_service(),
        "runtime": make_runtime(),
        "health": make_health(),
        "observed_at": BEFORE_TIME,
    }
    values.update(overrides)
    return ServiceRecoveryObservation(**values)  # type: ignore[arg-type]


def make_result(**overrides: object) -> ServiceRecoveryResult:
    before = make_observation()
    after = make_observation(
        runtime=make_runtime(
            restart_count=1,
            started_at="2026-08-05T00:04:00Z",
        ),
        health=make_health(evaluated_at=AFTER_TIME),
        observed_at=AFTER_TIME,
    )
    values: dict[str, object] = {
        "before": before,
        "after": after,
        "status": ServiceRecoveryStatus.RECOVERED,
        "reason": "Service recovered after restart.",
        "evaluated_at": EVALUATED_TIME,
    }
    values.update(overrides)
    return ServiceRecoveryResult(**values)  # type: ignore[arg-type]


def test_observation_normalizes_timestamp_and_serializes() -> None:
    observation = make_observation(
        observed_at="2026-08-04T20:00:00-04:00",
    )
    assert observation.observed_at == BEFORE_TIME
    assert observation.to_dict() == {
        "service": observation.service.to_dict(),
        "runtime": observation.runtime.to_dict(),
        "health": observation.health.to_dict(),
        "observed_at": BEFORE_TIME,
    }


@pytest.mark.parametrize(
    ("field_name", "value", "message"),
    [
        ("service", "sonarr", "service must be a ManagedService"),
        ("runtime", "running", "runtime must be a ServiceRuntime"),
        ("health", "healthy", "health must be a ServiceHealth"),
        ("observed_at", "2026-08-05T00:00:00", "must include a timezone"),
    ],
)
def test_observation_validates_contracts(
    field_name: str,
    value: object,
    message: str,
) -> None:
    with pytest.raises(ServiceLifecycleError, match=message):
        make_observation(**{field_name: value})


def test_observation_validates_health_identity() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="health service_identifier must match service identity",
    ):
        make_observation(
            health=make_health(
                details={"service_identifier": "radarr"},
            )
        )


def test_observation_allows_health_without_identity_metadata() -> None:
    observation = make_observation(
        health=make_health(details={}),
    )
    assert observation.service.identifier == "sonarr"


def test_observation_is_immutable() -> None:
    observation = make_observation()
    with pytest.raises(FrozenInstanceError):
        observation.observed_at = AFTER_TIME  # type: ignore[misc]


@pytest.mark.parametrize("status", list(ServiceRecoveryStatus))
def test_result_normalizes_all_statuses(status: ServiceRecoveryStatus) -> None:
    errors = ("Recovery failed.",) if status is ServiceRecoveryStatus.FAILED else ()
    result = make_result(status=status, errors=errors)
    assert result.status is status
    assert result.to_dict()["status"] == status.value


def test_result_normalizes_text_collections_and_timestamp() -> None:
    result = make_result(
        status=" DEGRADED ",
        reason="  Service is running with warnings.  ",
        warnings=[" Warning B ", "Warning A", "Warning A"],
        errors=[],
        evaluated_at="2026-08-04T20:06:00-04:00",
    )
    assert result.status is ServiceRecoveryStatus.DEGRADED
    assert result.reason == "Service is running with warnings."
    assert result.warnings == ("Warning A", "Warning B")
    assert result.errors == ()
    assert result.evaluated_at == EVALUATED_TIME


def test_result_derives_restart_count_evidence() -> None:
    result = make_result()
    assert result.restart_count_delta == 1
    assert result.start_time_advanced is True
    assert result.restart_observed is True
    assert result.passed is True
    assert result.requires_attention is False


def test_result_detects_advanced_start_time_without_count_delta() -> None:
    after = make_observation(
        runtime=make_runtime(
            restart_count=0,
            started_at="2026-08-05T00:04:00Z",
        ),
        health=make_health(evaluated_at=AFTER_TIME),
        observed_at=AFTER_TIME,
    )
    result = make_result(after=after)
    assert result.restart_count_delta == 0
    assert result.start_time_advanced is True
    assert result.restart_observed is True


def test_result_reports_no_restart_evidence() -> None:
    after = make_observation(
        health=make_health(evaluated_at=AFTER_TIME),
        observed_at=AFTER_TIME,
    )
    result = make_result(
        after=after,
        status="not_observed",
        reason="No restart evidence was observed.",
    )
    assert result.restart_count_delta == 0
    assert result.start_time_advanced is False
    assert result.restart_observed is False
    assert result.passed is False
    assert result.requires_attention is False


@pytest.mark.parametrize(
    ("status", "attention"),
    [
        (ServiceRecoveryStatus.NOT_OBSERVED, False),
        (ServiceRecoveryStatus.RECOVERING, True),
        (ServiceRecoveryStatus.RECOVERED, False),
        (ServiceRecoveryStatus.DEGRADED, True),
        (ServiceRecoveryStatus.FAILED, True),
        (ServiceRecoveryStatus.UNKNOWN, True),
    ],
)
def test_result_attention_contract(
    status: ServiceRecoveryStatus,
    attention: bool,
) -> None:
    errors = ("Failure",) if status is ServiceRecoveryStatus.FAILED else ()
    assert make_result(status=status, errors=errors).requires_attention is attention


def test_result_validates_child_contracts() -> None:
    with pytest.raises(ServiceLifecycleError, match="before must be"):
        make_result(before="before")
    with pytest.raises(ServiceLifecycleError, match="after must be"):
        make_result(after="after")


def test_result_requires_matching_service_identity() -> None:
    after = make_observation(
        service=make_service(identifier="radarr", name="Radarr"),
        health=make_health(
            details={"service_identifier": "radarr"},
            evaluated_at=AFTER_TIME,
        ),
        observed_at=AFTER_TIME,
    )
    with pytest.raises(ServiceLifecycleError, match="share a service identifier"):
        make_result(after=after)


def test_result_requires_matching_provider() -> None:
    after = make_observation(
        service=make_service(provider="podman"),
        health=make_health(evaluated_at=AFTER_TIME),
        observed_at=AFTER_TIME,
    )
    with pytest.raises(ServiceLifecycleError, match="share a provider"):
        make_result(after=after)


def test_result_rejects_reversed_observation_time() -> None:
    after = make_observation(observed_at="2026-08-04T23:59:00Z")
    with pytest.raises(ServiceLifecycleError, match="must not precede before"):
        make_result(after=after)


def test_result_rejects_early_evaluation_time() -> None:
    with pytest.raises(ServiceLifecycleError, match="must not precede the after"):
        make_result(evaluated_at=BEFORE_TIME)


def test_recovered_result_rejects_errors() -> None:
    with pytest.raises(ServiceLifecycleError, match="must not contain errors"):
        make_result(errors=("Unexpected failure",))


def test_result_serializes_complete_contract() -> None:
    result = make_result(warnings=("Restart observed.",))
    payload = result.to_dict()
    assert payload["service_identifier"] == "sonarr"
    assert payload["status"] == "recovered"
    assert payload["restart_observed"] is True
    assert payload["restart_count_delta"] == 1
    assert payload["start_time_advanced"] is True
    assert payload["passed"] is True
    assert payload["requires_attention"] is False
    assert payload["warnings"] == ["Restart observed."]
    assert payload["errors"] == []
    assert payload["before"] == result.before.to_dict()
    assert payload["after"] == result.after.to_dict()
    assert payload["evaluated_at"] == EVALUATED_TIME


def test_recovery_contracts_are_publicly_exported() -> None:
    from atlas import service_lifecycle

    assert service_lifecycle.ServiceRecoveryObservation is ServiceRecoveryObservation
    assert service_lifecycle.ServiceRecoveryResult is ServiceRecoveryResult
    assert service_lifecycle.ServiceRecoveryStatus is ServiceRecoveryStatus
    assert "ServiceRecoveryObservation" in service_lifecycle.__all__
    assert "ServiceRecoveryResult" in service_lifecycle.__all__
    assert "ServiceRecoveryStatus" in service_lifecycle.__all__
