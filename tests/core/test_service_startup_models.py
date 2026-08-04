"""Tests for immutable startup-order domain contracts."""

from __future__ import annotations

import pytest

from atlas.service_lifecycle.models import (
    ManagedService,
    ServiceLifecycleError,
)
from atlas.service_lifecycle.startup_models import (
    ServiceStartupContract,
    ServiceStartupDependency,
    StartupDependencyCondition,
)


def managed_service(
    identifier: str = "qbittorrent",
) -> ManagedService:
    return ManagedService(
        identifier=identifier,
        name=identifier.replace("-", " ").title(),
        provider="docker-compose",
        compose_project="project-atlas",
        container_name=identifier,
    )


def test_startup_dependency_normalizes_fields() -> None:
    dependency = ServiceStartupDependency(
        identifier="  GLUETUN  ",
        condition=" SERVICE_HEALTHY ",
        required=True,
    )

    assert dependency.identifier == "gluetun"
    assert (
        dependency.condition
        is StartupDependencyCondition.SERVICE_HEALTHY
    )
    assert dependency.required is True
    assert dependency.to_dict() == {
        "identifier": "gluetun",
        "condition": "service_healthy",
        "required": True,
    }


@pytest.mark.parametrize(
    "condition",
    tuple(StartupDependencyCondition),
)
def test_startup_dependency_accepts_supported_conditions(
    condition: StartupDependencyCondition,
) -> None:
    dependency = ServiceStartupDependency(
        identifier="api",
        condition=condition,
    )

    assert dependency.condition is condition


@pytest.mark.parametrize(
    "condition",
    (
        "",
        "ready",
        "healthy",
        None,
        True,
    ),
)
def test_startup_dependency_rejects_invalid_condition(
    condition: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="supported startup dependency condition",
    ):
        ServiceStartupDependency(
            identifier="api",
            condition=condition,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize(
    "required",
    (
        None,
        "true",
        1,
    ),
)
def test_startup_dependency_requires_boolean_required(
    required: object,
) -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="required must be a boolean",
    ):
        ServiceStartupDependency(
            identifier="api",
            required=required,  # type: ignore[arg-type]
        )


def test_startup_contract_normalizes_and_sorts() -> None:
    contract = ServiceStartupContract(
        service=managed_service(),
        dependencies=(
            ServiceStartupDependency(
                identifier="prowlarr",
            ),
            ServiceStartupDependency(
                identifier="gluetun",
                condition=(
                    StartupDependencyCondition.SERVICE_HEALTHY
                ),
            ),
        ),
        namespace_target=" GLUETUN ",
        restart_policy=" Unless-Stopped ",
        healthcheck_configured=False,
    )

    assert contract.dependency_identifiers == (
        "gluetun",
        "prowlarr",
    )
    assert contract.namespace_target == "gluetun"
    assert contract.restart_policy == "unless-stopped"
    assert contract.healthcheck_configured is False
    assert (
        contract.dependency("GLUETUN").condition
        is StartupDependencyCondition.SERVICE_HEALTHY
    )


def test_startup_contract_serializes_child_contracts() -> None:
    service = managed_service()

    contract = ServiceStartupContract(
        service=service,
        dependencies=(
            ServiceStartupDependency(
                identifier="gluetun",
                condition="service_started",
                required=True,
            ),
        ),
        namespace_target="gluetun",
        restart_policy="unless-stopped",
        healthcheck_configured=True,
    )

    assert contract.to_dict() == {
        "service": service.to_dict(),
        "dependencies": [
            {
                "identifier": "gluetun",
                "condition": "service_started",
                "required": True,
            },
        ],
        "dependency_identifiers": ["gluetun"],
        "namespace_target": "gluetun",
        "restart_policy": "unless-stopped",
        "healthcheck_configured": True,
    }


def test_startup_contract_rejects_duplicate_dependencies() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="unique identifiers",
    ):
        ServiceStartupContract(
            service=managed_service(),
            dependencies=(
                ServiceStartupDependency(
                    identifier="gluetun",
                ),
                ServiceStartupDependency(
                    identifier="GLUETUN",
                ),
            ),
        )


def test_startup_contract_rejects_self_dependency() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="must not contain the service identifier",
    ):
        ServiceStartupContract(
            service=managed_service(),
            dependencies=(
                ServiceStartupDependency(
                    identifier="qbittorrent",
                ),
            ),
        )


def test_startup_contract_rejects_self_namespace() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="namespace_target must not reference",
    ):
        ServiceStartupContract(
            service=managed_service(),
            namespace_target="QBittorrent",
        )


def test_startup_contract_requires_dependency_tuple() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="dependencies must be a tuple",
    ):
        ServiceStartupContract(
            service=managed_service(),
            dependencies=[],  # type: ignore[arg-type]
        )


def test_startup_contract_dependency_lookup_rejects_unknown() -> None:
    contract = ServiceStartupContract(
        service=managed_service(),
    )

    with pytest.raises(
        ServiceLifecycleError,
        match="startup dependency is not present",
    ):
        contract.dependency("gluetun")
