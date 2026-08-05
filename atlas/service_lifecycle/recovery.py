"""Pure restart-recovery evaluation for Atlas Service Lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime

from .models import (
    ServiceHealthStatus,
    ServiceLifecycleError,
)
from .recovery_models import (
    ServiceRecoveryObservation,
    ServiceRecoveryResult,
    ServiceRecoveryStatus,
)


class RestartRecoveryEvaluator:
    """Evaluate two normalized observations without provider access."""

    def evaluate(
        self,
        before: ServiceRecoveryObservation,
        after: ServiceRecoveryObservation,
        *,
        evaluated_at: str | None = None,
    ) -> ServiceRecoveryResult:
        """Return one deterministic restart-recovery result."""

        if not isinstance(before, ServiceRecoveryObservation):
            raise ServiceLifecycleError(
                "before must be a ServiceRecoveryObservation",
            )
        if not isinstance(after, ServiceRecoveryObservation):
            raise ServiceLifecycleError(
                "after must be a ServiceRecoveryObservation",
            )

        delta = (
            after.runtime.restart_count
            - before.runtime.restart_count
        )
        start_advanced = _start_time_advanced(before, after)
        restart_observed = delta > 0 or start_advanced

        if delta < 0:
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.UNKNOWN,
                reason=(
                    "Restart count decreased between observations; "
                    "recovery evidence is contradictory."
                ),
                errors=(
                    "Restart count decreased and may indicate container "
                    "replacement or incomplete evidence.",
                ),
                evaluated_at=evaluated_at,
            )

        if not restart_observed:
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.NOT_OBSERVED,
                reason="No restart evidence was observed.",
                evaluated_at=evaluated_at,
            )

        runtime = after.runtime
        health = after.health

        if runtime.state == "restarting":
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.RECOVERING,
                reason="The service restart is still in progress.",
                warnings=_warnings(
                    health.warnings,
                    "Container is restarting.",
                ),
                errors=health.errors,
                evaluated_at=evaluated_at,
            )

        if runtime.running and runtime.health == "starting":
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.RECOVERING,
                reason="The service is running and health is still starting.",
                warnings=_warnings(
                    health.warnings,
                    "Health readiness is still starting.",
                ),
                errors=health.errors,
                evaluated_at=evaluated_at,
            )

        if not runtime.running or runtime.state in {
            "created",
            "dead",
            "exited",
            "stopped",
        }:
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.FAILED,
                reason="The service did not return to a running state.",
                warnings=health.warnings,
                errors=_errors(
                    health.errors,
                    f"Current runtime state is {runtime.state}.",
                ),
                evaluated_at=evaluated_at,
            )

        if runtime.health == "unhealthy":
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.FAILED,
                reason="The service restarted but Docker health is unhealthy.",
                warnings=health.warnings,
                errors=_errors(
                    health.errors,
                    "Docker health is unhealthy.",
                ),
                evaluated_at=evaluated_at,
            )

        if health.errors:
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.FAILED,
                reason="The service restarted but health errors remain.",
                warnings=health.warnings,
                errors=health.errors,
                evaluated_at=evaluated_at,
            )

        if health.status in {
            ServiceHealthStatus.UNHEALTHY,
            ServiceHealthStatus.UNAVAILABLE,
        }:
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.FAILED,
                reason=(
                    "The service restarted but its normalized health "
                    f"status is {health.status.value}."
                ),
                warnings=health.warnings,
                errors=_errors(
                    health.errors,
                    f"Service health is {health.status.value}.",
                ),
                evaluated_at=evaluated_at,
            )

        if health.status is ServiceHealthStatus.UNKNOWN:
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.UNKNOWN,
                reason="The service restarted but health is unknown.",
                warnings=health.warnings,
                evaluated_at=evaluated_at,
            )

        if health.status is ServiceHealthStatus.DEGRADED:
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.DEGRADED,
                reason="The service restarted and is running with degraded health.",
                warnings=_warnings(
                    health.warnings,
                    "Service health remains degraded.",
                ),
                evaluated_at=evaluated_at,
            )

        if health.status is not ServiceHealthStatus.HEALTHY:
            return _result(
                before,
                after,
                status=ServiceRecoveryStatus.UNKNOWN,
                reason="The service restarted but recovery could not be classified.",
                warnings=health.warnings,
                evaluated_at=evaluated_at,
            )

        return _result(
            before,
            after,
            status=ServiceRecoveryStatus.RECOVERED,
            reason="The service recovered after restart.",
            warnings=health.warnings,
            evaluated_at=evaluated_at,
        )


def _start_time_advanced(
    before: ServiceRecoveryObservation,
    after: ServiceRecoveryObservation,
) -> bool:
    previous = before.runtime.started_at
    current = after.runtime.started_at
    if previous is None or current is None:
        return False
    return _parse_timestamp(current) > _parse_timestamp(previous)


def _result(
    before: ServiceRecoveryObservation,
    after: ServiceRecoveryObservation,
    *,
    status: ServiceRecoveryStatus,
    reason: str,
    warnings: tuple[str, ...] = (),
    errors: tuple[str, ...] = (),
    evaluated_at: str | None,
) -> ServiceRecoveryResult:
    return ServiceRecoveryResult(
        before=before,
        after=after,
        status=status,
        reason=reason,
        warnings=warnings,
        errors=errors,
        evaluated_at=evaluated_at or _now_timestamp(),
    )


def _warnings(values: tuple[str, ...], message: str) -> tuple[str, ...]:
    return tuple(sorted(set(values) | {message}))


def _errors(values: tuple[str, ...], message: str) -> tuple[str, ...]:
    return tuple(sorted(set(values) | {message}))


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _now_timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
