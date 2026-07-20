"""High-level media-policy service."""

from __future__ import annotations

from collections.abc import Iterable

from atlas.favorites import default_favorite_store
from atlas.policies.engine import PolicyEngine, PolicyRule
from atlas.policies.models import PolicyDecision
from atlas.policies.providers import PolicyProviders
from atlas.policies.rules import builtin_rules


def default_policy_providers() -> PolicyProviders:
    """Construct the default production policy-provider registry."""

    return PolicyProviders(
        favorites=default_favorite_store(),
    )


class PolicyService:
    """Stable application-facing interface for media-policy evaluation."""

    def __init__(
        self,
        providers: PolicyProviders | None = None,
        *,
        rules: Iterable[PolicyRule] | None = None,
    ) -> None:
        self.providers = (
            providers
            if providers is not None
            else default_policy_providers()
        )

        self.rules = tuple(
            builtin_rules()
            if rules is None
            else rules
        )

        self.engine = PolicyEngine(
            providers=self.providers,
        )

        for rule in self.rules:
            self.engine.register(rule)

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> PolicyDecision:
        """Evaluate one provider media item against all service rules."""

        return self.engine.evaluate(
            provider,
            item_id,
        )
