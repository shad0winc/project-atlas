from __future__ import annotations

import unittest

from atlas.policies import (
    PolicyAction,
    PolicyDecision,
    PolicyError,
    PolicyReason,
)


class PolicyReasonTests(unittest.TestCase):
    def test_normalizes_reason_and_serializes_metadata(self) -> None:
        reason = PolicyReason(
            code="favorite",
            source="favorites",
            detail="One or more Atlas users favorited this item.",
            expires_at="2026-08-01T12:00:00-04:00",
            metadata={"favorite_count": 2},
        )

        self.assertEqual("favorite", reason.code)
        self.assertEqual("2026-08-01T16:00:00Z", reason.expires_at)
        self.assertEqual(
            {
                "code": "favorite",
                "source": "favorites",
                "detail": "One or more Atlas users favorited this item.",
                "expires_at": "2026-08-01T16:00:00Z",
                "metadata": {"favorite_count": 2},
            },
            reason.to_dict(),
        )

    def test_rejects_invalid_reason_values(self) -> None:
        with self.assertRaisesRegex(PolicyError, "code is required"):
            PolicyReason("", "favorites", "Favorite protection")

        with self.assertRaisesRegex(PolicyError, "metadata must be an object"):
            PolicyReason(
                "favorite",
                "favorites",
                "Favorite protection",
                metadata=["invalid"],
            )


class PolicyDecisionTests(unittest.TestCase):
    def test_protect_decision_exposes_normalized_contract(self) -> None:
        reason = PolicyReason(
            code="favorite",
            source="favorites",
            detail="Item is favorited.",
        )

        decision = PolicyDecision(
            provider=" Jellyfin ",
            item_id="item-123",
            action=PolicyAction.PROTECT,
            reasons=(reason,),
            evaluated_at="2026-07-20T00:00:00+00:00",
        )

        self.assertTrue(decision.protected)
        self.assertEqual("jellyfin", decision.provider)
        self.assertEqual(
            {
                "provider": "jellyfin",
                "item_id": "item-123",
                "action": "protect",
                "protected": True,
                "reasons": [
                    {
                        "code": "favorite",
                        "source": "favorites",
                        "detail": "Item is favorited.",
                        "expires_at": None,
                        "metadata": {},
                    }
                ],
                "evaluated_at": "2026-07-20T00:00:00Z",
            },
            decision.to_dict(),
        )

    def test_nonprotect_decision_is_not_protected(self) -> None:
        decision = PolicyDecision(
            provider="jellyfin",
            item_id="item-456",
            action="ignore",
        )

        self.assertFalse(decision.protected)
        self.assertEqual(PolicyAction.IGNORE, decision.action)

    def test_rejects_invalid_action_and_reason_type(self) -> None:
        with self.assertRaisesRegex(PolicyError, "invalid policy action"):
            PolicyDecision(
                provider="jellyfin",
                item_id="item-123",
                action="delete",
            )

        with self.assertRaisesRegex(
            PolicyError,
            "reasons must contain PolicyReason",
        ):
            PolicyDecision(
                provider="jellyfin",
                item_id="item-123",
                action=PolicyAction.PROTECT,
                reasons=({"code": "favorite"},),
            )

    def test_rejects_naive_timestamps(self) -> None:
        with self.assertRaisesRegex(
            PolicyError,
            "evaluated_at must include a timezone",
        ):
            PolicyDecision(
                provider="jellyfin",
                item_id="item-123",
                action=PolicyAction.IGNORE,
                evaluated_at="2026-07-20T00:00:00",
            )


if __name__ == "__main__":
    unittest.main()
