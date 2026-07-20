"""High-level media-retention service."""

from __future__ import annotations

from atlas.policies import PolicyService
from atlas.retention.models import RetentionDecision


class RetentionService:
    """Stable interface for media-removal eligibility decisions."""

    def __init__(
        self,
        policy_service: PolicyService | None = None,
    ) -> None:
        self.policy_service = (
            policy_service
            if policy_service is not None
            else PolicyService()
        )

    def evaluate(
        self,
        provider: str,
        item_id: str,
    ) -> RetentionDecision:
        """Evaluate whether one provider media item may be removed."""

        policy = self.policy_service.evaluate(
            provider,
            item_id,
        )

        return RetentionDecision(
            provider=policy.provider,
            item_id=policy.item_id,
            eligible=not policy.protected,
            policy=policy,
        )
