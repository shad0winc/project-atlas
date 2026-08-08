"""Read-only restart-recovery orchestration for Atlas services."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

from ..models import ServiceLifecycleError
from ..recovery import RestartRecoveryEvaluator
from ..recovery_models import (
    ServiceRecoveryObservation,
    ServiceRecoveryResult,
)
from .lifecycle import ServiceLifecycleService


@dataclass(frozen=True)
class ServiceRestartRecoveryService:
    """Capture observations and delegate pure recovery evaluation."""

    lifecycle: ServiceLifecycleService
    evaluator: RestartRecoveryEvaluator = field(
        default_factory=RestartRecoveryEvaluator,
    )

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle, ServiceLifecycleService):
            raise ServiceLifecycleError(
                "lifecycle must be ServiceLifecycleService",
            )
        if not isinstance(self.evaluator, RestartRecoveryEvaluator):
            raise ServiceLifecycleError(
                "evaluator must be RestartRecoveryEvaluator",
            )

    def observe(
        self,
        identifier: str,
        *,
        observed_at: str | None = None,
    ) -> ServiceRecoveryObservation:
        """Capture one normalized read-only service observation."""

        service = self.lifecycle.inspect_service(identifier)
        runtime = self.lifecycle.inspect_runtime(service.identifier)
        health = self.lifecycle.inspect_health(service.identifier)

        return ServiceRecoveryObservation(
            service=service,
            runtime=runtime,
            health=health,
            observed_at=observed_at or _now_timestamp(),
        )

    def evaluate(
        self,
        before: ServiceRecoveryObservation,
        after: ServiceRecoveryObservation,
        *,
        evaluated_at: str | None = None,
    ) -> ServiceRecoveryResult:
        """Delegate comparison to the pure recovery evaluator."""

        return self.evaluator.evaluate(
            before,
            after,
            evaluated_at=evaluated_at,
        )

    def inspect(
        self,
        identifier: str,
        before: ServiceRecoveryObservation,
        *,
        observed_at: str | None = None,
        evaluated_at: str | None = None,
    ) -> ServiceRecoveryResult:
        """Capture the after observation and evaluate recovery."""

        after = self.observe(
            identifier,
            observed_at=observed_at,
        )
        return self.evaluate(
            before,
            after,
            evaluated_at=evaluated_at,
        )


def _now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
