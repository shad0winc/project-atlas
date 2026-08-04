"""Read-only startup-policy orchestration for Atlas services."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from ..models import ServiceLifecycleError
from ..startup_models import ServiceStartupContract
from ..startup_policy import StartupPolicyEvaluator
from ..startup_policy_models import StartupPolicyReport
from .lifecycle import ServiceLifecycleService


@dataclass(frozen=True)
class ServiceStartupPolicyService:
    """Inspect and evaluate normalized provider startup contracts."""

    lifecycle: ServiceLifecycleService
    evaluator: StartupPolicyEvaluator = field(
        default_factory=StartupPolicyEvaluator,
    )

    def __post_init__(self) -> None:
        if not isinstance(
            self.lifecycle,
            ServiceLifecycleService,
        ):
            raise ServiceLifecycleError(
                "lifecycle must be ServiceLifecycleService",
            )

        if not isinstance(
            self.evaluator,
            StartupPolicyEvaluator,
        ):
            raise ServiceLifecycleError(
                "evaluator must be StartupPolicyEvaluator",
            )

    def inspect(self) -> StartupPolicyReport:
        """Return one deterministic startup-policy report."""

        inspector = getattr(
            self.lifecycle.provider,
            "inspect_startup_contracts",
            None,
        )

        if not callable(inspector):
            raise ServiceLifecycleError(
                "service provider does not support "
                "startup contract inspection",
            )

        try:
            contracts = inspector()
        except ServiceLifecycleError:
            raise
        except Exception as exc:
            raise ServiceLifecycleError(
                "service provider failed to inspect "
                "startup contracts",
            ) from exc

        if (
            isinstance(contracts, (str, bytes))
            or not isinstance(contracts, Sequence)
        ):
            raise ServiceLifecycleError(
                "provider startup contracts must be a collection",
            )

        normalized = tuple(contracts)

        if any(
            not isinstance(
                contract,
                ServiceStartupContract,
            )
            for contract in normalized
        ):
            raise ServiceLifecycleError(
                "provider startup contracts must contain "
                "ServiceStartupContract objects",
            )

        return self.evaluator.evaluate(
            normalized,
        )
