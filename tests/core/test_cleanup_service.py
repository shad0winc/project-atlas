"""Tests for the Atlas cleanup planning service."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from atlas.cleanup.models import CleanupAction
from atlas.cleanup.service import CleanupService
from atlas.policies.models import (
    PolicyAction,
    PolicyDecision,
    PolicyReason,
)
from atlas.retention.models import RetentionDecision


def _retention_decision(
    *,
    provider: str = "jellyfin",
    item_id: str = "item-123",
    eligible: bool,
) -> RetentionDecision:
    reasons = ()

    if not eligible:
        reasons = (
            PolicyReason(
                code="favorite",
                source="favorites",
                detail="Favorited by an Atlas user",
            ),
        )

    policy = PolicyDecision(
        provider=provider,
        item_id=item_id,
        action=(
            PolicyAction.IGNORE
            if eligible
            else PolicyAction.PROTECT
        ),
        reasons=reasons,
    )

    return RetentionDecision(
        provider=provider,
        item_id=item_id,
        eligible=eligible,
        policy=policy,
    )


class CleanupServiceTests(unittest.TestCase):
    """Validate cleanup planning behavior."""

    def test_eligible_media_is_marked_for_deletion(self) -> None:
        retention_service = Mock()
        retention_service.evaluate.return_value = (
            _retention_decision(eligible=True)
        )

        service = CleanupService(retention_service)

        decision = service.evaluate(
            "jellyfin",
            "item-123",
        )

        self.assertEqual(
            decision.action,
            CleanupAction.DELETE,
        )
        self.assertTrue(decision.retention.eligible)
        self.assertFalse(decision.retention.retained)

    def test_retained_media_is_kept(self) -> None:
        retention_service = Mock()
        retention_service.evaluate.return_value = (
            _retention_decision(eligible=False)
        )

        service = CleanupService(retention_service)

        decision = service.evaluate(
            "jellyfin",
            "item-123",
        )

        self.assertEqual(
            decision.action,
            CleanupAction.KEEP,
        )
        self.assertFalse(decision.retention.eligible)
        self.assertTrue(decision.retention.retained)

    def test_service_forwards_provider_and_item_id(
        self,
    ) -> None:
        retention_service = Mock()
        retention_service.evaluate.return_value = (
            _retention_decision(
                provider="emby",
                item_id="custom-item",
                eligible=True,
            )
        )

        service = CleanupService(retention_service)

        decision = service.evaluate(
            "emby",
            "custom-item",
        )

        retention_service.evaluate.assert_called_once_with(
            "emby",
            "custom-item",
        )
        self.assertEqual(decision.provider, "emby")
        self.assertEqual(decision.item_id, "custom-item")

    def test_service_uses_normalized_retention_identity(
        self,
    ) -> None:
        retention_service = Mock()
        retention_service.evaluate.return_value = (
            _retention_decision(
                provider="jellyfin",
                item_id="item-123",
                eligible=True,
            )
        )

        service = CleanupService(retention_service)

        decision = service.evaluate(
            " JellyFin ",
            " item-123 ",
        )

        self.assertEqual(decision.provider, "jellyfin")
        self.assertEqual(decision.item_id, "item-123")


if __name__ == "__main__":
    unittest.main()
