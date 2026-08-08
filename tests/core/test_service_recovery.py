"""Tests for deterministic restart-recovery evaluation."""

from __future__ import annotations

import pytest

from atlas.service_lifecycle import (
    ManagedService,
    RestartRecoveryEvaluator,
    ServiceHealth,
    ServiceImage,
    ServiceLifecycleError,
    ServiceRecoveryObservation,
    ServiceRecoveryStatus,
    ServiceRuntime,
)


BEFORE = "2026-08-05T01:00:00Z"
AFTER = "2026-08-05T01:05:00Z"
EVALUATED = "2026-08-05T01:06:00Z"


def observation(
    *,
    identifier: str = "sonarr",
    provider: str = "docker-compose",
    state: str = "running",
    runtime_health: str = "healthy",
    restart_count: int = 0,
    started_at: str | None = "2026-08-05T00:00:00Z",
    health_status: str = "healthy",
    warnings: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
    observed_at: str = BEFORE,
) -> ServiceRecoveryObservation:
    service = ManagedService(
        identifier=identifier,
        name=identifier.title(),
        provider=provider,
    )
    return ServiceRecoveryObservation(
        service=service,
        runtime=ServiceRuntime(
            state=state,
            health=runtime_health,
            image=ServiceImage(reference=f"example/{identifier}:latest"),
            restart_count=restart_count,
            started_at=started_at,
        ),
        health=ServiceHealth(
            status=health_status,
            warnings=warnings,
            errors=errors,
            details={"service_identifier": identifier},
            evaluated_at=observed_at,
        ),
        observed_at=observed_at,
    )


def evaluate(
    after: ServiceRecoveryObservation,
    *,
    before: ServiceRecoveryObservation | None = None,
):
    return RestartRecoveryEvaluator().evaluate(
        before or observation(),
        after,
        evaluated_at=EVALUATED,
    )


def restarted(**overrides: object) -> ServiceRecoveryObservation:
    values: dict[str, object] = {
        "restart_count": 1,
        "started_at": "2026-08-05T01:04:00Z",
        "observed_at": AFTER,
    }
    values.update(overrides)
    return observation(**values)  # type: ignore[arg-type]


def test_healthy_restart_is_recovered() -> None:
    result = evaluate(restarted())
    assert result.status is ServiceRecoveryStatus.RECOVERED
    assert result.restart_observed is True
    assert result.passed is True
    assert result.requires_attention is False
    assert result.errors == ()


def test_restart_count_alone_is_restart_evidence() -> None:
    result = evaluate(
        restarted(started_at="2026-08-05T00:00:00Z"),
    )
    assert result.restart_count_delta == 1
    assert result.start_time_advanced is False
    assert result.status is ServiceRecoveryStatus.RECOVERED


def test_advanced_start_time_alone_is_restart_evidence() -> None:
    result = evaluate(restarted(restart_count=0))
    assert result.restart_count_delta == 0
    assert result.start_time_advanced is True
    assert result.status is ServiceRecoveryStatus.RECOVERED


def test_no_evidence_is_not_observed() -> None:
    result = evaluate(
        observation(observed_at=AFTER),
    )
    assert result.status is ServiceRecoveryStatus.NOT_OBSERVED
    assert result.restart_observed is False
    assert result.passed is False
    assert result.requires_attention is False


def test_decreased_restart_count_is_unknown() -> None:
    before = observation(restart_count=2)
    result = evaluate(restarted(restart_count=1), before=before)
    assert result.status is ServiceRecoveryStatus.UNKNOWN
    assert result.restart_count_delta == -1
    assert result.errors


def test_restarting_runtime_is_recovering() -> None:
    result = evaluate(
        restarted(state="restarting", runtime_health="starting"),
    )
    assert result.status is ServiceRecoveryStatus.RECOVERING
    assert "Container is restarting." in result.warnings


def test_starting_health_is_recovering() -> None:
    result = evaluate(restarted(runtime_health="starting"))
    assert result.status is ServiceRecoveryStatus.RECOVERING
    assert "Health readiness is still starting." in result.warnings


@pytest.mark.parametrize("state", ["created", "dead", "exited", "stopped"])
def test_non_running_runtime_is_failed(state: str) -> None:
    result = evaluate(
        restarted(state=state, runtime_health="none"),
    )
    assert result.status is ServiceRecoveryStatus.FAILED
    assert result.errors


def test_unhealthy_docker_health_is_failed() -> None:
    result = evaluate(restarted(runtime_health="unhealthy"))
    assert result.status is ServiceRecoveryStatus.FAILED
    assert "Docker health is unhealthy." in result.errors


def test_health_errors_are_failed() -> None:
    result = evaluate(restarted(errors=("Backend unavailable",)))
    assert result.status is ServiceRecoveryStatus.FAILED
    assert result.errors == ("Backend unavailable",)


@pytest.mark.parametrize("status", ["unhealthy", "unavailable"])
def test_failed_normalized_health_is_failed(status: str) -> None:
    result = evaluate(restarted(health_status=status))
    assert result.status is ServiceRecoveryStatus.FAILED
    assert result.errors


def test_unknown_health_is_unknown() -> None:
    result = evaluate(restarted(health_status="unknown"))
    assert result.status is ServiceRecoveryStatus.UNKNOWN
    assert result.requires_attention is True


def test_degraded_health_is_degraded() -> None:
    result = evaluate(
        restarted(
            health_status="degraded",
            warnings=("Dependency is slow",),
        )
    )
    assert result.status is ServiceRecoveryStatus.DEGRADED
    assert result.warnings == (
        "Dependency is slow",
        "Service health remains degraded.",
    )


def test_evaluator_preserves_healthy_warnings() -> None:
    result = evaluate(restarted(warnings=("Restart count increased",)))
    assert result.status is ServiceRecoveryStatus.RECOVERED
    assert result.warnings == ("Restart count increased",)


def test_result_serialization_is_deterministic() -> None:
    first = evaluate(restarted())
    second = evaluate(restarted())
    assert first.to_dict() == second.to_dict()


def test_evaluator_validates_child_contracts() -> None:
    evaluator = RestartRecoveryEvaluator()
    with pytest.raises(ServiceLifecycleError, match="before must be"):
        evaluator.evaluate("before", restarted())  # type: ignore[arg-type]
    with pytest.raises(ServiceLifecycleError, match="after must be"):
        evaluator.evaluate(observation(), "after")  # type: ignore[arg-type]


def test_evaluator_preserves_result_identity_validation() -> None:
    with pytest.raises(ServiceLifecycleError, match="share a service identifier"):
        RestartRecoveryEvaluator().evaluate(
            observation(),
            restarted(identifier="radarr"),
            evaluated_at=EVALUATED,
        )


def test_evaluator_is_publicly_exported() -> None:
    from atlas import service_lifecycle
    assert service_lifecycle.RestartRecoveryEvaluator is RestartRecoveryEvaluator
    assert "RestartRecoveryEvaluator" in service_lifecycle.__all__
