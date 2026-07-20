"""Tests for normalized Atlas cleanup models."""

from __future__ import annotations

import unittest

from atlas.cleanup.models import (
    CleanupAction,
    CleanupDecision,
    CleanupError,
)
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
    eligible: bool = True,
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


class CleanupDecisionTests(unittest.TestCase):
    """Validate the normalized cleanup decision contract."""

    def test_delete_decision_exposes_normalized_contract(
        self,
    ) -> None:
        decision = CleanupDecision(
            provider=" JellyFin ",
            item_id=" item-123 ",
            action=CleanupAction.DELETE,
            retention=_retention_decision(),
        )

        payload = decision.to_dict()

        self.assertEqual(decision.provider, "jellyfin")
        self.assertEqual(decision.item_id, "item-123")
        self.assertEqual(decision.action, CleanupAction.DELETE)
        self.assertEqual(payload["action"], "delete")
        self.assertTrue(payload["retention"]["eligible"])
        self.assertFalse(payload["retention"]["retained"])
        self.assertTrue(payload["evaluated_at"].endswith("Z"))

    def test_keep_decision_preserves_retention_reasons(
        self,
    ) -> None:
        decision = CleanupDecision(
            provider="jellyfin",
            item_id="item-123",
            action="keep",
            retention=_retention_decision(eligible=False),
        )

        payload = decision.to_dict()

        self.assertEqual(decision.action, CleanupAction.KEEP)
        self.assertFalse(payload["retention"]["eligible"])
        self.assertTrue(payload["retention"]["retained"])
        self.assertEqual(
            payload["retention"]["policy"]["reasons"][0]["code"],
            "favorite",
        )

    def test_review_action_is_supported(self) -> None:
        decision = CleanupDecision(
            provider="jellyfin",
            item_id="item-123",
            action=CleanupAction.REVIEW,
            retention=_retention_decision(),
        )

        self.assertEqual(
            decision.to_dict()["action"],
            "review",
        )

    def test_rejects_invalid_action_and_retention_type(
        self,
    ) -> None:
        with self.assertRaises(CleanupError):
            CleanupDecision(
                provider="jellyfin",
                item_id="item-123",
                action="archive",
                retention=_retention_decision(),
            )

        with self.assertRaises(CleanupError):
            CleanupDecision(
                provider="jellyfin",
                item_id="item-123",
                action=CleanupAction.DELETE,
                retention="invalid",  # type: ignore[arg-type]
            )

    def test_rejects_mismatched_retention_identity(
        self,
    ) -> None:
        with self.assertRaisesRegex(
            CleanupError,
            "retention provider does not match",
        ):
            CleanupDecision(
                provider="emby",
                item_id="item-123",
                action=CleanupAction.DELETE,
                retention=_retention_decision(),
            )

        with self.assertRaisesRegex(
            CleanupError,
            "retention item_id does not match",
        ):
            CleanupDecision(
                provider="jellyfin",
                item_id="different-item",
                action=CleanupAction.DELETE,
                retention=_retention_decision(),
            )

    def test_rejects_invalid_identity_and_timestamp(
        self,
    ) -> None:
        retention = _retention_decision()

        with self.assertRaises(CleanupError):
            CleanupDecision(
                provider="",
                item_id="item-123",
                action=CleanupAction.DELETE,
                retention=retention,
            )

        with self.assertRaises(CleanupError):
            CleanupDecision(
                provider="jellyfin",
                item_id="",
                action=CleanupAction.DELETE,
                retention=retention,
            )

        with self.assertRaisesRegex(
            CleanupError,
            "must include a timezone",
        ):
            CleanupDecision(
                provider="jellyfin",
                item_id="item-123",
                action=CleanupAction.DELETE,
                retention=retention,
                evaluated_at="2026-07-20T12:00:00",
            )


if __name__ == "__main__":
    unittest.main()
