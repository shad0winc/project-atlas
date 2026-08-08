"""Tests for the read-only Service Doctor evaluation engine."""

from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from atlas.service_lifecycle import (
    DoctorCategory,
    DoctorSeverity,
    ImageReference,
    ManagedService,
    ServiceDoctor,
    ServiceHealth,
    ServiceHealthStatus,
    ServiceImage,
    ServiceLifecycleError,
    ServiceLifecycleProvider,
    ServiceLifecycleService,
    ServiceRuntime,
    ServiceUpdate,
    UpdateStatus,
)


class DoctorProvider(ServiceLifecycleProvider):
    """Configurable provider for Service Doctor contracts."""

    def __init__(self) -> None:
        self.services: tuple[ManagedService, ...] = ()
        self.runtimes: dict[str, ServiceRuntime] = {}
        self.health: dict[str, ServiceHealth] = {}
        self.calls: list[tuple[str, str | None]] = []

    def list_services(self):
        self.calls.append(("list_services", None))
        return self.services

    def inspect_service(self, identifier: str):
        self.calls.append(("inspect_service", identifier))
        return next(
            service
            for service in self.services
            if service.identifier == identifier
        )

    def inspect_runtime(self, identifier: str):
        self.calls.append(("inspect_runtime", identifier))
        return self.runtimes[identifier]

    def inspect_health(self, identifier: str):
        self.calls.append(("inspect_health", identifier))
        return self.health[identifier]

    def inspect_update(
        self,
        identifier: str,
    ) -> ServiceUpdate:
        self.calls.append(("inspect_update", identifier))

        service = next(
            (
                service
                for service in self.services
                if service.identifier == identifier
            ),
            None,
        )
        if service is None:
            raise LookupError(identifier)

        return ServiceUpdate(
            service_identifier=service.identifier,
            service_name=service.name,
            current_image=ImageReference.parse(
                "example/service:stable"
            ),
            status=UpdateStatus.UNKNOWN,
        )

def managed(
    identifier: str,
    *,
    enabled: bool = True,
    dependencies: tuple[str, ...] = (),
    provider: str = "stub",
) -> ManagedService:
    return ManagedService(
        identifier=identifier,
        name=identifier.title(),
        provider=provider,
        enabled=enabled,
        dependencies=dependencies,
    )


def runtime(
    *,
    state: str = "running",
    health: str = "healthy",
    restart_count: int = 0,
    tag: str | None = "stable",
    exit_code: int | None = None,
) -> ServiceRuntime:
    reference = "example/service"
    if tag is not None:
        reference = f"{reference}:{tag}"
    return ServiceRuntime(
        state=state,
        health=health,
        image=ServiceImage(
            reference=reference,
            repository="example/service",
            tag=tag,
        ),
        restart_count=restart_count,
        exit_code=exit_code,
    )


def healthy() -> ServiceHealth:
    return ServiceHealth(
        status=ServiceHealthStatus.HEALTHY,
        score=100,
    )


def make_doctor(
    services: tuple[ManagedService, ...],
    *,
    runtimes: dict[str, ServiceRuntime] | None = None,
    health: dict[str, ServiceHealth] | None = None,
) -> tuple[ServiceDoctor, DoctorProvider]:
    provider = DoctorProvider()
    provider.services = services
    provider.runtimes = runtimes or {
        service.identifier: runtime()
        for service in services
    }
    provider.health = health or {
        service.identifier: healthy()
        for service in services
    }
    return ServiceDoctor(ServiceLifecycleService(provider)), provider


def finding_codes(report) -> set[str]:
    return {finding.code for finding in report.findings}


def test_doctor_requires_lifecycle_service() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="lifecycle must be ServiceLifecycleService",
    ):
        ServiceDoctor(object())  # type: ignore[arg-type]


def test_doctor_is_immutable() -> None:
    doctor, _ = make_doctor(())

    with pytest.raises(FrozenInstanceError):
        doctor.lifecycle = doctor.lifecycle  # type: ignore[misc]


def test_empty_infrastructure_is_healthy_unknown_provider() -> None:
    doctor, provider = make_doctor(())

    report = doctor.diagnose()

    assert report.status == "healthy"
    assert report.provider == "unknown"
    assert report.findings == ()
    assert provider.calls == [("list_services", None)]


def test_healthy_service_produces_no_findings() -> None:
    service = managed("sonarr")
    doctor, _ = make_doctor((service,))

    report = doctor.diagnose()

    assert report.findings == ()
    assert report.provider == "stub"


@pytest.mark.parametrize(
    ("state", "severity"),
    [
        ("exited", DoctorSeverity.ERROR),
        ("stopped", DoctorSeverity.ERROR),
        ("failed", DoctorSeverity.CRITICAL),
        ("dead", DoctorSeverity.CRITICAL),
    ],
)
def test_enabled_stopped_service_is_reported(
    state: str,
    severity: DoctorSeverity,
) -> None:
    service = managed("radarr")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"radarr": runtime(state=state, exit_code=1)},
    )

    finding = doctor.diagnose().findings[0]

    assert finding.code == "runtime-stopped"
    assert finding.severity is severity
    assert finding.category is DoctorCategory.RUNTIME
    assert finding.details["state"] == state


def test_restarting_service_is_reported() -> None:
    service = managed("bazarr")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"bazarr": runtime(state="restarting")},
    )

    assert "runtime-restarting" in finding_codes(doctor.diagnose())


@pytest.mark.parametrize(
    ("count", "severity"),
    [
        (5, DoctorSeverity.WARNING),
        (9, DoctorSeverity.WARNING),
        (10, DoctorSeverity.ERROR),
        (20, DoctorSeverity.ERROR),
    ],
)
def test_restart_thresholds_are_deterministic(
    count: int,
    severity: DoctorSeverity,
) -> None:
    service = managed("jellyfin")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"jellyfin": runtime(restart_count=count)},
    )

    finding = next(
        item
        for item in doctor.diagnose().findings
        if item.code == "restart-loop"
    )

    assert finding.severity is severity
    assert finding.details["restart_count"] == count


def test_restart_count_below_threshold_is_not_reported() -> None:
    service = managed("jellyfin")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"jellyfin": runtime(restart_count=4)},
    )

    assert "restart-loop" not in finding_codes(doctor.diagnose())


@pytest.mark.parametrize("health_state", ["none", "unknown", "unavailable", "starting"])
def test_running_service_without_conclusive_healthcheck_is_reported(
    health_state: str,
) -> None:
    service = managed("prowlarr")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"prowlarr": runtime(health=health_state)},
    )

    finding = doctor.diagnose().findings[0]

    assert finding.code == "healthcheck-missing"
    assert finding.category is DoctorCategory.OBSERVABILITY
    assert finding.severity is DoctorSeverity.WARNING


@pytest.mark.parametrize(
    ("status", "severity"),
    [
        (ServiceHealthStatus.DEGRADED, DoctorSeverity.WARNING),
        (ServiceHealthStatus.UNHEALTHY, DoctorSeverity.ERROR),
        (ServiceHealthStatus.UNAVAILABLE, DoctorSeverity.CRITICAL),
        (ServiceHealthStatus.UNKNOWN, DoctorSeverity.INFO),
    ],
)
def test_nonhealthy_health_status_is_reported(
    status: ServiceHealthStatus,
    severity: DoctorSeverity,
) -> None:
    service = managed("sonarr")
    doctor, _ = make_doctor(
        (service,),
        health={
            "sonarr": ServiceHealth(
                status=status,
                score=40,
                warnings=("review",),
            ),
        },
    )

    finding = doctor.diagnose().findings[0]

    assert finding.code == "health-degraded"
    assert finding.severity is severity
    assert finding.details["status"] == status.value


def test_missing_healthcheck_root_cause_is_reported_once() -> None:
    service = managed("bazarr")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"bazarr": runtime(health="unknown")},
        health={
            "bazarr": ServiceHealth(
                status=ServiceHealthStatus.DEGRADED,
                score=85,
                warnings=("No Docker health check is configured",),
            ),
        },
    )

    report = doctor.diagnose()

    assert [finding.code for finding in report.findings] == [
        "healthcheck-missing",
    ]
    assert report.counts["warning"] == 1


def test_additional_health_warning_preserves_health_finding() -> None:
    service = managed("bazarr")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"bazarr": runtime(health="unknown")},
        health={
            "bazarr": ServiceHealth(
                status=ServiceHealthStatus.DEGRADED,
                score=70,
                warnings=(
                    "No Docker health check is configured",
                    "Application endpoint validation failed",
                ),
            ),
        },
    )

    assert finding_codes(doctor.diagnose()) == {
        "healthcheck-missing",
        "health-degraded",
    }


def test_missing_healthcheck_with_errors_preserves_health_finding() -> None:
    service = managed("bazarr")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"bazarr": runtime(health="unknown")},
        health={
            "bazarr": ServiceHealth(
                status=ServiceHealthStatus.UNHEALTHY,
                score=30,
                warnings=("No Docker health check is configured",),
                errors=("Provider inspection failed",),
            ),
        },
    )

    assert finding_codes(doctor.diagnose()) == {
        "healthcheck-missing",
        "health-degraded",
    }


def test_healthy_status_with_messages_is_reported() -> None:
    service = managed("sonarr")
    doctor, _ = make_doctor(
        (service,),
        health={
            "sonarr": ServiceHealth(
                status=ServiceHealthStatus.HEALTHY,
                score=100,
                errors=("provider warning promoted",),
            ),
        },
    )

    finding = doctor.diagnose().findings[0]

    assert finding.code == "health-messages"
    assert finding.severity is DoctorSeverity.ERROR


def test_unknown_dependency_is_reported() -> None:
    service = managed("sonarr", dependencies=("database",))
    doctor, _ = make_doctor((service,))

    finding = doctor.diagnose().findings[0]

    assert finding.code == "dependency-missing-database"
    assert finding.category is DoctorCategory.DEPENDENCY
    assert finding.details["dependency"] == "database"


def test_stopped_known_dependency_is_reported() -> None:
    database = managed("database")
    sonarr = managed("sonarr", dependencies=("database",))
    doctor, _ = make_doctor(
        (database, sonarr),
        runtimes={
            "database": runtime(state="exited"),
            "sonarr": runtime(),
        },
    )

    report = doctor.diagnose()
    dependency_finding = next(
        item
        for item in report.findings
        if item.code == "dependency-not-running-database"
    )

    assert dependency_finding.service_identifier == "sonarr"
    assert dependency_finding.details["dependency_state"] == "exited"


def test_disabled_running_service_is_configuration_warning() -> None:
    service = managed("optional", enabled=False)
    doctor, _ = make_doctor((service,))

    finding = doctor.diagnose().findings[0]

    assert finding.code == "disabled-service-running"
    assert finding.category is DoctorCategory.CONFIGURATION
    assert finding.severity is DoctorSeverity.WARNING


def test_latest_image_tag_is_informational_configuration_finding() -> None:
    service = managed("jellyfin")
    doctor, _ = make_doctor(
        (service,),
        runtimes={"jellyfin": runtime(tag="latest")},
    )

    finding = doctor.diagnose().findings[0]

    assert finding.code == "image-tag-latest"
    assert finding.severity is DoctorSeverity.INFO
    assert finding.details["tag"] == "latest"


def test_mixed_provider_report_is_normalized() -> None:
    first = managed("sonarr", provider="docker-compose")
    second = managed("external", provider="external")
    doctor, _ = make_doctor((first, second))

    assert doctor.diagnose().provider == "mixed"


def test_doctor_inspects_each_runtime_and_health_once() -> None:
    first = managed("sonarr")
    second = managed("radarr")
    doctor, provider = make_doctor((first, second))

    doctor.diagnose()

    assert provider.calls == [
        ("list_services", None),
        ("inspect_runtime", "radarr"),
        ("inspect_runtime", "sonarr"),
        ("inspect_health", "radarr"),
        ("inspect_health", "sonarr"),
    ]


def test_report_and_findings_share_one_normalized_timestamp() -> None:
    service = managed("sonarr", dependencies=("database",))
    doctor, _ = make_doctor((service,))

    report = doctor.diagnose()

    assert report.findings
    assert {
        finding.created_at
        for finding in report.findings
    } == {report.evaluated_at}
