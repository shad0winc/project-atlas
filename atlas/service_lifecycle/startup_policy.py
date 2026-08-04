"""Read-only evaluation of normalized Atlas startup contracts."""

from __future__ import annotations

from collections.abc import Sequence

from .models import ServiceLifecycleError
from .startup_models import (
    ServiceStartupContract,
    StartupDependencyCondition,
)
from .startup_policy_models import (
    StartupPolicyFinding,
    StartupPolicyReport,
    StartupPolicySeverity,
)


_APPROVED_RESTART_POLICIES = frozenset(
    {
        "always",
        "unless-stopped",
        "on-failure",
    }
)


class StartupPolicyEvaluator:
    """Evaluate service startup contracts against Atlas policy."""

    def evaluate(
        self,
        contracts: tuple[ServiceStartupContract, ...],
    ) -> StartupPolicyReport:
        """Return one deterministic report for all startup contracts."""

        normalized = _normalize_contracts(
            contracts,
        )

        by_identifier = {
            contract.service.identifier: contract
            for contract in normalized
        }

        findings: list[StartupPolicyFinding] = []

        for contract in normalized:
            findings.extend(
                _restart_policy_findings(
                    contract,
                )
            )
            findings.extend(
                _dependency_findings(
                    contract,
                    by_identifier,
                )
            )
            findings.extend(
                _namespace_findings(
                    contract,
                    by_identifier,
                )
            )

        return StartupPolicyReport(
            findings=tuple(findings),
            provider="docker-compose",
        )


def _restart_policy_findings(
    contract: ServiceStartupContract,
) -> tuple[StartupPolicyFinding, ...]:
    service_identifier = contract.service.identifier
    restart_policy = contract.restart_policy

    if restart_policy is None:
        return (
            StartupPolicyFinding(
                identifier=(
                    f"{service_identifier}."
                    "restart-policy-missing"
                ),
                code="restart-policy-missing",
                severity=StartupPolicySeverity.WARNING,
                message=(
                    f"{service_identifier} does not define "
                    "a restart policy."
                ),
                service_identifier=service_identifier,
                recommendation=(
                    "Configure an approved restart policy: "
                    "always, unless-stopped, or on-failure."
                ),
                details={
                    "restart_policy": None,
                },
            ),
        )

    if restart_policy not in _APPROVED_RESTART_POLICIES:
        return (
            StartupPolicyFinding(
                identifier=(
                    f"{service_identifier}."
                    "restart-policy-unsupported"
                ),
                code="restart-policy-unsupported",
                severity=StartupPolicySeverity.ERROR,
                message=(
                    f"{service_identifier} uses unsupported "
                    f"restart policy {restart_policy}."
                ),
                service_identifier=service_identifier,
                recommendation=(
                    "Use always, unless-stopped, or on-failure."
                ),
                details={
                    "restart_policy": restart_policy,
                },
            ),
        )

    return ()


def _dependency_findings(
    contract: ServiceStartupContract,
    by_identifier: dict[str, ServiceStartupContract],
) -> tuple[StartupPolicyFinding, ...]:
    service_identifier = contract.service.identifier
    findings: list[StartupPolicyFinding] = []

    for dependency in contract.dependencies:
        target = by_identifier.get(
            dependency.identifier,
        )

        if target is None:
            findings.append(
                StartupPolicyFinding(
                    identifier=(
                        f"{service_identifier}."
                        f"{dependency.identifier}."
                        "dependency-missing"
                    ),
                    code="dependency-missing",
                    severity=StartupPolicySeverity.ERROR,
                    message=(
                        f"{service_identifier} references unknown "
                        f"startup dependency "
                        f"{dependency.identifier}."
                    ),
                    service_identifier=service_identifier,
                    recommendation=(
                        "Add the dependency service or remove "
                        "the unresolved startup dependency."
                    ),
                    details={
                        "dependency_identifier": (
                            dependency.identifier
                        ),
                        "condition": dependency.condition.value,
                        "required": dependency.required,
                    },
                )
            )
            continue

        if (
            dependency.condition
            is StartupDependencyCondition.SERVICE_HEALTHY
            and not target.healthcheck_configured
        ):
            findings.append(
                StartupPolicyFinding(
                    identifier=(
                        f"{service_identifier}."
                        f"{dependency.identifier}."
                        "healthcheck-required"
                    ),
                    code="healthcheck-required",
                    severity=StartupPolicySeverity.ERROR,
                    message=(
                        f"{service_identifier} waits for "
                        f"{dependency.identifier} to become healthy, "
                        "but that service has no enabled healthcheck."
                    ),
                    service_identifier=service_identifier,
                    recommendation=(
                        f"Configure an enabled healthcheck for "
                        f"{dependency.identifier} or use a different "
                        "dependency condition."
                    ),
                    details={
                        "dependency_identifier": (
                            dependency.identifier
                        ),
                        "condition": dependency.condition.value,
                    },
                )
            )

    return tuple(findings)


def _namespace_findings(
    contract: ServiceStartupContract,
    by_identifier: dict[str, ServiceStartupContract],
) -> tuple[StartupPolicyFinding, ...]:
    service_identifier = contract.service.identifier
    namespace_target = contract.namespace_target

    if namespace_target is None:
        return ()

    target = by_identifier.get(
        namespace_target,
    )

    if target is None:
        return (
            StartupPolicyFinding(
                identifier=(
                    f"{service_identifier}."
                    f"{namespace_target}."
                    "namespace-target-missing"
                ),
                code="namespace-target-missing",
                severity=StartupPolicySeverity.ERROR,
                message=(
                    f"{service_identifier} shares the network "
                    f"namespace of unknown service "
                    f"{namespace_target}."
                ),
                service_identifier=service_identifier,
                recommendation=(
                    "Add the namespace target service or remove "
                    "the service namespace reference."
                ),
                details={
                    "namespace_target": namespace_target,
                },
            ),
        )

    try:
        dependency = contract.dependency(
            namespace_target,
        )
    except ServiceLifecycleError:
        return (
            StartupPolicyFinding(
                identifier=(
                    f"{service_identifier}."
                    f"{namespace_target}."
                    "namespace-dependency-missing"
                ),
                code="namespace-dependency-missing",
                severity=StartupPolicySeverity.ERROR,
                message=(
                    f"{service_identifier} shares the network "
                    f"namespace of {namespace_target} without "
                    "declaring it as a startup dependency."
                ),
                service_identifier=service_identifier,
                recommendation=(
                    f"Declare {namespace_target} in depends_on."
                ),
                details={
                    "namespace_target": namespace_target,
                },
            ),
        )

    if (
        dependency.condition
        is StartupDependencyCondition.SERVICE_STARTED
    ):
        return (
            StartupPolicyFinding(
                identifier=(
                    f"{service_identifier}."
                    f"{namespace_target}."
                    "namespace-readiness-weak"
                ),
                code="namespace-readiness-weak",
                severity=StartupPolicySeverity.WARNING,
                message=(
                    f"{service_identifier} starts when "
                    f"{namespace_target} is only started, not healthy."
                ),
                service_identifier=service_identifier,
                recommendation=(
                    f"Add an enabled healthcheck to "
                    f"{namespace_target} and use service_healthy "
                    "when fail-closed readiness is required."
                ),
                details={
                    "namespace_target": namespace_target,
                    "condition": dependency.condition.value,
                },
            ),
        )

    return ()


def _normalize_contracts(
    value: object,
) -> tuple[ServiceStartupContract, ...]:
    if not isinstance(value, tuple):
        raise ServiceLifecycleError(
            "startup contracts must be a tuple "
            "of ServiceStartupContract",
        )

    if any(
        not isinstance(item, ServiceStartupContract)
        for item in value
    ):
        raise ServiceLifecycleError(
            "startup contracts must be a tuple "
            "of ServiceStartupContract",
        )

    by_identifier: dict[str, ServiceStartupContract] = {}

    for contract in value:
        identifier = contract.service.identifier

        if identifier in by_identifier:
            raise ServiceLifecycleError(
                "startup contracts must have unique "
                "service identifiers",
            )

        by_identifier[identifier] = contract

    return tuple(
        sorted(
            by_identifier.values(),
            key=lambda contract: (
                contract.service.name.casefold(),
                contract.service.identifier,
            ),
        )
    )
