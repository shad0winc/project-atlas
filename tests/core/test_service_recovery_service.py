"""Tests for read-only restart-recovery orchestration."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from atlas.service_lifecycle import (
    DockerComposeProvider,
    ManagedService,
    RestartRecoveryEvaluator,
    ServiceHealth,
    ServiceImage,
    ServiceLifecycleError,
    ServiceLifecycleService,
    ServiceRecoveryObservation,
    ServiceRecoveryStatus,
    ServiceRestartRecoveryService,
    ServiceRuntime,
)


BEFORE = "2026-08-05T02:00:00Z"
AFTER = "2026-08-05T02:05:00Z"
EVALUATED = "2026-08-05T02:06:00Z"


def lifecycle(tmp_path: Path) -> ServiceLifecycleService:
    compose = tmp_path / "compose.yml"
    compose.write_text(
        "services:\n  sonarr:\n    image: sonarr:latest\n",
        encoding="utf-8",
    )
    return ServiceLifecycleService(
        DockerComposeProvider(compose_file=compose),
    )


def service() -> ManagedService:
    return ManagedService(
        identifier="sonarr",
        name="Sonarr",
        provider="docker-compose",
    )


def runtime(
    *,
    restart_count: int = 0,
    started_at: str = "2026-08-05T01:00:00Z",
) -> ServiceRuntime:
    return ServiceRuntime(
        state="running",
        health="healthy",
        image=ServiceImage(reference="example/sonarr:latest"),
        restart_count=restart_count,
        started_at=started_at,
    )


def health(*, evaluated_at: str = BEFORE) -> ServiceHealth:
    return ServiceHealth(
        status="healthy",
        details={"service_identifier": "sonarr"},
        evaluated_at=evaluated_at,
    )


def observation(
    *,
    restart_count: int = 0,
    started_at: str = "2026-08-05T01:00:00Z",
    observed_at: str = BEFORE,
) -> ServiceRecoveryObservation:
    return ServiceRecoveryObservation(
        service=service(),
        runtime=runtime(
            restart_count=restart_count,
            started_at=started_at,
        ),
        health=health(evaluated_at=observed_at),
        observed_at=observed_at,
    )


def patch_observation(
    monkeypatch: pytest.MonkeyPatch,
    *,
    restart_count: int = 1,
    started_at: str = "2026-08-05T02:04:00Z",
) -> list[tuple[str, str]]:
    calls: list[tuple[str, str]] = []

    def inspect_service(
        self: ServiceLifecycleService,
        identifier: str,
    ) -> ManagedService:
        calls.append(("service", identifier))
        return service()

    def inspect_runtime(
        self: ServiceLifecycleService,
        identifier: str,
    ) -> ServiceRuntime:
        calls.append(("runtime", identifier))
        return runtime(
            restart_count=restart_count,
            started_at=started_at,
        )

    def inspect_health(
        self: ServiceLifecycleService,
        identifier: str,
    ) -> ServiceHealth:
        calls.append(("health", identifier))
        return health(evaluated_at=AFTER)

    monkeypatch.setattr(ServiceLifecycleService, "inspect_service", inspect_service)
    monkeypatch.setattr(ServiceLifecycleService, "inspect_runtime", inspect_runtime)
    monkeypatch.setattr(ServiceLifecycleService, "inspect_health", inspect_health)
    return calls


def test_service_is_immutable(tmp_path: Path) -> None:
    orchestration = ServiceRestartRecoveryService(lifecycle(tmp_path))
    with pytest.raises(FrozenInstanceError):
        orchestration.lifecycle = lifecycle(tmp_path)  # type: ignore[misc]


def test_service_validates_lifecycle() -> None:
    with pytest.raises(ServiceLifecycleError, match="lifecycle must be"):
        ServiceRestartRecoveryService(object())  # type: ignore[arg-type]


def test_service_validates_evaluator(tmp_path: Path) -> None:
    with pytest.raises(ServiceLifecycleError, match="evaluator must be"):
        ServiceRestartRecoveryService(
            lifecycle(tmp_path),
            evaluator=object(),  # type: ignore[arg-type]
        )


def test_observe_uses_lifecycle_boundary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = patch_observation(monkeypatch)
    result = ServiceRestartRecoveryService(
        lifecycle(tmp_path),
    ).observe(" SONARR ", observed_at=AFTER)

    assert calls == [
        ("service", " SONARR "),
        ("runtime", "sonarr"),
        ("health", "sonarr"),
    ]
    assert result.service.identifier == "sonarr"
    assert result.runtime.restart_count == 1
    assert result.observed_at == AFTER


def test_observe_defaults_to_utc_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_observation(monkeypatch)
    result = ServiceRestartRecoveryService(lifecycle(tmp_path)).observe("sonarr")
    assert result.observed_at.endswith("Z")


def test_observe_preserves_lifecycle_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail(self: ServiceLifecycleService, identifier: str) -> ManagedService:
        raise ServiceLifecycleError("known observation failure")

    monkeypatch.setattr(ServiceLifecycleService, "inspect_service", fail)
    with pytest.raises(ServiceLifecycleError, match="known observation failure"):
        ServiceRestartRecoveryService(lifecycle(tmp_path)).observe("sonarr")


def test_evaluate_delegates_to_pure_evaluator(tmp_path: Path) -> None:
    before = observation()
    after = observation(
        restart_count=1,
        started_at="2026-08-05T02:04:00Z",
        observed_at=AFTER,
    )
    result = ServiceRestartRecoveryService(lifecycle(tmp_path)).evaluate(
        before,
        after,
        evaluated_at=EVALUATED,
    )
    assert result.status is ServiceRecoveryStatus.RECOVERED
    assert result.evaluated_at == EVALUATED


def test_inspect_captures_after_and_evaluates(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = patch_observation(monkeypatch)
    result = ServiceRestartRecoveryService(lifecycle(tmp_path)).inspect(
        "sonarr",
        observation(),
        observed_at=AFTER,
        evaluated_at=EVALUATED,
    )
    assert calls == [
        ("service", "sonarr"),
        ("runtime", "sonarr"),
        ("health", "sonarr"),
    ]
    assert result.status is ServiceRecoveryStatus.RECOVERED
    assert result.restart_count_delta == 1


def test_service_does_not_expose_mutation_methods(tmp_path: Path) -> None:
    orchestration = ServiceRestartRecoveryService(lifecycle(tmp_path))
    for name in ("restart", "start", "stop", "recreate", "repair"):
        assert not hasattr(orchestration, name)


def test_service_is_publicly_exported() -> None:
    from atlas import service_lifecycle
    from atlas.service_lifecycle.services import (
        ServiceRestartRecoveryService as PackagedService,
    )
    assert ServiceRestartRecoveryService is PackagedService
    assert service_lifecycle.ServiceRestartRecoveryService is PackagedService
    assert "ServiceRestartRecoveryService" in service_lifecycle.__all__
