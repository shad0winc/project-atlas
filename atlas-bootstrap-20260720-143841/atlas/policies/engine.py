"""Policy evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping
from types import MappingProxyType

from atlas.policies.providers import PolicyProviders
from typing import Iterable, Protocol

from atlas.policies.models import (
    PolicyAction,
    PolicyDecision,
    PolicyReason,
)

@dataclass(frozen=True)
class PolicyContext:
    """Immutable evaluation context passed to every rule."""

    provider: str
    item_id: str
    providers: PolicyProviders
    metadata: Mapping[str, Any] = field(
        default_factory=lambda: MappingProxyType({})
    )

class PolicyRule(Protocol):
    """Interface implemented by policy rules."""

    def evaluate(
        self,
        context: PolicyContext,
    ) -> Iterable[PolicyReason]:
        ...


@dataclass
class PolicyEngine:
    """Evaluates media against registered policy rules."""

    providers: PolicyProviders
    rules: list[PolicyRule] = field(default_factory=list)

    def register(self, rule: PolicyRule) -> None:
        self.rules.append(rule)

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> PolicyDecision:

        context = PolicyContext(
            provider=provider,
            item_id=item_id,
            providers=self.providers,
        )

        reasons: list[PolicyReason] = []

        for rule in self.rules:
            reasons.extend(rule.evaluate(context))

        action = (
            PolicyAction.PROTECT
            if reasons
            else PolicyAction.IGNORE
        )

        return PolicyDecision(
            provider=provider,
            item_id=item_id,
            action=action,
            reasons=tuple(reasons),
        )
