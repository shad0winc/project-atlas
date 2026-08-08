"""Tests for deterministic startup-policy evaluation."""

from __future__ import annotations

import pytest

from atlas.service_lifecycle import (
    ManagedService,
    ServiceLifecycleError,
    ServiceStartupContract,
    ServiceStartupDependency,
    StartupDependencyCondition,
    StartupPolicyEvaluator,
    StartupPolicySeverity,
)


def managed_service(
    identifier: str,
) -> ManagedService:
    return ManagedService(
        identifier=identifier,
        name=identifier.replace("-", " ").title(),
        provider="docker-compose",
        compose_project="project-atlas",
        container_name=identifier,
    )


def contract(
    identifier: str,
    *,
    dependencies: tuple[
        ServiceStartupDependency,
        ...
    ] = (),
    namespace_target: str | None = None,
    restart_policy: str | None = "unless-stopped",
    healthcheck_configured: bool = False,
) -> ServiceStartupContract:
    return ServiceStartupContract(
        service=managed_service(
            identifier,
        ),
        dependencies=dependencies,
        namespace_target=namespace_target,
        restart_policy=restart_policy,
        healthcheck_configured=healthcheck_configured,
    )


def dependency(
    identifier: str,
    *,
    condition: StartupDependencyCondition | str = (
        StartupDependencyCondition.SERVICE_STARTED
    ),
    required: bool = True,
) -> ServiceStartupDependency:
    return ServiceStartupDependency(
        identifier=identifier,
        condition=condition,
        required=required,
    )


def findings_by_code(
    report: object,
) -> dict[str, object]:
    return {
        finding.code: finding
        for finding in report.findings
    }


def test_empty_contract_collection_is_healthy() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (),
    )

    assert report.findings == ()
    assert report.status == "healthy"
    assert report.passed is True
    assert report.requires_attention is False


def test_valid_contracts_produce_no_findings() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "api",
                restart_policy="unless-stopped",
                healthcheck_configured=True,
            ),
            contract(
                "portal",
                dependencies=(
                    dependency(
                        "api",
                        condition="service_healthy",
                    ),
                ),
                restart_policy="always",
                healthcheck_configured=True,
            ),
        )
    )

    assert report.findings == ()
    assert report.status == "healthy"
    assert report.passed is True


@pytest.mark.parametrize(
    "restart_policy",
    (
        "always",
        "unless-stopped",
        "on-failure",
    ),
)
def test_approved_restart_policies_pass(
    restart_policy: str,
) -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "sonarr",
                restart_policy=restart_policy,
            ),
        )
    )

    assert report.findings == ()


def test_missing_restart_policy_is_warning() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "sonarr",
                restart_policy=None,
            ),
        )
    )

    finding = report.findings[0]

    assert finding.code == "restart-policy-missing"
    assert finding.severity is StartupPolicySeverity.WARNING
    assert finding.service_identifier == "sonarr"
    assert finding.details == {
        "restart_policy": None,
    }
    assert report.status == "degraded"
    assert report.passed is True


def test_unsupported_restart_policy_is_error() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "sonarr",
                restart_policy="no",
            ),
        )
    )

    finding = report.findings[0]

    assert finding.code == "restart-policy-unsupported"
    assert finding.severity is StartupPolicySeverity.ERROR
    assert finding.details == {
        "restart_policy": "no",
    }
    assert report.status == "unhealthy"
    assert report.passed is False


def test_unknown_dependency_is_error() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "portal",
                dependencies=(
                    dependency(
                        "api",
                    ),
                ),
            ),
        )
    )

    finding = report.findings[0]

    assert finding.code == "dependency-missing"
    assert finding.severity is StartupPolicySeverity.ERROR
    assert finding.service_identifier == "portal"
    assert finding.details == {
        "dependency_identifier": "api",
        "condition": "service_started",
        "required": True,
    }


def test_optional_unknown_dependency_is_still_reported() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "portal",
                dependencies=(
                    dependency(
                        "api",
                        required=False,
                    ),
                ),
            ),
        )
    )

    finding = report.findings[0]

    assert finding.code == "dependency-missing"
    assert finding.details["required"] is False


def test_healthy_dependency_requires_healthcheck() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "api",
                healthcheck_configured=False,
            ),
            contract(
                "caddy",
                dependencies=(
                    dependency(
                        "api",
                        condition="service_healthy",
                    ),
                ),
            ),
        )
    )

    finding = report.findings[0]

    assert finding.code == "healthcheck-required"
    assert finding.severity is StartupPolicySeverity.ERROR
    assert finding.service_identifier == "caddy"
    assert finding.details == {
        "dependency_identifier": "api",
        "condition": "service_healthy",
    }


def test_healthy_dependency_with_healthcheck_passes() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "api",
                healthcheck_configured=True,
            ),
            contract(
                "caddy",
                dependencies=(
                    dependency(
                        "api",
                        condition="service_healthy",
                    ),
                ),
            ),
        )
    )

    assert report.findings == ()


def test_missing_namespace_target_is_error() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "qbittorrent",
                namespace_target="gluetun",
            ),
        )
    )

    finding = report.findings[0]

    assert finding.code == "namespace-target-missing"
    assert finding.severity is StartupPolicySeverity.ERROR
    assert finding.details == {
        "namespace_target": "gluetun",
    }


def test_namespace_target_requires_declared_dependency() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "gluetun",
            ),
            contract(
                "qbittorrent",
                namespace_target="gluetun",
            ),
        )
    )

    finding = report.findings[0]

    assert finding.code == "namespace-dependency-missing"
    assert finding.severity is StartupPolicySeverity.ERROR
    assert finding.service_identifier == "qbittorrent"


def test_started_namespace_dependency_is_warning() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "gluetun",
            ),
            contract(
                "qbittorrent",
                dependencies=(
                    dependency(
                        "gluetun",
                        condition="service_started",
                    ),
                ),
                namespace_target="gluetun",
            ),
        )
    )

    finding = report.findings[0]

    assert finding.code == "namespace-readiness-weak"
    assert finding.severity is StartupPolicySeverity.WARNING
    assert finding.details == {
        "namespace_target": "gluetun",
        "condition": "service_started",
    }
    assert report.status == "degraded"
    assert report.passed is True


def test_healthy_namespace_dependency_passes() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "gluetun",
                healthcheck_configured=True,
            ),
            contract(
                "qbittorrent",
                dependencies=(
                    dependency(
                        "gluetun",
                        condition="service_healthy",
                    ),
                ),
                namespace_target="gluetun",
            ),
        )
    )

    assert report.findings == ()


def test_namespace_health_dependency_without_healthcheck_is_error() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "gluetun",
                healthcheck_configured=False,
            ),
            contract(
                "qbittorrent",
                dependencies=(
                    dependency(
                        "gluetun",
                        condition="service_healthy",
                    ),
                ),
                namespace_target="gluetun",
            ),
        )
    )

    assert tuple(
        finding.code
        for finding in report.findings
    ) == (
        "healthcheck-required",
    )


def test_multiple_findings_are_not_fail_fast() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "api",
                restart_policy=None,
            ),
            contract(
                "portal",
                dependencies=(
                    dependency(
                        "missing-api",
                    ),
                ),
                restart_policy="unsupported",
            ),
            contract(
                "qbittorrent",
                namespace_target="gluetun",
            ),
        )
    )

    assert {
        finding.code
        for finding in report.findings
    } == {
        "restart-policy-missing",
        "dependency-missing",
        "restart-policy-unsupported",
        "namespace-target-missing",
    }
    assert len(report.findings) == 4
    assert report.status == "unhealthy"
    assert report.passed is False


def test_findings_have_unique_deterministic_identifiers() -> None:
    report = StartupPolicyEvaluator().evaluate(
        (
            contract(
                "portal",
                dependencies=(
                    dependency(
                        "api",
                    ),
                    dependency(
                        "database",
                    ),
                ),
            ),
        )
    )

    assert tuple(
        finding.identifier
        for finding in report.findings
    ) == (
        "portal.api.dependency-missing",
        "portal.database.dependency-missing",
    )


def test_contract_input_order_does_not_change_report() -> None:
    api = contract(
        "api",
        restart_policy=None,
    )
    portal = contract(
        "portal",
        dependencies=(
            dependency(
                "missing-api",
            ),
        ),
    )

    first = StartupPolicyEvaluator().evaluate(
        (
            portal,
            api,
        )
    )
    second = StartupPolicyEvaluator().evaluate(
        (
            api,
            portal,
        )
    )

    first_payload = first.to_dict()
    second_payload = second.to_dict()

    first_payload.pop(
        "evaluated_at",
    )
    second_payload.pop(
        "evaluated_at",
    )

    assert first_payload == second_payload


def test_evaluator_rejects_non_tuple_contract_collection() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="startup contracts must be a tuple",
    ):
        StartupPolicyEvaluator().evaluate(
            [],  # type: ignore[arg-type]
        )


def test_evaluator_rejects_invalid_child_contract() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="startup contracts must be a tuple",
    ):
        StartupPolicyEvaluator().evaluate(
            (
                object(),  # type: ignore[arg-type]
            )
        )


def test_evaluator_rejects_duplicate_service_identifiers() -> None:
    with pytest.raises(
        ServiceLifecycleError,
        match="unique service identifiers",
    ):
        StartupPolicyEvaluator().evaluate(
            (
                contract(
                    "sonarr",
                ),
                contract(
                    "SONARR",
                ),
            )
        )
