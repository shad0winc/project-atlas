"""Read-only diagnostic evaluation for Atlas Service Lifecycle."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from .doctor_models import (
    DoctorCategory,
    DoctorFinding,
    DoctorReport,
    DoctorSeverity,
)
from .models import (
    ManagedService,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceLifecycleError,
    ServiceRuntime,
)
from .service import ServiceLifecycleService


_RESTART_WARNING_THRESHOLD = 5
_RESTART_ERROR_THRESHOLD = 10
_MISSING_HEALTH_STATES = {
    "none",
    "unknown",
    "unavailable",
    "starting",
}
_STOPPED_STATES = {
    "created",
    "dead",
    "exited",
    "failed",
    "paused",
    "removing",
    "stopped",
}


@dataclass(frozen=True)
class ServiceDoctor:
    """Evaluate explainable, read-only infrastructure diagnostics."""

    lifecycle: ServiceLifecycleService

    def __post_init__(self) -> None:
        if not isinstance(self.lifecycle, ServiceLifecycleService):
            raise ServiceLifecycleError(
                "lifecycle must be ServiceLifecycleService",
            )

    def diagnose(self) -> DoctorReport:
        """Return one deterministic diagnostic report for managed services."""

        services = self.lifecycle.list_services()
        evaluated_at = _utc_now()
        runtimes = {
            service.identifier: self.lifecycle.inspect_runtime(
                service.identifier,
            )
            for service in services
        }
        health = {
            service.identifier: self.lifecycle.inspect_health(
                service.identifier,
            )
            for service in services
        }

        findings: list[DoctorFinding] = []
        by_identifier = {
            service.identifier: service
            for service in services
        }

        for service in services:
            runtime = runtimes[service.identifier]
            service_health = health[service.identifier]
            findings.extend(
                self._evaluate_service(
                    service,
                    runtime,
                    service_health,
                    evaluated_at=evaluated_at,
                )
            )
            findings.extend(
                self._evaluate_dependencies(
                    service,
                    by_identifier,
                    runtimes,
                    evaluated_at=evaluated_at,
                )
            )

        provider = _provider_name(services)
        return DoctorReport(
            findings=tuple(findings),
            provider=provider,
            evaluated_at=evaluated_at,
        )

    def _evaluate_service(
        self,
        service: ManagedService,
        runtime: ServiceRuntime,
        health: ServiceHealth,
        *,
        evaluated_at: str,
    ) -> tuple[DoctorFinding, ...]:
        findings: list[DoctorFinding] = []
        state = runtime.state.casefold()
        runtime_health = runtime.health.casefold()

        if service.enabled and state in _STOPPED_STATES:
            severity = (
                DoctorSeverity.CRITICAL
                if state in {"dead", "failed"}
                else DoctorSeverity.ERROR
            )
            findings.append(
                _finding(
                    service,
                    severity=severity,
                    category=DoctorCategory.RUNTIME,
                    code="runtime-stopped",
                    message=(
                        f"Enabled service {service.name} is not running "
                        f"(state: {state})."
                    ),
                    details={
                        "state": state,
                        "exit_code": runtime.exit_code,
                        "status_message": runtime.status_message,
                    },
                    created_at=evaluated_at,
                )
            )

        if service.enabled and state == "restarting":
            findings.append(
                _finding(
                    service,
                    severity=DoctorSeverity.ERROR,
                    category=DoctorCategory.RUNTIME,
                    code="runtime-restarting",
                    message=(
                        f"Enabled service {service.name} is currently restarting."
                    ),
                    details={
                        "state": state,
                        "restart_count": runtime.restart_count,
                    },
                    created_at=evaluated_at,
                )
            )

        if runtime.restart_count >= _RESTART_WARNING_THRESHOLD:
            severity = (
                DoctorSeverity.ERROR
                if runtime.restart_count >= _RESTART_ERROR_THRESHOLD
                else DoctorSeverity.WARNING
            )
            findings.append(
                _finding(
                    service,
                    severity=severity,
                    category=DoctorCategory.RUNTIME,
                    code="restart-loop",
                    message=(
                        f"Service {service.name} has restarted "
                        f"{runtime.restart_count} times."
                    ),
                    details={
                        "restart_count": runtime.restart_count,
                        "warning_threshold": _RESTART_WARNING_THRESHOLD,
                        "error_threshold": _RESTART_ERROR_THRESHOLD,
                    },
                    created_at=evaluated_at,
                )
            )

        if service.enabled and state == "running" and runtime_health in _MISSING_HEALTH_STATES:
            findings.append(
                _finding(
                    service,
                    severity=DoctorSeverity.WARNING,
                    category=DoctorCategory.OBSERVABILITY,
                    code="healthcheck-missing",
                    message=(
                        f"Running service {service.name} does not expose a "
                        "conclusive runtime health check."
                    ),
                    details={
                        "runtime_health": runtime_health,
                    },
                    created_at=evaluated_at,
                )
            )

        missing_healthcheck_only = _is_missing_healthcheck_only(
            health,
            runtime_health=runtime_health,
        )

        if (
            health.status is not ServiceHealthStatus.HEALTHY
            and not missing_healthcheck_only
        ):
            severity = _health_severity(health.status)
            findings.append(
                _finding(
                    service,
                    severity=severity,
                    category=DoctorCategory.HEALTH,
                    code="health-degraded",
                    message=(
                        f"Service {service.name} health is "
                        f"{health.status.value} (score: {health.score})."
                    ),
                    details={
                        "status": health.status.value,
                        "score": health.score,
                        "warnings": list(health.warnings),
                        "errors": list(health.errors),
                    },
                    created_at=evaluated_at,
                )
            )
        elif (health.warnings or health.errors) and not missing_healthcheck_only:
            findings.append(
                _finding(
                    service,
                    severity=(
                        DoctorSeverity.ERROR
                        if health.errors
                        else DoctorSeverity.WARNING
                    ),
                    category=DoctorCategory.HEALTH,
                    code="health-messages",
                    message=(
                        f"Service {service.name} reported health messages "
                        "that require review."
                    ),
                    details={
                        "warnings": list(health.warnings),
                        "errors": list(health.errors),
                    },
                    created_at=evaluated_at,
                )
            )

        if not service.enabled and state in {"running", "restarting"}:
            findings.append(
                _finding(
                    service,
                    severity=DoctorSeverity.WARNING,
                    category=DoctorCategory.CONFIGURATION,
                    code="disabled-service-running",
                    message=(
                        f"Disabled service {service.name} is still {state}."
                    ),
                    details={
                        "enabled": service.enabled,
                        "state": state,
                    },
                    created_at=evaluated_at,
                )
            )

        if service.enabled and runtime.image.tag == "latest":
            findings.append(
                _finding(
                    service,
                    severity=DoctorSeverity.INFO,
                    category=DoctorCategory.CONFIGURATION,
                    code="image-tag-latest",
                    message=(
                        f"Service {service.name} uses the mutable latest image tag."
                    ),
                    details={
                        "image": runtime.image.reference,
                        "tag": runtime.image.tag,
                    },
                    created_at=evaluated_at,
                )
            )

        return tuple(findings)

    def _evaluate_dependencies(
        self,
        service: ManagedService,
        services: dict[str, ManagedService],
        runtimes: dict[str, ServiceRuntime],
        *,
        evaluated_at: str,
    ) -> tuple[DoctorFinding, ...]:
        findings: list[DoctorFinding] = []

        for dependency_identifier in service.dependencies:
            dependency = services.get(dependency_identifier)
            if dependency is None:
                findings.append(
                    _finding(
                        service,
                        severity=DoctorSeverity.ERROR,
                        category=DoctorCategory.DEPENDENCY,
                        code=f"dependency-missing-{dependency_identifier}",
                        message=(
                            f"Service {service.name} declares unknown dependency "
                            f"{dependency_identifier}."
                        ),
                        details={
                            "dependency": dependency_identifier,
                        },
                        created_at=evaluated_at,
                    )
                )
                continue

            dependency_runtime = runtimes[dependency.identifier]
            if service.enabled and dependency_runtime.state.casefold() != "running":
                findings.append(
                    _finding(
                        service,
                        severity=DoctorSeverity.ERROR,
                        category=DoctorCategory.DEPENDENCY,
                        code=f"dependency-not-running-{dependency.identifier}",
                        message=(
                            f"Service {service.name} depends on "
                            f"{dependency.name}, which is not running."
                        ),
                        details={
                            "dependency": dependency.identifier,
                            "dependency_state": dependency_runtime.state,
                        },
                        created_at=evaluated_at,
                    )
                )

        return tuple(findings)


def _finding(
    service: ManagedService,
    *,
    severity: DoctorSeverity,
    category: DoctorCategory,
    code: str,
    message: str,
    details: dict[str, object],
    created_at: str,
) -> DoctorFinding:
    return DoctorFinding(
        identifier=f"{service.identifier}.{code}",
        severity=severity,
        category=category,
        code=code,
        message=message,
        service_identifier=service.identifier,
        details=details,
        created_at=created_at,
    )


def _is_missing_healthcheck_only(
    health: ServiceHealth,
    *,
    runtime_health: str,
) -> bool:
    """Return whether health degradation only reflects absent observability."""

    if runtime_health not in _MISSING_HEALTH_STATES:
        return False
    if health.errors:
        return False
    if not health.warnings:
        return False

    normalized = {warning.strip().casefold() for warning in health.warnings}
    return normalized == {"no docker health check is configured"}


def _health_severity(status: ServiceHealthStatus) -> DoctorSeverity:
    if status is ServiceHealthStatus.UNAVAILABLE:
        return DoctorSeverity.CRITICAL
    if status is ServiceHealthStatus.UNHEALTHY:
        return DoctorSeverity.ERROR
    if status is ServiceHealthStatus.DEGRADED:
        return DoctorSeverity.WARNING
    return DoctorSeverity.INFO


def _provider_name(services: tuple[ManagedService, ...]) -> str:
    providers = sorted({service.provider for service in services})
    if not providers:
        return "unknown"
    if len(providers) == 1:
        return providers[0]
    return "mixed"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
